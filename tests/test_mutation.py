"""Expression-kernel mutation testing.

Proves the expression-layer spec properties are *detected*, not vacuous: for
each deliberately-injected spec violation (a "mutant"), at least one oracle must
flip from pass to fail (KILLED). A surviving mutant is a spec property the
kernel's own tests cannot catch.

Three parts:
  - **oracles** — each returns True iff the kernel matches the spec (E2 fixed
    point / E8 empty-fold / E11 leaf-collapse / §7.2 / §7.3).
  - **mutants** — each injects one spec violation; KILLED iff some oracle flips.
  - **counterexamples** — spec-edge inputs vs the verifier verdict, asserted
    directly against the verifier verdict.

The resolution layer already ships its own mutation testing
(`test_resolution_smt.py`); this file covers the expression kernel.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from z3 import IntVal, simplify, is_true, is_false, If, Or
from fractions import Fraction

import erdl_formal.tvl as tvl
import erdl_formal.quantifiers as quants
import erdl_formal.fixed_point as fp
from erdl_formal.field_contracts import FieldContract, Schema
from erdl_formal.properties import can_fire

SCALE = 10 ** 14

# ---------- helpers ----------

def _b(x):
    return is_true(simplify(tvl.val_bool(x)))

def _bfalse(x):
    return is_false(simplify(tvl.val_bool(x)))

def _missing_int(x):
    return is_true(simplify(tvl.is_missing_int(x)))

def _agg_empty(x):
    return is_true(simplify(tvl.agg_is_empty(x)))


# ============================================================
#  ORACLES — each returns True iff behavior matches the spec.
#  A mutant is KILLED when it makes the oracle return False.
# ============================================================

def O_gt_missing_collapse():
    """SPEC §7.2 E11: gt with a Missing operand collapses to False."""
    return _bfalse(tvl.tvl_gt(tvl.TVLInt.Def(IntVal(5)), tvl.TVLInt.Missing))

def O_gt_normal_true():
    """SPEC: gt(5,3)=True, gt(3,5)=False (normal ordering, kills gt<->lt mutant)."""
    return _b(tvl.tvl_gt(tvl.TVLInt.Def(IntVal(5)), tvl.TVLInt.Def(IntVal(3)))) and \
           not _b(tvl.tvl_gt(tvl.TVLInt.Def(IntVal(3)), tvl.TVLInt.Def(IntVal(5))))

def O_ne_missing_collapse():
    """SPEC §7.2 E11: ne ALSO collapses to False on Missing (not Kleene)."""
    return _bfalse(tvl.tvl_ne(tvl.TVLInt.Def(IntVal(5)), tvl.TVLInt.Missing))

def O_exists_missing_false():
    """exists is the ONLY operator sensing presence: exists(Missing)=False."""
    return (not _b(tvl.exists_int(tvl.TVLInt.Missing))) and \
           _b(tvl.exists_int(tvl.TVLInt.Def(IntVal(1))))

def O_all_empty_false():
    """SPEC §7.2 E8: all([]) = False (anti-vacuous-truth)."""
    return not _b(quants.tvl_all(IntVal(0), []))

def O_any_empty_false():
    """SPEC §7.2 E8: any([]) = False."""
    return not _b(quants.tvl_any(IntVal(0), []))

def O_none_empty_false():
    """SPEC §7.2 E8: none([]) = False (safe deviation from vacuous True)."""
    return not _b(quants.tvl_none(IntVal(0), []))

def O_avg_empty_is_empty_fold():
    """SPEC §7.3(e): avg over empty = AggVal.empty (boolean-false fold), NOT num(0)."""
    return _agg_empty(tvl.tvl_aggregate("avg", IntVal(0), []))

def O_min_empty_is_empty_fold():
    """SPEC §7.3(e): min over empty = empty fold."""
    return _agg_empty(tvl.tvl_aggregate("min", IntVal(0), []))

def O_half_even_rounding():
    """SPEC §7.2 E2: half-even at the half-way point (even floor stays).

    v = (10^14+1)/(2*10^14) -> scaled = (10^14+1)/2 = 5e13 + 0.5 (half-way).
    floor 5e13 is even -> half-even stays 5e13; half-up -> 5e13+1.
    """
    v = Fraction(10 ** 14 + 1, 2 * 10 ** 14)
    return fp.to_scale14_int(v) == 5 * 10 ** 13

def O_half_even_floor0_stays():
    """SPEC §7.2 E2: half-way at floor 0 (even) stays 0; half-up -> 1."""
    v = Fraction(1, 2 * 10 ** 14)   # scaled = 1/2 = 0.5 (half-way), floor 0 even
    return fp.to_scale14_int(v) == 0

def O_div_zero_missing():
    """SPEC E3/E12: div by zero -> Missing (EvalError folded to Missing)."""
    return _missing_int(tvl.tvl_div(tvl.TVLInt.Def(IntVal(SCALE)),
                                    tvl.TVLInt.Def(IntVal(0))))

def O_mul_exact():
    """mul = round_half_even(a*b/10^14); 0.5*0.5=0.25 exact -> scaled 2.5e13."""
    a = tvl.TVLInt.Def(IntVal(SCALE // 2))
    b = tvl.TVLInt.Def(IntVal(SCALE // 2))
    return simplify(tvl.val_int(tvl.tvl_mul(a, b))).as_long() == (SCALE // 4)

def O_type_mismatch_eq_false():
    """SPEC §7.3(a): eq of mismatched-typed operands folds False."""
    s = Schema(); s.add(FieldContract(field="name", type="string"))
    return can_fire({"eq": [{"field": "name"}, 100]}, s, premises=["name"]) is False

def O_in_member_sort_mismatch_false():
    """SPEC §7.3(a): in with a member of the wrong sort -> False."""
    s = Schema(); s.add(FieldContract(field="cat", type="string"))
    return can_fire({"in": [{"field": "cat"}, [1, 2]]}, s, premises=["cat"]) is False

def O_match_redos_folds_false():
    """SPEC §7.3(d): ReDoS pattern (a+)+ folds False."""
    s = Schema(); s.add(FieldContract(field="cmd", type="string"))
    return can_fire({"match": [{"field": "cmd"}, "(a+)+$"]}, s, premises=["cmd"]) is False

def O_between_missing_false():
    """SPEC: between with a Missing operand -> Def(False)."""
    s = Schema(); s.add(FieldContract(field="x", type="int"))
    return can_fire({"between": [{"field": "x"}, 0, 100]}, s, missing=["x"]) is False

def O_not_exists_alias():
    """SPEC §5.2: not_exists is the valid bare not_* alias -> not(exists(...))."""
    s = Schema(); s.add(FieldContract(field="name", type="string"))
    return (can_fire({"not_exists": {"field": "name"}}, s, missing=["name"]) is True) and \
           (can_fire({"not_exists": {"field": "name"}}, s, premises=["name"]) is False)

def O_quantifier_over_non_array_false():
    """SPEC §7.3(e): quantifier over a non-array (scalar) -> False."""
    s = Schema(); s.add(FieldContract(field="items", type="string"))
    expr = {"all": {"binding": "x", "over": {"field": "items"},
                    "predicate": {"gt": [{"var": "x"}, 0]}}}
    return can_fire(expr, s) is False

def O_aggregate_over_non_array_missing():
    """SPEC §7.3(e): aggregate over a scalar -> Missing -> downstream folds false."""
    s = Schema(); s.add(FieldContract(field="nums", type="int"))
    return can_fire({"gt": [{"avg": {"field": "nums"}}, 5]}, s, premises=["nums"]) is False

ORACLES = {
    "O_gt_missing_collapse (E11)": O_gt_missing_collapse,
    "O_gt_normal_true (ordering)": O_gt_normal_true,
    "O_ne_missing_collapse (E11 ne also folds)": O_ne_missing_collapse,
    "O_exists_missing_false (E11 presence)": O_exists_missing_false,
    "O_all_empty_false (E8)": O_all_empty_false,
    "O_any_empty_false (E8)": O_any_empty_false,
    "O_none_empty_false (E8)": O_none_empty_false,
    "O_avg_empty_is_empty_fold (§7.3e)": O_avg_empty_is_empty_fold,
    "O_min_empty_is_empty_fold (§7.3e)": O_min_empty_is_empty_fold,
    "O_half_even_rounding (E2 banker's)": O_half_even_rounding,
    "O_half_even_floor0_stays (E2 half-way even)": O_half_even_floor0_stays,
    "O_div_zero_missing (E3/E12)": O_div_zero_missing,
    "O_mul_exact (E2 mul)": O_mul_exact,
    "O_type_mismatch_eq_false (§7.3a)": O_type_mismatch_eq_false,
    "O_in_member_sort_mismatch_false (§7.3a)": O_in_member_sort_mismatch_false,
    "O_match_redos_folds_false (§7.3d)": O_match_redos_folds_false,
    "O_between_missing_false": O_between_missing_false,
    "O_not_exists_alias (§5.2)": O_not_exists_alias,
    "O_quantifier_over_non_array_false (§7.3e)": O_quantifier_over_non_array_false,
    "O_aggregate_over_non_array_missing (§7.3e)": O_aggregate_over_non_array_missing,
}


# ============================================================
#  MUTANTS — each injects a spec violation; KILLED iff some oracle flips.
# ============================================================

def _save():
    return {
        "tvl_gt": tvl.tvl_gt, "tvl_ne": tvl.tvl_ne,
        "tvl_all": quants.tvl_all, "tvl_any": quants.tvl_any, "tvl_none": quants.tvl_none,
        "tvl_aggregate": tvl.tvl_aggregate, "tvl_div": tvl.tvl_div,
        "to_scale14_int": fp.to_scale14_int,
    }

def _restore(s):
    tvl.tvl_gt = s["tvl_gt"]; tvl.tvl_ne = s["tvl_ne"]
    quants.tvl_all = s["tvl_all"]; quants.tvl_any = s["tvl_any"]; quants.tvl_none = s["tvl_none"]
    tvl.tvl_aggregate = s["tvl_aggregate"]; tvl.tvl_div = s["tvl_div"]
    fp.to_scale14_int = s["to_scale14_int"]

def _mutant_gt_no_collapse():
    """Drop E11 leaf-collapse on gt: operate on raw values even when Missing."""
    tvl.tvl_gt = lambda a, b: tvl.TVLBool.Def(tvl.val_int(a) > tvl.val_int(b))

def _mutant_ne_missing_true():
    """Violate E11: ne with a Missing operand returns True (Kleene-ish)."""
    def m(a, b):
        return tvl.TVLBool.Def(If(Or(tvl.is_missing_int(a), tvl.is_missing_int(b)),
                                   True, tvl.val_int(a) != tvl.val_int(b)))
    tvl.tvl_ne = m

def _mutant_all_vacuous_true():
    """Violate E8: all([]) returns True (standard vacuous truth)."""
    _orig = quants.tvl_all
    quants.tvl_all = lambda length, preds: (
        tvl.TVLBool.Def(True) if not preds else _orig(length, preds))

def _mutant_any_empty_true():
    """Violate E8: any([]) returns True."""
    _orig = quants.tvl_any
    quants.tvl_any = lambda length, preds: (
        tvl.TVLBool.Def(True) if not preds else _orig(length, preds))

def _mutant_avg_empty_num0():
    """Violate §7.3(e): avg([]) returns num(0) instead of the empty fold."""
    _orig = tvl.tvl_aggregate
    def m(fn, length, elements):
        if fn == "avg" and not elements:
            return tvl.AggVal.num(IntVal(0))
        return _orig(fn, length, elements)
    tvl.tvl_aggregate = m

def _mutant_min_empty_num0():
    """Violate §7.3(e): min([]) returns num(0) instead of the empty fold."""
    _orig = tvl.tvl_aggregate
    def m(fn, length, elements):
        if fn == "min" and not elements:
            return tvl.AggVal.num(IntVal(0))
        return _orig(fn, length, elements)
    tvl.tvl_aggregate = m

def _mutant_half_up():
    """Violate E2: half-up rounding instead of half-even."""
    def m(v):
        scaled = v * (10 ** 14)
        n, d = scaled.numerator, scaled.denominator
        floor = n // d
        rem = n - floor * d
        if rem * 2 == d:           # exactly half-way -> always round UP
            return floor + 1 if n >= 0 else floor
        if rem * 2 < d:
            return floor
        return floor + 1
    fp.to_scale14_int = m

def _mutant_div_zero_def0():
    """Violate E3/E12: div by zero returns Def(0) instead of Missing."""
    def m(a, b):
        return If(Or(tvl.is_missing_int(a), tvl.is_missing_int(b)),
                  tvl.TVLInt.Missing,
                  tvl.TVLInt.Def(If(tvl.val_int(b) == 0, IntVal(0),
                                    tvl._round_half_even_div_signed(
                                        tvl.val_int(a) * SCALE, tvl.val_int(b)))))
    tvl.tvl_div = m

def _mutant_gt_inverted():
    """Violate comparison: gt returns lt (inverted ordering)."""
    def m(a, b):
        return tvl.TVLBool.Def(If(Or(tvl.is_missing_int(a), tvl.is_missing_int(b)),
                                   False, tvl.val_int(a) < tvl.val_int(b)))
    tvl.tvl_gt = m

MUTANTS = {
    "M_gt_no_collapse (drop E11 on gt)": _mutant_gt_no_collapse,
    "M_ne_missing_true (E11->Kleene on ne)": _mutant_ne_missing_true,
    "M_all_vacuous_true (E8->standard all[])": _mutant_all_vacuous_true,
    "M_any_empty_true (E8->any[]True)": _mutant_any_empty_true,
    "M_avg_empty_num0 (§7.3e->num0)": _mutant_avg_empty_num0,
    "M_min_empty_num0 (§7.3e->num0)": _mutant_min_empty_num0,
    "M_half_up (E2->half-up)": _mutant_half_up,
    "M_div_zero_def0 (E3/E12->Def0)": _mutant_div_zero_def0,
    "M_gt_inverted (gt<->lt)": _mutant_gt_inverted,
}


# ============================================================
#  RUNNERS
# ============================================================

def run_oracles():
    results = {}
    for name, fn in ORACLES.items():
        try:
            results[name] = bool(fn())
        except Exception as e:
            results[name] = f"ERR: {type(e).__name__}: {e}"
    return results


def run_counterexamples():
    """Spec-edge inputs vs verifier verdict (asserted directly, not via author tests)."""
    out = {}
    s = Schema(); s.add(FieldContract(field="n", type="string"))
    got = can_fire({"gt": [{"field": "n"}, 50]}, s, premises=["n"])
    out["C1 str gt int -> false (§7.3a)"] = (False, got, got is False)

    s = Schema(); s.add(FieldContract(field="cat", type="string"))
    got = can_fire({"in": [{"field": "cat"}, [1, 2]]}, s, premises=["cat"])
    out["C2 in(member sort mismatch) -> false (§7.3a)"] = (False, got, got is False)

    s = Schema(); s.add(FieldContract(field="cmd", type="string"))
    got = can_fire({"match": [{"field": "cmd"}, "(a+)+$"]}, s, premises=["cmd"])
    out["C3 match ReDoS (a+)+ -> false (§7.3d)"] = (False, got, got is False)

    s = Schema(); s.add(FieldContract(field="x", type="int"))
    got = can_fire({"between": [{"field": "x"}, 0, 100]}, s, missing=["x"])
    out["C4 between(Missing) -> false"] = (False, got, got is False)

    s = Schema(); s.add(FieldContract(field="name", type="string"))
    got = can_fire({"eq": [{"field": "name"}, None]}, s, missing=["name"])
    out["C5 eq(field,null) missing -> true (senses absence)"] = (True, got, got is True)

    s = Schema(); s.add(FieldContract(field="nums", type="int"))
    got = can_fire({"gt": [{"sum": {"field": "nums"}}, 5]}, s, premises=["nums"])
    out["C6 sum(scalar) -> Missing -> gt false (§7.3e)"] = (False, got, got is False)

    s = Schema()
    s.add(FieldContract(field="a", type="array", element_type="bool", cardinality=0))
    got = can_fire({"all": {"binding": "x", "over": {"field": "a"},
                            "predicate": {"var": "x"}}}, s)
    out["C7 all([]) cardinality 0 -> false (E8)"] = (False, got, got is False)
    return out


# ============================================================
#  PYTEST TESTS
# ============================================================

def test_oracles_hold_on_intact_verifier():
    """Every oracle holds on the intact kernel (else the oracles are wrong)."""
    saved = _save()
    res = run_oracles()
    _restore(saved)
    for name, r in res.items():
        assert r is True, f"oracle {name} does not hold on the intact verifier: {r}"


def test_mutants_are_killed():
    """Every spec-violating mutant is KILLED (some oracle flips to fail)."""
    for mname, mfn in MUTANTS.items():
        saved = _save()
        mfn()
        mres = run_oracles()
        _restore(saved)
        killed = [n for n, r in mres.items() if r is not True]
        assert killed, f"mutant {mname} SURVIVED: no oracle detected this violation"


def test_counterexamples_match_spec():
    """Spec-edge inputs match the verifier verdict."""
    for name, (expected, got, ok) in run_counterexamples().items():
        assert ok, f"{name}: spec={expected} verifier={got}"
