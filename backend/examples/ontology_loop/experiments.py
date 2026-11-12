"""Run paired live episodes with fixed worlds, frozen kernels, and a shared budget."""

import argparse
import asyncio
import hashlib
import json
import random
from pathlib import Path

from .budget import Budget
from .kernel import Candidate
from .native import run_native
from .session_usage import recover_session_usage
from .suite import make_suite, score_episode


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def paired_interval(differences, seed=1067, repetitions=5000):
    if not differences:
        return None
    rng = random.Random(seed)
    means = sorted(
        sum(rng.choices(differences, k=len(differences))) / len(differences)
        for _ in range(repetitions)
    )
    return [means[int(repetitions * 0.025)], means[int(repetitions * 0.975)]]


def summarize(rows, manifest, budget):
    groups = {}
    for row in rows:
        groups.setdefault(row["arm"], []).append(row)
    results = {}
    baseline = {r["case"]: r for r in groups.get("baseline", [])}
    for arm, items in groups.items():
        answerable = [row for row in items if row["score"]["answerable"]]
        incomplete = [row for row in items if not row["score"]["answerable"]]
        differences = [
            int(row["score"]["exact_task_success"])
            - int(baseline[row["case"]]["score"]["exact_task_success"])
            for row in answerable
            if row["case"] in baseline
        ]
        family = {}
        for row in items:
            record = family.setdefault(row["score"]["family"], {"passed": 0, "total": 0})
            record["total"] += 1
            record["passed"] += int(row["score"]["exact_task_success"])
        results[arm] = {
            "episodes": len(items),
            "first_answers_correct": sum(r["score"]["first_answer_correct"] for r in items),
            "exact_task_successes": sum(r["score"]["exact_task_success"] for r in items),
            "answerable_successes": sum(r["score"]["exact_task_success"] for r in answerable),
            "answerable_total": len(answerable),
            "incomplete_correct": sum(r["score"]["first_answer_correct"] for r in incomplete),
            "incomplete_total": len(incomplete),
            "invalid_answer_proposals": sum(r["score"]["invalid_answer_proposals"] for r in items),
            "accepted_invalid_answers": sum(r["score"]["accepted_invalid_answers"] for r in items),
            "accepted_invalid_actions": sum(r["score"]["accepted_invalid_actions"] for r in items),
            "function_used": sum(r["function_used"] for r in items),
            "native_tool_calls": sum(r["native_tool_calls"] for r in items),
            "wall_seconds": sum(r["wall_seconds"] for r in items),
            "paired_answerable_count": len(differences),
            "paired_difference": sum(differences) / len(differences) if differences else None,
            "paired_bootstrap_95_interval": paired_interval(differences),
            "families": family,
        }
    return {
        "experiment": manifest,
        "arms": results,
        "budget": budget.snapshot(),
        "completed_episodes": len(rows),
        "planned_episodes": len(manifest["jobs"]),
        "formal_victory": "not_demonstrated",
        "scope": "Small live pilot. The planned 240-world repeated evaluation is not complete.",
    }


