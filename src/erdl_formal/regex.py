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

"""ERDL ``match`` operator — safe-regex subset → Z3 regular expression.

Compiles the ERDL safe-regex subset (spec v2.1 §7.3(d): a **regular language** —
backreferences and lookaround forbidden) into a Z3 regular expression that
encodes JS ``RegExp.test()`` semantics with **no flags** (the exact runtime
call in ``evaluator.ts`` is ``safeRegExp(rn)``, i.e. ``new RegExp(pattern)``):

- **unanchored substring search**: ``re.test(s)`` is true iff the pattern
  matches a contiguous substring of ``s``;
- ``^`` = start of input, ``$`` = end of input (no ``m`` flag);
- ``.`` = any char except line terminators ``\\n \\r \\u2028 \\u2029``;
- ``\\d \\w \\s`` (and ``\\D \\W \\S``) = **ASCII** classes (no ``u`` flag);
- greedy and lazy quantifiers are identical for boolean membership;
- ``\\b`` = ASCII word boundary (word chars ``[A-Za-z0-9_]``).

Rejected (outside the subset): backreferences ``\\1``–``\\9`` / ``\\k<…>``,
lookahead ``(?=`` ``(?!``, lookbehind ``(?<=`` ``(?<!``, atomic groups ``(?>``,
conditionals ``(?(``, inline flags, ``\\B``, and ``^``/``$``/``\\b`` in a
non-anchor position — fail-closed, never silently mis-encoded.

Quantifier repeat counts (``{m}`` / ``{m,}`` / ``{m,n}``) are bounded by
``MAX_REPEAT`` (10000, aligned with the E4 resource limit): exceeding it raises
:class:`RegexError`. ``{m,n}`` with ``m > n`` is also rejected (a JS SyntaxError).
The ``{m,}`` form is encoded lazily as ``(atom^m)·(atom*)`` — no O(m) expansion.
"""

from z3 import (
    AllChar,
    Complement,
    Concat,
    Full,
    Intersect,
    Loop,
    Option,
    Plus,
    Range,
    Re,
    ReSort,
    Star,
    StringSort,
    Union,
)

_RE_SORT = ReSort(StringSort())
# Universal language: every string (including the empty string).
ANY_STRING = Full(_RE_SORT)
# Every single-character string.
ANY_CHAR = AllChar(_RE_SORT)


class RegexError(ValueError):
    """Raised for a pattern outside the ERDL safe-regex subset."""


def _char(s: str):
    """Literal char/string → regex."""
    return Re(s)


def _union(*rs):
    rs = [r for r in rs if r is not None]
    if not rs:
        return None
    if len(rs) == 1:
        return rs[0]
    return Union(*rs)


def _concat(*rs):
    rs = [r for r in rs if r is not None]
    if not rs:
        return _char("")
    if len(rs) == 1:
        return rs[0]
    return Concat(*rs)


def _not_char(r):
    """Single-character complement: any char not in ``r``'s language."""
    return Intersect(ANY_CHAR, Complement(r))


# --- predefined JS character classes (no 'u' flag → ASCII semantics) ---------

_DIGIT = Range("0", "9")
_WORD = _union(Range("A", "Z"), Range("a", "z"), Range("0", "9"), _char("_"))
# JS \s = WhiteSpace ∪ LineTerminator (ECMAScript, no 'u' flag)
_SPACE = _union(
    _char("\t"), _char("\x0b"), _char("\x0c"), _char(" "),
    _char("\u00a0"), _char("\ufeff"), _char("\u1680"),
    Range("\u2000", "\u200a"), _char("\u202f"), _char("\u205f"), _char("\u3000"),
    _char("\n"), _char("\r"), _char("\u2028"), _char("\u2029"),
)
_LINE_TERMINATORS = _union(_char("\n"), _char("\r"), _char("\u2028"), _char("\u2029"))
_DOT = _not_char(_LINE_TERMINATORS)
_NON_WORD = _not_char(_WORD)


_CLASS_ESCAPES = {
    "d": _DIGIT,
    "D": _not_char(_DIGIT),
    "w": _WORD,
    "W": _not_char(_WORD),
    "s": _SPACE,
    "S": _not_char(_SPACE),
}

