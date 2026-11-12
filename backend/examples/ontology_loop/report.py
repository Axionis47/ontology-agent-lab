"""Create a local experiment report from recorded evidence."""
# ruff: noqa: E501

import argparse
import html
import json
from pathlib import Path

from .budget import Budget

ARM_LABELS = {
    "baseline": "Plain ReAct",
    "schema_only": "Schema only",
    "full_explicit_stratified": "Full: explicit task",
    "full_concise_stratified": "Full: concise task",
    "full_explicit_random": "Full: random sample",
    "full_counterexample_stratified": "Full: counterexample review",
}


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def escape(value):
    return html.escape(str(value))


def make_report(root):
    root = Path(root).resolve()
    construction = []
    for path in sorted((root / "construction").glob("*/construction.json")):
        record = read(path)
        final = record["rounds"][-1]
        passed = sum(item["passed"] for item in final.get("observations", []))
        construction.append(
            {
                "variant": record["variant"],
                "status": record["status"],
                "rounds": len(record["rounds"]),
                "passed": passed,
                "total": len(record["training_cases"]),
                "fingerprint": record.get("fingerprint", ""),
                "path": str(path.relative_to(root)),
            }
        )
    summaries = [(path.parent.name, read(path)) for path in sorted(root.glob("*/summary.json"))]
    retired = [
        (name, data) for name, data in summaries if isinstance(data, dict) and data.get("retired")
    ]
    summaries = [
        (name, data)
        for name, data in summaries
        if isinstance(data, dict) and "arms" in data and not data.get("retired")
    ]
    budget = Budget(root / "budget.jsonl").snapshot()
    ledger = [json.loads(line) for line in (root / "budget.jsonl").read_text().splitlines()]
    released = {
        row["id"]
        for row in ledger
        if row["type"] in {"verified_no_request", "usage_reconciliation"}
    }
    unknown = sum(
        row["charged_usd"]
        for row in ledger
        if row["type"] == "settle" and not row["usage_known"] and row["id"] not in released
    )
    known = sum(
        row["charged_usd"] for row in ledger if row["type"] == "settle" and row["usage_known"]
    )
    reconciled = [row for row in ledger if row["type"] == "usage_reconciliation"]
    unknown += sum(row["retry_reserve_usd"] for row in reconciled)
    known += sum(row["observed_estimate_usd"] for row in reconciled)
    episodes = sum(report["completed_episodes"] for _, report in summaries)
    construction_rows = "".join(
        f"<tr><td>{escape(row['variant'])}</td><td>{row['passed']}/{row['total']}</td>"
        f'<td>{row["rounds"]}</td><td><span class="pill">{row["status"]}</span></td>'
        f'<td><a href="{row["path"]}">{row["fingerprint"][:12]}</a></td></tr>'
        for row in construction
    )
    comparison = ""
    for label, report in summaries:
        records = [
            json.loads(line) for line in (root / label / "results.jsonl").read_text().splitlines()
        ]
        baseline_records = {row["case"]: row for row in records if row["arm"] == "baseline"}
        first_correct = sum(row["score"]["first_answer_correct"] for row in records)
        missing_answers = 0
        terminal_only = 0
        metadata_detours = 0
        failure_rows = ""
        for row in records:
            runtime = read(Path(row["result_path"]), {})
            score = row["score"]
            missing_answers += not bool(runtime.get("proposals"))
            terminal_only += bool(
                score["first_answer_correct"]
                and score["first_action_correct"]
                and score["committed_action_correct"]
                and runtime.get("completed")
                and runtime.get("error")
            )
            metadata_detours += sum(
                entry.get("decision", {}).get("decision") == "deny"
                and any(
                    word in entry.get("arguments", {}).get("query", "").lower()
                    for word in ("sqlite_master", "pragma")
                )
                for entry in runtime.get("trace", [])
            )
            if not score["exact_task_success"]:
                result_link = Path(row["result_path"]).relative_to(root)
                failure_rows += (
                    f"<tr><td>{escape(ARM_LABELS[row['arm']])}</td><td>{escape(score['family'].replace('_', ' '))}</td>"
                    f"<td>{'yes' if runtime.get('completed') and score['committed_action_correct'] else 'no'}</td>"
                    f"<td>{escape(runtime.get('cli_exit_code', 'unknown'))}</td>"
                    f'<td><a href="{escape(result_link)}">Trace</a></td></tr>'
                )
        rows = ""
        arm_order = [arm for arm in ARM_LABELS if arm in report["arms"]]
        for arm in arm_order:
            result = report["arms"][arm]
            arm_records = [row for row in records if row["arm"] == arm]
            runtime = [read(Path(row["result_path"]), {}) for row in arm_records]
            count, passed = result["episodes"], result["exact_task_successes"]
            percentage = passed / count * 100 if count else 0
            interval = result["paired_bootstrap_95_interval"]
            ci = f"{100 * interval[0]:+.0f} to {100 * interval[1]:+.0f} pp" if interval else "n/a"
            if result["paired_answerable_count"] < 10:
                ci = "interval not shown for fewer than 10 pairs"
            errors = sum(bool(row.get("error")) for row in runtime)
            first_actions = sum(
                bool(row["score"].get("first_action_correct")) for row in arm_records
            )
            rows += (
                f"<tr><td>{escape(ARM_LABELS[arm])}</td><td>{result['first_answers_correct']}/{count}</td>"
                f'<td>{first_actions}/{count}</td><td><div class="bar"><i style="width:{percentage}%">'
                f"</i></div><b>{passed}/{count}</b></td><td>{errors}</td>"
                f"<td>{result['native_tool_calls'] / count:.1f}</td></tr>"
            )
            if arm != "baseline":
                paired = [
                    row
                    for row in arm_records
                    if row["score"]["answerable"] and row["case"] in baseline_records
                ]
                paired_success = sum(row["score"]["exact_task_success"] for row in paired)
                baseline_success = sum(
                    baseline_records[row["case"]]["score"]["exact_task_success"] for row in paired
                )
                rows += (
                    f'<tr class="detail"><td colspan="6">Same answerable worlds: this condition {paired_success}/{len(paired)}, '
                    f"plain ReAct {baseline_success}/{len(paired)}. {ci}. "
                    f"Function used: {result['function_used']}/{count}. "
                    f"Invalid accepted: {result['accepted_invalid_answers'] + result['accepted_invalid_actions']}.</td></tr>"
                )
        families = sorted({family for arm in report["arms"].values() for family in arm["families"]})
        family_rows = ""
        for family in families:
            family_rows += f"<tr><td>{escape(family.replace('_', ' '))}</td>"
            for arm in arm_order:
                score = report["arms"][arm]["families"].get(family, {})
                state = (
                    "pass" if score.get("passed") else "fail" if score.get("total") else "pending"
                )
                family_rows += f'<td><span class="cell {state}">{state}</span></td>'
            family_rows += "</tr>"
        family_header = "".join(f"<th>{escape(ARM_LABELS[arm])}</th>" for arm in arm_order)
        unstarted = report["planned_episodes"] - report["completed_episodes"]
        stop_note = (
            f"<p>The budget gate stopped {unstarted} unstarted episodes. "
            "Each new episode requires a USD 4 reservation. The remaining allowance was too small. "
            "This is a partial pilot, not a completed 60-episode comparison.</p>"
            if report.get("job_errors") and unstarted
            else ""
        )
        comparison += (
            f"<h3>{escape(label)} <small>{report['completed_episodes']}/"
            f"{report['planned_episodes']} episodes complete</small></h3>"
            + stop_note
            + "<table><thead><tr><th>Agent condition</th><th>First answer</th><th>First action*</th>"
            "<th>Whole task</th><th>CLI errors</th>"
            f"<th>Calls / episode</th></tr></thead><tbody>{rows}</tbody></table>"
            '<p class="caption">Whole task requires the correct first answer, correct first action, '
            "correct final database state, and a clean CLI exit. *For incomplete data, the correct action is no reservation.</p>"
            f"<p><b>Interpretation:</b> {first_correct}/{len(records)} episodes submitted a correct first answer. "
            f"{missing_answers} episodes submitted no answer. "
            f"{terminal_only} failed episodes already had the correct answer and final database state when the CLI ended with an error. "
            f"There were {metadata_detours} blocked metadata inspection calls. "
            "The frozen metric still counts these failures. These results do not isolate answer accuracy from execution efficiency.</p>"
            "<details><summary>Inspect whole-task failures</summary><table><thead><tr><th>Condition</th><th>Family</th>"
            f"<th>Business state correct</th><th>CLI exit code</th><th>Evidence</th></tr></thead><tbody>{failure_rows}</tbody></table>"
            '<p class="caption">CLI code 53 means the model turn limit was reached. Metadata restrictions may cause extra planning steps.</p></details>'
            f"<details><summary>Inspect all ten task families</summary><table><thead><tr><th>Family</th>{family_header}</tr></thead>"
            f"<tbody>{family_rows}</tbody></table></details>"
            f'<p><a href="{escape(label)}/summary.json">Summary data</a> · '
            f'<a href="{escape(label)}/results.jsonl">Every scored episode</a></p>'
        )
        if (root / label / "final-audit.json").exists():
            comparison += f'<p><a href="{escape(label)}/final-audit.json">Final hash, failure, and budget audit</a></p>'
    if not comparison:
        comparison = (
            "<p>Live paired comparison has not completed. No reliability gain is claimed.</p>"
        )
    retired_links = " · ".join(
        f'<a href="{escape(name)}/summary.json">{escape(name)}: {data["completed_episodes"]} diagnostic episodes</a>'
        for name, data in retired
    )
    schema_repair = read(root / "schema-repair-challenge/construction.json", {})
    function_repair = read(root / "function-repair-challenge/construction.json", {})
    repair_rows = "".join(
        "<tr><td>"
        + title
        + "</td><td>"
        + before
        + "</td><td>"
        + escape(record.get("status", "not run"))
        + '</td><td><a href="'
        + link
        + '">Evidence</a></td></tr>'
        for title, before, record, link in (
            (
                "Schema mutation",
                "Minimum 2 and maximum 1 make RoomOffer unsatisfiable.",
                schema_repair,
                "schema-repair-challenge/mutation.json",
            ),
            (
                "Function mutation",
                "Remove the budget predicate: OWL still passes, but 15 of 24 training worlds fail.",
                function_repair,
                "function-repair-challenge/construction.json",
            ),
        )
    )
    document = f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OaK | Evidence before interface</title><style>
