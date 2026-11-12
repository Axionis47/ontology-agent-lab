"""Check compiled SQL against the independent source-record oracle."""

import copy
import json
import sqlite3
from pathlib import Path

import pytest

from .kernel import Candidate
from .sql_kernel import SCHEMA, compile_views, prepare_database
from .suite import make_suite, reference


@pytest.fixture(scope="module")
def candidate():
    return Candidate.model_validate_json(Path(__file__).with_name("seed.json").read_text())


def result(connection):
    return {
        "status": connection.execute("SELECT status FROM snapshot_status").fetchone()[0],
        "eligible": dict(connection.execute("SELECT offer_id, total_cents FROM eligible_stays")),
    }


def test_five_hundred_worlds_match_independent_oracle(candidate, tmp_path):
    for index, case in enumerate(make_suite("sql-stress", 2703, 500)):
        path = tmp_path / f"world-{index}.sqlite"
        prepare_database(case, candidate, path)
        with sqlite3.connect(path) as connection:
            expected = reference(case)
            assert result(connection) == {key: expected[key] for key in ("status", "eligible")}
            assert connection.execute("SELECT COUNT(*) FROM offer").fetchone()[0] == len(
                case["inventory"]["offers"]
            )


def test_baseline_has_raw_tables_and_no_computed_answers(tmp_path):
    case = make_suite("sql-baseline", 7, 1)[0]
    path = tmp_path / "baseline.sqlite"
    manifest = prepare_database(case, None, path)
    assert manifest["views"] == []
    with sqlite3.connect(path) as connection:
        assert (
            connection.execute("SELECT name FROM sqlite_master WHERE type='view'").fetchall() == []
        )
        assert connection.execute("SELECT COUNT(*) FROM reservations").fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM offer").fetchone()[0] == len(
            case["inventory"]["offers"]
        )
    with pytest.raises(FileExistsError):
        prepare_database(case, None, path)


def test_views_recompute_from_source_changes_and_record_typed_evidence(candidate, tmp_path):
    case = make_suite("sql-live", 107, 1)[0]
    path = tmp_path / "live.sqlite"
    prepare_database(case, candidate, path)
    with sqlite3.connect(path) as connection:
        rows = connection.execute("SELECT * FROM eligible_stays").fetchall()
        assert rows
        evidence, relations = json.loads(rows[0][2]), json.loads(rows[0][3])
        assert {item["type"] for item in evidence} == {"Hotel", "RoomOffer", "ChildPolicy"}
        assert [item["relation"] for item in relations] == ["belongsTo", "hasPolicy"]
        connection.execute("UPDATE policy SET minimum_child_age=18")
        assert result(connection) == {"status": "complete", "eligible": {}}
        connection.execute("UPDATE hotel SET policy_id=NULL")
        assert result(connection) == {"status": "incomplete", "eligible": {}}


def test_identity_order_and_budget_changes_match_oracle(candidate, tmp_path):
    for index, original in enumerate(make_suite("sql-metamorphic", 331, 20)):
        case = copy.deepcopy(original)
        groups = (
            case["inventory"]["hotels"],
            case["inventory"]["offers"],
            case["policies"]["policies"],
        )
        mapping = {item["id"]: f"renamed_{item['id']}" for group in groups for item in group}
        for group in groups:
            group.reverse()
            for item in group:
                item["id"] = mapping[item["id"]]
                for field in ("hotel_id", "policy_id"):
                    if field in item and item[field] in mapping:
                        item[field] = mapping[item[field]]
        path = tmp_path / f"changed-{index}.sqlite"
        prepare_database(case, candidate, path)
        with sqlite3.connect(path) as connection:
            expected = reference(case)
            assert result(connection) == {key: expected[key] for key in ("status", "eligible")}
            connection.execute("UPDATE request SET budget_cents = budget_cents + 100000")
            case["query"]["budget_cents"] += 100000
            expected = reference(case)
            assert result(connection) == {key: expected[key] for key in ("status", "eligible")}


def test_sql_uses_generated_computation_and_does_not_import_gold(candidate, tmp_path):
    case = make_suite("sql-program", 704, 4)[3]
    changed = candidate.model_copy(
        update={
            "program": candidate.program.model_copy(
                update={"filters": candidate.program.filters[:-1]}
            )
        }
    )
    case["expected"] = {"invented_gold": -1}
    path = tmp_path / "program.sqlite"
    prepare_database(case, changed, path)
    with sqlite3.connect(path) as connection:
        assert result(connection)["eligible"] != reference(case)["eligible"]
        assert "invented_gold" not in dict(
            connection.execute("SELECT offer_id,total_cents FROM eligible_stays")
        )


def test_compiler_rejects_sql_injection_and_handles_reserved_alias(candidate):
    value = json.loads(candidate.model_dump_json())
    value["program"]["total_cents"] = {
        "op": "field",
        "name": "offer.nightly_cents); DROP TABLE offer;--",
    }
    with pytest.raises(ValueError, match="Unknown source field"):
        compile_views(Candidate.model_validate_json(json.dumps(value)))
    renamed = json.loads(
        candidate.model_dump_json().replace('"offer.', '"select.').replace('"offer"', '"select"')
    )
    sql = compile_views(Candidate.model_validate_json(json.dumps(renamed)))
    with sqlite3.connect(":memory:") as connection:
        connection.executescript(SCHEMA + sql)
        assert connection.execute("SELECT status FROM snapshot_status").fetchone() == ("complete",)
