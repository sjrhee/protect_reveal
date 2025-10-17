def increment_numeric_string(s: str) -> str:
    """Increment a numeric string while preserving width (zero padding).

    Raises ValueError if the input is not a digit-only string.
    """
    if not s.isdigit():
        raise ValueError("data must be a numeric string")
    width = len(s)
    n = int(s) + 1
    return f"{n:0{width}d}"
