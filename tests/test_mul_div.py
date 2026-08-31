"""M3.1 — mul/div（非线性定点算术 + half-even 舍入），并与 fixed_point 参考交叉验证."""

from fractions import Fraction

from z3 import simplify

from erdl_formal.fixed_point import div as ref_div
from erdl_formal.fixed_point import mul as ref_mul
from erdl_formal.fixed_point import parse, to_scale14_half_even
from erdl_formal.tvl import TVLInt, tvl_div, tvl_mul, val_int

_SCALE = 10 ** 14


def _scaled(decimal_str):
    """decimal string → scaled int（value * 10^14 的整数；Fraction 会约分，须用乘法而非 .numerator）"""
    return int(parse(decimal_str) * _SCALE)


def test_mul_concrete():
    # 0.1 * 0.2 = 0.02  (scaled: 10^13 * 2*10^13 → 2*10^12)
    a = TVLInt.Def(_scaled("0.1"))
    b = TVLInt.Def(_scaled("0.2"))
    assert simplify(val_int(tvl_mul(a, b))).as_long() == _scaled("0.02")


def test_div_concrete():
    # 1 / 8 = 0.125
    a = TVLInt.Def(_scaled("1"))
    b = TVLInt.Def(_scaled("8"))
    assert simplify(val_int(tvl_div(a, b))).as_long() == _scaled("0.125")


def test_div_by_zero_is_missing():
    from erdl_formal.tvl import is_missing_int
    a = TVLInt.Def(_scaled("1"))
    b = TVLInt.Def(0)
    assert simplify(is_missing_int(tvl_div(a, b)))


def test_mul_div_crosscheck_reference():
    """SMT mul/div 逐例 = fixed_point 参考语义（scale=14 + half-even）."""
    cases = [("0.1", "0.2"), ("0.1", "0.1"), ("1.5", "2.5"), ("0.3", "0.7"), ("0.125", "0.5")]
    for a_s, b_s in cases:
        ref = int(to_scale14_half_even(ref_mul(parse(a_s), parse(b_s))) * _SCALE)
        got = simplify(val_int(tvl_mul(TVLInt.Def(_scaled(a_s)), TVLInt.Def(_scaled(b_s))))).as_long()
        assert got == ref, f"mul({a_s},{b_s}): SMT {got} != ref {ref}"

    div_cases = [("1", "8"), ("1", "3"), ("2.5", "0.5"), ("0.1", "0.3")]
    for a_s, b_s in div_cases:
        ref = int(to_scale14_half_even(ref_div(parse(a_s), parse(b_s))) * _SCALE)
        got = simplify(val_int(tvl_div(TVLInt.Def(_scaled(a_s)), TVLInt.Def(_scaled(b_s))))).as_long()
        assert got == ref, f"div({a_s},{b_s}): SMT {got} != ref {ref}"