_CONTROL_ESCAPES = {
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "f": "\f",
    "v": "\v",
    "0": "\x00",
}

# word-boundary prefix/suffix languages (ASCII word chars)
# A word boundary is where word-ness flips across a position: for a body B with
# a leading \b, the prefix's last char and B's first char must have opposite
# word-ness (start-of-string counts as non-word); symmetric for a trailing \b.
_LEFT_BOUNDARY = _union(_char(""), _concat(ANY_STRING, _NON_WORD))   # ε ∪ Σ*·N  (prev non-word / start)
_LEFT_WORD = _concat(ANY_STRING, _WORD)                               # Σ*·W  (prev word)
_RIGHT_BOUNDARY = _union(_char(""), _concat(_NON_WORD, ANY_STRING))   # ε ∪ N·Σ*  (next non-word / end)
_RIGHT_WORD = _concat(_WORD, ANY_STRING)                              # W·Σ*  (next word)
_STARTS_WORD = _concat(_WORD, ANY_STRING)                             # body first char is word
_STARTS_NONWORD = _concat(_NON_WORD, ANY_STRING)                      # body first char is non-word
_ENDS_WORD = _concat(ANY_STRING, _WORD)                               # body last char is word
_ENDS_NONWORD = _concat(ANY_STRING, _NON_WORD)                        # body last char is non-word


def _boundary_terms(body, leading_b, anchored_start, trailing_b, anchored_end):
    """Return the concatenations of (prefix · body · suffix) for the given
    anchor/boundary combination.

    A word boundary means word-ness flips across the edge, so the body is split
    by its first-char / last-char word-ness and the adjacent prefix/suffix is
    constrained to the *opposite* word-ness. ``anchored_start``/``anchored_end``
    pin the boundary to the string edge (start/end count as non-word).
    """
    first_options = (True, False) if leading_b else (None,)
    last_options = (True, False) if trailing_b else (None,)
    terms = []
    for first_word in first_options:
        for last_word in last_options:
            b = body
            if leading_b:
                if anchored_start:
                    if not first_word:
                        continue  # start-of-string boundary needs a word char next
                    prefix = _char("")
                else:
                    prefix = _LEFT_BOUNDARY if first_word else _LEFT_WORD
                b = Intersect(b, _STARTS_WORD if first_word else _STARTS_NONWORD)
            else:
                prefix = _char("") if anchored_start else ANY_STRING
            if trailing_b:
                if anchored_end:
                    if not last_word:
                        continue  # end-of-string boundary needs a word char before
                    suffix = _char("")
                else:
                    suffix = _RIGHT_BOUNDARY if last_word else _RIGHT_WORD
                b = Intersect(b, _ENDS_WORD if last_word else _ENDS_NONWORD)
            else:
                suffix = _char("") if anchored_end else ANY_STRING
            terms.append(_concat(prefix, b, suffix))
    return terms

# Resource limit for quantifier repeat counts (spec §7.3(d) / E4): bounds the
# {{m}}/{{m,}}/{{m,n}} repeats to prevent the {{m,}} O(m) Concat expansion and
# unbounded Z3 Loop bounds from becoming a DoS surface. Aligned with the E4
# array limit (10000); legitimate rule quantifiers are far below this.
MAX_REPEAT = 10000


