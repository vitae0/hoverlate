"""Pure screen-coordinate helpers, independent of display libraries."""


def region_around(x: int, y: int, monitor: dict, *, width: int = 520, height: int = 220) -> dict:
    """Return a non-empty capture rectangle clamped to a virtual display.

    Monitor is an MSS monitor mapping with left/top/width/height keys.
    Supports monitors whose origin has negative coordinates.
    """
    ml, mt = int(monitor["left"]), int(monitor["top"])
    mw, mh = int(monitor["width"]), int(monitor["height"])
    if mw <= 0 or mh <= 0 or width <= 0 or height <= 0:
        raise ValueError("Monitor and capture dimensions must be positive")
    w, h = min(width, mw), min(height, mh)
    left = min(max(x - w // 2, ml), ml + mw - w)
    top = min(max(y - h // 2, mt), mt + mh - h)
    return {"left": left, "top": top, "width": w, "height": h}
