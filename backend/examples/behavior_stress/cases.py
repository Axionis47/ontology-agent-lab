"""Keep construction inputs separate from the four new queries."""

from datetime import date, timedelta

BOOK_TOOLS = ["book_search", "book_record", "book_editions", "author_works"]
FOOD_TOOLS = ["food_search", "food_product"]
ALL_TOOLS = ["weather_forecast", *FOOD_TOOLS, *BOOK_TOOLS]

SCOPE = {
    "responsibilities": "Research weather, packaged food products, and books from granted public "
    "sources.",
    "context_and_rules": (
        "Use actual source records. Preserve identifiers, dates, units, and missing values. "
        "Follow edition, work, and author links. Inspect publisher, language, and subject links. "
        "Compare food nutrient values per 100 g. A minimum fibre condition is inclusive. "
        "For a lowest-sugar request, compare numeric sugars_100g and resolve "
        "ties by ascending barcode. "
        "Separate products with missing required nutrients. Limit every "
        "conclusion to retrieved records. "
        "Use supplied coordinates and ISO dates for weather. Report forecast "
        "values, not guarantees. "
        "A broad request can require all three sources. State missing evidence "
        "and partial coverage. "
        "Source publisher and subject labels are exact labels. Do not merge "
        "different labels by guess. "
        "Each link row is a direct projection of a source field, not a generated "
        "ontology relation. "
        "Read-only source responses are cached within an episode group and "
        "retain their fetch times. "
        "No accounts or credentials are required for these public reads. "
        "Discovery can probe Boston (42.3601, -71.0589), food category en:canned-beans, "
        "and book title The Hobbit by J. R. R. Tolkien. Inspect operations only "
        "as needed for these responsibilities."
    ),
    "boundaries": (
        "Read only through the granted MCP operations. Do not write to the source services. "
        "Do not claim store availability, food safety, or complete catalogue coverage. "
        "Do not create missing records or replace source errors with invented data. "
        "Stop within the supplied cost, call, and time limits."
    ),
    "success_criteria": (
        "Answer each requested part with observed facts and source identifiers or URLs. "
        "Distinguish source records from connected records. Explain unavailable "
        "or incomplete evidence."
    ),
    "examples": [],
}


def weekend(anchor: date):
    days = (5 - anchor.weekday()) % 7
    saturday = anchor + timedelta(days=days or 7)
    return saturday.isoformat(), (saturday + timedelta(days=1)).isoformat()


def cases(anchor: date):
    saturday, sunday = weekend(anchor)

    def outing(city, latitude, longitude):
        return (
            f"Prepare a {city} picnic brief for {saturday} and {sunday}, in America/New_York. "
            f"Use latitude {latitude} and longitude {longitude}. Compare the daily weather. "
            "Find three packaged snack products in category en:snacks and include "
            "their reported nutrition per 100 g. "
            "Find three picnic or cooking books. Include source identifiers or URLs for each part. "
            "Do not infer missing nutrition or local product availability."
        )

    training = [
        {
            "name": "book_chain",
            "query": "Find The Hobbit by J. R. R. Tolkien. Read its work record, inspect one "
            "edition, read the author record, and find two other works by that "
            "author. Include identifiers for the connections.",
            "tools": BOOK_TOOLS,
            "task_success": "The answer identifies the requested work, an edition, its author, and "
            "two other works with observed source links. It states any source "
            "limitation.",
        },
        {
            "name": "outing",
            "query": outing("New York", "40.7128", "-74.0060"),
            "tools": ALL_TOOLS,
            "task_success": "The brief includes the requested dated weather, three observed food "
            "products with available nutrition, and three relevant books. Missing "
            "values and partial results remain explicit.",
        },
        {
            "name": "products",
            "query": "Inspect the first ten products from category en:canned-beans. Find the "
            "lowest-sugar product with at least 6 g of fibre per 100 g. Compare "
            "sugars_100g numerically and resolve ties by ascending barcode. List "
            "product barcodes with missing required nutrients separately. Use only "
            "this returned page.",
            "tools": FOOD_TOOLS,
            "task_success": "The answer applies the fibre condition and sugar comparison to the "
            "returned products. It gives the selected barcode, or explains why no "
            "selection is established. It identifies products with missing required "
            "nutrients.",
        },
        {
            "name": "book_relations",
            "query": "Find Pride and Prejudice and Emma by Jane Austen. Inspect up to two "
            "editions per work. Show work, author, edition, publisher, language, and "
            "subject connections. Identify any shared publisher or language labels "
            "within these results. Keep exact source labels and identifiers.",
            "tools": BOOK_TOOLS,
            "task_success": "The answer preserves the two works and their observed connections. "
            "Shared labels have source support. Missing links and partial edition "
            "coverage remain explicit.",
        },
    ]
    new = [
        {
            "name": "deep",
            "query": "Start with ISBN 9780441478125, The Left Hand of Darkness. Find its "
            "edition, parent work, author, and three other works by that author. "
            "Include source identifiers for each connection. Keep editions and works "
            "distinct. State missing links or source failures.",
            "tools": BOOK_TOOLS,
        },
        {"name": "wide", "query": outing("Boston", "42.3601", "-71.0589"), "tools": ALL_TOOLS},
        {
            "name": "many_entities",
            "query": "Inspect the first 100 breakfast-cereal products returned by Open Food "
            "Facts, using category en:breakfast-cereals and the first page. Find the "
            "lowest-sugar product with at least 6 g of fibre per 100 g. Compare "
            "sugars_100g numerically. Resolve ties by ascending barcode. Report "
            "products with missing required values separately, by barcode. Report "
            "how many records were returned. Limit the conclusion to those records.",
            "tools": FOOD_TOOLS,
        },
        {
            "name": "many_relationships",
            "query": "Find Frankenstein by Mary Shelley, Dracula by Bram Stoker, and The Time "
            "Machine by H. G. Wells. Inspect the first page of up to 20 editions per "
            "work. Show connections between works, authors, editions, publishers, "
            "languages, and subjects. Identify publishers and languages shared "
            "across works within these results. Use exact source labels and "
            "identifiers. Report missing connections and partial coverage.",
            "tools": BOOK_TOOLS,
        },
    ]
    return {
        "anchor_date": anchor.isoformat(),
        "timezone": "America/New_York",
        "saturday": saturday,
        "sunday": sunday,
        "training": training,
        "comparisons": new,
    }
