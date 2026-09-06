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

"""Calendar (date_part / month_last_day / date_add) + civil algorithm sanity."""

import pytest

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
    # 2026-01-01 is Thursday → 4 (1=Monday...7=Sunday)
    assert _val(tvl_date_part("day_of_week", TVLInt.Def(epoch_ms("2026-01-01")))) == 4


def test_month_last_day_leap():
    # month_last_day("2024-02-15") = full date "2024-02-29" (erdl endOfMonth)
    assert _val(tvl_month_last_day(TVLInt.Def(epoch_ms("2024-02-15")))) == epoch_ms("2024-02-29")


def test_date_add_months_clamp():
    # 2026-01-31 + 1 month → 2026-02-28 (month-end clamp)
    got = _val(tvl_date_add("months", TVLInt.Def(epoch_ms("2026-01-31")), TVLInt.Def(1 * 10 ** 14)))
    assert got == epoch_ms("2026-02-28")


def test_date_add_days():
    got = _val(tvl_date_add("days", TVLInt.Def(epoch_ms("2026-01-01")), TVLInt.Def(1 * 10 ** 14)))
    assert got == epoch_ms("2026-01-02")


def test_date_add_hours():
    got = _val(tvl_date_add("hours", TVLInt.Def(epoch_ms("2026-01-01T00:00:00")), TVLInt.Def(24 * 10 ** 14)))
    assert got == epoch_ms("2026-01-02T00:00:00")


def test_date_add_years_leap_clamp():
    # 2024-02-29 + 1 year → 2025-02-28 (non-leap clamp)
    got = _val(tvl_date_add("years", TVLInt.Def(epoch_ms("2024-02-29")), TVLInt.Def(1 * 10 ** 14)))
    assert got == epoch_ms("2025-02-28")


def test_date_add_unsupported_unit_raises():
    with pytest.raises(NotImplementedError):
        tvl_date_add("seconds", TVLInt.Def(epoch_ms("2026-01-01")), TVLInt.Def(1 * 10 ** 14))


def test_date_add_non_integer_amount_folds_missing():
    """G3 (SPEC §7.3(f)): amount MUST be an integer; a non-integer scale-14 amount folds to Missing."""
    from erdl_formal.tvl import is_missing_int
    # 1.5 months = 150000000000000 scale-14 units → not divisible by 10^14 → Missing
    got = tvl_date_add("months", TVLInt.Def(epoch_ms("2024-01-15")), TVLInt.Def(15 * 10 ** 13))
    assert is_true(simplify(is_missing_int(got)))


def test_date_add_integer_amount_ok():
    """An integer amount (divisible by 10^14) proceeds normally."""
    got = _val(tvl_date_add("months", TVLInt.Def(epoch_ms("2024-01-15")), TVLInt.Def(2 * 10 ** 14)))
    assert got == epoch_ms("2024-03-15")
