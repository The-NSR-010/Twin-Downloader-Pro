from __future__ import annotations

import re

HEX32 = re.compile(r"^[0-9a-fA-F]{32}$")


def _clean(value: str) -> str:
    return value.strip().strip('"').strip("'")


def validate_hex32(value: str, label: str) -> str:
    value = _clean(value)
    if not HEX32.fullmatch(value):
        raise ValueError(f"{label} must be exactly 32 hexadecimal characters (128-bit).")
    return value.lower()


def parse_key_specs(text: str, separate_kid: str = "", separate_key: str = "") -> list[str]:
    """Parse supported authorized key forms.

    Supported forms:
      1) separate_kid + separate_key fields
      2) KID:KEY on one line
      3) multiple KID:KEY lines
      4) KEY-only on one line (supported by N_m3u8DL-RE when all tracks share it)

    Blank lines, commas and semicolons are accepted as separators for convenience.
    """
    raw = _clean(text)
    result: list[str] = []

    if separate_kid.strip() or separate_key.strip():
        if not separate_kid.strip() or not separate_key.strip():
            raise ValueError("Enter both KID/track ID and key when using separate fields.")
        kid = _clean(separate_kid)
        key = validate_hex32(separate_key, "Key")
        if not (kid.isdigit() or HEX32.fullmatch(kid)):
            raise ValueError("KID must be a decimal track ID or 32 hexadecimal characters.")
        result.append(f"{kid}:{key}")

    if raw:
        # Permit one or more entries separated by newlines, commas or semicolons.
        entries = [x.strip() for x in re.split(r"[\r\n,;]+", raw) if x.strip()]
        for entry in entries:
            entry = _clean(entry)
            if ":" in entry:
                kid, key = entry.split(":", 1)
                kid = _clean(kid)
                key = validate_hex32(key, "Key")
                if not (kid.isdigit() or HEX32.fullmatch(kid)):
                    raise ValueError("Each KID must be a decimal track ID or 32 hexadecimal characters.")
                result.append(f"{kid}:{key}")
            else:
                # Key-only is intentionally accepted for N_m3u8DL-RE; the caller
                # decides whether the selected backend can use it.
                result.append(validate_hex32(entry, "Key"))

    # preserve order while removing duplicates
    return list(dict.fromkeys(result))
