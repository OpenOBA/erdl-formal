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

"""ERDL match operator — safe-regex subset → Z3 Re (spec v2.1 §7.3(d)).

Verifies that compile_match encodes JS RegExp.test() semantics (no flags) and
rejects non-regular constructs, aligning with the runtime safeRegExp guard.
"""

from z3 import InRe, Solver, StringVal, sat

from erdl_formal.regex import RegexError, compile_match


def _matches(pattern: str, s: str) -> bool:
    re_ = compile_match(pattern)
    solver = Solver()
    solver.add(InRe(StringVal(s), re_))
    return solver.check() == sat


# --- substring search (unanchored) ------------------------------------------

def test_unanchored_substring():
    assert _matches("ab", "xxabyy") is True
    assert _matches("ab", "xyz") is False


# --- anchors -----------------------------------------------------------------

def test_start_anchor():
    assert _matches("^ab", "abc") is True
    assert _matches("^ab", "xabc") is False


def test_end_anchor():
    assert _matches("ab$", "xxab") is True
    assert _matches("ab$", "abx") is False


def test_both_anchors():
    assert _matches("^ab$", "ab") is True
    assert _matches("^ab$", "xab") is False


# --- dot (excludes line terminators) ----------------------------------------

def test_dot_excludes_line_terminators():
    assert _matches(".", "x") is True
    assert _matches(".", "\n") is False
    assert _matches("a.b", "axb") is True
    assert _matches("a.b", "a\nb") is False


# --- character classes --------------------------------------------------------

def test_char_class_range():
    assert _matches("[a-z]+", "hello") is True
    assert _matches("[a-z]+", "HELLO") is False


def test_negated_char_class():
    assert _matches("[^a-z]+", "123") is True
    assert _matches("[^a-z]+", "abc") is False


def test_escaped_bracket_in_class():
    assert _matches("[\\]]", "]") is True


# --- shorthands --------------------------------------------------------------

def test_digit_shorthand():
    assert _matches("\\d+", "abc123") is True
    assert _matches("\\d+", "abc") is False


def test_non_digit_shorthand():
    assert _matches("\\D+", "abc") is True
    assert _matches("\\D+", "123") is False


def test_word_shorthand():
    assert _matches("\\w+", "hello_123") is True
    assert _matches("\\w+", "---") is False


def test_space_shorthand():
    assert _matches("\\s+", "a b\tc") is True
    assert _matches("\\s+", "abc") is False
    assert _matches("\\S+", "   ") is False


# --- quantifiers -------------------------------------------------------------

def test_bounded_repetition():
    assert _matches("a{2,4}", "aaa") is True
    assert _matches("a{2,4}", "a") is False
    assert _matches("a{2,}", "aaaaa") is True
    assert _matches("a{2,}", "a") is False


def test_lazy_quantifier_same_language():
    assert _matches("a*?b", "aaab") is True


def test_open_range_lazy_form():
    # {m,} is encoded lazily as (atom^m)·(atom*) — semantics preserved, incl. {0,} == a*.
    assert _matches("a{0,}", "") is True
    assert _matches("a{0,}", "aaa") is True
    assert _matches("a{3,}", "aa") is False
    assert _matches("a{3,}", "aaa") is True


def test_quantifier_resource_limit():
    # At the boundary (allowed): compiles without raising.
    compile_match("a{10000}")
    compile_match("a{10000,}")
    compile_match("a{1,10000}")
    # Exceeding the limit → RegexError (fail-closed), not silent expansion.
    for p in ["a{10001}", "a{10001,}", "a{1,10001}", "a{10001,20000}"]:
        try:
            compile_match(p)
            assert False, f"{p!r} should be rejected"
        except RegexError:
            pass


def test_quantifier_lower_exceeds_upper():
    # {m,n} with m > n is a SyntaxError in JS; must be a clean RegexError, not a Z3 crash.
    try:
        compile_match("a{5,2}")
        assert False, "a{5,2} should be rejected"
    except RegexError:
        pass


# --- alternation and groups ---------------------------------------------------

def test_alternation():
    assert _matches("(rm|shutdown|reboot)", "rm -rf") is True
    assert _matches("(rm|shutdown|reboot)", "ls") is False


def test_non_capturing_group():
    assert _matches("(?:abc)", "abc") is True


def test_named_group_is_regular():
    assert _matches("(?<name>abc)", "abc") is True


# --- word boundary -------------------------------------------------------------

def test_word_boundary():
    assert _matches("\\bword\\b", "a word b") is True
    assert _matches("\\bword\\b", "sword") is False
    assert _matches("\\bword\\b", "words") is False
    assert _matches("\\beval\\s*\\(", "eval(") is True
    assert _matches("\\beval\\s*\\(", "deval(") is False


# --- real rule corpus patterns ------------------------------------------------

def test_real_rule_patterns():
    assert _matches("package\\.json", "xpackage.json") is True
    assert _matches("@ts-ignore|@ts-nocheck", "@ts-nocheck") is True
    assert _matches("[0-9a-f]{2,4}", "12ab") is True


# --- rejection of non-regular constructs --------------------------------------

def test_reject_backreference():
    for p in ["(a)\\1", "\\1(a)", "\\k<name>"]:
        try:
            compile_match(p)
            assert False, f"{p!r} should be rejected"
        except RegexError:
            pass


def test_reject_lookaround():
    for p in ["(?=a)b", "(?!a)b", "(?<=a)b", "(?<!a)b"]:
        try:
            compile_match(p)
            assert False, f"{p!r} should be rejected"
        except RegexError:
            pass


def test_reject_atomic_and_inline_flags():
    for p in ["(?>a)b", "(?i)abc", "\\B"]:
        try:
            compile_match(p)
            assert False, f"{p!r} should be rejected"
        except RegexError:
            pass


def test_reject_mid_pattern_anchor():
    for p in ["a^b", "a$b"]:
        try:
            compile_match(p)
            assert False, f"{p!r} should be rejected"
        except RegexError:
            pass


# --- compiler integration -----------------------------------------------------

def test_compiler_match_integration():
    from erdl_formal.field_contracts import FieldContract, Schema
    from erdl_formal.properties import can_fire

    s = Schema()
    s.add(FieldContract(field="tool.name", type="string"))
    # match with a regex alternation (not just a literal)
    assert can_fire(["match", ["field", "tool.name"], "(rm|shutdown|reboot)"], s, premises=["tool.name"]) is True
    assert can_fire(["match", ["field", "tool.name"], "^/etc/"], s, premises=["tool.name"]) is True
