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

"""Fixed-point decimal semantics (E2): scale=14 + half-even rounding.

Spec v2.1 §7.2 E2 + §7.3(c):
- intermediate computation uses high-precision bounded rationals (128-bit num/den)
- ONLY output nodes round to scale=14 + half-even (banker's rounding)
- serialization uses minimal representation (§28.2)

This is the *reference semantics* (exact rational) that the SMT model
(QF_LIA linear / QF_NRA nonlinear) is validated against via counterexample replay.
"""

from fractions import Fraction

SCALE = 14
_SCALE_FACTOR = 10 ** SCALE


def parse(s: str) -> Fraction:
    """Parse a decimal string → exact Fraction.

    Rejects scientific notation (spec §28.2 minimal representation forbids it).
    """
    if "e" in s.lower() or "E" in s:
        raise ValueError(f"non-minimal: scientific notation: {s!r}")
    return Fraction(s)


def to_scale14_int(v: Fraction) -> int:
    """Exact rational → scale-14 integer (half-even rounding to 14 places).

    The integer is the fixed-point representation of ``v`` in the SMT model
    (``TVLInt`` values are scale-14 integers). Exact integer arithmetic — no
    floating point, no Decimal round-trip.
    """
    scaled = v * _SCALE_FACTOR
    floor = scaled.numerator // scaled.denominator
    rem = scaled.numerator - floor * scaled.denominator
    if rem * 2 == scaled.denominator:
        # exactly halfway → round to even
        return floor if floor % 2 == 0 else floor + 1
    if rem * 2 < scaled.denominator:
        return floor
    return floor + 1


def to_scale14_half_even(v: Fraction) -> Fraction:
    """Round an exact rational to scale=14, half-even (banker's rounding)."""
    return Fraction(to_scale14_int(v), _SCALE_FACTOR)


def serialize(v: Fraction) -> str:
    """Serialize in minimal representation (§28.2): no trailing zeros, integer
    part without decimal point. Exact (no float, no format-precision default)."""
    n, d = v.numerator, v.denominator
    sign = "-" if n < 0 else ""
    n = abs(n)
    int_part, rem = divmod(n, d)
    if rem == 0:
        return sign + str(int_part)
    digits = []
    while rem != 0:
        rem *= 10
        q, rem = divmod(rem, d)
        digits.append(str(q))
        if len(digits) > 100:  # safety cap (non-terminating must not be serialized)
            raise ValueError(f"non-terminating decimal: {v}")
    frac = "".join(digits).rstrip("0")
    return f"{sign}{int_part}.{frac}" if frac else f"{sign}{int_part}"


def add(a: Fraction, b: Fraction) -> Fraction:
    return a + b


def sub(a: Fraction, b: Fraction) -> Fraction:
    return a - b


def mul(a: Fraction, b: Fraction) -> Fraction:
    return a * b


def div(a: Fraction, b: Fraction) -> Fraction:
    if b == 0:
        raise ZeroDivisionError("division by zero (E3 → eval_warnings → E12 fold)")
    return a / b
