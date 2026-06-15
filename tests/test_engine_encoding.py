"""UTF-8 validation + lossless repair for engine source files —
``atomicshop.mitm.engines.encoding``.

Engine .py files and engine_config.toml must be UTF-8 (the interpreter and tomllib
require it). These tests pin the classifier and the lossless fixer against real byte
sequences, so expected results come from the bytes we write, not the implementation.

Run from the repo root:  python -m pytest tests/test_engine_encoding.py -v
"""
from atomicshop.mitm.engines import encoding


def _write(tmp_path, name, data: bytes) -> str:
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


# --- scan_engine_file: clean files return None ------------------------------

def test_clean_ascii_returns_none(tmp_path):
    path = _write(tmp_path, "parser.py", b"class Parser:\n    pass\n")
    assert encoding.scan_engine_file(path) is None


def test_clean_utf8_nonascii_returns_none(tmp_path):
    path = _write(tmp_path, "parser.py", "x = '''  # smart quote\n".encode("utf-8"))
    assert encoding.scan_engine_file(path) is None


def test_empty_file_returns_none(tmp_path):
    path = _write(tmp_path, "parser.py", b"")
    assert encoding.scan_engine_file(path) is None


# --- scan_engine_file: each problem class -----------------------------------

def test_utf8_bom_is_flagged(tmp_path):
    path = _write(tmp_path, "parser.py", b"\xef\xbb\xbfclass Parser:\n    pass\n")
    finding = encoding.scan_engine_file(path)
    assert [i.kind for i in finding.issues] == ["utf8_bom"]
    assert finding.issues[0].auto_fixable is True
    assert finding.needs_manual is False


def test_utf16_bom_is_flagged(tmp_path):
    path = _write(tmp_path, "parser.py", "class Parser:\n    pass\n".encode("utf-16"))
    finding = encoding.scan_engine_file(path)
    assert [i.kind for i in finding.issues] == ["utf16_bom"]
    assert finding.needs_manual is False


def test_coding_cookie_cp1255_is_flagged(tmp_path):
    body = b"# -*- coding: cp1255 -*-\nx = 1  # \x93hi\x94\nclass P:\n    pass\n"
    path = _write(tmp_path, "parser.py", body)
    finding = encoding.scan_engine_file(path)
    assert [i.kind for i in finding.issues] == ["coding_cookie"]
    assert finding.issues[0].auto_fixable is True
    assert finding.needs_manual is False


def test_stray_bytes_are_flagged_manual(tmp_path):
    # cp1252 smart quote 0x92 with no BOM and no cookie -> unknowable.
    path = _write(tmp_path, "parser.py", b"x = 1  # it\x92s\nclass P:\n    pass\n")
    finding = encoding.scan_engine_file(path)
    assert [i.kind for i in finding.issues] == ["non_utf8_bytes"]
    assert finding.issues[0].auto_fixable is False
    assert finding.needs_manual is True
    assert "0x92" in finding.issues[0].detail


def test_mixed_bom_and_stray_bytes(tmp_path):
    # UTF-8 BOM AND a stray cp1252 byte -> two issues, still needs manual.
    path = _write(tmp_path, "parser.py", b"\xef\xbb\xbfx = 1  # it\x92s\nclass P:\n    pass\n")
    finding = encoding.scan_engine_file(path)
    assert [i.kind for i in finding.issues] == ["utf8_bom", "non_utf8_bytes"]
    assert finding.needs_manual is True
