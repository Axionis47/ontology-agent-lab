"""Hand-authored teaching example, not OaK or live-model evidence.

Run: python3 outputs/ontology-walkthrough/walkthrough.py

This lightweight domain schema is not an OWL ontology. The field requirements
below are supplied by the example's author, not discovered by an automated
grader. Passing them establishes coverage only for these declared questions.
There are no model calls, generated-code execution, external actions, or imports
from the frozen AppWorld memory comparison.
"""

import json


HOTELS = {"H1": {"id": "H1", "name": "Example Hotel"}}
ROOMS = [
    {"id": "A", "hotel_id": "H1", "price_usd_per_night": 100, "maximum_guests": 2},
    {"id": "B", "hotel_id": "H1", "price_usd_per_night": 100, "maximum_guests": 4},
    {"id": "C", "hotel_id": "H1", "price_usd_per_night": 180, "maximum_guests": 4},
]

V1 = {
    "version": "v1",
    "types": {
        "Hotel": ["id", "name"],
        "Room": ["id", "hotel_id", "price_usd_per_night"],
    },
    "relationships": [{"name": "belongs_to", "from": "Room", "to": "Hotel"}],
}
V2 = {
    **V1,
    "version": "v2",
    "types": {**V1["types"], "Room": [*V1["types"]["Room"], "maximum_guests"]},
}

# Author-declared competency questions and required evidence. These are checks
# of this example's representation coverage, not a universal ontology grader.
QUESTIONS = [
    ("Can we check the nightly USD budget?", {"price_usd_per_night"}),
    ("Can we check the number of guests?", {"maximum_guests"}),
]

# Expected results are separately authored fixtures. Equalities and empty
# results expose omitted checks and reversed/strict comparison errors.
CASES = [
    {"guests": 4, "budget": 150, "expected": ["B"]},
    {"guests": 2, "budget": 100, "expected": ["A", "B"]},
    {"guests": 4, "budget": 100, "expected": ["B"]},
    {"guests": 5, "budget": 150, "expected": []},
    {"guests": 4, "budget": 99, "expected": []},
]


def price_only(rooms, guests, budget):
    """Intentionally faulty, hand-authored function for the lesson."""
    return [r["id"] for r in rooms if r["price_usd_per_night"] <= budget]


def price_and_capacity(rooms, guests, budget):
    """Hand-authored repaired function, not a model-generated artifact."""
    return [
        r["id"] for r in rooms
        if r["price_usd_per_night"] <= budget and r["maximum_guests"] >= guests
    ]


def show_schema(schema):
    types = schema["types"]
    structural_check = all("id" in fields for fields in types.values()) and all(
        rel["from"] in types and rel["to"] in types
        for rel in schema["relationships"]
    )
    coverage = [
        {"question": question, "missing_fields": sorted(required - set(types["Room"]))}
        for question, required in QUESTIONS
    ]
    # Projection makes the information lost by the inadequate schema visible.
    projected = [{field: room[field] for field in types["Room"]} for room in ROOMS]
    return {
        "version": schema["version"],
        "limited_structural_check_passed": structural_check,
        "question_coverage": coverage,
        "room_facts_represented": projected,
    }


def check_function(function):
    results = []
    for case in CASES:
        actual = function(ROOMS, case["guests"], case["budget"])
        results.append({**case, "actual": actual, "passed": actual == case["expected"]})
    return {"function": function.__name__, "cases": results}


def main():
    schemas = [show_schema(V1), show_schema(V2)]
    functions = [check_function(price_only), check_function(price_and_capacity)]
    assert schemas[0]["limited_structural_check_passed"]
    assert schemas[0]["question_coverage"][1]["missing_fields"] == ["maximum_guests"]
    assert all(not q["missing_fields"] for q in schemas[1]["question_coverage"])
    assert all(room["hotel_id"] in HOTELS for room in ROOMS)
    assert any(not case["passed"] for case in functions[0]["cases"])
    assert all(case["passed"] for case in functions[1]["cases"])
    print(json.dumps({
        "evidence": {
            "model_output": "not-a-model", "provider": None,
            "requested_model": None, "resolved_model_version": None,
            "prompt_version": None, "call_identity": None,
            "scope": "Hand-authored teaching example; no model-quality conclusions.",
        },
        "schemas": schemas,
        "functions": functions,
        "limitations": [
            "Coverage requirements and expected answers are author-supplied.",
            "No OWL reasoner, model construction, AppWorld task, or feedback judge was run.",
            "These cases do not prove correctness for all inputs or domain questions.",
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
