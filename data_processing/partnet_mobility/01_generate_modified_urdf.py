import argparse
import math
import os
import random
import xml.etree.ElementTree as ET

import numpy as np


def rpy_to_matrix(rpy):
    roll, pitch, yaw = rpy
    rx = np.array(
        [
            [1, 0, 0],
            [0, math.cos(roll), -math.sin(roll)],
            [0, math.sin(roll), math.cos(roll)],
        ]
    )
    ry = np.array(
        [
            [math.cos(pitch), 0, math.sin(pitch)],
            [0, 1, 0],
            [-math.sin(pitch), 0, math.cos(pitch)],
        ]
    )
    rz = np.array(
        [
            [math.cos(yaw), -math.sin(yaw), 0],
            [math.sin(yaw), math.cos(yaw), 0],
            [0, 0, 1],
        ]
    )
    return rz @ ry @ rx


def matrix_to_rpy(rotation):
    sy = math.sqrt(rotation[0, 0] ** 2 + rotation[1, 0] ** 2)
    singular = sy < 1e-6

    if not singular:
        roll = math.atan2(rotation[2, 1], rotation[2, 2])
        pitch = math.atan2(-rotation[2, 0], sy)
        yaw = math.atan2(rotation[1, 0], rotation[0, 0])
    else:
        roll = math.atan2(-rotation[1, 2], rotation[1, 1])
        pitch = math.atan2(-rotation[2, 0], sy)
        yaw = 0.0

    return [roll, pitch, yaw]


def axis_angle_to_matrix(axis, theta):
    axis = np.array(axis, dtype=float)
    axis_norm = np.linalg.norm(axis)
    if axis_norm < 1e-12:
        return np.eye(3)

    axis = axis / axis_norm
    x, y, z = axis
    c = math.cos(theta)
    s = math.sin(theta)
    return np.array(
        [
            [c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
            [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
            [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)],
        ]
    )


def modify_joint_origin(joint, offset_ratio, existing_continuous_angles, min_diff=0.175):
    joint_type = joint.attrib.get("type", "")
    origin = joint.find("origin")
    if origin is None:
        return False

    rpy = [float(x) for x in origin.attrib.get("rpy", "0 0 0").split()]
    xyz = [float(x) for x in origin.attrib.get("xyz", "0 0 0").split()]

    axis_elem = joint.find("axis")
    axis = [0, 0, 1] if axis_elem is None else [float(x) for x in axis_elem.attrib.get("xyz", "0 0 1").split()]

    if joint_type in ["revolute", "prismatic"]:
        limit = joint.find("limit")
        if limit is None:
            return False
        lower = float(limit.attrib.get("lower", "0"))
        upper = float(limit.attrib.get("upper", "0"))
    elif joint_type == "continuous":
        lower = -math.inf
        upper = math.inf
    else:
        return False

    span = upper - lower if joint_type != "continuous" else 2 * math.pi
    offset = offset_ratio * span

    new_rpy = list(rpy)
    new_xyz = list(xyz)

    if joint_type in ["revolute", "continuous"]:
        rotation = rpy_to_matrix(rpy)
        rotation_axis = axis_angle_to_matrix(axis, offset)
        new_rotation = rotation_axis @ rotation
        new_rpy = matrix_to_rpy(new_rotation)

        if joint_type == "continuous":
            theta_mod = offset % (2 * math.pi)
            for existing in existing_continuous_angles:
                if abs(theta_mod - existing) < 0.087:
                    return False
            existing_continuous_angles.append(theta_mod)
        else:
            if not (lower <= offset <= upper):
                return False

    elif joint_type == "prismatic":
        new_xyz = [xyz[i] + offset * axis[i] for i in range(3)]
        move_along_axis = sum((new_xyz[i] - xyz[i]) * axis[i] for i in range(3))
        if not (lower <= move_along_axis <= upper):
            return False

    diff = sum(abs(new_rpy[i] - rpy[i]) for i in range(3)) + sum(abs(new_xyz[i] - xyz[i]) for i in range(3))
    if diff < min_diff:
        return False

    origin.set("rpy", " ".join(f"{v:.6f}" for v in new_rpy))
    origin.set("xyz", " ".join(f"{v:.6f}" for v in new_xyz))
    return True


def process_urdf(urdf_path, output_count, output_template, max_attempts=64):
    base_dir = os.path.dirname(urdf_path)
    generated = 0
    used_offsets = set()
    continuous_angles = []

    candidate_offsets = [-1.0, -0.5, 0.5, 1.0]
    attempts = 0

    while generated < output_count and attempts < max_attempts:
        attempts += 1

        if candidate_offsets:
            offset = candidate_offsets.pop(0)
        else:
            offset = random.uniform(-1.0, 1.0)
            while round(offset, 2) in used_offsets:
                offset = random.uniform(-1.0, 1.0)

        tree = ET.parse(urdf_path)
        root = tree.getroot()

        valid = False
        for joint in root.findall("joint"):
            if modify_joint_origin(joint, offset, continuous_angles):
                valid = True

        if valid:
            out_file = output_template.format(idx=generated)
            out_path = os.path.join(base_dir, out_file)
            tree.write(out_path, encoding="utf-8", xml_declaration=True)
            used_offsets.add(round(offset, 2))
            generated += 1
            print(f"Saved {out_path} (offset={offset:.2f})")

    if generated < output_count:
        print(f"Warning: only generated {generated}/{output_count} variants for {urdf_path}")


def process_dataset(dataset_dir, source_name, output_count, output_template):
    for folder in sorted(os.listdir(dataset_dir)):
        sample_dir = os.path.join(dataset_dir, folder)
        if not os.path.isdir(sample_dir):
            continue

        urdf_path = os.path.join(sample_dir, source_name)
        if not os.path.exists(urdf_path):
            continue

        print(f"Processing {urdf_path}")
        try:
            process_urdf(
                urdf_path=urdf_path,
                output_count=output_count,
                output_template=output_template,
            )
        except Exception as exc:
            print(f"Error processing {urdf_path}: {exc}")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate modified URDF variants from articulation joints.")
    parser.add_argument("--dataset-dir", required=True, help="Directory with per-sample folders.")
    parser.add_argument("--source-name", default="mobility.urdf", help="Source URDF filename.")
    parser.add_argument("--output-count", type=int, default=3, help="Number of modified URDF files to generate.")
    parser.add_argument(
        "--output-template",
        default="mobility_mod_{idx}.urdf",
        help="Output filename template. Use {idx} as index placeholder.",
    )
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed.")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.seed is not None:
        random.seed(args.seed)
        np.random.seed(args.seed)

    process_dataset(
        dataset_dir=args.dataset_dir,
        source_name=args.source_name,
        output_count=args.output_count,
        output_template=args.output_template,
    )


if __name__ == "__main__":
    main()
