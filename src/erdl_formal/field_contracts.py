"""Field contracts — the verification schema (v2.1 candidate).

Spec v2.0 has ``EntityFieldContract`` (field/display_name/type/description)
for **rule production**, but no *verification* schema (no cardinality bound).
This module is the **verification schema** (schema-as-assumption): field type +
cardinality + optionality, which grounds quantifier/aggregate index expansion
(see `docs/schema-assumption.md` + `docs/plan.md` §9).
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FieldContract:
    field: str
    type: str  # 'int' | 'rational' | 'string' | 'bool' | 'array'
    element_type: str | None = None  # for 'array': element type
    cardinality: int | None = None  # for 'array': max length (schema premise)
    optional: bool = True  # field may be missing (E11)


@dataclass
class Schema:
    contracts: dict[str, FieldContract] = field(default_factory=dict)

    def add(self, c: FieldContract) -> None:
        self.contracts[c.field] = c

    def get(self, field: str) -> FieldContract | None:
        return self.contracts.get(field)

    def requires(self, field: str) -> FieldContract:
        c = self.contracts.get(field)
        if c is None:
            raise KeyError(f"no contract for field {field!r}")
        return c

    def cardinality(self, field: str) -> int:
        """The concrete array cardinality for a contracted array field.

        Raises if the field is not an array or has no cardinality — the schema
        premise that grounds quantifier index expansion.
        """
        c = self.requires(field)
        if c.type != "array":
            raise TypeError(f"field {field!r} is {c.type!r}, not 'array'")
        if c.cardinality is None:
            raise ValueError(f"array field {field!r} has no cardinality bound")
        return c.cardinality
