"""Independent synthetic worlds and outcome checks for the hotel task.

This module uses source records only. It does not use the ontology executor.
Missing links or conflicting identities make the full snapshot incomplete.
"""

import copy
import hashlib
import random

FAMILIES = (
    "ordinary_mixture",
    "age_boundary",
    "capacity_boundary",
    "budget_boundary",
    "shared_policy",
    "changed_relation",
    "distractors",
    "identical_duplicates",
    "missing_link",
    "conflicting_record",
)


def reference(case: dict) -> dict:
    """Calculate the expected outcome without a generated schema or function."""
    request = case["query"]
    collections = (
        case["inventory"]["hotels"],
        case["inventory"]["offers"],
        case["policies"]["policies"],
    )
    indexes = []
    for records in collections:
        index = {}
        for record in records:
            key = record["id"]
            if key in index and index[key] != record:
                return {"status": "incomplete", "eligible": {}, "action": None}
            index[key] = record
        indexes.append(index)
    hotels, offers, policies = indexes
    linked = []
    for offer in offers.values():
        hotel = hotels.get(offer["hotel_id"])
        if hotel is None:
            return {"status": "incomplete", "eligible": {}, "action": None}
        policy = policies.get(hotel["policy_id"])
        if policy is None:
            return {"status": "incomplete", "eligible": {}, "action": None}
        linked.append((offer, hotel, policy))
    eligible = {}
    for offer, hotel, policy in linked:
        total = offer["nightly_cents"] * request["nights"] + offer["fee_cents"]
        if (
            hotel["city"] == request["city"]
            and offer["capacity"] >= request["adults"] + 1
            and policy["minimum_child_age"] <= request["child_age"]
            and total <= request["budget_cents"]
        ):
            eligible[offer["id"]] = total
    return {
        "status": "complete",
        "eligible": dict(sorted(eligible.items())),
        "action": min(eligible, key=lambda key: (eligible[key], key)) if eligible else None,
    }


def public_case(case: dict) -> dict:
    """Return only the request and source records permitted in one episode."""
    return copy.deepcopy({key: case[key] for key in ("name", "query", "inventory", "policies")})


def _world(split: str, seed: int, number: int, family: str) -> dict:
    material = f"oak-hotel-suite-v1:{split}:{seed}:{number}"
    digest = hashlib.sha256(material.encode()).hexdigest()
    rng = random.Random(int(digest, 16))
    prefix = digest[:10]

    def identifier():
        return f"{prefix}_{rng.getrandbits(48):012x}"

    cities = ("Newark", "Boston", "Albany", "Trenton", "Portland", "Salem")
    city = rng.choice(cities)
    other_city = rng.choice([value for value in cities if value != city])
    nights, adults, child_age = rng.randint(1, 9), rng.randint(1, 5), rng.randint(0, 17)
    base, fee = rng.randint(5000, 40000), rng.randint(0, 12000)
    budget = base * nights + fee
    request = {
        "city": city,
        "nights": nights,
        "adults": adults,
        "child_age": child_age,
        "budget_cents": budget,
    }
    policies = [
        {"id": identifier(), "minimum_child_age": rng.randint(0, 18)}
        for _ in range(rng.randint(6, 10))
    ]
    hotels = [
        {
            "id": identifier(),
            "city": rng.choice((city, city, other_city)),
            "policy_id": policy["id"],
        }
        for policy in policies[:-2]
    ]
    offers = [
        {
            "id": identifier(),
            "hotel_id": rng.choice(hotels)["id"],
            "capacity": rng.randint(1, 9),
            "nightly_cents": rng.randint(2000, 55000),
            "fee_cents": rng.randint(0, 15000),
        }
        for _ in range(rng.randint(8, 20))
    ]
    # Give each family a valid witness before its specific changes.
    hotels[0]["city"] = city
    policies[0]["minimum_child_age"] = rng.randint(0, child_age)
    offers[0].update(
        hotel_id=hotels[0]["id"], capacity=adults + 1, nightly_cents=base, fee_cents=fee
    )
    offers[1].update(
        hotel_id=hotels[0]["id"], capacity=adults + 1, nightly_cents=base, fee_cents=fee
    )

    if family == "ordinary_mixture":
        if number // len(FAMILIES) % 3 == 1:
            request["budget_cents"] = 0
    elif family == "age_boundary":
        policies[0]["minimum_child_age"] = child_age
        hotels[1]["city"] = city
        policies[1]["minimum_child_age"] = child_age + 1
        offers[1]["hotel_id"] = hotels[1]["id"]
    elif family == "capacity_boundary":
        offers[1]["capacity"] = adults
    elif family == "budget_boundary":
        offers[1]["fee_cents"] += 1
    elif family == "shared_policy":
        hotels[1].update(city=city, policy_id=policies[0]["id"])
        policies[1]["minimum_child_age"] = 18
        offers[1]["hotel_id"] = hotels[1]["id"]
    elif family == "changed_relation":
        hotels[0]["policy_id"] = policies[1]["id"]
        hotels[1].update(city=city, policy_id=policies[0]["id"])
        policies[1]["minimum_child_age"] = 18
        offers[1]["hotel_id"] = hotels[1]["id"]
    elif family == "distractors":
        hotels[1]["city"] = other_city
        policies[1]["minimum_child_age"] = 0
        offers[1].update(hotel_id=hotels[1]["id"], nightly_cents=1, fee_cents=0)
        policies.append({"id": identifier(), "minimum_child_age": 0})
        hotels.append({"id": identifier(), "city": city, "policy_id": policies[-1]["id"]})
    elif family == "identical_duplicates":
        hotels.append(copy.deepcopy(hotels[0]))
        policies.append(copy.deepcopy(policies[0]))
        offers.append(copy.deepcopy(offers[0]))
    elif family == "missing_link":
        variant = number // len(FAMILIES) % 3
        if variant == 0:
            hotels[0]["policy_id"] = None
        elif variant == 1:
            offers[0]["hotel_id"] = identifier()
        else:
            hotels[0]["policy_id"] = identifier()
    elif family == "conflicting_record":
        variant = number // len(FAMILIES) % 3
        records, field = (
            (offers, "fee_cents"),
            (policies, "minimum_child_age"),
            (hotels, "city"),
        )[variant]
        duplicate = copy.deepcopy(records[0])
        if field == "city":
            duplicate[field] = other_city
        elif field == "minimum_child_age":
            duplicate[field] = (duplicate[field] + 1) % 19
        else:
            duplicate[field] += 1
        records.append(duplicate)
    else:
        raise ValueError(f"Unknown case family: {family}")

    for records in (hotels, offers, policies):
        rng.shuffle(records)
    case = {
        "name": f"{split}-{number:04d}-{prefix}",
        "family": family,
        "query": request,
        "inventory": {"hotels": hotels, "offers": offers},
        "policies": {"policies": policies},
    }
    expected = reference(case)
    case.update(
        expected=expected["eligible"],
        expected_status=expected["status"],
        expected_action=expected["action"],
    )
    return case


