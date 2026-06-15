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


# --- scan_engine_directory --------------------------------------------------

def test_scan_directory_flags_py_and_config_only(tmp_path):
    _write(tmp_path, "parser.py", b"class P:\n    pass\n")                 # clean
    _write(tmp_path, "responder.py", b"\xef\xbb\xbfclass R:\n    pass\n")  # utf8 bom
    _write(tmp_path, "engine_config.toml", b"\xef\xbb\xbf[engine]\n")      # utf8 bom
    _write(tmp_path, "notes.txt", b"\xef\xbb\xbfignored\n")                # out of scope
    findings = encoding.scan_engine_directory(str(tmp_path))
    flagged = sorted(__import__("os").path.basename(f.path) for f in findings)
    assert flagged == ["engine_config.toml", "responder.py"]


def test_scan_directory_clean_returns_empty(tmp_path):
    _write(tmp_path, "parser.py", b"class P:\n    pass\n")
    assert encoding.scan_engine_directory(str(tmp_path)) == []


# --- format_findings --------------------------------------------------------

def test_format_findings_groups_and_marks(tmp_path):
    eng = tmp_path / "argentinall"
    eng.mkdir()
    bom = _write(eng, "responder.py", b"\xef\xbb\xbfx = 1  # it\x92s\nclass R:\n    pass\n")
    findings = [encoding.scan_engine_file(bom)]
    report = encoding.format_findings(findings)
    assert "Engine 'argentinall'" in report
    assert "responder.py" in report
    assert "(auto-fixable)" in report          # the BOM
    assert "manual" in report                  # the stray byte
    assert "python tools/fix_engine_encoding.py" in report


# --- fix_file_lossless ------------------------------------------------------

def test_fix_already_clean(tmp_path):
    path = _write(tmp_path, "parser.py", b"class P:\n    pass\n")
    assert encoding.fix_file_lossless(path) is encoding.FixOutcome.ALREADY_CLEAN


def test_fix_strips_utf8_bom_and_backs_up_and_clears_pycache(tmp_path):
    pycache = tmp_path / "__pycache__"
    pycache.mkdir()
    (pycache / "parser.cpython-313.pyc").write_bytes(b"stale")
    path = _write(tmp_path, "parser.py", b"\xef\xbb\xbfclass P:\n    pass\n")
    outcome = encoding.fix_file_lossless(path)
    assert outcome is encoding.FixOutcome.FIXED
    with open(path, "rb") as f:
        new = f.read()
    assert new == b"class P:\n    pass\n"               # BOM gone, body intact
    assert (tmp_path / "parser.py.bak").read_bytes().startswith(b"\xef\xbb\xbf")
    assert not pycache.exists()                          # stale bytecode cleared
    assert encoding.scan_engine_file(path) is None       # now clean


def test_fix_transcodes_utf16(tmp_path):
    path = _write(tmp_path, "parser.py", "class P:\n    pass\n".encode("utf-16"))
    assert encoding.fix_file_lossless(path) is encoding.FixOutcome.FIXED
    with open(path, "rb") as f:
        assert f.read() == b"class P:\n    pass\n"


def test_fix_rewrites_coding_cookie_to_utf8(tmp_path):
    body = b"# -*- coding: cp1255 -*-\nx = 1  # \x93q\x94\nclass P:\n    pass\n"
    path = _write(tmp_path, "parser.py", body)
    assert encoding.fix_file_lossless(path) is encoding.FixOutcome.FIXED
    with open(path, "rb") as f:
        new = f.read()
    new.decode("utf-8")                                  # now valid UTF-8
    assert b"coding: utf-8" in new
    assert "“" in new.decode("utf-8")               # cp1255 0x93 -> left double quote


def test_fix_stray_bytes_is_needs_manual_and_untouched(tmp_path):
    original = b"x = 1  # it\x92s\nclass P:\n    pass\n"
    path = _write(tmp_path, "parser.py", original)
    assert encoding.fix_file_lossless(path) is encoding.FixOutcome.NEEDS_MANUAL
    with open(path, "rb") as f:
        assert f.read() == original                      # not modified
    assert not (tmp_path / "parser.py.bak").exists()     # no backup written


def test_fix_mixed_strips_bom_but_still_needs_manual(tmp_path):
    path = _write(tmp_path, "parser.py", b"\xef\xbb\xbfx = 1  # it\x92s\nclass P:\n    pass\n")
    assert encoding.fix_file_lossless(path) is encoding.FixOutcome.NEEDS_MANUAL
    with open(path, "rb") as f:
        new = f.read()
    assert not new.startswith(b"\xef\xbb\xbf")           # BOM stripped (lossless)
    assert new == b"x = 1  # it\x92s\nclass P:\n    pass\n"  # stray byte preserved


def test_fix_preserves_crlf_newlines(tmp_path):
    path = _write(tmp_path, "parser.py", b"\xef\xbb\xbfa = 1\r\nb = 2\r\n")
    encoding.fix_file_lossless(path)
    with open(path, "rb") as f:
        assert f.read() == b"a = 1\r\nb = 2\r\n"          # CRLF intact, not doubled