:root{{--ink:#173132;--muted:#5b7272;--paper:#f5f7f2;--line:#d8e2dd;--green:#16725d;--blue:#3769a1}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 system-ui,sans-serif}}
main{{max-width:1240px;margin:auto;padding:44px 48px 70px}}header{{border-bottom:1px solid var(--line);padding-bottom:28px}}
.eyebrow{{font-size:12px;font-weight:750;letter-spacing:2px;color:var(--green);text-transform:uppercase}}
h1{{font-size:44px;letter-spacing:-1.8px;line-height:1.12;max-width:850px;margin:12px 0}}h2{{font-size:23px;margin:0 0 15px}}
h3{{font-size:16px;margin:22px 0 8px}}p{{margin:8px 0;color:var(--muted)}}.lead{{font-size:18px;max-width:900px}}
.status{{margin-top:20px;padding:12px 16px;background:#fff4d5;border-left:4px solid #ba8633;color:#624717}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:28px 0}}.card,section{{background:white;border:1px solid var(--line);border-radius:13px}}
.card{{padding:18px}}.card strong{{font-size:31px;display:block;line-height:1.2}}.card span{{font-size:12px;color:var(--muted)}}
section{{padding:25px;margin:18px 0}}.flow{{display:grid;grid-template-columns:repeat(5,1fr);gap:13px;margin:19px 0}}
.node{{position:relative;padding:17px 12px;border-radius:9px;background:#eaf3ed;min-height:112px}}
.node:not(:last-child):after{{content:'→';position:absolute;right:-13px;top:40px;color:var(--green);font-weight:900}}
.node b{{display:block;font-size:14px;margin-bottom:5px}}.node span{{font-size:12px;color:var(--muted)}}
.runtime .node{{background:#edf3fa}}.caption{{font-size:13px}}.split{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
table{{border-collapse:collapse;width:100%;font-size:12px}}th{{text-align:left;color:var(--muted);font-weight:600;background:#f7f9f6}}
td,th{{padding:12px 9px;border-bottom:1px solid var(--line);vertical-align:middle}}td:first-child{{font-weight:650}}
a{{color:var(--blue);text-decoration:none}}a:hover{{text-decoration:underline}}.pill{{background:#e4f3e9;color:var(--green);padding:3px 8px;border-radius:30px}}
.bar{{height:7px;background:#e5ece7;border-radius:6px;width:110px;display:inline-block;margin-right:9px;overflow:hidden}}
.bar i{{height:100%;display:block;background:var(--green)}}small{{color:var(--muted);font-weight:400;margin-left:12px}}
.detail td{{font-size:11px;font-weight:400;color:var(--muted);padding-top:3px}}summary{{cursor:pointer;color:var(--blue);margin:15px 0}}
.cell{{font-size:11px;border-radius:5px;padding:3px 7px}}.pass{{color:#146c43;background:#e4f3e9}}.fail{{color:#a13e30;background:#fae9e4}}.pending{{color:#667;background:#eef0f2}}
ul{{padding-left:20px;color:var(--muted)}}li{{margin:7px 0}}code{{font-size:12px;background:#eef2ee;padding:2px 5px;border-radius:4px}}
footer{{font-size:12px;color:var(--muted);padding-top:20px}}@media(max-width:850px){{main{{padding:25px 18px}}.cards,.split{{grid-template-columns:1fr 1fr}}.flow{{grid-template-columns:1fr}}.node:after{{display:none}}h1{{font-size:34px}}section{{overflow:auto}}}}
</style><main><header><div class="eyebrow">OaK experiment notebook · 7 to 8 November 2026</div>
<h1>Make the relationships executable.<br>Then test the agent.</h1>
<p class="lead">One hotel task surface. Real Gemini. Existing free SQLite and Filesystem MCP servers.
Fictional records and local reservations. No product frontend.</p>
<div class="status"><b>Decision:</b> A small mechanism demonstration. The full reliability victory criterion remains unproven.</div></header>
<div class="cards"><div class="card"><strong>{len(construction)}</strong><span>Live construction variants</span></div>
<div class="card"><strong>10,000</strong><span>Fresh executor checks per kernel, not LLM runs</span></div>
<div class="card"><strong>{episodes}</strong><span>Scored live comparison episodes</span></div>
<div class="card"><strong>${budget["charged_usd"]:.2f} / 40</strong><span>Conservative budget accounting</span></div></div>
<section><h2>The mechanism</h2><div class="eyebrow">Build once for a task surface</div><div class="flow">
<div class="node"><b>1. Describe</b><span>Task rules, granted tool contracts, sampled training worlds.</span></div>
<div class="node"><b>2. Generate</b><span>Named relations, typed traversals, comparisons, arithmetic.</span></div>
<div class="node"><b>3. Validate</b><span>OWL + HermiT for schema logic. Separate execution checks.</span></div>
<div class="node"><b>4. Repair</b><span>Judge scores and observable trajectories. Revise failed artifacts.</span></div>
<div class="node"><b>5. Freeze</b><span>Save schema and function hashes before unseen runs.</span></div></div>
<div class="eyebrow">Use the frozen kernel on each new request</div><div class="flow runtime">
<div class="node"><b>Gemini ReAct</b><span>Select a granted native MCP tool.</span></div>
<div class="node"><b>Read source tables</b><span>Existing SQLite MCP reads the new fictional world.</span></div>
<div class="node"><b>Call named query</b><span>The generated function runs as a live SQL view.</span></div>
<div class="node"><b>Check the action</b><span>The agent hook checks evidence, snapshot, and allowed writes.</span></div>
<div class="node"><b>Write and reserve</b><span>Existing Filesystem and SQLite MCPs execute local writes.</span></div></div>
<p class="caption">No custom MCP server is used. Schema and function construction do not repeat on every inference run.</p></section>
<section><h2>The generated relationship that matters</h2>
<p style="font-size:22px;color:var(--ink)"><b>RoomOffer</b> → <code>hotel</code> → <b>Hotel</b> → <code>policy</code> → <b>ChildPolicy</b></p>
<p>The function follows these exact links. It checks city, room capacity, child age, and total cost.
It computes <code>nightly_cents × nights + fee_cents</code> once for each offer.</p>
<p>A cheap room cannot pass with another hotel's child policy. A missing link produces an incomplete result.
Each accepted row includes the source IDs and the relation path used to compute it.</p>
<p class="caption">The generated function computes eligibility. A fixed action contract then permits one reservation
for the cheapest eligible offer. This prototype does not generate arbitrary action plans.</p>
<p><a href="construction/explicit_stratified/kernel.json">Generated function and relation map</a> ·
<a href="construction/explicit_stratified/schema.owl">Validated OWL schema</a></p></section>
<section><h2>Construction experiments</h2><p>One task surface. Change the wording, sample selection, or review prompt.
All attempts remain in the log. Equal results do not establish that one prompt is better.</p>
<table><thead><tr><th>Variant</th><th>Training cases</th><th>Rounds</th><th>State</th><th>Frozen hash</th></tr></thead>
<tbody>{construction_rows}</tbody></table><p class="caption">The four constructions produce one equivalent reasoning procedure.
Two artifact fingerprints reflect syntax differences. This is not evidence for four distinct solutions.</p></section>
<section><h2>Unseen native MCP comparison</h2><p>Same facts, model, request, action, and tool-call limit.
Plain ReAct and schema-only can write read-only SQL joins and calculations. Full conditions must use the generated function.
Score the first proposal before the guard. An accepted correction does not erase an earlier error.</p>{comparison}
<p class="caption">Intervals resample paired answerable source worlds. All four full conditions share the same worlds.
They do not provide forty independent worlds. Small samples cannot prove long-tail reliability.</p></section>
<section><h2>Two different kinds of repair</h2><table><thead><tr><th>Challenge</th><th>Observed fault</th><th>Result</th><th>Record</th></tr></thead>
<tbody>{repair_rows}</tbody></table><p class="caption">These are explicit fault injections into generated artifacts.
Real Gemini construction and judge calls repair both faults. The repaired artifacts pass all 24 training worlds.
They test repair ability. They are not presented as natural construction failures.</p></section>
<div class="split"><section><h2>What the ontology buys</h2><ul>
<li>One explicit path from offer to hotel to its child policy.</li>
<li>Reusable calculations with typed inputs and outputs.</li>
<li>Evidence paths that identify the records behind each result.</li>
<li>A concrete artifact that validation and feedback can repair.</li>
<li>In strict mode, the accepted answer must match the generated function.</li></ul></section>
<section><h2>What it does not prove</h2><ul>
<li>OWL consistency does not prove source truth or data completeness.</li>
<li>A shared write guard does not prove that the agent reasoned correctly.</li>
<li>This small hotel surface does not cover arbitrary MCP tools or tasks.</li>
<li>Typed structured records replace the paper's text extraction stage.</li>
<li>Action checks use isolated databases. The hook and write are not one transaction.</li>
<li>No model weights, general agent onboarding, or multi-agent coordination are trained here.</li></ul></section></div>
<section><h2>Integration findings</h2><p>The unchanged MCP packages work through Gemini's native client.
Three local CLI fixes handle empty tool catalogs, required-hook failures, and empty JSON array results.
The guard patch is active only for this experiment. Its tests check missing, failed, and malformed hook results.</p>
<p>The first two pilots are retained as integration diagnostics. They are excluded from this comparison because
the execution protocol changed. The current pilot uses fresh worlds and frozen execution files.</p><p>{retired_links}</p></section>
<section><h2>Budget and audit</h2><p>${known:.3f} measured-token estimate at conservative regular rates,
plus ${unknown:.2f} retained for runs with missing usage. Open reservations: ${budget["reserved_usd"]:.2f}.
The ledger uses full input prices for cached tokens
and includes reasoning tokens. This is an estimate, not a billing invoice.</p>
<p><a href="budget.jsonl">Append-only budget ledger</a> ·
<a href="construction/executor-checks.json">Executor evidence</a> ·
<a href="https://cloud.google.com/model-garden/pricing">Google pricing source</a></p></section>
<footer>Paper basis: Toward Effective and Reliable LLM Agents via Dynamic Ontology, Sections 3.1 to 3.3.
Project decision thresholds remain in docs/ontology-victory.md. The SQLite reference MCP package is archived;
this is a local experiment, not a deployment recommendation.</footer></main></html>"""
    (root / "report.html").write_text(document)
    return root / "report.html"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(".local/ontology-experiments"))
    print(make_report(parser.parse_args().root))
