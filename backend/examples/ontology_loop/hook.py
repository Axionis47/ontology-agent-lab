"""Control task calls in Gemini hooks. The existing MCP servers stay unchanged."""

import argparse
import fcntl
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

READ = re.compile(r"SELECT\s+\*\s+FROM\s+(\w+)\s*;?", re.I)
WRITE = re.compile(
    r"INSERT(?:\s+OR\s+IGNORE)?\s+INTO\s+reservations\s*"
    r"\(\s*reservation_id\s*,\s*offer_id\s*,\s*total_cents\s*,\s*idempotency_key\s*\)"
    r"\s*VALUES\s*\(\s*'([A-Za-z0-9_-]+)'\s*,\s*'([A-Za-z0-9_-]+)'\s*,"
    r"\s*(\d+)\s*,\s*'([A-Za-z0-9_-]+)'\s*\)\s*;?",
    re.I,
)


def source_answer(case):
    """Enforce the shared local action contract, independently of the generated program."""
    indexes = []
    for rows in (
        case["inventory"]["hotels"],
        case["inventory"]["offers"],
        case["policies"]["policies"],
    ):
        index = {}
        for row in rows:
            if row["id"] in index and index[row["id"]] != row:
                return {"status": "incomplete", "eligible": []}
            index[row["id"]] = row
        indexes.append(index)
    hotels, offers, policies = indexes
    eligible = []
    request = case["query"]
    for offer in offers.values():
        hotel = hotels.get(offer["hotel_id"])
        if hotel is None or hotel["policy_id"] not in policies:
            return {"status": "incomplete", "eligible": []}
        policy = policies[hotel["policy_id"]]
        total = offer["nightly_cents"] * request["nights"] + offer["fee_cents"]
        if (
            hotel["city"] == request["city"]
            and offer["capacity"] >= request["adults"] + 1
            and policy["minimum_child_age"] <= request["child_age"]
            and total <= request["budget_cents"]
        ):
            eligible.append({"offer_id": offer["id"], "total_cents": total})
    return {"status": "complete", "eligible": sorted(eligible, key=lambda x: x["offer_id"])}


def normalize_answer(value):
    if not isinstance(value, dict) or value.get("status") not in {"complete", "incomplete"}:
        raise ValueError("Use status complete or incomplete and an eligible list.")
    rows = value.get("eligible")
    if not isinstance(rows, list):
        raise ValueError("The eligible field must be a list.")
    result, identifiers = [], set()
    for row in rows:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("offer_id"), str)
            or type(row.get("total_cents")) is not int
            or row["offer_id"] in identifiers
        ):
            raise ValueError("Use unique offer IDs and integer total costs.")
        identifiers.add(row["offer_id"])
        result.append({"offer_id": row["offer_id"], "total_cents": row["total_cents"]})
    return {"status": value["status"], "eligible": sorted(result, key=lambda x: x["offer_id"])}


def db_case(database, name):
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        rows = {
            table: [dict(row) for row in connection.execute(f'SELECT * FROM "{table}"')]
            for table in ("hotel", "offer", "policy", "request")
        }
    return {
        "name": name,
        "query": rows["request"][0],
        "inventory": {"hotels": rows["hotel"], "offers": rows["offer"]},
        "policies": {"policies": rows["policy"]},
    }


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def initial_state(config, case):
    return {
        "case": case["name"],
        "mode": config["mode"],
        "first_proposal": None,
        "proposals": [],
        "answer": None,
        "action_proposals": [],
        "actions": [],
        "trace": [],
        "completed": False,
        "read_tables": [],
        "function_used": False,
        "source_digest": digest(case),
        "allowed_calls": {},
    }


def call_kind(name):
    name = name.replace("-", "_")
    for suffix in ("read_query", "write_query", "write_file", "read_text_file"):
        if name == suffix or name.endswith("_" + suffix):
            return suffix
    return name