class _Parser:
    """Recursive-descent parser: ERDL safe-regex pattern → Z3 Re."""

    def __init__(self, pattern: str):
        self.p = pattern
        self.i = 0
        self.n = len(pattern)

    def _err(self, msg: str):
        raise RegexError(f"{msg} (at position {self.i}, pattern {self.p!r})")

    def _peek(self):
        return self.p[self.i] if self.i < self.n else None

    def _eof(self):
        return self.i >= self.n

    def _take(self, s: str) -> bool:
        """Consume literal prefix ``s`` if present; return whether consumed."""
        if self.p.startswith(s, self.i):
            self.i += len(s)
            return True
        return False

    # ------------------------------------------------------------------
    # entry: compile the pattern into the "unanchored substring search" language
    # ------------------------------------------------------------------
    def compile(self):
        if not isinstance(self.p, str):
            raise RegexError("match pattern must be a string")

        anchored_start = self._take("^")
        leading_b = self._take("\\b")
        body = self.parse_alt()
        trailing_b = self._take("\\b")
        anchored_end = self._take("$")

        if not self._eof():
            self._err("trailing garbage")

        return _union(*_boundary_terms(body, leading_b, anchored_start, trailing_b, anchored_end))

    # alternation: seq ('|' seq)*
    def parse_alt(self):
        branches = [self.parse_seq()]
        while self._peek() == "|":
            self.i += 1
            branches.append(self.parse_seq())
        return _union(*branches)

    # sequence: (atom quantifier?)*
    def parse_seq(self):
        parts = []
        while True:
            c = self._peek()
            if c is None or c in "|)$":
                break
            # trailing word boundary: stop here so compile() consumes it as the
            # whole-pattern trailing assertion (\b mid-pattern is unsupported)
            if c == "\\" and self.i + 1 < self.n and self.p[self.i + 1] == "b":
                break
            parts.append(self.parse_atom())
        return _concat(*parts)

    def parse_atom(self):
        c = self._peek()
        if c is None:
            self._err("unexpected end of pattern")

        if c == "\\":
            atom = self.parse_escape()
        elif c == ".":
            self.i += 1
            atom = _DOT
        elif c == "[":
            atom = self.parse_char_class()
        elif c == "(":
            atom = self.parse_group()
        elif c == "^":
            self._err("anchor '^' is only allowed at the start of the pattern")
        elif c in "*+?":
            self._err(f"quantifier {c!r} has nothing to repeat")
        elif c == "}":
            self._err("unmatched '}'")
        else:
            self.i += 1
            atom = _char(c)

        return self.apply_quantifier(atom)

    def apply_quantifier(self, atom):
        c = self._peek()
        if c == "*":
            self.i += 1
            self._skip_lazy()
            return Star(atom)
        if c == "+":
            self.i += 1
            self._skip_lazy()
            return Plus(atom)
        if c == "?":
            self.i += 1
            self._skip_lazy()
            return Option(atom)
        if c == "{":
            q = self.try_brace_quantifier()
            if q is not None:
                lo, hi = q
                if lo > MAX_REPEAT:
                    self._err(f"quantifier lower bound {lo} exceeds the limit {MAX_REPEAT}")
                if hi is not None:
                    if hi > MAX_REPEAT:
                        self._err(f"quantifier upper bound {hi} exceeds the limit {MAX_REPEAT}")
                    if lo > hi:
                        self._err(f"quantifier {{m,n}} requires m <= n (got {lo} > {hi})")
                    return Loop(atom, lo, hi)
                # {m,} → m or more, encoded lazily as (atom^m) · (atom*) — avoids
                # the O(m) Concat expansion that made {m,} a compile-time DoS.
                return _concat(Loop(atom, lo, lo), Star(atom))
            # bare '{' is a literal (JS treats invalid {…} as literal)
        return atom

    def _skip_lazy(self):
        if self._peek() == "?":
            self.i += 1

    def try_brace_quantifier(self):
        """Parse {m}, {m,}, {m,n} at self.i (self.p[self.i] == '{'); return (lo, hi) or None."""
        j = self.i + 1
        lo = self._read_digits(j)
        if lo is None:
            return None
        j += len(lo)
        lo = int(lo)
        if j < self.n and self.p[j] == "}":
            self.i = j + 1
            return (lo, lo)
        if j < self.n and self.p[j] == ",":
            j += 1
            if j < self.n and self.p[j] == "}":
                self.i = j + 1
                return (lo, None)
            hi = self._read_digits(j)
            if hi is None:
                return None
            j += len(hi)
            if j < self.n and self.p[j] == "}":
                self.i = j + 1
                return (lo, int(hi))
        return None

    def _read_digits(self, j):
        k = j
        while k < self.n and self.p[k].isdigit():
            k += 1
        return self.p[j:k] if k > j else None

    def parse_escape(self):
        # self.p[self.i] == '\\'
        self.i += 1
        if self._eof():
            self._err("trailing backslash")
        c = self.p[self.i]
        self.i += 1

        if c in _CLASS_ESCAPES:
            return _CLASS_ESCAPES[c]
        if c in _CONTROL_ESCAPES:
            return _char(_CONTROL_ESCAPES[c])
        if c in "123456789":
            self._err(f"backreference \\{c} is not allowed (non-regular)")
        if c == "k" and self._peek() == "<":
            self._err("named backreference \\k<…> is not allowed (non-regular)")
        if c == "b":
            self._err("\\b is only allowed at the start/end of the pattern")
        if c == "B":
            self._err("\\B is not supported")
        if c == "x":
            return _char(self._read_hex(2))
        if c == "u":
            return _char(self._read_hex(4))
        # escaped metachar or any other char → literal (JS non-u semantics)
        return _char(c)

    def _read_hex(self, k):
        s = self.p[self.i : self.i + k]
        if len(s) != k or not all(ch in "0123456789abcdefABCDEF" for ch in s):
            self._err("invalid hex escape")
        self.i += k
        return chr(int(s, 16))

    def parse_char_class(self):
        # self.p[self.i] == '['
        self.i += 1
        negate = False
        if self._peek() == "^":
            negate = True
            self.i += 1

        items = []
        while not self._eof() and self._peek() != "]":
            items.append(self.parse_class_item())

        if self._eof():
            self._err("unterminated character class")
        self.i += 1  # consume ']'

        if not items:
            self._err("empty character class")
        cls = _union(*items)
        if negate:
            return _not_char(cls)
        return cls

    def parse_class_item(self):
        c = self._peek()
        if c == "\\":
            self.i += 1
            if self._eof():
                self._err("trailing backslash in class")
            e = self.p[self.i]
            self.i += 1
            if e in _CLASS_ESCAPES:
                return _CLASS_ESCAPES[e]
            if e in _CONTROL_ESCAPES:
                return _char(_CONTROL_ESCAPES[e])
            if e in "123456789":
                self._err(f"backreference \\{e} is not allowed (non-regular)")
            return _char(e)

        lo = self._read_class_char()
        if self._peek() == "-" and self.i + 1 < self.n and self.p[self.i + 1] != "]":
            self.i += 1  # consume '-'
            hi = self._read_class_char()
            if ord(lo) > ord(hi):
                self._err("invalid range (start > end)")
            return Range(lo, hi)
        return _char(lo)

    def _read_class_char(self):
        if self._eof():
            self._err("unterminated character class")
        c = self.p[self.i]
        self.i += 1
        return c

    def parse_group(self):
        # self.p[self.i] == '('
        self.i += 1
        if self._peek() == "?":
            nxt = self.p[self.i + 1] if self.i + 1 < self.n else None
            if nxt == ":":
                self.i += 2  # non-capturing group (?:…)
            elif nxt == "=" or nxt == "!":
                self._err(f"lookahead (?{nxt} is not allowed (non-regular)")
            elif nxt == "<":
                after = self.p[self.i + 2] if self.i + 2 < self.n else None
                if after in ("=", "!"):
                    self._err(f"lookbehind (?<{after} is not allowed (non-regular)")
                # named capturing group (?<name>…) — regular; skip the name
                gt = self.p.find(">", self.i + 2)
                if gt == -1:
                    self._err("unterminated named group")
                self.i = gt + 1
            elif nxt == ">":
                self._err("atomic group (?> is not allowed")
            elif nxt == "(":
                self._err("conditional (?( is not allowed")
            else:
                self._err(f"unsupported group (?{nxt}")
        # else: plain capturing group — capture semantics irrelevant to membership

        inner = self.parse_alt()
        if self._peek() != ")":
            self._err("unterminated group")
        self.i += 1
        return inner


def compile_match(pattern: str):
    """Compile an ERDL ``match`` pattern into a Z3 regular expression.

    The returned regex R encodes ``RegExp(pattern).test(s)``: a string ``s``
    satisfies the rule's ``match`` condition iff ``InRe(s, R)`` holds.

    Raises :class:`RegexError` for patterns outside the safe-regex subset.
    """
    return _Parser(pattern).compile()
