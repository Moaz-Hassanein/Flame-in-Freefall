"""Field catalog exposing names, types, units, and allowed values.

Provides metadata and data-driven constraints for each field in the trusted
dataset snapshot, intended for consumption by the LLM planner and frontend UI.
"""

from __future__ import annotations

from typing import Any

import duckdb
from pydantic import BaseModel, ConfigDict, Field

from flame.schemas.experiment import (
    CANONICAL_COLUMNS,
    ENRICHMENT_COLUMNS,
    DatasetRecord,
)

CATEGORICAL_COLUMNS: frozenset[str] = frozenset(
    {
        "dataset_family",
        "investigation_id",
        "material_category",
        "gravity_condition",
        "extinction_outcome",
        "fuel_material",
        "flow_direction",
        "record_source",
        "pi_name",
    }
)

NUMERIC_COLUMNS: frozenset[str] = frozenset(
    {
        "oxygen_pct",
        "pressure_mmhg",
        "pressure_kpa",
        "burn_time_s",
        "extinction_diameter_mm",
        "initial_diameter_mm",
        "burning_rate_mms",
        "airflow_velocity_cms",
        "flame_temp_k",
        "ignition_power_w",
        "ignition_time_s",
        "co2_pct",
        "he_pct",
        "co_ppm",
        "airflow_velocity_cms_raw",
        "specimen_length_cm",
        "specimen_width_cm",
        "specimen_thickness_cm",
        "microgravity_duration_s",
        "source_row",
    }
)


class FieldInfo(BaseModel):
    """Metadata and bounds for a single dataset column."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(description="Column name.")
    data_type: str = Field(
        description="Logical data type (string, float, int, boolean, date, list[str])."
    )
    unit: str | None = Field(default=None, description="Physical unit of measurement.")
    description: str | None = Field(default=None, description="Field documentation.")
    caveat: str | None = Field(default=None, description="Documented limitations or caveats.")
    is_canonical: bool = Field(description="True if one of the 28 original canonical columns.")
    is_enrichment: bool = Field(description="True if an enrichment or provenance column.")
    is_numeric: bool = Field(description="True if numeric (float or integer).")
    is_categorical: bool = Field(description="True if categorical string with bounded domain.")
    allowed_values: list[Any] | None = Field(
        default=None, description="Observed distinct non-null values for categorical columns."
    )
    min_value: float | int | None = Field(
        default=None, description="Minimum observed non-null value for numeric columns."
    )
    max_value: float | int | None = Field(
        default=None, description="Maximum observed non-null value for numeric columns."
    )
    null_count: int = Field(default=0, description="Total null count in the snapshot.")


class FieldCatalog(BaseModel):
    """Catalog of all fields in the trusted experiment snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fields: dict[str, FieldInfo] = Field(description="Map of field name to FieldInfo.")

    def get_field(self, name: str) -> FieldInfo | None:
        """Look up metadata for a field by name."""
        return self.fields.get(name)

    @property
    def field_names(self) -> list[str]:
        """List of all field names in alphabetical order."""
        return sorted(self.fields.keys())

    @property
    def categorical_fields(self) -> list[str]:
        """List of categorical field names."""
        return sorted([name for name, f in self.fields.items() if f.is_categorical])

    @property
    def numeric_fields(self) -> list[str]:
        """List of numeric field names."""
        return sorted([name for name, f in self.fields.items() if f.is_numeric])

    def to_summary_dict(self) -> dict[str, Any]:
        """Serialize catalog to a dictionary suitable for LLM context or UI."""
        return {
            name: {
                "type": f.data_type,
                "unit": f.unit,
                "description": f.description,
                "caveat": f.caveat,
                "allowed_values": f.allowed_values,
                "min": f.min_value,
                "max": f.max_value,
                "null_count": f.null_count,
            }
            for name, f in self.fields.items()
        }


def build_field_catalog(
    cur: duckdb.DuckDBPyConnection,
    *,
    table_name: str = "experiments",
) -> FieldCatalog:
    """Build a FieldCatalog by inspecting schema metadata and querying DuckDB."""
    fields_dict: dict[str, FieldInfo] = {}

    all_col_names = CANONICAL_COLUMNS + ENRICHMENT_COLUMNS
    schema_fields = DatasetRecord.model_fields

    for col in all_col_names:
        pydantic_field = schema_fields.get(col)
        description: str | None = None
        unit: str | None = None
        caveat: str | None = None

        if pydantic_field is not None:
            description = pydantic_field.description
            if pydantic_field.json_schema_extra and isinstance(
                pydantic_field.json_schema_extra, dict
            ):
                extra = pydantic_field.json_schema_extra
                unit_val = extra.get("unit")
                caveat_val = extra.get("caveat")
                unit = str(unit_val) if unit_val is not None else None
                caveat = str(caveat_val) if caveat_val is not None else None

        is_canonical = col in CANONICAL_COLUMNS
        is_enrichment = col in ENRICHMENT_COLUMNS
        is_num = col in NUMERIC_COLUMNS
        is_cat = col in CATEGORICAL_COLUMNS

        # Logical type determination
        if col == "is_modeled":
            data_type = "boolean"
        elif col == "data_quality_flags":
            data_type = "list[str]"
        elif col == "test_date":
            data_type = "date"
        elif col in ("source_row",):
            data_type = "integer"
        elif is_num:
            data_type = "float"
        else:
            data_type = "string"

        # Query stats from DuckDB
        allowed_vals: list[Any] | None = None
        min_val: float | int | None = None
        max_val: float | int | None = None
        null_count = 0

        if is_cat:
            # Query distinct non-null values
            res = cur.execute(
                f"SELECT DISTINCT {col} FROM {table_name} WHERE {col} IS NOT NULL ORDER BY {col}"
            ).fetchall()
            allowed_vals = [row[0] for row in res]
            null_res = cur.execute(
                f"SELECT COUNT(*) FROM {table_name} WHERE {col} IS NULL"
            ).fetchone()
            if null_res is not None:
                null_count = int(null_res[0])
        elif is_num:
            stats = cur.execute(
                f"SELECT MIN({col}), MAX({col}), COUNT(*) - COUNT({col}) FROM {table_name}"
            ).fetchone()
            if stats is not None:
                min_val = float(stats[0]) if stats[0] is not None else None
                max_val = float(stats[1]) if stats[1] is not None else None
                null_count = int(stats[2])
        else:
            null_res = cur.execute(
                f"SELECT COUNT(*) FROM {table_name} WHERE {col} IS NULL"
            ).fetchone()
            if null_res is not None:
                null_count = int(null_res[0])

        fields_dict[col] = FieldInfo(
            name=col,
            data_type=data_type,
            unit=unit,
            description=description,
            caveat=caveat,
            is_canonical=is_canonical,
            is_enrichment=is_enrichment,
            is_numeric=is_num,
            is_categorical=is_cat,
            allowed_values=allowed_vals,
            min_value=min_val,
            max_value=max_val,
            null_count=null_count,
        )

    return FieldCatalog(fields=fields_dict)


__all__ = [
    "CATEGORICAL_COLUMNS",
    "NUMERIC_COLUMNS",
    "FieldCatalog",
    "FieldInfo",
    "build_field_catalog",
]
