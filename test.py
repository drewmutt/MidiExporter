# tadc_hammer_sharks.py
# Blender 5.0+ (works in 4.x too)
#
# Usage:
#   /path/to/Blender -b --python tadc_hammer_sharks.py -- --out /path/to/tadc_sharks.glb
#
# Generates two stylized “Digital Circus” hammerhead-ish sharks like your reference:
# - wide hammerhead, big side eyes, pouty lips, stubby fins, soft gradients-ish materials
# - exports a single .glb with both sharks

from __future__ import annotations

import sys
import math
import argparse
from dataclasses import dataclass
from typing import Tuple, List

import bpy


# ----------------------------
# CLI
# ----------------------------

def parse_args() -> argparse.Namespace:
    argv = []
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1 :]

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Output .glb path")
    return ap.parse_args(argv)


# ----------------------------
# Scene helpers
# ----------------------------

def clean_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    # Purge orphans a couple times (Blender can require repeats)
    for _ in range(3):
        try:
            bpy.ops.outliner.orphans_purge(do_recursive=True)
        except Exception:
            pass


def deselect_all() -> None:
    bpy.ops.object.select_all(action="DESELECT")


def shade_smooth(obj: bpy.types.Object) -> None:
    if obj.type != "MESH":
        return
    deselect_all()
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()
    obj.select_set(False)


def ensure_collection(name: str) -> bpy.types.Collection:
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def link_to_collection(obj: bpy.types.Object, col: bpy.types.Collection) -> None:
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)


def join_objects(objs: List[bpy.types.Object], name: str) -> bpy.types.Object:
    # Safe join: do not touch objects after join (they get removed)
    live = [o for o in objs if o and o.name in bpy.data.objects]
    if not live:
        raise RuntimeError("join_objects(): no live objects")

    deselect_all()
    for o in live:
        o.select_set(True)
    bpy.context.view_layer.objects.active = live[0]
    bpy.ops.object.join()

    out = bpy.context.view_layer.objects.active
    out.name = name

    deselect_all()
    out.select_set(True)
    bpy.context.view_layer.objects.active = out
    return out


# ----------------------------
# Materials (Principled socket names differ across Blender versions)
# ----------------------------

def _set_input_if_exists(node, names, value) -> bool:
    if isinstance(names, str):
        names = [names]
    for n in names:
        sock = node.inputs.get(n)
        if sock is not None:
            sock.default_value = value
            return True
    return False


def make_principled_material(name: str, rgba: Tuple[float, float, float, float], rough=0.55, spec=0.2) -> bpy.types.Material:
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)

    # NOTE: Blender 5 warns use_nodes will be removed in 6; still works now.
    # Avoid reading it (that triggers warnings). Just set it.
    try:
        mat.use_nodes = True
    except Exception:
        pass

    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links

    bsdf = nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.location = (0, 0)

    out = nodes.get("Material Output")
    if out is None:
        out = nodes.new("ShaderNodeOutputMaterial")
        out.location = (300, 0)

    if not out.inputs["Surface"].is_linked:
        links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    _set_input_if_exists(bsdf, "Base Color", rgba)
    _set_input_if_exists(bsdf, "Roughness", float(rough))
    _set_input_if_exists(bsdf, ["Specular", "Specular IOR Level"], float(spec))

    # Soft toon-ish look (lower spec, higher rough already)
    _set_input_if_exists(bsdf, "Subsurface", 0.0)
    _set_input_if_exists(bsdf, "Metallic", 0.0)

    return mat


def assign_mat(obj: bpy.types.Object, mat: bpy.types.Material) -> None:
    if obj.type != "MESH":
        return
    obj.data.materials.clear()
    obj.data.materials.append(mat)


# ----------------------------
# Model parameters
# ----------------------------

@dataclass(frozen=True)
class SharkStyle:
    name: str
    body_color: Tuple[float, float, float, float]
    belly_tint: Tuple[float, float, float, float]
    lip_color: Tuple[float, float, float, float]
    eye_white: Tuple[float, float, float, float]
    iris_color: Tuple[float, float, float, float]
    pupil_color: Tuple[float, float, float, float]
    tongue_color: Tuple[float, float, float, float]


