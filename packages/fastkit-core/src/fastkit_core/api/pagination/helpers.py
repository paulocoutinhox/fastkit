def clamp_page_size(requested: int, default: int, maximum: int) -> int:
    if requested <= 0:
        return default

    return min(requested, maximum)
