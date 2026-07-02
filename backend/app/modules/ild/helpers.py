"""
Helpers shared across ILD modules.

Scope filtering (single source of truth — do NOT reimplement elsewhere):
* PRR  : rule NAME **contains** any of PRR_SCOPE_SUFFIXES  (case-insensitive)
* RBAR : DESTINATION **ends with** any of RBAR_SCOPE_SUFFIXES (case-insensitive)
Out-of-scope rows are passed through / skipped silently (no log, no DB record).
"""

from decimal import Decimal, InvalidOperation

from app.core.config import settings


def _suffixes(raw: str) -> list[str]:
    return [s.strip().lower() for s in raw.split(",") if s.strip()]


def in_prr_scope(name: str | None) -> bool:
    """True when the PRR rule name CONTAINS any configured suffix."""
    nl = (name or "").lower()
    if not nl:
        return False
    return any(suf in nl for suf in _suffixes(settings.PRR_SCOPE_SUFFIXES))


def in_rbar_scope(destination: str | None) -> bool:
    """True when the RBAR destination ENDS WITH any configured suffix."""
    dl = (destination or "").lower()
    if not dl:
        return False
    return any(dl.endswith(suf) for suf in _suffixes(settings.RBAR_SCOPE_SUFFIXES))


def _parse_number(value: str) -> int:
    """
    Safely parse integer or scientific-notation values without
    floating-point precision loss.

    Examples:
        "1234"          -> 1234
        "4.0584E+14"    -> 405840000000000
    """
    return int(Decimal(value.strip()))


def parse_range(range_str: str) -> tuple[int, int]:
    """
    Parse a range string into (start_addr, end_addr).

    Supported formats:
        1234-5678
        1234–5678      (en dash)
        1234—5678      (em dash)
        1234 5678      (single or multiple spaces)
        4.0584E+14-4.1E+14
        1234           (single value)

    Returns:
        (start_addr, end_addr)

    Raises:
        ValueError
            If the range cannot be parsed or start > end.
    """

    if range_str is None:
        raise ValueError("Range cannot be None")

    # Normalize whitespace
    s = " ".join(range_str.strip().split())

    # ------------------------------------------------------------
    # Space separated values
    # ------------------------------------------------------------
    parts = s.split()
    if len(parts) == 2:
        try:
            start = _parse_number(parts[0])
            end = _parse_number(parts[1])

            if start > end:
                raise ValueError(
                    f"Invalid range '{range_str}': start ({start}) > end ({end})"
                )

            return start, end

        except (InvalidOperation, ValueError):
            pass

    # ------------------------------------------------------------
    # Dash separated values
    # ------------------------------------------------------------
    for sep in ("-", "\u2013", "\u2014"):  # -, en dash, em dash
        if sep in s:
            left, _, right = s.partition(sep)

            left = left.strip()
            right = right.strip()

            if left and right:
                try:
                    start = _parse_number(left)
                    end = _parse_number(right)

                    if start > end:
                        raise ValueError(
                            f"Invalid range '{range_str}': start ({start}) > end ({end})"
                        )

                    return start, end

                except (InvalidOperation, ValueError):
                    continue

    # ------------------------------------------------------------
    # Single value
    # ------------------------------------------------------------
    try:
        value = _parse_number(s)
        return value, value

    except (InvalidOperation, ValueError):
        raise ValueError(f"Cannot parse range string: {range_str!r}")