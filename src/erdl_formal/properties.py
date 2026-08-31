"""Property verification (M3): satisfiability + counterexample.

Properties (plan §2): never-errors, always-allows, always-denies, subsumption,
equivalence, disjointness + ERDL-specific override-soundness / ring-respect /
emergency-shortcut. The POC subset provides the canonical satisfiability check
`can_fire`, from which the first properties are derived.
"""

from z3 import Solver, sat

from .compiler import CompileContext, compile_expr
from .tvl import is_missing_int, val_bool


def can_fire(rule_expr, schema, premises=(), missing=()):
    """Can the rule's `when` condition evaluate to true?

    - `premises`: field paths assumed present (schema premise, E11 collapse off).
    - `missing`: field paths forced Missing (to probe fail-open).

    Returns True iff the condition is satisfiable under those constraints.
    """
    ctx = CompileContext(schema)
    cond = compile_expr(rule_expr, ctx)
    s = Solver()
    for p in premises:
        s.add(ctx.premise(p))
    for m in missing:
        s.add(is_missing_int(ctx.field(m)))
    s.add(val_bool(cond))
    return s.check() == sat


def always_denies(rule_expr, schema, premises, missing_field):
    """ERDL 'always-denies' property (fail-closed check).

    A DENY rule must block whenever its guard is satisfiable, but must ALSO
    fail-closed: a missing guard field must NOT open a bypass.

    Returns True iff:
    - the rule can fire under the premises (reachable), AND
    - forcing `missing_field` Missing makes it NEVER fire (collapse → fail-closed).
    """
    reachable = can_fire(rule_expr, schema, premises=premises)
    closed = not can_fire(rule_expr, schema, premises=premises, missing=[missing_field])
    return reachable and closed
