"""Splat-driven terrain material for build_blend.py.

Weights come from out/splat_*.png (written by gen_splat.py), layer order and palette from
out/splat.json. Each layer gets two editable RGB nodes ("<layer> dark" / "<layer> light")
blended by world-space noise, so colors can be tuned in Blender without regenerating.
"""
import json
from pathlib import Path

import bpy


def srgb_to_linear(c: int) -> float:
    v = c / 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _rgb(nt, label: str, srgb, x: float, y: float):
    n = nt.nodes.new("ShaderNodeRGB")
    n.label = n.name = label
    n.outputs[0].default_value = (*(srgb_to_linear(c) for c in srgb), 1.0)
    n.location = (x, y)
    return n.outputs[0]


def _noise_fac(nt, x: float, y: float):
    """Two-scale world-space noise (0..1) used to mix each layer's dark/light color."""
    links = nt.links
    coord = nt.nodes.new("ShaderNodeTexCoord")
    coord.location = (x - 600, y)
    fac = None
    for i, (scale, detail) in enumerate([(0.03, 6.0), (0.35, 3.0)]):
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.name = nz.label = f"Paint_Noise_{'Large' if i == 0 else 'Small'}"
        nz.inputs["Scale"].default_value = scale
        nz.inputs["Detail"].default_value = detail
        nz.location = (x - 400, y - 220 * i)
        links.new(coord.outputs["Object"], nz.inputs["Vector"])
        if fac is None:
            fac = nz.outputs["Fac"]
            continue
        mix = nt.nodes.new("ShaderNodeMix")  # data_type FLOAT: inputs 0=fac, 2=A, 3=B
        mix.inputs[0].default_value = 0.35
        mix.location = (x - 200, y)
        links.new(fac, mix.inputs[2]); links.new(nz.outputs["Fac"], mix.inputs[3])
        fac = mix.outputs[0]
    rng = nt.nodes.new("ShaderNodeMapRange")
    rng.inputs["From Min"].default_value, rng.inputs["From Max"].default_value = 0.3, 0.7
    rng.location = (x, y)
    links.new(fac, rng.inputs["Value"])
    return rng.outputs["Result"]


def _weights(nt, out_dir: Path, images: list, x: float, y: float) -> list:
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    uv.location = (x - 450, y)
    socks = []
    for i, name in enumerate(images):
        tex = nt.nodes.new("ShaderNodeTexImage")
        img = bpy.data.images.load(str(out_dir / name))
        img.colorspace_settings.name = "Non-Color"
        tex.image, tex.interpolation, tex.extension = img, "Linear", "EXTEND"
        tex.name = tex.label = f"Splat_{i}"
        tex.location = (x - 250, y - 300 * i)
        nt.links.new(uv.outputs["UV"], tex.inputs["Vector"])
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        sep.location = (x, y - 300 * i)
        nt.links.new(tex.outputs["Color"], sep.inputs["Color"])
        socks += list(sep.outputs[:3])
    return socks


def painted_material(out_dir: Path) -> bpy.types.Material:
    cfg = json.loads((out_dir / "splat.json").read_text())
    mat = bpy.data.materials.new("Terrain_Painted")
    if hasattr(mat, "use_nodes"):
        mat.use_nodes = True
    nt, links = mat.node_tree, mat.node_tree.links
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.location = (1400, 0)
    fac = _noise_fac(nt, -200, 600)
    weights = _weights(nt, out_dir, cfg["images"], -200, -200)
    acc = None
    for i, (layer, w) in enumerate(zip(cfg["layers"], weights)):
        y = 900 - 260 * i
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"  # inputs 0=fac, 6=A, 7=B; output 2
        mix.name = mix.label = f"Layer_{layer['name']}"
        mix.location = (500, y)
        links.new(fac, mix.inputs[0])
        links.new(_rgb(nt, f"{layer['name']} dark", layer["dark"], 300, y), mix.inputs[6])
        links.new(_rgb(nt, f"{layer['name']} light", layer["light"], 300, y - 110), mix.inputs[7])
        sc = nt.nodes.new("ShaderNodeVectorMath")
        sc.operation = "SCALE"
        sc.location = (700, y)
        links.new(mix.outputs[2], sc.inputs[0]); links.new(w, sc.inputs["Scale"])
        if acc is None:
            acc = sc.outputs[0]
            continue
        add = nt.nodes.new("ShaderNodeVectorMath")
        add.operation = "ADD"
        add.location = (900 + 20 * i, y)
        links.new(acc, add.inputs[0]); links.new(sc.outputs[0], add.inputs[1])
        acc = add.outputs[0]
    links.new(acc, bsdf.inputs["Base Color"])
    wet = nt.nodes.new("ShaderNodeMath")  # water layers are the first two: glossy, rest matte
    wet.operation = "ADD"
    wet.location = (1000, -500)
    links.new(weights[0], wet.inputs[0]); links.new(weights[1], wet.inputs[1])
    rough = nt.nodes.new("ShaderNodeMath")
    rough.operation = "MULTIPLY_ADD"
    rough.inputs[1].default_value, rough.inputs[2].default_value = -0.8, 0.92
    rough.location = (1200, -500)
    links.new(wet.outputs[0], rough.inputs[0])
    links.new(rough.outputs[0], bsdf.inputs["Roughness"])
    return mat
