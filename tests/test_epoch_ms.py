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

"""epoch_ms node — date-string (date-only / ISO 8601 datetime) → epoch ms (§7.3(f))."""

from datetime import datetime, timezone

from z3 import is_true, simplify

from erdl_formal.calendar import tvl_epoch_ms
from erdl_formal.tvl import TVLStr, is_missing_int, str_def, val_int


def _ref(s: str) -> int:
    """Reference epoch-ms via Python (UTC)."""
    t = s.replace("Z", "+00:00")
    dt = datetime.fromisoformat(t)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _run(s: str):
    r = tvl_epoch_ms(str_def(s))
    if is_true(simplify(is_missing_int(r))):
        return None
    return simplify(val_int(r)).as_long()


def test_epoch_ms_date_only():
    assert _run("1970-01-01") == 0
    assert _run("1969-12-31") == -86400000


def test_epoch_ms_datetime():
    for s in [
        "2026-01-01T12:30:45",
        "2026-01-01T12:30:45Z",
        "2026-01-01T12:30:45+08:00",
        "2026-01-01T12:30:45-05:00",
        "2000-12-31T23:59:59",
    ]:
        assert _run(s) == _ref(s), f"{s!r}"


def test_epoch_ms_leap_day():
    assert _run("2024-02-29") == _ref("2024-02-29")


def test_epoch_ms_invalid_is_missing():
    for s in [
        "invalid", "2026-13-01", "2026-02-30", "2026-01-01T25:00:00", "not-a-date",
        # fractional seconds are outside the deterministic whole-second subset
        "2026-01-01T12:30:45.123Z", "2026-01-01T12:30:45.5",
    ]:
        assert _run(s) is None, f"{s!r} should be Missing"


def test_epoch_ms_missing_field_is_missing():
    assert is_true(simplify(is_missing_int(tvl_epoch_ms(TVLStr.Missing))))


def test_compiler_routes_epoch_ms():
    from erdl_formal.field_contracts import FieldContract, Schema
    from erdl_formal.properties import can_fire

    s = Schema()
    s.add(FieldContract(field="d1", type="string"))
    # epoch_ms(d1) > 0 is satisfiable (d1 can be a date after 1970-01-01)
    assert can_fire(["gt", ["epoch_ms", ["field", "d1"]], ["lit", 0]], s, premises=["d1"]) is True