async def run_experiments(
    directory, construction_root, count=10, seed=913, parallel=3, selected=None
):
    directory, construction_root = Path(directory).resolve(), Path(construction_root).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    variants = selected or [
        "explicit_stratified",
        "concise_stratified",
        "explicit_random",
        "counterexample_stratified",
    ]
    artifacts = {name: construction_root / name / "kernel.json" for name in variants}
    candidates = {
        name: Candidate.model_validate_json(path.read_text()) for name, path in artifacts.items()
    }
    cases = make_suite("unseen_live", seed, count)
    arms = {"baseline": ("baseline", None)}
    if len(variants) > 1:
        arms["schema_only"] = ("schema_only", variants[0])
    arms.update({f"full_{name}": ("strict", name) for name in variants})
    jobs = [{"case": case["name"], "arm": arm} for case in cases for arm in arms]
    random.Random(seed + 17).shuffle(jobs)
    manifest = {
        "kind": "live_pilot",
        "seed": seed,
        "count": count,
        "model": "gemini-3.8-flash",
        "kernel_hashes": {name: file_hash(path) for name, path in artifacts.items()},
        "source_hashes": {
            name: file_hash(Path(__file__).with_name(name))
            for name in ("suite.py", "hook.py", "sql_kernel.py", "native.py")
        },
        "cases_sha256": hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest(),
        "jobs": jobs,
    }
    manifest_path = directory / "manifest.json"
    if manifest_path.exists():
        if json.loads(manifest_path.read_text()) != manifest:
            raise ValueError("The existing evaluation manifest differs. Use a new run directory.")
    else:
        manifest_path.write_text(json.dumps(manifest, indent=2))
        (directory / "reference-worlds.json").write_text(json.dumps(cases, indent=2))
    budget = Budget(construction_root.parent / "budget.jsonl")
    case_map = {case["name"]: case for case in cases}
    gate = asyncio.Semaphore(parallel)
    rows = []

    async def episode(job):
        async with gate:
            arm, name = job["arm"], job["case"]
            mode, variant = arms[arm]
            case = case_map[name]
            output = directory / "episodes" / arm / name
            result_path = output / "scored.json"
            if result_path.exists():
                rows.append(json.loads(result_path.read_text()))
                return
            for label, path in artifacts.items():
                if file_hash(path) != manifest["kernel_hashes"][label]:
                    raise ValueError("A frozen kernel changed during evaluation.")
            for source, expected in manifest["source_hashes"].items():
                if file_hash(Path(__file__).with_name(source)) != expected:
                    raise ValueError("The scoring or execution code changed during evaluation.")
            while True:
                try:
                    reservation = budget.reserve(f"{directory.name}:{arm}:{name}", amount=4)
                    break
                except RuntimeError:
                    if budget.snapshot()["charged_usd"] + 4 > budget.limit:
                        raise
                    await asyncio.sleep(0.25)
            result = None
            try:
                result = await run_native(case, candidates.get(variant), mode, output)
            except Exception as exc:
                output.mkdir(parents=True, exist_ok=True)
                result = {
                    "case": name,
                    "mode": mode,
                    "completed": False,
                    "error": str(exc),
                    "stats": {},
                }
                (output / "result.json").write_text(json.dumps(result, indent=2))
            finally:
                accounting = budget.settle(reservation, result.get("stats") if result else None)
                if result and result.get("cli_exit_code") == 53 and result.get("session_id"):
                    try:
                        recovered = recover_session_usage(result["session_id"])
                        accounting = budget.reconcile_completed_usage(
                            reservation,
                            recovered["stats"],
                            recovered["evidence"],
                            retry_reserve=1.0,
                        )
                    except ValueError:
                        pass
            scored_result = {
                **result,
                "completed": bool(result.get("completed") and not result.get("error")),
            }
            row = {
                "case": name,
                "arm": arm,
                "score": score_episode(case, scored_result),
                "function_used": result.get("function_used", False),
                "native_tool_calls": result.get("native_tool_calls", 0),
                "wall_seconds": result.get("wall_seconds", 0),
                "accounting": accounting,
                "result_path": str(output / "result.json"),
            }
            result_path.write_text(json.dumps(row, indent=2))
            rows.append(row)
            with (directory / "results.jsonl").open("a") as stream:
                stream.write(json.dumps(row) + "\n")
            report = summarize(rows, manifest, budget)
            (directory / "summary.json").write_text(json.dumps(report, indent=2))
            print(
                json.dumps(
                    {
                        "done": len(rows),
                        "planned": len(jobs),
                        "arm": arm,
                        "case": name,
                        "passed": row["score"]["exact_task_success"],
                        "budget_charged": budget.snapshot()["charged_usd"],
                    }
                ),
                flush=True,
            )

    results = await asyncio.gather(*(episode(job) for job in jobs), return_exceptions=True)
    errors = [str(result) for result in results if isinstance(result, BaseException)]
    report = summarize(rows, manifest, budget)
    report["job_errors"] = errors
    (directory / "summary.json").write_text(json.dumps(report, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(".local/ontology-experiments/pilot"))
    parser.add_argument(
        "--construction", type=Path, default=Path(".local/ontology-experiments/construction")
    )
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--seed", type=int, default=913)
    parser.add_argument("--parallel", type=int, default=3)
    parser.add_argument("--reference-only", action="store_true")
    args = parser.parse_args()
    asyncio.run(
        run_experiments(
            args.output,
            args.construction,
            args.count,
            args.seed,
            args.parallel,
            ["explicit_stratified"] if args.reference_only else None,
        )
    )


if __name__ == "__main__":
    main()
