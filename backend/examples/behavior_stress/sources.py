"""Read public sources and retain their original responses."""

import asyncio
import hashlib
import json
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
from mcp.server.mcpserver.exceptions import ToolError

HOSTS = {"api.open-meteo.com", "world.openfoodfacts.org", "openlibrary.org"}


def now():
    return datetime.now(UTC).isoformat()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str))
    temporary.replace(path)


def key(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class Sources:
    def __init__(self, root, *, transport=None, throttle=True):
        self.root = Path(root)
        self.group = "preflight"
        self.throttle = throttle
        self.next_request = {}
        self.lock = asyncio.Lock()
        self.client = httpx.AsyncClient(
            transport=transport,
            timeout=20,
            headers={
                "User-Agent": "OakBehaviorStress/0.1 (local research)",
                "Accept": "application/json",
            },
        )

    def select_group(self, group):
        if not group or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for c in group):
            raise ValueError("Invalid cache group.")
        self.group = group

    async def close(self):
        await self.client.aclose()

    async def get(self, url, params=None):
        request_url = httpx.URL(url, params=params)
        if request_url.scheme != "https" or request_url.host not in HOSTS:
            raise ValueError("This source is outside the test grants.")
        identity = key(str(request_url))
        path = self.root / "sources" / self.group / f"{identity}.json"
        async with self.lock:
            reused = path.exists()
            if reused:
                saved = json.loads(path.read_text())
            else:
                host = request_url.host
                delay = max(0, self.next_request.get(host, 0) - time.monotonic())
                if self.throttle and delay:
                    await asyncio.sleep(delay)
                interval = 6.2 if host == "world.openfoodfacts.org" else 1.1
                self.next_request[host] = time.monotonic() + interval
                try:
                    response = await self.client.get(request_url)
                    # Open Library can redirect an ISBN to its edition record.
                    for _ in range(4):
                        if not response.is_redirect:
                            break
                        target = response.url.join(response.headers["location"])
                        if target.scheme != "https" or target.host not in HOSTS:
                            raise ValueError("The source redirected outside the test grants.")
                        response = await self.client.get(target)
                    saved = {
                        "request_url": str(request_url),
                        "response_url": str(response.url),
                        "fetched_at": now(),
                        "status": response.status_code,
                        "headers": {
                            k: v
                            for k, v in response.headers.items()
                            if k in {"content-type", "etag", "last-modified", "retry-after"}
                        },
                        "body": response.text,
                    }
                    if not response.is_success:
                        save(path.with_name(f"{identity}-error-{time.time_ns()}.json"), saved)
                        response.raise_for_status()
                    json.loads(response.text)
                    save(path, saved)
                except Exception as exc:
                    self.log({"url": str(request_url), "error": str(exc), "cache_hit": False})
                    if isinstance(exc, httpx.HTTPError):
                        status = (
                            exc.response.status_code
                            if isinstance(exc, httpx.HTTPStatusError)
                            else type(exc).__name__
                        )
                        raise ToolError(
                            f"Public source request failed: {status}. URL: {request_url}"
                        ) from exc
                    raise
            metadata = {
                "source_url": saved["request_url"],
                "fetched_at": saved["fetched_at"],
                "response_id": identity,
                "cache_group": self.group,
                "cache_hit": reused,
                "raw_response_file": str(path.relative_to(self.root)),
                "numeric_encoding": "Decimal source numbers use exact decimal strings.",
            }
            self.log(metadata)
            return json.loads(saved["body"], parse_float=Decimal), metadata

    def log(self, value):
        path = self.root / "source-access.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as stream:
            stream.write(
                json.dumps({"observed_at": now(), "group": self.group, **value}, default=str) + "\n"
            )


def decimal_text(value):
    return (
        str(value)
        if isinstance(value, (Decimal, float, int)) and not isinstance(value, bool)
        else value
    )


def products(data):
    """Project source fields. Keep absent fields absent and null fields null."""
    rows = []
    for source in data:
        row = {
            k: source[k]
            for k in ("code", "product_name", "brands", "categories_tags", "countries_tags")
            if k in source
        }
        nutrients = source.get("nutriments")
        if isinstance(nutrients, dict):
            for name in (
                "sugars_100g",
                "fiber_100g",
                "proteins_100g",
                "salt_100g",
                "energy-kcal_100g",
            ):
                if name in nutrients:
                    row[name.replace("-", "_")] = decimal_text(nutrients[name])
        rows.append(row)
    return rows


def book_rows(items, *, collection_work=None):
    """Project records and explicit source links. Do not infer missing links."""
    records, links = [], []
    for source in items:
        record = {
            k: source[k]
            for k in (
                "key",
                "title",
                "name",
                "publish_date",
                "first_publish_year",
                "number_of_pages",
                "isbn_10",
                "isbn_13",
            )
            if k in source
        }
        if collection_work:
            record["collection_work_key"] = collection_work
        records.append(record)
        for field in (
            "authors",
            "author_key",
            "works",
            "publishers",
            "languages",
            "subjects",
            "subject",
        ):
            values = source.get(field)
            if not isinstance(values, list):
                continue
            for index, value in enumerate(values):
                if isinstance(value, dict):
                    value = value.get("key") or value.get("author", {}).get("key")
                if not isinstance(value, str):
                    continue
                if field == "author_key" and not value.startswith("/"):
                    value = "/authors/" + value
                links.append(
                    {
                        "id": key([source.get("key"), field, index, value]),
                        "record_key": source.get("key"),
                        "field": field,
                        "target": value,
                        "source_index": index,
                    }
                )
    return {"records": records, "links": links}
