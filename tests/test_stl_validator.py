import struct

from app.utils.stl_validator import validate_stl

MAX = 50 * 1024 * 1024

ASCII_STL = (
    b"solid x\n"
    b"facet normal 0 0 0\nouter loop\n"
    b"vertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\n"
    b"endloop\nendfacet\nendsolid x\n"
)


def _bin_stl(n, trailing=0):
    tri = struct.pack("<12fH", *([0.0] * 12), 0)
    return b"\x00" * 80 + struct.pack("<I", n) + tri * n + b"\x00" * trailing


def test_accepts_exact_binary():
    assert validate_stl(_bin_stl(2), MAX) == (True, "")


def test_accepts_binary_with_trailing_bytes():
    # Some exporters pad the file; this must not be rejected.
    assert validate_stl(_bin_stl(2, trailing=8), MAX)[0] is True


def test_accepts_binary_header_starting_with_solid():
    body = struct.pack("<I", 1) + struct.pack("<12fH", *([0.0] * 12), 0)
    data = b"solid" + b"\x00" * 75 + body + b"\x00" * 3
    assert validate_stl(data, MAX)[0] is True


def test_accepts_ascii_regardless_of_case():
    assert validate_stl(ASCII_STL, MAX)[0] is True
    assert validate_stl(ASCII_STL.upper(), MAX)[0] is True


def test_rejects_too_small():
    assert validate_stl(b"hi", MAX)[0] is False


def test_rejects_oversize():
    assert validate_stl(_bin_stl(1), max_size=10)[0] is False


def test_rejects_non_stl_garbage():
    # 0xFF header -> huge declared triangle count -> file far too short.
    assert validate_stl(b"\xff" * 200, MAX)[0] is False
