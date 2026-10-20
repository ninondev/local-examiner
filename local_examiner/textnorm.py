# Copyright (c) 2026 Ninon
# SPDX-License-Identifier: MIT
"""Canonical JSON and IEEE-754 binary64 conversion used for capsule digests."""

from __future__ import annotations
import json
import struct
from typing import Any


def _reject_floats(obj: Any) -> None:
    if isinstance(obj, float):
        raise ValueError('float in canonical payload — encode via f64_hex')
    if isinstance(obj, dict):
        for k, v in obj.items():
            _reject_floats(k)
            _reject_floats(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _reject_floats(v)


def canon_json(obj: Any) -> bytes:
    """Encode compact, key-sorted UTF-8 JSON. Raw floats are rejected."""
    _reject_floats(obj)
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode(
        'utf-8'
    )


def f64_hex(x: float) -> str:
    """Encode an IEEE-754 binary64 float as big-endian lowercase hex."""
    return struct.pack('>d', x).hex()


def f64_unhex(h: str) -> float:
    return struct.unpack('>d', bytes.fromhex(h))[0]


def hexify_floats(obj: Any) -> Any:
    """Recursively replace floats with a {"~f64": hex} object."""
    if isinstance(obj, float):
        return {'~f64': f64_hex(obj)}
    if isinstance(obj, dict):
        return {k: hexify_floats(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [hexify_floats(v) for v in obj]
    return obj
