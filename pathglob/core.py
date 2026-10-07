r"""A glob style path matching kernel (standard library only).

A pattern describes a whole path with these elements:

  /        separates two components of the path and is matched literally
  ?        exactly one character, never a separator
  *        zero or more characters, none of them a separator
  **       a whole component of two or more stars; it matches zero or more
           characters, separators included, and it swallows the separator
           that follows it when it matched no character at all
  [abc]    exactly one character of the set, never a separator; [a-z] writes
           a range, a '-' first or last inside the set is a literal, and
           [!abc] or [^abc] takes the complement of the set
  \x       the character x itself, with its wildcard meaning removed

Matching is exhaustive with backtracking: a star is retried with every run
length until the rest of the pattern matches, and the answer for a pair of
positions is remembered.  Both the pattern and the path are normalised before
they are compared, so repeated separators collapse and leading, trailing and
'.' components disappear.

The kernel is deterministic and free of side effects: the same pattern and the
same path always answer the same way, whatever order the alternatives are
explored in.
"""

SEPARATOR = "/"
COMPLEMENT_LEADERS = "!^"


class GlobError(Exception):
    """Base class of the errors raised by this module."""


class PatternSyntaxError(GlobError):
    """The pattern cannot be parsed."""


def fold(text, case_sensitive):
    """The form of text used when two characters are compared."""
    return text if case_sensitive else text.casefold()


def syntax_error(pattern, index, message):
    """Build the error raised for a malformed pattern."""
    return PatternSyntaxError("%s at %d in %r" % (message, index, pattern))


def split_components(pattern):
    """The text between unescaped separators, escapes left in place."""
    parts = []
    current = []
    index = 0
    while index < len(pattern):
        ch = pattern[index]
        if ch == "\\" and index + 1 < len(pattern):
            current.append(ch)
            current.append(pattern[index + 1])
            index += 2
            continue
        if ch == SEPARATOR:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
        index += 1
    parts.append("".join(current))
    return parts


def normalize(path):
    """Collapse repeated separators and drop empty and '.' components."""
    parts = [part for part in split_components(path) if part not in ("", ".")]
    return SEPARATOR.join(parts)


def parse_class(pattern, start):
    """Parse the character class that starts at pattern[start].

    Returns the class token and the index just after the closing bracket.
    """
    index = start + 1
    negated = False
    if index < len(pattern) and pattern[index] in COMPLEMENT_LEADERS:
        negated = True
        index += 1
    literals = set()
    ranges = []
    while True:
        if index == len(pattern):
            raise syntax_error(pattern, start, "unterminated character class")
        ch = pattern[index]
        if ch == "]":
            index += 1
            break
        if ch == "\\":
            if index + 1 == len(pattern):
                raise syntax_error(pattern, index, "a backslash cannot end a pattern")
            literals.add(pattern[index + 1])
            index += 2
            continue
        if ch == SEPARATOR:
            raise syntax_error(pattern, index, "a character class cannot hold a separator")
        if index + 2 < len(pattern) and pattern[index + 1] == "-" and pattern[index + 2] != "]":
            high = pattern[index + 2]
            if ord(high) < ord(ch):
                raise syntax_error(pattern, index, "character range is out of order")
            ranges.append((ch, high))
            index += 3
            continue
        literals.add(ch)
        index += 1
    if not literals and not ranges:
        raise syntax_error(pattern, start, "empty character class")
    return ("class", (frozenset(literals), tuple(ranges)), negated), index


def class_matches(terms, negated, ch, case_sensitive):
    """True when ch belongs to a parsed character class."""
    literals, ranges = terms
    target = fold(ch, case_sensitive)
    hit = False
    for item in literals:
        if fold(item, case_sensitive) == target:
            hit = True
            break
    if not hit:
        for low, high in ranges:
            if fold(low, case_sensitive) <= target <= fold(high, case_sensitive):
                hit = True
                break
    return hit != negated


def tokenize(pattern):
    """Turn a normalised pattern into a tuple of tokens.

    Token kinds: ``sep`` one separator, ``lit`` one literal character,
    ``any`` one character other than a separator, ``class`` one character of
    a character class, ``star`` a run of characters without a separator and
    ``globstar`` a whole component of stars carrying the flag that tells
    whether the separator behind it may be swallowed.
    """
    tokens = []
    index = 0
    while index < len(pattern):
        ch = pattern[index]
        if ch == "\\":
            if index + 1 == len(pattern):
                raise syntax_error(pattern, index, "a backslash cannot end a pattern")
            tokens.append(("lit", pattern[index + 1]))
            index += 2
            continue
        if ch == SEPARATOR:
            tokens.append(("sep",))
            index += 1
            continue
        if ch == "?":
            tokens.append(("any",))
            index += 1
            continue
        if ch == "*":
            end = index
            while end < len(pattern) and pattern[end] == "*":
                end += 1
            opens = not tokens or tokens[-1] == ("sep",)
            closes = end == len(pattern) or pattern[end] == SEPARATOR
            globstar = opens and closes and end - index > 1
            tokens.append(("globstar",) if globstar else ("star",))
            index = end
            continue
        if ch == "[":
            token, index = parse_class(pattern, index)
            tokens.append(token)
            continue
        tokens.append(("lit", ch))
        index += 1
    marked = []
    for position, token in enumerate(tokens):
        if token == ("globstar",):
            following = tokens[position + 1] if position + 1 < len(tokens) else None
            marked.append(("globstar", following == ("sep",)))
        else:
            marked.append(token)
    return tuple(marked)


