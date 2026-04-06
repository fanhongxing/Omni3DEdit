import argparse
import os

import numpy as np
import sapien
from PIL import Image


DEFAULT_CAMERA_POSITIONS = [
    np.array([-2.0, -2.0, 3.0]),
    np.array([2.0, -2.0, 2.0]),
    np.array([-2.0, 2.0, 2.0]),
]


def compute_cam_pose(cam_pos):
    forward = -cam_pos / np.linalg.norm(cam_pos)
    left = np.cross([0.0, 0.0, 1.0], forward)
    left /= np.linalg.norm(left)
    up = np.cross(forward, left)

    mat44 = np.eye(4)
    mat44[:3, :3] = np.stack([forward, left, up], axis=1)
    mat44[:3, 3] = cam_pos
    return mat44


def render_one_urdf(urdf_path, save_prefix, width, height, fovy, near, far, camera_positions):
    scene = sapien.Scene()
    scene.set_timestep(1 / 100.0)

    scene.set_ambient_light([0.5, 0.5, 0.5])
    scene.add_directional_light([0, 1, -1], [0.5, 0.5, 0.5], shadow=True)
    scene.add_point_light([1, 2, 2], [1, 1, 1])
    scene.add_point_light([1, -2, 2], [1, 1, 1])
    scene.add_point_light([-1, 0, 1], [1, 1, 1])

    loader = scene.create_urdf_loader()
    loader.fix_root_link = True
    asset = loader.load(urdf_path)
    if not asset:
        print(f"[ERROR] Failed to load {urdf_path}")
        return

    for view_id, cam_pos in enumerate(camera_positions):
        cam_mat = compute_cam_pose(cam_pos)
        camera = scene.add_camera(
            name=f"camera_{view_id}",
            width=width,
            height=height,
            fovy=fovy,
            near=near,
            far=far,
        )
        camera.entity.set_pose(sapien.Pose(cam_mat))

        scene.step()
        scene.update_render()
        camera.take_picture()

        rgba = camera.get_picture("Color")
        rgba_img = (rgba * 255).clip(0, 255).astype("uint8")
        save_path = f"{save_prefix}_view{view_id}.png"
        Image.fromarray(rgba_img).save(save_path)
        print(f"Saved {save_path}")


def parse_camera_positions(value):
    positions = []
    if not value.strip():
        return DEFAULT_CAMERA_POSITIONS

    for chunk in value.split(";"):
        xyz = [float(x) for x in chunk.split(",")]
        if len(xyz) != 3:
            raise ValueError("Each camera position must have 3 comma-separated numbers.")
        positions.append(np.array(xyz, dtype=float))

    return positions


def parse_args():
    parser = argparse.ArgumentParser(description="Render URDF files from fixed camera views.")
    parser.add_argument("--dataset-dir", required=True, help="Directory with per-sample folders containing URDF files.")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="If omitted, images are saved into each sample folder. If set, images are saved under output_dir/<sample_id>/.",
    )
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fovy-deg", type=float, default=35.0)
    parser.add_argument("--near", type=float, default=0.1)
    parser.add_argument("--far", type=float, default=100.0)
    parser.add_argument(
        "--camera-positions",
        default="",
        help="Semicolon-separated camera xyz values. Example: -2,-2,3;2,-2,2;-2,2,2",
    )
    parser.add_argument("--urdf-suffix", default=".urdf", help="Render files ending with this suffix.")
    return parser.parse_args()


def main():
    args = parse_args()

    camera_positions = parse_camera_positions(args.camera_positions)
    fovy = np.deg2rad(args.fovy_deg)

    for sample_id in sorted(os.listdir(args.dataset_dir)):
        sample_dir = os.path.join(args.dataset_dir, sample_id)
        if not os.path.isdir(sample_dir):
            continue

        if args.output_dir is None:
            out_sample_dir = sample_dir
        else:
            out_sample_dir = os.path.join(args.output_dir, sample_id)
            os.makedirs(out_sample_dir, exist_ok=True)

        urdf_files = sorted([f for f in os.listdir(sample_dir) if f.endswith(args.urdf_suffix)])
        for urdf_file in urdf_files:
            urdf_path = os.path.join(sample_dir, urdf_file)
            base_name = os.path.splitext(urdf_file)[0]
            save_prefix = os.path.join(out_sample_dir, f"{sample_id}_{base_name}")
            render_one_urdf(
                urdf_path=urdf_path,
                save_prefix=save_prefix,
                width=args.width,
                height=args.height,
                fovy=fovy,
                near=args.near,
                far=args.far,
                camera_positions=camera_positions,
            )


if __name__ == "__main__":
    main()
