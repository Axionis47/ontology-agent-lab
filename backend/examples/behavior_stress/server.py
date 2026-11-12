"""Read-only MCP operations for weather, food products, and books."""

import re
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Literal

from fastapi import FastAPI
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from .sources import book_rows, decimal_text, products

FOOD_FIELDS = "code,product_name,brands,categories_tags,countries_tags,nutriments"
READ = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
)


def build_server(sources):
    server = MCPServer("Oak public research sources")

    @server.tool(annotations=READ)
    async def weather_forecast(
        latitude: Annotated[float, Field(ge=-90, le=90)],
        longitude: Annotated[float, Field(ge=-180, le=180)],
        start_date: str,
        end_date: str,
        timezone: str = "America/New_York",
    ) -> dict:
        """Read daily Open-Meteo forecasts for supplied coordinates and ISO dates. No geocoding.
        Returns date rows and source units. Numeric measurements are decimal strings.
        Complete only for the returned interval."""
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
        if not 0 <= (end - start).days <= 15:
            raise ToolError("Supply an interval of at most 16 days.")
        data, metadata = await sources.get(
            "https://api.open-meteo.com/v1/forecast",
            {
                "latitude": latitude,
                "longitude": longitude,
                "start_date": start_date,
                "end_date": end_date,
                "timezone": timezone,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_pr"
                "obability_max,wind_speed_10m_max",
            },
        )
        daily = data.get("daily", {})
        rows = []
        for index, day in enumerate(daily.get("time", [])):
            row = {
                "date": day,
                "latitude": str(data["latitude"]),
                "longitude": str(data["longitude"]),
                "timezone": data.get("timezone"),
            }
            for field, values in daily.items():
                if field != "time" and index < len(values):
                    row[field] = decimal_text(values[index])
            rows.append(row)
        return {
            "metadata": metadata,
            "days": rows,
            "units": data.get("daily_units", {}),
            "interval_complete": len(rows) == (end - start).days + 1,
        }

    @server.tool(annotations=READ)
    async def food_search(
        category: str,
        page: Annotated[int, Field(ge=1)] = 1,
        page_size: Annotated[int, Field(ge=1, le=100)] = 10,
    ) -> dict:
        """Read Open Food Facts products in an exact category tag, such as en:breakfast-cereals,
        en:canned-beans, or en:snacks. Preserve provider order. Nutrient values are
        decimal strings in g/100g, except energy_kcal_100g in kcal/100g. Missing
        fields are unknown. Completeness is limited to this page, not the catalogue."""
        data, metadata = await sources.get(
            "https://world.openfoodfacts.org/api/v2/search",
            {
                "categories_tags": category,
                "page": page,
                "page_size": page_size,
                "fields": FOOD_FIELDS,
            },
        )
        rows = products(data.get("products", []))
        return {
            "metadata": metadata,
            "products": rows,
            "page": data.get("page"),
            "page_size": data.get("page_size"),
            "total": data.get("count"),
            "returned": len(rows),
            "coverage": "requested page only",
        }

    @server.tool(annotations=READ)
    async def food_product(barcode: str) -> dict:
        """Read one Open Food Facts product by its exact barcode. Use the same nutrient units
        and missing-field rules as food_search. A missing product returns no records."""
        if not re.fullmatch(r"[0-9]{4,30}", barcode):
            raise ToolError("Supply a numeric product barcode.")
        data, metadata = await sources.get(
            f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json",
            {"fields": FOOD_FIELDS},
        )
        return {
            "metadata": metadata,
            "products": products([data["product"]])
            if isinstance(data.get("product"), dict)
            else [],
            "source_status": data.get("status"),
            "source_status_verbose": data.get("status_verbose"),
        }

    @server.tool(annotations=READ)
    async def book_search(query: str, limit: Annotated[int, Field(ge=1, le=20)] = 5) -> dict:
        """Search Open Library works. The query can include title: or author: clauses. Returns
        work records and their explicit author and subject links. Search results are
        partial. Resolve exact identities with book_record. Link targets for
        publishers and subjects are source labels, not global identifiers."""
        data, metadata = await sources.get(
            "https://openlibrary.org/search.json",
            {
                "q": query,
                "limit": limit,
                "fields": "key,title,author_key,first_publish_year,subject",
            },
        )
        return {
            "metadata": metadata,
            **book_rows(data.get("docs", [])),
            "total": data.get("numFound", data.get("num_found")),
            "coverage": "search subset",
        }

    @server.tool(annotations=READ)
    async def book_record(
        kind: Literal["isbn", "edition", "work", "author"], identifier: str
    ) -> dict:
        """Read one Open Library record. An ISBN resolves to an edition. Editions can link to
        works and authors. Works link to authors and subjects. An author record has
        its source key and name. Supply a bare identifier or the exact source key.
        records retain source keys; links retain record_key, source field, and
        target. Missing links are not inferred."""
        singular = {"edition": "books", "work": "works", "author": "authors", "isbn": "isbn"}[kind]
        value = identifier.removeprefix(f"/{singular}/")
        pattern = (
            r"[0-9Xx-]{10,17}"
            if kind == "isbn"
            else {"edition": r"OL[0-9]+M", "work": r"OL[0-9]+W", "author": r"OL[0-9]+A"}[kind]
        )
        if not re.fullmatch(pattern, value):
            raise ToolError("The identifier does not match the requested record type.")
        data, metadata = await sources.get(f"https://openlibrary.org/{singular}/{value}.json")
        return {"metadata": metadata, **book_rows([data]), "coverage": "one source record"}

    @server.tool(annotations=READ)
    async def book_editions(
        work_id: str,
        limit: Annotated[int, Field(ge=1, le=20)] = 5,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> dict:
        """Read a page of editions for an Open Library work. collection_work_key records the
        requested parent work. Publisher and language links preserve source labels
        and keys. The page does not establish facts about unreturned editions."""
        identifier = work_id.removeprefix("/works/")
        if not re.fullmatch(r"OL[0-9]+W", identifier):
            raise ToolError("Supply an Open Library work identifier.")
        data, metadata = await sources.get(
            f"https://openlibrary.org/works/{identifier}/editions.json",
            {"limit": limit, "offset": offset},
        )
        return {
            "metadata": metadata,
            **book_rows(data.get("entries", []), collection_work=f"/works/{identifier}"),
            "total": data.get("size"),
            "offset": offset,
            "limit": limit,
            "pagination": data.get("links", {}),
            "coverage": "requested page only",
        }

    @server.tool(annotations=READ)
    async def author_works(
        author_id: str,
        limit: Annotated[int, Field(ge=1, le=20)] = 5,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> dict:
        """Read a page of works for an Open Library author. Preserve source work keys and author
        links. Returned works are a subset of the author's catalogue."""
        identifier = author_id.removeprefix("/authors/")
        if not re.fullmatch(r"OL[0-9]+A", identifier):
            raise ToolError("Supply an Open Library author identifier.")
        data, metadata = await sources.get(
            f"https://openlibrary.org/authors/{identifier}/works.json",
            {"limit": limit, "offset": offset},
        )
        return {
            "metadata": metadata,
            **book_rows(data.get("entries", [])),
            "total": data.get("size"),
            "offset": offset,
            "limit": limit,
            "pagination": data.get("links", {}),
            "coverage": "requested page only",
        }

    @asynccontextmanager
    async def lifespan(app):
        async with server.session_manager.run():
            yield

    app = FastAPI(lifespan=lifespan)
    app.mount("/public", server.streamable_http_app(json_response=True, stateless_http=True))
    return app
