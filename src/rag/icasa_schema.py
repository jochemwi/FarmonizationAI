"""Schema for one variable in the harmonisation index (ICASA + target schema)."""
from typing import Literal

from pydantic import BaseModel, field_validator

DataType = Literal["single", "text", "memo", "date", "integer", "double"]


class IcasaVariable(BaseModel):
    # identity 
    id: int | None = None          # ICASA var_uid; None for custom variables
    name: str
    code: str
    description: str

    # type and unit
    unit: str                      # original unit, e.g. kg[N]/ha
    unit_pint: str | None = None   # pint-parseable unit (target schema only, for now)
    data_type: DataType
    min: float | None = None
    max: float | None = None

    # ICASA hierarchy (None for custom variables)
    dataset: str | None = None
    subset: str | None = None
    group: str | None = None
    subgroup: str | None = None

    # from the FieldBigData target schema (None if not in it)
    required: bool | None = None
    file: list[str] | None = None  # output file(s) the variable belongs in
    topic: str | None = None
    example: str | None = None
    comment: str | None = None

    # provenance flags
    in_icasa: bool
    in_target: bool

    # add later (place holder for vector store)
    embedding_text: str | None = None

    @field_validator("file", mode="before")
    @classmethod
    def split_files(cls, v):
        """'a.csv;b.csv' -> ['a.csv', 'b.csv']"""
        if isinstance(v, str):
            return [f.strip() for f in v.split(";") if f.strip()]
        return v