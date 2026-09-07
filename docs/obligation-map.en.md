# §7.1 Obligation → Property Map

> Maintainer: OpenOBA · Generated 2026-09-07 · Scope: `src/erdl_formal/resolution.py` (reference) + `resolution_smt.py` (Z3 proofs)

This file maps every normative obligation in ERDL SPEC §7.1 (Precedence and
Conflict Resolution) and §7.0.2 (Evaluation Algorithm) to the property that
proves or anchors it. It is the mechanical "obligation list" ANP2 Network
asked for: an obligation with no mapped property shows up here as a **gap**
*before* a reviewer has to name it.

## Mapping

| SPEC obligation | Property (erdl-formal) | Kind | Status |
|---|---|---|---|
| §7.1.1 — sort by `priority` ascending | `sorted_premise()` + differential grid | input contract (sorting) | ✅ anchored |
| §7.1.2 — among equal priority, `override` marker goes first | `sorted_premise()` + differential grid | input contract (sorting) | ✅ anchored |
| §7.1.3 — `override` enumeration `critical` > `high` > `normal` > `low` | `override_rank()` + differential grid | input contract (sorting) | ✅ anchored |
| §7.1.4 — equal priority + equal override → definition order | `sorted_premise()` (array order) | input contract (sorting) | ✅ anchored |
| §7.1.5a — `override` only DENY→ALLOW (never to a less-safe state) | `override_soundness` | safety (must-not) | ✅ proved |
| §7.1.5b — `critical`/`high` works across rings: higher-ring override ALLOW covers lower-ring DENY | *none* | capability (reachability) | ⚠️ gap — see below |
| §7.1.6 — catch-all MUST NOT rewrite an explicit-condition decision | `catch_all_inert_when_explicit` | safety (must-not) | ✅ proved + mutation-tested |
| §7.1.6a (quantifier 1) — catch-all's `then` irrelevant to the final decision | `catch_all_then_irrelevant_when_explicit` | safety, over the decision observable | ✅ proved + mutation-tested |
| §7.1.6b (quantifier 2) — catch-all's `override` irrelevant to the final decision | `catch_all_override_irrelevant_when_explicit` | safety, over the decision observable | ✅ proved + mutation-tested |
| §7.0.2 — ring order 0→3 | `ring_respect` | safety (DENY direction) | ✅ proved |
| §7.0.2 — EMERGENCY_HALT short-circuits on hit | `emergency_shortcut` | safety (terminal) | ✅ proved |
| §7.0.2 — WORKFLOW short-circuits into its state machine | `workflow_shortcut` | safety (terminal) | ✅ proved |

## Notes on kind

- **input contract (sorting)** — the sorting rules decide the *processing
  order*, not a post-condition to prove. `sorted_premise()` encodes them as
  the fold's input contract, and the exhaustive differential grid
  (`test_reformulation_matches_reference_exhaustive`) anchors that encoding
  against the hand-written `resolution.resolve`. These are mechanical rules
  whose mis-reading is caught at the "obviously wrong" level; they do not
  carry the subtle cross-rule semantic that §7.1.6 does.
- **safety (must-not)** — a negative obligation ("MUST NOT …"); proved as
  UNSAT over the bad term.
- **capability (reachability)** — a positive obligation ("may …"); proved by
  showing the state is reachable (non-vacuity), not by UNSAT.

## Gaps

### ⚠️ §7.1.5b — higher-ring override ALLOW covers lower-ring DENY

`override_soundness` proves only the *negative* half of §7.1.5 (a same-ring
override DENY never tightens ALLOW). It does **not** prove the *positive* half:
that a `critical`/`high` override ALLOW genuinely covers a lower-ring
DENY/ROLLBACK/QUARANTINE **without comparing ring**. In the fold this is the
`allow_relax` branch (`dec == ALLOW & enables & has & is_restrictive(fin)`).

This is a **capability**, so it should be closed with a non-vacuity proof that
the cross-ring relax is reachable — not a new UNSAT property. Tracked as a
follow-up; not a correctness defect (the capability is exercised by the
differential grid).

### Sorting rules (§7.1.1–4) have no independent UNSAT property

The sorting rules are modeled as the fold's input contract rather than as
proved post-conditions. They are anchored by the exhaustive differential grid
against the hand-written reference. If the reference and the fold shared the
same mis-reading of a sorting rule, neither the grid nor any property would
catch it. In practice these rules are mechanical (numeric ascending / fixed
enum order / stable definition order) and their mis-reading is not the kind of
subtle cross-rule bug §7.1.6 was; the *independence* gap is real but bounded,
and the true independent anchor for §7.1 remains a third-party runner (see
`erdl-vectors`).

## How this map is produced (mechanical extraction)

This table is not a curated summary — it is a **sentence-by-sentence
projection** of SPEC §7.1 / §7.0.2 onto the property list (ANP2 Network:
"the sentence-by-sentence extraction stays trusted input, not the goal").
Concretely:

1. Each *normative* clause of §7.1 (§7.1.1–6) and each short-circuit clause of
   §7.0.2 becomes one row.
2. A clause carrying several conjuncts or quantifiers is **split** — one row
   per quantifier/conjunct (§7.1.5 → 5a negative / 5b positive; §7.1.6 → 6a
   `then` / 6b `override`). Splitting is what surfaced 6b as a previously
   unmapped obligation.
3. A row is **closed** iff there is a named property whose docstring quotes
   that obligation and whose test asserts it (proved + mutation-tested). A row
   with no such property is a **gap**, listed under "Gaps" above.

The extraction itself is trusted input (a human reads the SPEC); the *goal* is
the resulting coverage bound — every obligation is either closed or visibly a
gap, so a reviewer never has to discover an unmapped obligation by hand.
