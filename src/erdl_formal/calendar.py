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
functions, over raw epoch-millisecond timestamps (UTC). The spec §7.3(f) anchors
the calendar layer's cross-implementation consistency via dual-implementation
vectors; this SMT encoding additionally enables static verification.
"""

from z3 import And, Concat, Extract, If, InRe, IntToStr, Length, Not, Or, Range, StrToInt, StringVal

from .tvl import TVLInt, TVLStr, is_missing_int, is_missing_str, val_int, val_str

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


def _pad2(n):
    """Zero-pad a non-negative int to 2 ASCII digits."""
    return If(n < 10, Concat(StringVal("0"), IntToStr(n)), IntToStr(n))


def _pad3(n):
    """Zero-pad a non-negative int to 3 ASCII digits (milliseconds)."""
    return If(n < 10, Concat(StringVal("00"), IntToStr(n)),
              If(n < 100, Concat(StringVal("0"), IntToStr(n)), IntToStr(n)))


def _format_datetime(epoch_ms):
    """epoch ms → 'YYYY-MM-DDTHH:MM:SS.mmmZ' (UTC, full datetime; ms 000 at whole-second precision)."""
    y, m, d = civil_from_days(epoch_ms / DAY_MS)
    h = (epoch_ms / 3600000) % 24
    mi = (epoch_ms / 60000) % 60
    se = (epoch_ms / 1000) % 60
    ms = epoch_ms % 1000
    return Concat(
        IntToStr(y), StringVal("-"), _pad2(m), StringVal("-"), _pad2(d),
        StringVal("T"), _pad2(h), StringVal(":"), _pad2(mi), StringVal(":"), _pad2(se),
        StringVal("."), _pad3(ms), StringVal("Z"),
    )


def _parse_date_arg(arg):
    """Date string node argument → (valid, epoch_ms)."""
    return _epoch_ms_parse(val_str(arg))


def tvl_date_part(unit, arg):
    """date_part{unit}: date string → integer UTC component (§7.3(f))."""

    valid, arg_ms = _parse_date_arg(arg)

    def body():
        z = arg_ms / DAY_MS
        e = arg_ms
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

    return If(Or(is_missing_str(arg), Not(valid)), TVLInt.Missing, TVLInt.Def(body()))


def tvl_month_last_day(arg):
    """month_last_day: date string → date string (last day of the month)."""

    valid, arg_ms = _parse_date_arg(arg)

    def body():
        y, m, _ = civil_from_days(arg_ms / DAY_MS)
        return _format_datetime(days_from_civil(y, m, days_in_month(y, m)) * DAY_MS)

    return If(Or(is_missing_str(arg), Not(valid)), TVLStr.Missing, TVLStr.Def(body()))


def tvl_date_add(unit, base, amount):
    """date_add{unit}: date string → date string (UTC + month-end clamp, §7.3(f)).

    The ``amount`` MUST be an integer (a duration is an integer unit); a
    non-integer amount (scale-14 value not divisible by 10^14) folds to Missing.
    """

    valid, base_ms = _parse_date_arg(base)
    n = val_int(amount) / 10 ** 14  # amount scale-14 → integer step

    def body():
        z = base_ms / DAY_MS
        if unit == "days":
            result = (z + n) * DAY_MS
        elif unit == "hours":
            result = z * DAY_MS + n * 3600000
        else:
            y, m, d = civil_from_days(z)
            if unit == "months":
                total = y * 12 + (m - 1) + n
                ny = total / 12
                nm = total % 12 + 1
                nd = If(d > days_in_month(ny, nm), days_in_month(ny, nm), d)
                result = days_from_civil(ny, nm, nd) * DAY_MS
            elif unit == "years":
                ny = y + n
                nd = If(d > days_in_month(ny, m), days_in_month(ny, m), d)
                result = days_from_civil(ny, m, nd) * DAY_MS
            else:
                raise NotImplementedError(f"date_add unit {unit!r}")
        return _format_datetime(result)

    return If(
        Or(
            is_missing_str(base),
            Not(valid),
            is_missing_int(amount),
            val_int(amount) % 10 ** 14 != 0,  # non-integer amount → type_mismatch → Missing
        ),
        TVLStr.Missing,
        TVLStr.Def(body()),
    )


# --- epoch_ms: date-string (date-only / ISO 8601 datetime) → epoch ms ---

def _digits_exact(n):
    """A regex matching exactly n ASCII digits."""
    return Concat(*([Range("0", "9")] * n))


def _parse_fixed_int(v, start, length):
    """Parse v[start:start+length] as a non-negative int.

    Returns (is_valid, int_value): is_valid is a Z3 Bool that is true only when
    the substring is exactly ``length`` ASCII digits; int_value is StrToInt of the
    substring (well-defined whenever is_valid holds).
    """
    sub = Extract(v, start, length)
    return InRe(sub, _digits_exact(length)), StrToInt(sub)


def _epoch_ms_parse(v):
    """Parse a symbolic date string → (valid, epoch_ms), UTC semantics (§7.3(f)).

    Supported formats (all fixed-length, so each is tractable in SMT):
      - date-only        "YYYY-MM-DD"                     (len 10)
      - datetime, UTC    "YYYY-MM-DDTHH:MM:SS"             (len 19)
      - datetime, Z      "YYYY-MM-DDTHH:MM:SSZ"            (len 20)
      - datetime, offset "YYYY-MM-DDTHH:MM:SS±HH:MM"       (len 25)

    ``valid`` is a Z3 Bool; ``epoch_ms`` is well-defined only when ``valid``.
    """
    y_ok, y = _parse_fixed_int(v, 0, 4)
    mo_ok, mo = _parse_fixed_int(v, 5, 2)
    d_ok, d = _parse_fixed_int(v, 8, 2)
    h_ok, h = _parse_fixed_int(v, 11, 2)
    mi_ok, mi = _parse_fixed_int(v, 14, 2)
    se_ok, se = _parse_fixed_int(v, 17, 2)
    oh_ok, oh = _parse_fixed_int(v, 20, 2)
    om_ok, om = _parse_fixed_int(v, 23, 2)

    n = Length(v)
    sep1 = Extract(v, 4, 1) == "-"
    sep2 = Extract(v, 7, 1) == "-"
    sepT = Extract(v, 10, 1) == "T"
    sep3 = Extract(v, 13, 1) == ":"
    sep4 = Extract(v, 16, 1) == ":"

    date_ok = And(y_ok, mo_ok, d_ok, mo >= 1, mo <= 12, d >= 1, d <= days_in_month(y, mo))
    time_ok = And(h_ok, mi_ok, se_ok, h >= 0, h <= 23, mi >= 0, mi <= 59, se >= 0, se <= 59)

    base_days = days_from_civil(y, mo, d) * DAY_MS
    time_ms = h * 3600000 + mi * 60000 + se * 1000

    date_only = And(n == 10, sep1, sep2, date_ok)
    dt_utc = And(n == 19, sep1, sep2, sepT, sep3, sep4, date_ok, time_ok)
    dt_z = And(n == 20, sep1, sep2, sepT, sep3, sep4, Extract(v, 19, 1) == "Z", date_ok, time_ok)

    sign = Extract(v, 19, 1)
    off_ok = And(oh_ok, om_ok, oh >= 0, oh <= 23, om >= 0, om <= 59)
    dt_off = And(
        n == 25, sep1, sep2, sepT, sep3, sep4,
        Or(sign == "+", sign == "-"), Extract(v, 22, 1) == ":",
        date_ok, time_ok, off_ok,
    )
    # UTC = local − offset (for '+08:00', UTC is 8h earlier)
    offset_ms = oh * 3600000 + om * 60000
    dt_off_epoch = base_days + time_ms - If(sign == "+", offset_ms, -offset_ms)

    valid = Or(date_only, dt_utc, dt_z, dt_off)
    epoch_ms = If(
        date_only, base_days,
        If(Or(dt_utc, dt_z), base_days + time_ms,
           dt_off_epoch,
        ),
    )
    return valid, epoch_ms


def tvl_epoch_ms(s):
    """epoch_ms node: date string → epoch milliseconds (Missing when invalid/missing)."""
    valid, epoch_ms = _epoch_ms_parse(val_str(s))
    return If(is_missing_str(s), TVLInt.Missing, If(valid, TVLInt.Def(epoch_ms), TVLInt.Missing))
