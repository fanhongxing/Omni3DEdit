import os
import sys

import bpy


def safe_view_selected():
    print("[Phobos Patch] Skip bpy.ops.view3d.view_selected in background mode.")


bpy.ops.view3d.view_selected = safe_view_selected


def parse_args_from_blender_argv():
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []

    if len(argv) < 2:
        print(
            "Usage: blender --background --python 02_convert_urdf_to_glb_blender.py -- "
            "<input_root> <output_root> [file_prefix]"
        )
        sys.exit(1)

    input_root = os.path.abspath(argv[0])
    output_root = os.path.abspath(argv[1])
    file_prefix = argv[2] if len(argv) >= 3 else "mobility"
    return input_root, output_root, file_prefix


def main():
    input_root, output_root, file_prefix = parse_args_from_blender_argv()

    print(f"Input root: {input_root}")
    print(f"Output root: {output_root}")
    print(f"URDF filename prefix: {file_prefix}")

    for root, _dirs, files in os.walk(input_root):
        for file_name in files:
            if not file_name.endswith(".urdf"):
                continue
            if not file_name.startswith(file_prefix):
                continue

            urdf_path = os.path.join(root, file_name)
            rel_dir = os.path.relpath(root, input_root)
            output_dir = os.path.join(output_root, rel_dir)
            os.makedirs(output_dir, exist_ok=True)

            glb_name = os.path.splitext(file_name)[0] + ".glb"
            glb_path = os.path.join(output_dir, glb_name)

            print(f"Processing {urdf_path}")
            print(f"Exporting to {glb_path}")

            bpy.ops.wm.read_homefile(use_empty=True)

            try:
                bpy.ops.phobos.import_robot_model(filepath=urdf_path)
            except Exception as exc:
                print(f"[ERROR] Import failed for {urdf_path}: {exc}")
                continue

            bpy.ops.object.select_all(action="SELECT")

            try:
                bpy.ops.export_scene.gltf(
                    filepath=glb_path,
                    export_format="GLB",
                    use_selection=True,
                    export_apply=True,
                )
                print(f"[OK] Exported {glb_path}")
            except Exception as exc:
                print(f"[ERROR] Export failed for {glb_path}: {exc}")

    print("All conversions finished.")


if __name__ == "__main__":
    main()