@dataclass(frozen=True)
class SharkParams:
    # overall proportions
    body_len: float = 1.55
    body_w: float = 0.95
    body_h: float = 0.70

    # hammerhead width + eye pads
    head_w: float = 1.35
    head_len: float = 0.95
    head_h: float = 0.75

    # tail
    tail_len: float = 0.60
    tail_fin_h: float = 0.65
    tail_fin_w: float = 0.45

    # fins
    dorsal_h: float = 0.55
    dorsal_w: float = 0.12
    pectoral_len: float = 0.65
    pectoral_w: float = 0.20
    pectoral_h: float = 0.10

    # face
    eye_r: float = 0.20
    iris_r: float = 0.115
    pupil_r: float = 0.055
    mouth_w: float = 0.70
    mouth_h: float = 0.20
    mouth_depth: float = 0.16
    mouth_open: float = 0.065

    # goofy asymmetry
    cross_eye: float = 0.08  # pupil inward offset factor


# ----------------------------
# Builder
# ----------------------------

class TADCSharkBuilder:
    def __init__(self, params: SharkParams, style: SharkStyle, collection_name="TADC_Sharks"):
        self.p = params
        self.s = style
        self.col = ensure_collection(collection_name)

        self.mat_body  = make_principled_material(f"MAT_{style.name}_Body", style.body_color, rough=0.62, spec=0.12)
        self.mat_belly = make_principled_material(f"MAT_{style.name}_Belly", style.belly_tint, rough=0.70, spec=0.08)
        self.mat_lip   = make_principled_material(f"MAT_{style.name}_Lip", style.lip_color, rough=0.55, spec=0.10)
        self.mat_eye   = make_principled_material(f"MAT_{style.name}_Eye", style.eye_white, rough=0.35, spec=0.20)
        self.mat_iris  = make_principled_material(f"MAT_{style.name}_Iris", style.iris_color, rough=0.35, spec=0.18)
        self.mat_pupil = make_principled_material(f"MAT_{style.name}_Pupil", style.pupil_color, rough=0.40, spec=0.10)
        self.mat_tongue= make_principled_material(f"MAT_{style.name}_Tongue", style.tongue_color, rough=0.55, spec=0.06)

    def build(self, origin=(0.0, 0.0, 0.0), yaw_deg=0.0, add_tongue=False) -> bpy.types.Object:
        # Root
        root = bpy.data.objects.new(self.s.name, None)
        root.empty_display_type = "PLAIN_AXES"
        root.location = origin
        root.rotation_euler = (0.0, 0.0, math.radians(yaw_deg))
        link_to_collection(root, self.col)

        body = self._make_body_mesh()
        body.parent = root

        fins = self._make_fins()
        for f in fins:
            f.parent = root

        face = self._make_face(add_tongue=add_tongue)
        for obj in face:
            obj.parent = root

        # Optional: quick “belly” tint via a second slightly scaled duplicate (cheap gradient-ish cheat)
        # belly = self._make_belly_shell(body)
        # belly.parent = root

        # Group the main pieces visually by leaving them separate (GLB still fine).
        # If you want single-mesh per shark, you can join body+fins, but keep eyes separate.

        return root

    def _make_body_mesh(self) -> bpy.types.Object:
        deselect_all()

        # Create ONE metaball object
        bpy.ops.object.metaball_add(type="BALL", location=(0, 0, 0))
        mb_obj = bpy.context.active_object
        mb_obj.name = f"{self.s.name}_MB"
        mb = mb_obj.data

        # Metaball resolution (lower = smoother but heavier)
        mb.resolution = 0.08
        mb.render_resolution = 0.08
        mb.threshold = 0.6

        # Helper to add an element
        def add_ball(x, y, z, radius, stiffness=2.0):
            e = mb.elements.new(type="BALL")
            e.co = (x, y, z)
            e.radius = radius
            e.stiffness = stiffness
            return e

        # --- Build silhouette (numbers tuned to your reference) ---
        # Main body (torpedo-ish)
        add_ball(0.00, 0.00, 0.00, 0.85)
        add_ball(-0.55, 0.00, 0.00, 0.65)  # rear taper
        add_ball(0.55, 0.00, 0.05, 0.70)  # front bulk

        # Hammerhead width (two side lobes + center pad)
        add_ball(0.85, 0.80, 0.12, 0.55)  # left hammer
        add_ball(0.85, -0.80, 0.12, 0.55)  # right hammer
        add_ball(0.92, 0.00, 0.10, 0.58)  # center hammer

        # Snout / mouth pad (slightly lower)
        add_ball(1.15, 0.00, -0.08, 0.40)

        # Tail stalk
        add_ball(-1.05, 0.00, 0.00, 0.40)
        add_ball(-1.35, 0.00, 0.00, 0.28)

        # Scale the whole metaball object to match your param sizes
        mb_obj.scale = (self.p.body_len * 0.55, self.p.body_w * 0.55, self.p.body_h * 0.55)
        bpy.ops.object.transform_apply(scale=True)

        # Convert THIS single metaball object to mesh
        deselect_all()
        mb_obj.select_set(True)
        bpy.context.view_layer.objects.active = mb_obj
        bpy.ops.object.convert(target="MESH")

        body_mesh = bpy.context.active_object
        body_mesh.name = f"{self.s.name}_Body"
        link_to_collection(body_mesh, self.col)
        assign_mat(body_mesh, self.mat_body)
        shade_smooth(body_mesh)

        return body_mesh

    def _make_belly_shell(self, body_mesh: bpy.types.Object) -> bpy.types.Object:
        # Duplicate body, scale slightly, assign belly material, and offset down a hair.
        belly = body_mesh.copy()
        belly.data = body_mesh.data.copy()
        belly.name = f"{self.s.name}_BellyShell"
        bpy.context.collection.objects.link(belly)
        link_to_collection(belly, self.col)
        assign_mat(belly, self.mat_belly)
        belly.scale = (1.0, 1.0, 0.92)
        belly.location.z -= 0.10
        shade_smooth(belly)
        return belly

    def _make_fins(self) -> List[bpy.types.Object]:
        fins = []

        # Dorsal fin (thin triangular, on top)
        bpy.ops.mesh.primitive_cone_add(vertices=3, radius1=0.35, radius2=0.01, depth=0.9,
                                        location=(-0.05, 0.0, self.p.body_h * 0.75))
        dorsal = bpy.context.active_object
        dorsal.name = f"{self.s.name}_Dorsal"
        dorsal.rotation_euler = (0, math.radians(90), 0)
        dorsal.scale = (self.p.dorsal_w, 0.65, self.p.dorsal_h)
        link_to_collection(dorsal, self.col)
        assign_mat(dorsal, self.mat_body)
        shade_smooth(dorsal)
        fins.append(dorsal)

        # Pectoral fins (big, wing-like)
        for side in (-1, 1):
            bpy.ops.mesh.primitive_cone_add(vertices=3, radius1=0.40, radius2=0.01, depth=1.0,
                                            location=(0.05, side * (self.p.body_w * 0.78), -0.05))
            fin = bpy.context.active_object
            fin.name = f"{self.s.name}_Pectoral_{'L' if side < 0 else 'R'}"
            fin.rotation_euler = (math.radians(90), 0.0, math.radians(20 * side))
            fin.scale = (self.p.pectoral_h, self.p.pectoral_len, self.p.pectoral_w)
            link_to_collection(fin, self.col)
            assign_mat(fin, self.mat_body)
            shade_smooth(fin)
            fins.append(fin)

        # Tail fin (two triangles)
        tail_x = -self.p.body_len * 0.92
        for side in (-1, 1):
            bpy.ops.mesh.primitive_cone_add(vertices=3, radius1=0.35, radius2=0.01, depth=0.9,
                                            location=(tail_x, side * 0.10, 0.15))
            tf = bpy.context.active_object
            tf.name = f"{self.s.name}_TailFin_{'L' if side < 0 else 'R'}"
            tf.rotation_euler = (math.radians(90), 0.0, math.radians(25 * side))
            tf.scale = (self.p.tail_fin_w, 0.75, self.p.tail_fin_h)
            link_to_collection(tf, self.col)
            assign_mat(tf, self.mat_body)
            shade_smooth(tf)
            fins.append(tf)

        return fins

    def _make_face(self, add_tongue: bool) -> List[bpy.types.Object]:
        parts: List[bpy.types.Object] = []

        # Lips: upper + lower “pout” (scaled spheres)
        mouth_x = self.p.body_len * 0.55
        mouth_z = -self.p.body_h * 0.20

        for i, zoff in enumerate((+self.p.mouth_open * 0.5, -self.p.mouth_open * 0.5)):
            bpy.ops.mesh.primitive_uv_sphere_add(segments=28, ring_count=16, radius=0.25,
                                                location=(mouth_x, 0.0, mouth_z + zoff))
            lip = bpy.context.active_object
            lip.name = f"{self.s.name}_Lip_{'Top' if i == 0 else 'Bot'}"
            lip.scale = (self.p.mouth_depth, self.p.mouth_w, self.p.mouth_h)
            link_to_collection(lip, self.col)
            assign_mat(lip, self.mat_lip)
            shade_smooth(lip)
            parts.append(lip)

        # Tiny tongue nub (only on the blue one in your reference)
        if add_tongue:
            bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=0.09,
                                                location=(mouth_x + 0.08, -0.20, mouth_z - 0.02))
            tongue = bpy.context.active_object
            tongue.name = f"{self.s.name}_Tongue"
            tongue.scale = (0.70, 1.20, 0.55)
            link_to_collection(tongue, self.col)
            assign_mat(tongue, self.mat_tongue)
            shade_smooth(tongue)
            parts.append(tongue)

        # Eyes: big whites, iris ring, pupil disk (slightly cross-eyed)
        eye_x = self.p.body_len * 0.42
        eye_z = self.p.body_h * 0.18
        eye_y = self.p.head_w * 0.48

        for side in (-1, 1):
            # Eye white
            bpy.ops.mesh.primitive_uv_sphere_add(segments=28, ring_count=16, radius=self.p.eye_r,
                                                location=(eye_x, side * eye_y, eye_z))
            eye = bpy.context.active_object
            eye.name = f"{self.s.name}_EyeWhite_{'L' if side < 0 else 'R'}"
            link_to_collection(eye, self.col)
            assign_mat(eye, self.mat_eye)
            shade_smooth(eye)
            parts.append(eye)

            # Iris (thin cylinder/disc)
            bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=self.p.iris_r, depth=0.03,
                                                location=(eye_x + self.p.eye_r * 0.80, side * eye_y, eye_z))
            iris = bpy.context.active_object
            iris.name = f"{self.s.name}_Iris_{'L' if side < 0 else 'R'}"
            iris.rotation_euler = (0.0, math.radians(90), 0.0)
            link_to_collection(iris, self.col)
            assign_mat(iris, self.mat_iris)
            shade_smooth(iris)
            parts.append(iris)

            # Pupil (thin cylinder/disc), offset inward for cross-eye
            inward = -side * (self.p.cross_eye * self.p.iris_r)
            bpy.ops.mesh.primitive_cylinder_add(vertices=28, radius=self.p.pupil_r, depth=0.03,
                                                location=(eye_x + self.p.eye_r * 0.90, side * eye_y + inward, eye_z))
            pupil = bpy.context.active_object
            pupil.name = f"{self.s.name}_Pupil_{'L' if side < 0 else 'R'}"
            pupil.rotation_euler = (0.0, math.radians(90), 0.0)
            link_to_collection(pupil, self.col)
            assign_mat(pupil, self.mat_pupil)
            shade_smooth(pupil)
            parts.append(pupil)

        return parts


