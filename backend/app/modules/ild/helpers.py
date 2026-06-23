"""
Helpers shared across ILD modules.
"""


def parse_range(range_str: str) -> tuple[int, int]:
    """
    Parse a range string into (start_addr, end_addr) as ints.

    Accepted formats:
        "1234-5678"          standard hyphen
        "1234–5678"          em-dash (copy-paste from docs)
        "1234 5678"          space separator
        "1234:5678"          colon separator
        "4.0584E+14-4.1E+14" scientific notation
        "1234"               single value → start == end
    """
    s = range_str.strip()
    for sep in ("-", "\u2013", "\u2014", " ", ":"):
        if sep in s:
            left, _, right = s.partition(sep)
            left = left.strip()
            right = right.strip()
            if left and right:
                try:
                    return int(float(left)), int(float(right))
                except (ValueError, OverflowError):
                    continue
    # Single value
    try:
        val = int(float(s))
        return val, val
    except (ValueError, OverflowError):
        raise ValueError(f"Cannot parse range string: {range_str!r}")
