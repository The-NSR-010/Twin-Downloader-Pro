"""Reusable advanced option normalization for both download engines."""
from __future__ import annotations


def split_lines(value: str) -> list[str]:
    return [line.strip() for line in value.replace(";", "\n").splitlines() if line.strip()]


def add_repeatable(args: list[str], flag: str, values: str) -> None:
    for value in split_lines(values):
        args.extend([flag, value])


def valid_size(value: str) -> bool:
    if not value:
        return True
    import re
    return bool(re.fullmatch(r"\d+(?:\.\d+)?(?:K|M|G|T|KiB|MiB|GiB|TiB)?", value, re.I))