def make_suite(split: str, seed: int, count: int) -> list[dict]:
    """Make deterministic worlds with distinct identities for each split and seed."""
    if not split or count < 0:
        raise ValueError("The split must be nonempty and the count must not be negative.")
    return [
        _world(split, seed, number, FAMILIES[number % len(FAMILIES)]) for number in range(count)
    ]


def _answer_matches(proposal: object, expected: dict) -> bool:
    if not isinstance(proposal, dict) or proposal.get("status") != expected["status"]:
        return False
    items = proposal.get("eligible")
    if not isinstance(items, list):
        return False
    actual = {}
    for item in items:
        if not isinstance(item, dict):
            return False
        identifier, total = item.get("offer_id"), item.get("total_cents")
        if not isinstance(identifier, str) or type(total) is not int or identifier in actual:
            return False
        actual[identifier] = total
    return actual == expected["eligible"]


def score_episode(case: dict, episode: dict) -> dict:
    """Score proposals before the guard. Score committed actions separately."""
    expected = reference(case)
    proposals = episode.get("proposals") or []
    first = episode.get("first_proposal", proposals[0] if proposals else None)
    attempts = episode.get("action_proposals") or []
    actions = episode.get("actions") or []
    accepted = episode.get("answer")
    answer_correct = _answer_matches(first, expected)
    action_target = expected["action"]

    def action_matches(action):
        return (
            isinstance(action, dict)
            and action_target is not None
            and action.get("offer_id") == action_target
            and type(action.get("total_cents")) is int
            and action["total_cents"] == expected["eligible"][action_target]
        )

    proposed_action_correct = (
        not attempts if action_target is None else bool(attempts) and action_matches(attempts[0])
    )
    action_correct = (
        not actions
        if action_target is None
        else len(actions) == 1
        and actions[0].get("offer_id") == action_target
        and type(actions[0].get("total_cents")) is int
        and actions[0]["total_cents"] == expected["eligible"][action_target]
    )
    invalid_actions = sum(
        index > 0
        or action_target is None
        or action.get("offer_id") != action_target
        or type(action.get("total_cents")) is not int
        or action.get("total_cents") != expected["eligible"].get(action_target)
        for index, action in enumerate(actions)
    )
    return {
        "case": case["name"],
        "family": case.get("family", "unspecified"),
        "expected_status": expected["status"],
        "answerable": expected["status"] == "complete",
        "has_eligible": bool(expected["eligible"]),
        "first_answer_correct": answer_correct,
        "first_action_correct": proposed_action_correct,
        "exact_task_success": bool(
            answer_correct
            and proposed_action_correct
            and action_correct
            and episode.get("completed")
        ),
        "committed_action_correct": action_correct,
        "invalid_answer_proposals": sum(not _answer_matches(item, expected) for item in proposals),
        "invalid_action_proposals": sum(not action_matches(item) for item in attempts),
        "accepted_invalid_answers": int(
            accepted is not None and not _answer_matches(accepted, expected)
        ),
        "accepted_invalid_actions": invalid_actions,
        "completed": bool(episode.get("completed")),
    }
