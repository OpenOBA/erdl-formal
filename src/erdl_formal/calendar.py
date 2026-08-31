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

"""Gregorian calendar (civil algorithm) — SMT encoding for date_add / date_part / month_last_day.

Days-from-civil / civil-from-days (Howard Hinnant) as deterministic Z3 integer
functions, over raw epoch-millisecond timestamps (UTC). The spec §10.5 anchors
the calendar layer's cross-implementation consistency via dual-implementation
vectors; this SMT encoding additionally enables static verification.
"""

from z3 import If, Or

from .tvl import TVLInt, is_missing_int, val_int

DAY_MS = 86400000


def is_leap(y):
    return If(y % 4 != 0, False, If(y % 100 != 0, True, If(y % 400 != 0, False, True)))


def days_from_civil(y, m, d):
    """(y, m, d) → days since 1970-01-01 (Hinnant's algorithm, Z3 Int)."""
    y = If(m <= 2, y - 1, y)
    era = If(y >= 0, y, y - 399) / 400
    yoe = y - era * 400
    mp = m + If(m > 2, -3, 9)
    doy = (153 * mp + 2) / 5 + d - 1
    doe = yoe * 365 + yoe / 4 - yoe / 100 + doy
    return era * 146097 + doe - 719468


def civil_from_days(z):
    """days since 1970-01-01 → (y, m, d)."""
    z = z + 719468
    era = If(z >= 0, z, z - 146096) / 146097
    doe = z - era * 146097
    yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe / 4 - yoe / 100)
    mp = (5 * doy + 2) / 153
    d = doy - (153 * mp + 2) / 5 + 1
    m = mp + If(mp < 10, 3, -9)
    return (y + If(m <= 2, 1, 0), m, d)


def days_in_month(y, m):
    return If(
        Or(m == 1, m == 3, m == 5, m == 7, m == 8, m == 10, m == 12), 31,
        If(Or(m == 4, m == 6, m == 9, m == 11), 30, If(is_leap(y), 29, 28)),
    )


def _z(epoch_ms):
    return val_int(epoch_ms) / DAY_MS


def tvl_date_part(unit, epoch):
    """date_part{unit}: extract a UTC component from an epoch-ms timestamp."""

    def body():
        z = _z(epoch)
        e = val_int(epoch)
        y, m, d = civil_from_days(z)
        return {
            "year": y,
            "month": m,
            "day": d,
            "hour": (e / 3600000) % 24,
            "minute": (e / 60000) % 60,
            "second": (e / 1000) % 60,
            "day_of_week": (z + 3) % 7 + 1,  # 1=Monday ... 7=Sunday
        }[unit]

    return If(is_missing_int(epoch), TVLInt.Missing, TVLInt.Def(body()))


def tvl_month_last_day(epoch):
    """month_last_day: last day of the month as a full date (erdl endOfMonth),
    returned as that day's epoch ms."""

    def body():
        y, m, _ = civil_from_days(_z(epoch))
        return days_from_civil(y, m, days_in_month(y, m)) * DAY_MS

    return If(is_missing_int(epoch), TVLInt.Missing, TVLInt.Def(body()))


def tvl_date_add(unit, base, amount):
    """date_add{unit}: add an integer amount (years/months/days/hours), UTC + month-end clamp."""

    def body():
        z = _z(base)
        n = val_int(amount) / 10 ** 14  # amount is scale-14 → integer step
        if unit == "days":
            return (z + n) * DAY_MS
        if unit == "hours":
            return z * DAY_MS + n * 3600000
        y, m, d = civil_from_days(z)
        if unit == "months":
            total = y * 12 + (m - 1) + n
            ny = total / 12
            nm = total % 12 + 1
            nd = If(d > days_in_month(ny, nm), days_in_month(ny, nm), d)
            return days_from_civil(ny, nm, nd) * DAY_MS
        if unit == "years":
            ny = y + n
            nd = If(d > days_in_month(ny, m), days_in_month(ny, m), d)
            return days_from_civil(ny, m, nd) * DAY_MS
        raise NotImplementedError(f"date_add unit {unit!r}")

    return If(
        Or(is_missing_int(base), is_missing_int(amount)),
        TVLInt.Missing,
        TVLInt.Def(body()),
    )
