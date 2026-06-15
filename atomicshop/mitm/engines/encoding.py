"""UTF-8 validation and lossless repair for engine source files.

Engine .py files and engine_config.toml must be UTF-8 -- the interpreter and tomllib
require it. This module detects files that are not clean UTF-8 (decode as UTF-8 AND no
BOM), classifies each problem, and losslessly fixes the deterministic cases (BOM strip,
UTF-16 transcode, PEP 263 coding-cookie decode). Stray bytes with no encoding
declaration are reported only -- their intended character is unknowable.
"""
import enum
import io
import os
import re
import shutil
import tokenize
from dataclasses import dataclass

BOM_UTF8 = b"\xef\xbb\xbf"
BOM_UTF16_LE = b"\xff\xfe"
BOM_UTF16_BE = b"\xfe\xff"

_CODING_RE = re.compile(r"coding[:=]\s*[-\w.]+")


@dataclass
class Issue:
    kind: str          # 'utf8_bom' | 'utf16_bom' | 'coding_cookie' | 'non_utf8_bytes'
    detail: str        # human-readable description
    auto_fixable: bool


@dataclass
class Finding:
    path: str
    issues: list[Issue]

    @property
    def needs_manual(self) -> bool:
        return any(not issue.auto_fixable for issue in self.issues)


class FixOutcome(enum.Enum):
    ALREADY_CLEAN = "already_clean"
    FIXED = "fixed"
    NEEDS_MANUAL = "needs_manual"


def _declared_codec(raw: bytes) -> str | None:
    """The PEP 263 / BOM-declared codec if it is *not* UTF-8, else None."""
    try:
        enc, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
    except SyntaxError:
        return None
    return None if enc.replace("-", "").lower() in ("utf8", "utf8sig") else enc


def _decodes_cleanly(raw: bytes, codec: str) -> bool:
    try:
        raw.decode(codec)
        return True
    except (UnicodeDecodeError, LookupError):
        return False


def _context_snippet(raw: bytes, offset: int, radius: int = 20) -> str:
    start, end = max(0, offset - radius), min(len(raw), offset + radius)
    out = []
    for i in range(start, end):
        b = raw[i]
        if i == offset:
            out.append(f"<0x{b:02X}>")
        elif 0x20 <= b < 0x7F:
            out.append(chr(b))
        else:
            out.append(".")
    return '"' + "".join(out) + '"'


def scan_engine_file(path: str) -> Finding | None:
    """Return a Finding if the file is not clean UTF-8 (decodes as UTF-8 and no BOM)."""
    with open(path, "rb") as f:
        raw = f.read()
    if not raw:
        return None

    if raw.startswith(BOM_UTF16_LE) or raw.startswith(BOM_UTF16_BE):
        return Finding(path, [Issue("utf16_bom", "UTF-16 BOM at start of file", True)])

    issues: list[Issue] = []
    has_utf8_bom = raw.startswith(BOM_UTF8)
    if has_utf8_bom:
        issues.append(Issue("utf8_bom", "UTF-8 BOM at start of file", True))
    body = raw[len(BOM_UTF8):] if has_utf8_bom else raw

    decode_error = None
    try:
        body.decode("utf-8")
    except UnicodeDecodeError as exc:
        decode_error = exc
    if decode_error is None:
        return Finding(path, issues) if issues else None

    declared = _declared_codec(raw)
    if declared and _decodes_cleanly(raw, declared):
        issues.append(Issue("coding_cookie", f"declared coding cookie '{declared}', not UTF-8", True))
        return Finding(path, issues)

    file_off = decode_error.start + (len(BOM_UTF8) if has_utf8_bom else 0)
    detail = (f"invalid UTF-8 byte 0x{raw[file_off]:02X} at offset {file_off}: "
              f"{_context_snippet(raw, file_off)}")
    issues.append(Issue("non_utf8_bytes", detail, False))
    return Finding(path, issues)
