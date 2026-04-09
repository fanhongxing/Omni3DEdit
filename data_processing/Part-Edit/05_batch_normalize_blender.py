import os
import sys

import bpy


def import_glb(filepath):
    bpy.ops.import_scene.gltf(filepath=filepath)
    return [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]


def get_bbox(objects):
    min_x = min(min(v.co.x for v in obj.data.vertices) for obj in objects)
    max_x = max(max(v.co.x for v in obj.data.vertices) for obj in objects)
    min_y = min(min(v.co.y for v in obj.data.vertices) for obj in objects)
    max_y = max(max(v.co.y for v in obj.data.vertices) for obj in objects)
    min_z = min(min(v.co.z for v in obj.data.vertices) for obj in objects)
    max_z = max(max(v.co.z for v in obj.data.vertices) for obj in objects)
    return min_x, max_x, min_y, max_y, min_z, max_z


def normalize_objects(objects, bbox, target_size=1.0):
    min_x, max_x, min_y, max_y, min_z, max_z = bbox
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    center_z = (min_z + max_z) / 2
    max_len = max(max_x - min_x, max_y - min_y, max_z - min_z)
    if max_len <= 1e-12:
        return

    scale_factor = target_size / max_len
    for obj in objects:
        for vertex in obj.data.vertices:
            vertex.co.x = (vertex.co.x - center_x) * scale_factor
            vertex.co.y = (vertex.co.y - center_y) * scale_factor
            vertex.co.z = (vertex.co.z - center_z) * scale_factor


def export_selected(objects, filepath):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=filepath, export_format="GLB", use_selection=True)


def normalize_one_sample(sample_dir):
    model_glb = os.path.join(sample_dir, "model.glb")
    mask_glb = os.path.join(sample_dir, "mask.glb")
    if not (os.path.exists(model_glb) and os.path.exists(mask_glb)):
        return False, "missing model.glb or mask.glb"

    normalize_dir = os.path.join(sample_dir, "normalize")
    normalized_model = os.path.join(normalize_dir, "model_normalized.glb")
    normalized_mask = os.path.join(normalize_dir, "mask.glb")

    if os.path.exists(normalized_model) and os.path.exists(normalized_mask):
        return False, "already normalized"

    os.makedirs(normalize_dir, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    model_objects = import_glb(model_glb)
    mask_objects = import_glb(mask_glb)
    all_objects = model_objects + mask_objects

    if not all_objects:
        return False, "no mesh objects found"

    bbox = get_bbox(all_objects)
    normalize_objects(all_objects, bbox, target_size=1.0)

    export_selected(model_objects, normalized_model)
    export_selected(mask_objects, normalized_mask)

    return True, "ok"


def parse_args_from_blender_argv():
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []

    if len(argv) != 1:
        print("Usage: blender --background --python 05_batch_normalize_blender.py -- <output_root>")
        sys.exit(1)

    return os.path.abspath(argv[0])


def main():
    output_root = parse_args_from_blender_argv()

    total = 0
    success = 0

    for folder in sorted(os.listdir(output_root)):
        sample_dir = os.path.join(output_root, folder)
        if not os.path.isdir(sample_dir):
            continue

        total += 1
        ok, reason = normalize_one_sample(sample_dir)
        if ok:
            success += 1
            print(f"Normalized {sample_dir}")
        else:
            print(f"Skip {sample_dir}: {reason}")

    print(f"Normalize done: {success}/{total} samples updated")


if __name__ == "__main__":
    main()
