"""Shared image processing utilities."""

from collections import deque
from typing import Optional


def detect_background(image) -> Optional[tuple[int, int, int]]:
    """Detect the background color of an image (most common corner pixel).

    Returns an (r, g, b) tuple or None if detection fails.
    """
    try:
        from PIL import Image
    except ImportError:
        return None

    if not isinstance(image, Image.Image):
        return None

    corners = [
        image.getpixel((0, 0)),
        image.getpixel((image.width - 1, 0)),
        image.getpixel((0, image.height - 1)),
        image.getpixel((image.width - 1, image.height - 1)),
    ]
    from collections import Counter

    most_common = Counter(corners).most_common(1)
    return most_common[0][0] if most_common else None


def bfs_component(
    image, seed: tuple[int, int], tolerance: int = 10
) -> list[tuple[int, int]]:
    """Flood-fill (BFS) a connected component starting at `seed`.

    Args:
        image: PIL Image or similar with width/height/getpixel
        seed: (x, y) starting pixel
        tolerance: max color distance for a pixel to be included

    Returns:
        List of (x, y) pixel coordinates in the component.
    """
    try:
        from PIL import Image
    except ImportError:
        return []

    if not isinstance(image, Image.Image):
        return []

    w, h = image.width, image.height
    sx, sy = seed
    if not (0 <= sx < w and 0 <= sy < h):
        return []

    target_color = image.getpixel((sx, sy))

    def color_distance(c1, c2):
        return sum((a - b) ** 2 for a, b in zip(c1[:3], c2[:3])) ** 0.5

    visited = set()
    queue = deque([(sx, sy)])
    component = []

    while queue:
        x, y = queue.popleft()
        if (x, y) in visited:
            continue
        if not (0 <= x < w and 0 <= y < h):
            continue
        pixel = image.getpixel((x, y))
        if color_distance(target_color, pixel) > tolerance:
            continue
        visited.add((x, y))
        component.append((x, y))
        queue.extend([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)])

    return component