def response_failed(response):
    if isinstance(response, str):
        return any(line.lstrip().startswith("Error:") for line in response.splitlines())
    if isinstance(response, list):
        return any(response_failed(item) for item in response)
    if isinstance(response, dict):
        return bool(response.get("error") or response.get("isError")) or any(
            response_failed(value)
            for key, value in response.items()
            if key in {"text", "llmContent", "content", "returnDisplay"}
        )
    return False


def read_tables(database, query):
    """Permit ordinary read-only SQL over granted source tables for the baseline."""
    if not query.lstrip().upper().startswith("SELECT"):
        raise ValueError("Use a SELECT query.")
    seen = set()
    allowed = {"hotel", "offer", "policy", "request", "reservations"}

    def authorize(action, first, second, database_name, origin):
        if action == sqlite3.SQLITE_READ:
            if first not in allowed:
                return sqlite3.SQLITE_DENY
            seen.add(first)
        elif action == sqlite3.SQLITE_FUNCTION:
            if second in {"load_extension", "readfile", "writefile"}:
                return sqlite3.SQLITE_DENY
        elif action not in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE}:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    with sqlite3.connect(f"file:{Path(database).resolve()}?mode=ro", uri=True) as connection:
        connection.set_authorizer(authorize)
        connection.execute("EXPLAIN " + query).fetchall()
    return sorted(seen)


def before(config, state, event):
    args = event.get("tool_input", {})
    kind = call_kind(event.get("tool_name", ""))
    if kind == "read_query":
        if config["mode"] in {"baseline", "schema_only"}:
            tables = read_tables(config["database_path"], args.get("query", ""))
            state.setdefault("query_tables", {})[digest(args)] = tables
            return
        match = READ.fullmatch(args.get("query", "").strip())
        allowed = {"hotel", "offer", "policy", "request", "reservations"}
        if config["mode"] in {"full", "strict"}:
            allowed |= {"snapshot_status", "eligible_stays"}
        if not match or match[1].lower() not in allowed:
            raise ValueError("Use SELECT * FROM a declared source table or function view.")
        return
    if kind == "read_text_file":
        if Path(args.get("path", "")).resolve() != Path(config["answer_path"]).resolve():
            raise ValueError("Only the task answer file is readable through Filesystem MCP.")
        return
    if kind == "write_file":
        try:
            value = json.loads(args.get("content", ""))
        except ValueError:
            value = {"invalid_json": args.get("content", "")}
        state["proposals"].append(value)
        if len(state["proposals"]) == 1:
            state["first_proposal"] = value
        if Path(args.get("path", "")).resolve() != Path(config["answer_path"]).resolve():
            raise ValueError("Write only the exact task answer path.")
        actual = normalize_answer(value)
        if not {"hotel", "offer", "policy"}.issubset(state["read_tables"]):
            raise ValueError("Read the hotel, offer, and policy source tables first.")
        case = db_case(config["database_path"], state["case"])
        if digest(case) != state["source_digest"]:
            raise ValueError("The source snapshot changed. Start a new episode.")
        if actual != source_answer(case):
            raise ValueError("The proposed answer violates the task contract. Check the sources.")
        if config["mode"] == "strict":
            if not state["function_used"]:
                raise ValueError("Call the declared eligible_stays function view first.")
            with sqlite3.connect(config["database_path"]) as connection:
                connection.row_factory = sqlite3.Row
                status = connection.execute("SELECT status FROM snapshot_status").fetchone()[0]
                rows = [
                    dict(row)
                    for row in connection.execute(
                        "SELECT offer_id,total_cents FROM eligible_stays ORDER BY offer_id"
                    )
                ]
            if actual != {"status": status, "eligible": rows}:
                raise ValueError("The proposal differs from the frozen generated function.")
        return
    if kind == "write_query":
        match = WRITE.fullmatch(args.get("query", "").strip())
        proposal = (
            {
                "reservation_id": match[1],
                "offer_id": match[2],
                "total_cents": int(match[3]),
                "idempotency_key": match[4],
            }
            if match
            else {"query": args.get("query")}
        )
        state["action_proposals"].append(proposal)
        if not match:
            raise ValueError("Only the declared reservation INSERT operation is allowed.")
        answer = state["answer"]
        if not answer or not answer["eligible"]:
            raise ValueError("Write a valid nonempty answer before a reservation.")
        if digest(db_case(config["database_path"], state["case"])) != state["source_digest"]:
            raise ValueError("The source snapshot changed. Start a new episode.")
        chosen = min(answer["eligible"], key=lambda row: (row["total_cents"], row["offer_id"]))
        if any(proposal[key] != chosen[key] for key in ("offer_id", "total_cents")):
            raise ValueError("Reserve the cheapest eligible offer. Break ties by offer ID.")
        with sqlite3.connect(config["database_path"]) as connection:
            connection.row_factory = sqlite3.Row
            existing = [dict(row) for row in connection.execute("SELECT * FROM reservations")]
        if existing and existing != [proposal]:
            raise ValueError("This episode already has a different reservation.")
        pending = state.get("pending_reservation")
        if pending and pending != proposal:
            raise ValueError("A different reservation is already authorized for this episode.")
        state["pending_reservation"] = proposal
        return
    raise ValueError("This tool is outside the granted task surface.")


