---
name: gpu-timing-mac
description: How to get trustworthy GPU ms on this Mac (M4 Pro) for Godot perf work; vsync'd --perf runs are DVFS-noisy and other agents share the GPU
metadata:
  type: reference
---

Godot `--perf` GPU times (main.gd PERF lines) with vsync on are unusable for small deltas: GPU clocks drop between frames (DVFS), so "no grass" measured slower than "grass" (2026-09-30). Add engine arg `--disable-vsync` before `--`: p50/p95 then agree within ~0.2 ms.

**Why:** parallel agents also run valley.tscn / Blender on the same GPU; timings jump 2x mid-run, and the measured value sometimes freezes (identical every frame) while another process holds the GPU.

**How to apply:** compare variants with `--disable-vsync`, check `ps aux | grep godot` is empty first, and prefer in-process A/B: valley.tscn `--perf --groundcover_debug=ab` toggles groundcover every 30 frames and prints paired-block cost (GROUNDCOVER_AB). See [[groundcover-cost-model]].