class Matcher:
    """Matches a token tuple against the characters of one path.

    The answer for a pair of positions is remembered, so a pattern with
    several stars stays cheap instead of retrying the same suffix again and
    again.
    """

    def __init__(self, tokens, text, case_sensitive):
        self.tokens = tokens
        self.text = text
        self.case_sensitive = case_sensitive
        self.memo = {}

    def run(self, token_index, char_index):
        """True when tokens[token_index:] matches text[char_index:] exactly."""
        key = (token_index, char_index)
        if key in self.memo:
            return self.memo[key]
        tokens = self.tokens
        text = self.text
        if token_index == len(tokens):
            result = char_index == len(text)
        else:
            token = tokens[token_index]
            kind = token[0]
            if kind == "star":
                result = self.run_star(token_index, char_index)
            elif kind == "globstar":
                result = self.run_globstar(token, token_index, char_index)
            elif kind == "sep":
                result = (char_index < len(text) and text[char_index] == SEPARATOR
                          and self.run(token_index + 1, char_index + 1))
            elif kind == "any":
                result = (char_index < len(text)
                          and text[char_index] != SEPARATOR
                          and self.run(token_index + 1, char_index + 1))
            elif kind == "lit":
                result = (char_index < len(text)
                          and fold(token[1], self.case_sensitive) == fold(text[char_index], self.case_sensitive)
                          and self.run(token_index + 1, char_index + 1))
            elif kind == "class":
                result = (char_index < len(text) and text[char_index] != SEPARATOR
                          and class_matches(token[1], token[2], text[char_index], self.case_sensitive)
                          and self.run(token_index + 1, char_index + 1))
            else:
                raise GlobError("unknown token %r" % (kind,))
        self.memo[key] = result
        return result

    def run_star(self, token_index, char_index):
        """A star takes zero or more characters that are not separators."""
        while True:
            if self.run(token_index + 1, char_index):
                return True
            if char_index == len(self.text) or self.text[char_index] == SEPARATOR:
                return False
            char_index += 1

    def run_globstar(self, token, token_index, char_index):
        """A globstar takes zero or more characters, separators included."""
        if self.run(token_index + 1, char_index):
            return True
        if token[1] and self.run(token_index + 2, char_index):
            return True
        while char_index < len(self.text):
            char_index += 1
            if self.run(token_index + 1, char_index):
                return True
        return False


class Glob:
    """A compiled path pattern."""

    def __init__(self, source, tokens, case_sensitive=True):
        self.source = source
        self.tokens = tokens
        self.case_sensitive = case_sensitive

    def matches(self, path):
        """True when the pattern matches the whole path."""
        if not isinstance(path, str):
            raise TypeError("the path must be a string")
        matcher = Matcher(self.tokens, normalize(path), self.case_sensitive)
        return matcher.run(0, 0)

    def filter(self, paths):
        """The given paths that match, in order and without repetitions."""
        return collect_paths([self], paths)

    def __repr__(self):
        return "Glob(%r, case_sensitive=%r)" % (self.source, self.case_sensitive)


def collect_paths(patterns, paths):
    """Paths matched by at least one pattern, in input order, once each."""
    result = []
    seen = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        if any(pattern.matches(path) for pattern in patterns):
            result.append(path)
    return result


def compile_pattern(pattern, case_sensitive=True):
    """Compile a path pattern into a Glob, or raise PatternSyntaxError."""
    if not isinstance(pattern, str):
        raise TypeError("the pattern must be a string")
    tokens = tokenize(normalize(pattern))
    if not tokens:
        raise PatternSyntaxError("%r carries no component" % (pattern,))
    return Glob(pattern, tokens, bool(case_sensitive))


def matches(pattern, path, case_sensitive=True):
    """True when the pattern matches the whole path."""
    return compile_pattern(pattern, case_sensitive).matches(path)


def match_any(patterns, path, case_sensitive=True):
    """True when at least one of the patterns matches the path."""
    return any(matches(pattern, path, case_sensitive) for pattern in patterns)


def filter_paths(patterns, paths, case_sensitive=True):
    """Paths matched by at least one pattern, in input order, once each."""
    compiled = [compile_pattern(pattern, case_sensitive) for pattern in patterns]
    return collect_paths(compiled, paths)
