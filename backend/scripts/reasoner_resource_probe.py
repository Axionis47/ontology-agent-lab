"""Check a maximum-size representative schema beside the running API."""

import asyncio
import json
import os
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen

MEMORY_BYTES = 512 * 1024 * 1024
CGROUP = Path("/sys/fs/cgroup")


def maximum_schema():
    from oak.ontology_verification import (
        MAX_AXIOMS,
        MAX_ENTITIES,
        MAX_PROPERTIES,
        MAX_RELATIONS,
    )

    entities = []
    for index in range(MAX_ENTITIES):
        count = MAX_PROPERTIES // MAX_ENTITIES + (index < MAX_PROPERTIES % MAX_ENTITIES)
        entities.append(
            {
                "id": f"entity_{index}",
                "name": f"Entity {index}",
                "properties": [
                    {
                        "name": f"property_{field}",
                        "type": ("string", "integer", "boolean")[field % 3],
                    }
                    for field in range(count)
                ],
                "identity_keys": ["property_0"],
                "requirement_ids": ["resource_check"],
            }
        )
    relations = [
        {
            "id": f"relation_{index}",
            "name": f"Relation {index}",
            "from_entity": f"entity_{index % MAX_ENTITIES}",
            "to_entity": f"entity_{(index + 1) % MAX_ENTITIES}",
            "from_property": "property_0",
            "to_property": "property_0",
            "requirement_ids": ["resource_check"],
            "binding_ids": [],
        }
        for index in range(MAX_RELATIONS)
    ]
    axioms = [
        {
            "id": f"axiom_{index}",
            "kind": "functional" if index % 2 == 0 else "inverse_functional",
            "relation_id": f"relation_{(index // 2) % MAX_RELATIONS}",
            "requirement_ids": ["resource_check"],
        }
        for index in range(MAX_AXIOMS)
    ]
    return {
        "schema": {"entities": entities, "relations": relations},
        "formal_axioms": axioms,
        "requirements": {"requirements": [{"id": "resource_check"}]},
    }


def resource_limits():
    memory = int((CGROUP / "memory.max").read_text().strip())
    quota, period = (CGROUP / "cpu.max").read_text().split()
    cpu = int(quota) / int(period)
    if memory != MEMORY_BYTES or abs(cpu - 0.1) > 0.0001:
        raise ValueError("Run this probe with 512 MB of memory and 0.1 CPU.")
    return {"memory_limit_bytes": memory, "cpu_limit": cpu}


def traffic(stop, stats):
    headers = {"X-Oak-Key": os.environ["OAK_API_KEY"], "X-Oak-User": "demo-alex"}
    paths = ("/health", "/api/tasks")
    while not stop.is_set():
        started = time.monotonic()
        path = paths[stats["requests"] % len(paths)]
        try:
            request = Request("http://127.0.0.1:8000" + path, headers=headers)
            with urlopen(request, timeout=5) as response:
                json.load(response)
            stats["succeeded"] += 1
        except Exception:
            stats["failed"] += 1
        stats["requests"] += 1
        stats["max_latency_ms"] = max(
            stats["max_latency_ms"], round((time.monotonic() - started) * 1000, 1)
        )
        stop.wait(0.1)


async def probe():
    from oak.ontology_verification import verify_candidate

    limits = resource_limits()
    candidate = maximum_schema()
    stats = {"requests": 0, "succeeded": 0, "failed": 0, "max_latency_ms": 0}
    stop = threading.Event()
    worker = threading.Thread(target=traffic, args=(stop, stats), daemon=True)
    worker.start()
    started = time.monotonic()
    try:
        verification = await verify_candidate(candidate, timeout=30, heap_mb=128)
    finally:
        stop.set()
        worker.join(timeout=6)
    passed = (
        verification.get("status") == "passed"
        and stats["succeeded"] >= 2
        and stats["failed"] == 0
        and not worker.is_alive()
    )
    peak = int((CGROUP / "memory.peak").read_text().strip())
    return {
        "status": "passed" if passed else "unsupported_resource_envelope",
        **limits,
        "peak_container_memory_bytes": peak,
        "duration_seconds": round(time.monotonic() - started, 3),
        "heap_mb": 128,
        "api_traffic": stats,
        "schema_size": {
            "entities": len(candidate["schema"]["entities"]),
            "properties": sum(
                len(entity["properties"]) for entity in candidate["schema"]["entities"]
            ),
            "relations": len(candidate["schema"]["relations"]),
            "axioms": len(candidate["formal_axioms"]),
        },
        "verification": {
            key: verification.get(key)
            for key in ("status", "schema_digest", "versions", "errors", "unsatisfiable_classes")
        },
    }


if __name__ == "__main__":
    try:
        result = asyncio.run(probe())
    except Exception as error:
        result = {
            "status": "unsupported_resource_envelope",
            "error": f"The resource probe failed ({type(error).__name__}).",
        }
    print(json.dumps(result))
