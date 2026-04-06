import os
import sys

import bpy


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def export_single_obj_to_glb(obj_path, glb_path):
    clear_scene()
    bpy.ops.wm.obj_import(filepath=obj_path)
    bpy.ops.export_scene.gltf(filepath=glb_path, export_format="GLB")


def export_merged_glb(objs_dir, merged_path):
    clear_scene()
    for file_name in sorted(os.listdir(objs_dir)):
        if file_name.endswith(".obj"):
            obj_path = os.path.join(objs_dir, file_name)
            bpy.ops.wm.obj_import(filepath=obj_path)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.join()
    bpy.ops.export_scene.gltf(filepath=merged_path, export_format="GLB")


def parse_args_from_blender_argv():
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []

    if len(argv) != 2:
        print(
            "Usage: blender --background --python 01_export_obj_to_glb_worker_blender.py -- "
            "<dataset_dir> <model_id>"
        )
        sys.exit(1)

    dataset_dir = os.path.abspath(argv[0])
    model_id = argv[1]
    return dataset_dir, model_id


def main():
    dataset_dir, model_id = parse_args_from_blender_argv()

    objs_dir = os.path.join(dataset_dir, model_id, "objs")
    glb_dir = os.path.join(objs_dir, "glbs")
    os.makedirs(glb_dir, exist_ok=True)

    merged_glb = os.path.join(glb_dir, "model_merged.glb")
    if os.path.exists(merged_glb):
        print(f"Skip {model_id}: {merged_glb} already exists")
        return

    print(f"Processing model {model_id}")
    for file_name in sorted(os.listdir(objs_dir)):
        if not file_name.endswith(".obj"):
            continue
        obj_path = os.path.join(objs_dir, file_name)
        glb_path = os.path.join(glb_dir, file_name.replace(".obj", ".glb"))
        export_single_obj_to_glb(obj_path, glb_path)
        print(f"Exported {glb_path}")

    export_merged_glb(objs_dir, merged_glb)
    print(f"Exported merged model {merged_glb}")


if __name__ == "__main__":
    main()
