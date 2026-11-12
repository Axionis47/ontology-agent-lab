"""Render recorded behavior without scores or rankings."""

import html
import json
from collections import Counter
from pathlib import Path


def read(root, name, default=None):
    path = root / name
    return json.loads(path.read_text()) if path.exists() else default


def escaped(value):
    return html.escape(str(value))


def details(label, data):
    payload = escaped(json.dumps(data, indent=2, ensure_ascii=False))
    return f"<details><summary>{escaped(label)}</summary><pre>{payload}</pre></details>"


def stop_details(document, result):
    reasons = []
    for event in document.get("events", result.get("trace", [])):
        data = event.get("data", event)
        if event.get("kind") == "model_error":
            reasons.append(data.get("error", "Model error"))
    for call in document.get("calls", []):
        observation = call.get("result", {})
        if observation.get("error"):
            reasons.extend(
                part["text"]
                for part in observation.get("raw", {}).get("content", [])
                if part.get("type") == "text"
            )
            if not observation.get("raw"):
                reasons.append(observation["error"])
    if result.get("error"):
        reasons.append(result["error"])
    return list(dict.fromkeys(reasons))


def repetitions(document, result):
    counts = Counter(
        json.dumps(
            {"tool": call.get("name", call.get("tool_id")), "arguments": call.get("arguments", {})},
            sort_keys=True,
        )
        for call in document.get("calls", result.get("observations", []))
    )
    return [
        {**json.loads(call), "executions": count} for call, count in counts.items() if count > 1
    ]


def render(root):
    root = Path(root)
    state = read(root, "run.json", {})
    manifest = read(root, "manifest.json", {})
    budget = read(root, "budget.json", {})
    accepted = read(root, "accepted.json", {})
    discovery = read(root, "discovery.json", {})
    review = read(root, "review.json", {})
    cards = []
    for case in manifest.get("comparisons", []):
        columns = []
        for mode in ("baseline", "ontology"):
            outcome = (
                state.get("comparisons", {}).get(case["name"], {}).get(mode, {"status": "not_run"})
            )
            document = read(root, outcome["artifact"], {}) if outcome.get("artifact") else {}
            episodes = document.get("episodes", [])
            result = document.get("result") or (episodes[0].get("result") if episodes else {}) or {}
            cost = (
                sum(
                    item["accounted_nanos"]
                    for item in budget.get("entries", [])
                    if item["phase"] == f"{case['name']}_{mode}"
                )
                / 1_000_000_000
            )
            link = (
                f'<a href="{escaped(outcome["artifact"])}">Full recorded episode</a>'
                if outcome.get("artifact")
                else ""
            )
            title = "Ordinary ReAct" if mode == "baseline" else "Accepted ontology"
            answer = result.get("final_output") or "No final answer was recorded."
            columns.append(
                f"<article><h3>{title}</h3>"
                f'<p class="status">{escaped(outcome["status"])} · USD {cost:.4f}</p>'
                f"<p>{escaped(outcome.get('message', ''))}</p>"
                f"<p>{escaped(' '.join(stop_details(document, result)))}</p>"
                f"<p>Elapsed seconds: {escaped(round(outcome.get('elapsed_seconds', 0), 2))}</p>"
                f'<pre class="answer">{escaped(answer)}</pre>{link}'
                + details("Calls and errors", document.get("calls", result.get("observations", [])))
                + details("Repeated calls with identical arguments", repetitions(document, result))
                + details(
                    "Functions and dispatch decisions",
                    {
                        "function_calls": result.get("function_calls", []),
                        "dispatch_decisions": result.get("dispatch_decisions", []),
                    },
                )
                + details(
                    "Working graph and evidence",
                    {
                        "graph": result.get("graph"),
                        "graph_processing": result.get("graph_processing", []),
                        "evidence_refs": result.get("evidence_refs", []),
                    },
                )
                + details(
                    "Trace and unresolved facts",
                    {
                        "trace": result.get("trace", document.get("events", [])),
                        "unresolved": result.get("unresolved_outcomes", []),
                    },
                )
                + "</article>"
            )
        cards.append(
            f"<section><h2>{escaped(case['name'].replace('_', ' ').title())}</h2>"
            f'<p>{escaped(case["query"])}</p><div class="pair">{"".join(columns)}</div></section>'
        )
    links = " ".join(
        f'<a href="{name}">{label}</a>'
        for name, label in (
            ("manifest.json", "Requests and source hashes"),
            ("preflight.json", "Source checks"),
            ("discovery.json", "Discovery"),
            ("training.json", "Training"),
            ("budget.json", "Cost ledger"),
            ("review.json", "Observed behavior and setup history"),
            ("source-access.jsonl", "Source reads and cache reuse"),
        )
        if (root / name).exists()
    )
    construction = {"discovery": state.get("discovery"), "training": state.get("training")}
    observations = "".join(
        f"<li>{escaped(item['observation'])} "
        f'<a href="{escaped(item["artifact"])}">Evidence</a></li>'
        for item in review.get("observations", [])
    )
    content = f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Oak live behavior stress test</title>
<style>
body{{font:16px/1.5 system-ui,sans-serif;background:#f4f6f5;color:#17251e;
padding:32px;max-width:1500px;margin:auto;overflow-wrap:anywhere}}
h1{{font-size:34px;margin-bottom:8px}}h2{{text-transform:capitalize}}
a{{color:#176144;margin-right:18px}}section{{margin:32px 0}}
.pair{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
article,header{{background:white;padding:24px;border:1px solid #d5dfd9;
border-radius:10px;min-width:0}}.status{{font-weight:700}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.5 ui-monospace,monospace;
max-height:500px;overflow:auto}}
.answer{{font:15px/1.6 system-ui,sans-serif;max-height:none}}
details{{border-top:1px solid #d5dfd9;padding:12px 0}}summary{{cursor:pointer;font-weight:600}}
@media(max-width:850px){{.pair{{grid-template-columns:1fr}}body{{padding:16px}}}}
</style>
<header><h1>Oak live behavior stress test</h1>
<p>One research agent. Four task shapes. Actual public source responses. No scores or rankings.</p>
<p>Run status: <strong>{escaped(state.get("status"))}</strong>.
Accounted model cost: <strong>USD {budget.get("accounted_usd", 0):.4f}</strong> of USD 10.</p>
<p>{escaped(state.get("error", ""))}</p>
<p>Request dates: {escaped(manifest.get("saturday"))} and
{escaped(manifest.get("sunday"))}, America/New_York.</p>
<p>Frozen ontology digest: {escaped(state.get("frozen_digest", "No accepted ontology."))}</p>
<nav>{links}</nav>
<p>{escaped(state.get("discovery", {}).get("message") or "")}</p>
<ul>{observations}</ul>
{details("Construction status", construction)}
{details("Discovery declarations, not an accepted ontology", discovery.get("schema_proposal"))}
{details("Accepted declarations", accepted.get("payload"))}</header>{"".join(cards)}
<footer><p>Responses are fetched from real sources.
Matching requests reuse responses within a comparison pair.
Raw responses retain their timestamps. Counts and costs describe execution, not task quality.
Unknown model usage retains a conservative reservation.
No reliability claim is made.</p></footer></html>"""
    (root / "report.html").write_text(content)
