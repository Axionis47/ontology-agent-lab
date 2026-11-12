import asyncio
import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from oak.model_client import GenerationLimits, ModelFailure

from .budget import NANOS, PHASE_CAPS, BudgetModel
from .cases import cases, weekend
from .report import render, repetitions, stop_details
from .sources import Sources, book_rows, products, save


def test_projection_preserves_missing_null_zero_and_decimal_precision():
    rows = products(
        [
            {
                "code": "1",
                "nutriments": {"sugars_100g": Decimal("0.000000000000000001"), "fiber_100g": None},
            },
            {"code": "2", "nutriments": {"sugars_100g": 0}},
            {"code": "3"},
        ]
    )
    assert rows[0]["sugars_100g"] == "1E-18"
    assert rows[0]["fiber_100g"] is None
    assert rows[1]["sugars_100g"] == "0"
    assert "fiber_100g" not in rows[1]
    assert set(rows[2]) == {"code"}


def test_book_projection_preserves_distinct_records_and_explicit_links():
    result = book_rows(
        [
            {
                "key": "/works/OL1W",
                "title": "Same title",
                "authors": [{"author": {"key": "/authors/OL1A"}}],
                "subjects": ["Food"],
            },
            {
                "key": "/books/OL1M",
                "title": "Same title",
                "works": [{"key": "/works/OL1W"}],
                "languages": [{"key": "/languages/eng"}],
                "publishers": ["Exact Label"],
            },
        ]
    )
    assert [record["key"] for record in result["records"]] == ["/works/OL1W", "/books/OL1M"]
    assert {link["target"] for link in result["links"]} == {
        "/authors/OL1A",
        "Food",
        "/works/OL1W",
        "/languages/eng",
        "Exact Label",
    }
    assert not any(
        link["field"] == "authors" and link["record_key"] == "/books/OL1M"
        for link in result["links"]
    )


async def test_cache_reuses_exact_requests_and_separates_pairs(tmp_path):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, text='{"value": 1.234567890123456789, "items": []}')

    source = Sources(tmp_path, transport=httpx.MockTransport(handler), throttle=False)
    try:
        source.select_group("training")
        first, original = await source.get("https://openlibrary.org/search.json", {"q": "test"})
        second, reused = await source.get("https://openlibrary.org/search.json", {"q": "test"})
        assert first == second and first["value"] == Decimal("1.234567890123456789")
        assert not original["cache_hit"] and reused["cache_hit"]
        assert original["fetched_at"] == reused["fetched_at"]
        source.select_group("pair_deep")
        _, fresh = await source.get("https://openlibrary.org/search.json", {"q": "test"})
        assert not fresh["cache_hit"] and len(requests) == 2
        assert (
            "1.234567890123456789"
            in json.loads((tmp_path / original["raw_response_file"]).read_text())["body"]
        )
    finally:
        await source.close()


async def test_source_errors_are_retained_without_success_cache(tmp_path):
    source = Sources(
        tmp_path,
        transport=httpx.MockTransport(lambda request: httpx.Response(429, text="rate limited")),
        throttle=False,
    )
    try:
        with pytest.raises(ToolError, match="429"):
            await source.get("https://world.openfoodfacts.org/api/v2/search")
        assert len(list((tmp_path / "sources" / "preflight").glob("*-error-*.json"))) == 1
        log = json.loads((tmp_path / "source-access.jsonl").read_text())
        assert "429" in log["error"]
        with pytest.raises(ValueError, match="outside"):
            await source.get("http://127.0.0.1/private")
    finally:
        await source.close()


class UnknownModel:
    def __init__(self):
        self.calls = 0

    async def turn(self, *args, **kwargs):
        self.calls += 1
        raise RuntimeError("No usage receipt")


async def test_budget_keeps_unknown_reservation_and_blocks_next_call(tmp_path):
    upstream = UnknownModel()
    model = BudgetModel(upstream, tmp_path)
    model.phase = "deep_baseline"
    limits = GenerationLimits(100_000, 20_000, 5)
    with pytest.raises(RuntimeError, match="receipt"):
        await model.turn([], [], limits=limits)
    assert model.total() == 300_000_000
    with pytest.raises(RuntimeError, match="before dispatch"):
        await model.turn([], [], limits=limits)
    assert upstream.calls == 1
    assert json.loads((tmp_path / "budget.json").read_text())["accounted_usd"] == 0.3
    with pytest.raises(ValueError, match="already"):
        BudgetModel(upstream, tmp_path)


async def test_budget_accounts_known_failure_usage_without_retry(tmp_path):
    class FailedModel:
        async def turn(self, *args, **kwargs):
            raise ModelFailure(
                "output_truncated",
                SimpleNamespace(
                    model_dump=lambda **kwargs: {"input_tokens": 100, "output_tokens": 200}
                ),
            )

    model = BudgetModel(FailedModel(), tmp_path)
    with pytest.raises(ModelFailure):
        await model.turn([], [], limits=GenerationLimits(1000, 1000, 5))
    assert model.total() == 1_650_000
    assert len(model.entries) == 1
    assert sum(PHASE_CAPS.values()) == 10 * NANOS


async def test_cancelled_model_call_retains_reservation(tmp_path):
    class CancelledModel:
        async def turn(self, *args, **kwargs):
            raise asyncio.CancelledError()

    model = BudgetModel(CancelledModel(), tmp_path)
    with pytest.raises(asyncio.CancelledError):
        await model.turn([], [], limits=GenerationLimits(1000, 1000, 5))
    assert model.total() == 9_000_000
    assert model.entries[0]["status"] == "unknown"


def test_dates_are_fixed_and_held_out_requests_are_separate():
    manifest = cases(date(2026, 11, 10))
    assert (manifest["saturday"], manifest["sunday"]) == ("2026-11-14", "2026-11-15")
    assert weekend(date(2026, 11, 14)) == ("2026-11-21", "2026-11-22")
    assert "9780441478125" not in json.dumps(manifest["training"])
    assert len(manifest["comparisons"]) == len(manifest["training"]) == 4


def test_report_retains_blocked_runs_and_escapes_source_text(tmp_path):
    save(
        tmp_path / "manifest.json",
        {"comparisons": [{"name": "deep", "query": "<script>alert(1)</script>"}]},
    )
    save(
        tmp_path / "run.json",
        {
            "status": "finished",
            "comparisons": {
                "deep": {"ontology": {"status": "blocked", "message": "No accepted ontology"}}
            },
        },
    )
    render(tmp_path)
    page = (tmp_path / "report.html").read_text()
    assert "<script>" not in page
    assert "&lt;script&gt;" in page
    assert "blocked" in page and "No accepted ontology" in page
    assert "No scores or rankings" in page


def test_report_exposes_stop_reasons_and_identical_calls():
    call = {
        "name": "food_search",
        "arguments": {"category": "en:snacks"},
        "result": {
            "error": "tool_error",
            "raw": {"content": [{"type": "text", "text": "Public source HTTP 503"}]},
        },
    }
    document = {
        "calls": [call, call],
        "events": [{"kind": "model_error", "data": {"error": "Input limit reached"}}],
    }
    assert stop_details(document, {}) == ["Input limit reached", "Public source HTTP 503"]
    assert repetitions(document, {}) == [
        {"tool": "food_search", "arguments": {"category": "en:snacks"}, "executions": 2}
    ]
