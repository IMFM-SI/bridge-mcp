"""The provenance domains of the `math_data` database: which sources — tools and
upstream databases — the facts rest on."""

from bridge_mcp.mathql.database import Column, ForeignKey, Schema
from bridge_mcp.mathql.types import StringType

SOURCE = Schema(
    table="source",
    columns={
        "id": Column("id", StringType(), True, "the source's identifier, e.g. 'geng'"),
        "tool": Column("tool", StringType(), False, "the tool or database"),
        "version": Column(
            "version", StringType(), False, "the version used; undefined when unrecorded"
        ),
        "description": Column("description", StringType(), False, "what the source provides"),
        "retrieved": Column(
            "retrieved",
            StringType(),
            False,
            "when the data was fetched, and any upstream identifier; undefined for pure tools",
        ),
        "attribution": Column(
            "attribution",
            StringType(),
            False,
            "credit and license; undefined when not applicable",
        ),
    },
    foreign_keys={},
    doc="A tool or upstream database that facts in this database rest on.",
)

PROVENANCE = Schema(
    table="provenance",
    columns={
        "domain": Column("domain", StringType(), True, "the domain the facts belong to"),
        "field": Column("field", StringType(), True, "the field within the domain"),
        "source_id": Column("source", StringType(), True, "the source's id"),
        "note": Column("note", StringType(), False, "when or how the source applies"),
    },
    foreign_keys={"source": ForeignKey("Source", (("source", "id"),), "the source")},
    doc=(
        "The sources a field's facts rest on; a single fact may rest on fewer. "
        "A field touched by several tools has several rows."
    ),
)

DOMAINS = {"Source": SOURCE, "Provenance": PROVENANCE}
