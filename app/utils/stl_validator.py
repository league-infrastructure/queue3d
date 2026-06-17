import struct


def validate_stl(file_bytes: bytes, max_size: int) -> tuple[bool, str]:
    """Validate that bytes plausibly represent an STL file.

    The print queue is admin-moderated (every job is reviewed with a 3D preview
    before it prints), so this leans toward accepting real models rather than
    rejecting them on strict structural nits — it only needs to weed out files
    that clearly are not STL.

    Returns (is_valid, error_message).
    """
    if len(file_bytes) > max_size:
        return False, f"File exceeds maximum size of {max_size // (1024 * 1024)} MB"

    if len(file_bytes) < 84:
        return False, "File too small to be a valid STL"

    # ASCII STL: characteristic keywords, matched case-insensitively and
    # tolerant of leading whitespace.
    if file_bytes[:512].lstrip().lower().startswith(b"solid"):
        text = file_bytes.decode("ascii", errors="ignore").lower()
        if "facet" in text and "vertex" in text and "endsolid" in text:
            return True, ""
        # Some binary STLs also begin with "solid" — fall through to binary check.

    # Binary STL: 80-byte header + uint32 triangle count + 50 bytes per triangle.
    # Accept the exact size OR extra trailing bytes (some exporters pad the file),
    # rather than requiring a byte-exact match that rejects otherwise-valid files.
    num_triangles = struct.unpack("<I", file_bytes[80:84])[0]
    expected_size = 84 + (num_triangles * 50)

    if num_triangles > 0 and len(file_bytes) >= expected_size:
        return True, ""

    return False, "File does not match STL format (invalid structure)"
