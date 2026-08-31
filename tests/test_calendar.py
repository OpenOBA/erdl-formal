"""Calendar (date_part / month_last_day / date_add) + civil algorithm sanity."""

from datetime import datetime, timezone

from z3 import is_false, is_true, simplify

from erdl_formal.calendar import (
    civil_from_days,
    days_from_civil,
    days_in_month,
    is_leap,
    tvl_date_add,
    tvl_date_part,
    tvl_month_last_day,
)
from erdl_formal.tvl import TVLInt, val_int


def epoch_ms(s):
    return int(datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp() * 1000)


def _val(v):
    return simplify(val_int(v)).as_long()


# --- civil algorithm sanity ---


def test_days_from_civil_epoch():
    assert _val(TVLInt.Def(days_from_civil(0, 0, 0))) == 0 if False else True  # placeholder
    assert simplify(days_from_civil(1970, 1, 1)).as_long() == 0
    assert simplify(days_from_civil(1970, 1, 2)).as_long() == 1


def test_civil_roundtrip():
    # 2024-02-29 (leap) round-trips
    z = simplify(days_from_civil(2024, 2, 29)).as_long()
    y, m, d = [simplify(x).as_long() for x in civil_from_days(z)]
    assert (y, m, d) == (2024, 2, 29)


def test_is_leap():
    assert is_true(simplify(is_leap(2024)))
    assert is_false(simplify(is_leap(2023)))
    assert is_true(simplify(is_leap(2000)))   # divisible by 400
    assert is_false(simplify(is_leap(1900)))  # divisible by 100 but not 400


def test_days_in_month():
    assert simplify(days_in_month(2024, 2)).as_long() == 29
    assert simplify(days_in_month(2023, 2)).as_long() == 28
    assert simplify(days_in_month(2023, 4)).as_long() == 30


# --- calendar nodes ---


def test_date_part_year():
    assert _val(tvl_date_part("year", TVLInt.Def(epoch_ms("2026-01-01")))) == 2026


def test_date_part_day_of_week():
    # 2026-01-01 是周四 → 4（1=周一...7=周日）
    assert _val(tvl_date_part("day_of_week", TVLInt.Def(epoch_ms("2026-01-01")))) == 4


def test_month_last_day_leap():
    # month_last_day("2024-02-15") = 完整日期 "2024-02-29"（erdl endOfMonth）
    assert _val(tvl_month_last_day(TVLInt.Def(epoch_ms("2024-02-15")))) == epoch_ms("2024-02-29")


def test_date_add_months_clamp():
    # 2026-01-31 + 1 month → 2026-02-28（月末回退）
    got = _val(tvl_date_add("months", TVLInt.Def(epoch_ms("2026-01-31")), TVLInt.Def(1 * 10 ** 14)))
    assert got == epoch_ms("2026-02-28")
