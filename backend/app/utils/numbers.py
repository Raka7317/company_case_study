import re

_NUM_RE = re.compile(r"\(?-?\s*[₹$€£]?\s*-?\d[\d,]*(?:\.\d+)?\s*\)?")


def parse_number(raw: str):
    """Parse a currency/plain number string. Parentheses => negative.
    Returns None if it cannot be parsed."""
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    negative = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    s = re.sub(r"[₹$€£,]", "", s).strip()
    s = s.replace(" ", "")
    if s in ("", "-", "--"):
        return None
    try:
        val = float(s)
    except ValueError:
        return None
    return -val if negative else val


def find_numbers(text: str) -> list[float]:
    out = []
    for m in _NUM_RE.finditer(text):
        val = parse_number(m.group())
        if val is not None:
            out.append(val)
    return out
