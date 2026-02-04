import struct


def validate_stl(file_bytes: bytes, max_size: int) -> tuple[bool, str]:
    """Validate that bytes represent a valid STL file.

    Returns (is_valid, error_message).
    """
    if len(file_bytes) > max_size:
        return False, f"File exceeds maximum size of {max_size // (1024 * 1024)} MB"

    if len(file_bytes) < 84:
        return False, "File too small to be a valid STL"

    # Check for ASCII STL
    if file_bytes[:5] == b"solid":
        try:
            text = file_bytes.decode("ascii", errors="ignore")
            if "facet normal" in text and "vertex" in text and "endsolid" in text:
                return True, ""
        except Exception:
            pass
        # Fall through to binary check (some binary STLs start with "solid")

    # Binary STL validation
    # Header: 80 bytes, triangle count: 4 bytes (uint32 LE)
    # Each triangle: 50 bytes (12 floats for normal + 3 vertices + 2 byte attribute)
    num_triangles = struct.unpack("<I", file_bytes[80:84])[0]
    expected_size = 84 + (num_triangles * 50)

    if len(file_bytes) == expected_size:
        return True, ""

    return False, "File does not match STL format (invalid structure)"