def apply_event(config, state, event):
    if event.get("session_id"):
        state["session_id"] = event["session_id"]
    phase = event.get("hook_event_name")
    args, tool = event.get("tool_input", {}), event.get("tool_name", "")
    key = digest({"tool": tool, "arguments": args})
    entry = {"phase": phase, "tool": tool, "arguments": args}
    state["trace"].append(entry)
    if phase == "BeforeTool":
        try:
            if sum(x["phase"] == "BeforeTool" for x in state["trace"]) > 24:
                raise ValueError("The episode tool-call limit was reached.")
            before(config, state, event)
            state["allowed_calls"][key] = True
            decision = {"decision": "allow"}
        except (ValueError, KeyError, sqlite3.Error) as exc:
            state["allowed_calls"][key] = False
            decision = {"decision": "deny", "reason": str(exc)}
        entry["decision"] = decision
        return decision
    response = event.get("tool_response", {})
    entry["observation"] = response
    if not state["allowed_calls"].get(key) or response_failed(response):
        return {}
    kind = call_kind(tool)
    if kind == "read_query":
        if config["mode"] in {"baseline", "schema_only"}:
            tables = state.get("query_tables", {}).get(digest(args), [])
        else:
            match = READ.fullmatch(args["query"].strip())
            tables = [match[1].lower()]
        state["read_tables"] = sorted(set(state["read_tables"]) | set(tables))
        state["function_used"] |= "eligible_stays" in tables
    elif kind == "write_file" and Path(config["answer_path"]).is_file():
        actual = normalize_answer(json.loads(Path(config["answer_path"]).read_text()))
        state["answer"] = actual
        state["completed"] = not actual["eligible"]
    elif kind == "write_query":
        with sqlite3.connect(config["database_path"]) as connection:
            connection.row_factory = sqlite3.Row
            state["actions"] = [
                dict(row) for row in connection.execute("SELECT * FROM reservations")
            ]
        state["completed"] = bool(state["actions"])
    return {}


def handle(config, event):
    state_path = Path(config["state_path"])
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        original = json.loads(Path(config["case_path"]).read_text())
        case = {key: original[key] for key in ("name", "query", "inventory", "policies")}
        state = (
            json.loads(state_path.read_text())
            if state_path.exists()
            else initial_state(config, case)
        )
        result = apply_event(config, state, event)
        temporary = state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2))
        temporary.replace(state_path)
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(handle(json.loads(Path(args.episode).read_text()), json.load(sys.stdin))))
    except Exception as exc:
        # Exit 2 also blocks a tool if JSON handling fails in the CLI.
        print(json.dumps({"decision": "deny", "reason": f"Task guard failed: {exc}"}))
        sys.exit(2)


if __name__ == "__main__":
    main()
