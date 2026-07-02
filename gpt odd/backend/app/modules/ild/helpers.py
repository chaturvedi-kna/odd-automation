import json
import re
from typing import Any


def parse_imsi_value(value: Any) -> int:
    if value is None:
        raise ValueError("IMSI value cannot be None")

    if isinstance(value, int):
        return value

    value_str = str(value).strip()

    if not value_str:
        raise ValueError("IMSI value cannot be empty")

    return int(float(value_str))


def parse_range(range_value: str) -> tuple[int, int]:
    parts = [x.strip() for x in range_value.split("-")]

    if len(parts) != 2:
        raise ValueError(f"Invalid range format: {range_value}")

    start_addr = parse_imsi_value(parts[0])
    end_addr = parse_imsi_value(parts[1])

    if start_addr > end_addr:
        raise ValueError("Range start cannot be greater than end")

    return start_addr, end_addr


def normalize_text(value: str) -> str:
    return value.strip("_")