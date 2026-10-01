"""Small math helpers shared by the spruce generator modules (Blender 5.2, headless)."""
from __future__ import annotations

import math


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def smoothstep(a: float, b: float, x: float) -> float:
    t = clamp((x - a) / (b - a))
    return t * t * (3.0 - 2.0 * t)


def hash01(a: int, b: int) -> float:
    """Deterministic pseudo random 0..1 for bark strip noise."""
    return (math.sin(a * 127.1 + b * 311.7) * 43758.5453) % 1.0


def shape(s: float, a: float = 0.75, b: float = 1.0) -> float:
    """Leaf-like 0..1 profile: 0 at both ends, 1 at its widest (s = a / (a + b))."""
    peak = a / (a + b)
    norm = peak ** a * (1.0 - peak) ** b
    return (max(s, 0.0) ** a * max(1.0 - s, 0.0) ** b) / norm
