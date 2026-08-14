"""Map-only enclosed-white metric for choropleth QA.

Usage: uv run python scripts/map_holes.py path/to/figure.png [more.png ...]

Method:
1. Find large colored components (states are big blobs; text is small).
2. Union bbox = map region (legend excluded by area filter).
3. Flood-fill white from region border; unreachable white = holes INSIDE the map.
4. Report hole px + biggest components with centroids (water check).

Interpretation (calibrated 2026-08-04 against the UT/CO/WY/KS/TX/TN glitch):
- BROKEN geometry (per-feature simplification): ~60,000 enclosed px at
  2200px-wide render, with components in the 1,000-50,000 px range =
  state-sized tears. FAIL.
- CLEAN geometry (mapshaper topology-preserving): ~9,700 px at full render
  / ~600 px at explorer viewport, largest component < 300 px =
  antialiasing seams + legitimate water (Great Salt Lake). PASS.
Rule of thumb: largest single component > 1,000 px at full render means a
structural hole — do not commit the geometry.

Requires: numpy, Pillow, scipy (project venv has all three).
"""

import sys
from collections import deque

import numpy as np
from PIL import Image
from scipy import ndimage


def measure(path: str) -> int:
    img = Image.open(path).convert("RGB")
    a = np.array(img).astype(int)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    colored = ((mx - mn) > 30) & (mx < 245)

    lab, n = ndimage.label(colored)
    sizes = ndimage.sum(colored, lab, range(1, n + 1))
    big_ids = [i + 1 for i, s in enumerate(sizes) if s > 4000]
    states_mask = np.isin(lab, big_ids)
    ys, xs = states_mask.nonzero()
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    print(f"{path.split('/')[-1]}: {len(big_ids)} state blobs, map bbox=({x0},{y0})-({x1},{y1})")

    white = ((r > 245) & (g > 245) & (b > 245))[y0 : y1 + 1, x0 : x1 + 1]
    H, W = white.shape
    visited = np.zeros_like(white, dtype=bool)
    dq = deque()
    for x in range(W):
        for y in (0, H - 1):
            if white[y, x] and not visited[y, x]:
                dq.append((y, x))
                visited[y, x] = True
    for y in range(H):
        for x in (0, W - 1):
            if white[y, x] and not visited[y, x]:
                dq.append((y, x))
                visited[y, x] = True
    while dq:
        y, x = dq.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < H and 0 <= nx < W and white[ny, nx] and not visited[ny, nx]:
                visited[ny, nx] = True
                dq.append((ny, nx))
    holes = white & ~visited
    hlab, hn = ndimage.label(holes)
    hsizes = ndimage.sum(holes, hlab, range(1, hn + 1))
    big_holes = sorted([(int(s), i + 1) for i, s in enumerate(hsizes) if s > 50], reverse=True)
    print(f"  enclosed white INSIDE map: {holes.sum()} px in {hn} components")
    worst = 0
    for s, cid in big_holes[:12]:
        cy, cx = (hlab == cid).nonzero()
        print(f"    hole {s:>6} px at centroid ({int(cx.mean()) + x0},{int(cy.mean()) + y0})")
        worst = max(worst, s)
    if worst > 1000:
        print(f"  FAIL: largest component {worst} px > 1,000 — structural hole")
        return 1
    print("  PASS: no structural holes")
    return 0


if __name__ == "__main__":
    rc = 0
    for p in sys.argv[1:]:
        rc |= measure(p)
    sys.exit(rc)