# ----------------------------
# Export
# ----------------------------

def export_glb(path: str) -> None:
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        export_apply=True,
        export_texcoords=True,
        export_normals=True,
        export_materials="EXPORT",
    )


# ----------------------------
# Main
# ----------------------------

def main():
    args = parse_args()
    clean_scene()

    # Nice-ish preview light/cam (optional)
    bpy.ops.object.light_add(type="AREA", location=(3.5, 2.5, 3.2))
    bpy.context.active_object.data.energy = 600
    bpy.ops.object.camera_add(location=(4.0, -4.0, 2.4), rotation=(math.radians(70), 0.0, math.radians(45)))

    params = SharkParams()

    blue_style = SharkStyle(
        name="TADC_Shark_Blue",
        body_color=(0.12, 0.35, 0.78, 1.0),
        belly_tint=(0.12, 0.32, 0.72, 1.0),
        lip_color=(0.35, 0.24, 0.45, 1.0),
        eye_white=(0.60, 0.95, 0.98, 1.0),
        iris_color=(0.12, 0.55, 0.95, 1.0),
        pupil_color=(0.02, 0.18, 0.45, 1.0),
        tongue_color=(0.35, 0.70, 0.92, 1.0),
    )

    green_style = SharkStyle(
        name="TADC_Shark_Green",
        body_color=(0.08, 0.52, 0.52, 1.0),
        belly_tint=(0.08, 0.48, 0.50, 1.0),
        lip_color=(0.24, 0.40, 0.44, 1.0),
        eye_white=(0.60, 0.95, 0.98, 1.0),
        iris_color=(0.12, 0.55, 0.95, 1.0),
        pupil_color=(0.02, 0.18, 0.45, 1.0),
        tongue_color=(0.50, 0.60, 0.65, 1.0),
    )

    TADCSharkBuilder(params, blue_style).build(origin=(-1.8, 0.0, 0.0), yaw_deg=10.0, add_tongue=True)
    TADCSharkBuilder(params, green_style).build(origin=(1.8, 0.0, 0.0), yaw_deg=-12.0, add_tongue=False)

    export_glb(args.out)


if __name__ == "__main__":
    main()
