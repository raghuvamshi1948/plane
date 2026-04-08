"""Prodoc materialization engine (Extension 3).

`build_plan` constructs a pure-data `Plan` of `PlannedWorkItem`s and
`PlannedRelation`s from a template + project + sites + waves. `materialize`
consumes a `Plan` and either writes it to the database (wet run, wrapped
in `cascade_suppressed()` by the caller) or returns it unchanged
(dry run).

Separating the planner from the executor lets both the Celery task and
the management command reuse the exact same expansion logic, and makes
the dry-run endpoint a one-liner that never opens a write transaction.
"""

from plane.prodoc.materialization.plan import (
    MaterializationValidationError,
    Plan,
    PlannedRelation,
    PlannedWorkItem,
    build_plan,
)

__all__ = [
    "MaterializationValidationError",
    "Plan",
    "PlannedRelation",
    "PlannedWorkItem",
    "build_plan",
]
