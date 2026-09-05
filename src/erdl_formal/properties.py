# Copyright 2026 Shenzhen Miaojing Technology Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Property verification: satisfiability + counterexample.

Properties: never-errors, always-allows, always-denies, subsumption,
equivalence, disjointness + ERDL-specific override-soundness / ring-respect /
emergency-shortcut. The supported subset provides the canonical satisfiability
check `can_fire`, from which the first properties are derived.
"""

from z3 import Not, Solver, sat

from .compiler import CompileContext, compile_expr
from .tvl import val_bool


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
        s.add(ctx.missing(m))
    s.add(val_bool(cond))
    return s.check() == sat


def always_denies(rule_expr, schema, premises=(), missing_field=None, *, default_decision="ALLOW"):
    """ERDL 'always-denies' property (reachability + fail-closed check).

    A DENY rule blocks **when its guard fires**. A guard that does not fire does
    NOT block — the action falls through to the document's unmatched-fallback
    decision (`default_decision`, see `resolution.resolve`: ``ALLOW`` when no
    rule matches).

    ``missing_field`` probes fail-closedness: a missing guard field must not
    open a bypass. Whether it does depends on the fallback:

    - ``default_decision="DENY"`` → a silenced guard still denies → closed.
    - ``default_decision="ALLOW"`` → a silenced guard falls through to ALLOW →
      the rule FAILS OPEN (property is False).

    If ``missing_field`` is also in ``premises``, it is forced Missing for the
    probe (the premise is dropped for that field) — otherwise ``premise ∧
    missing`` would be contradictory and falsely report fail-open even for a
    rule that never references the field.

    Returns True iff:
    - the rule can fire under the premises (reachable), AND
    - (no ``missing_field`` given) OR
    - (``missing_field`` given): the guard still fires with the field Missing
      **or** the fallback decision is DENY (so a silenced guard cannot bypass).
    """
    reachable = can_fire(rule_expr, schema, premises=premises)
    if missing_field is None:
        return reachable
    still_fires = can_fire(
        rule_expr, schema,
        premises=[p for p in premises if p != missing_field],
        missing=[missing_field],
    )
    closed = (default_decision == "DENY") or still_fires
    return reachable and closed


def subsumes(a_expr, b_expr, schema):
    """Cedar 'subsumption': a ⇒ b (a's condition is stricter than b's).

    True iff ``a ∧ ¬b`` is unsatisfiable.
    """
    ctx = CompileContext(schema)
    a = compile_expr(a_expr, ctx)
    b = compile_expr(b_expr, ctx)
    s = Solver()
    s.add(val_bool(a), Not(val_bool(b)))
    return s.check() != sat


def equivalent(a_expr, b_expr, schema):
    """Cedar 'equivalence': a ⇔ b."""
    return subsumes(a_expr, b_expr, schema) and subsumes(b_expr, a_expr, schema)


def disjoint(a_expr, b_expr, schema):
    """Cedar 'disjointness': a ∧ b is unsatisfiable (mutually exclusive)."""
    ctx = CompileContext(schema)
    a = compile_expr(a_expr, ctx)
    b = compile_expr(b_expr, ctx)
    s = Solver()
    s.add(val_bool(a), val_bool(b))
    return s.check() != sat
