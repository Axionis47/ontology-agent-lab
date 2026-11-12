"""Check shared spending limits and conservative token accounting."""

import pytest

from .budget import Budget, usage_cost


def test_budget_counts_open_jobs_and_retains_unknown_usage(tmp_path):
    ledger = Budget(tmp_path / "budget.jsonl", limit=4)
    first = ledger.reserve("first", 3)
    with pytest.raises(RuntimeError, match="budget"):
        Budget(ledger.path, limit=4).reserve("parallel", 2)
    ledger.settle(first, None)
    assert ledger.snapshot()["charged_usd"] == 3
    with pytest.raises(RuntimeError, match="budget"):
        ledger.reserve("after failure", 2)


def test_reasoning_and_cached_tokens_are_counted(tmp_path):
    stats = {
        "models": {
            "gemini-3.8-flash": {
                "tokens": {
                    "prompt": 1000000,
                    "cached": 900000,
                    "candidates": 100000,
                    "thoughts": 100000,
                    "total": 1200000,
                }
            }
        }
    }
    assert usage_cost(stats) == 3
    ledger = Budget(tmp_path / "budget.jsonl")
    identifier = ledger.reserve("known", 4)
    ledger.settle(identifier, stats)
    assert ledger.snapshot()["reserved_usd"] == 0
    assert ledger.snapshot()["charged_usd"] == 3
    assert usage_cost({"models": {"unknown": {}}}) is None


def test_usage_reconciliation_keeps_unknown_retry_allowance(tmp_path):
    ledger = Budget(tmp_path / "budget.jsonl")
    identifier = ledger.reserve("missing exit summary", 4)
    ledger.settle(identifier, None)
    stats = {"models": {"gemini-3.8-flash": {"tokens": {"prompt": 100000}}}}
    ledger.reconcile_completed_usage(identifier, stats, {"source": "test"})
    assert ledger.snapshot()["charged_usd"] == pytest.approx(1.15)
    with pytest.raises(ValueError, match="already reconciled"):
        ledger.reconcile_completed_usage(identifier, stats, {"source": "test"})
    assert len(ledger.path.read_text().splitlines()) == 3
