import argparse
import hashlib
import os

import pandas as pd
from tqdm import tqdm


def compute_sha256(file_path):
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def build_metadata(raw_dir, local_path_prefix):
    records = []

    sample_folders = [
        folder for folder in sorted(os.listdir(raw_dir)) if os.path.isdir(os.path.join(raw_dir, folder))
    ]

    for folder in tqdm(sample_folders, desc="Scanning sample folders"):
        folder_path = os.path.join(raw_dir, folder)
        glb_files = sorted([f for f in os.listdir(folder_path) if f.endswith(".glb")])

        for glb_name in glb_files:
            file_path = os.path.join(folder_path, glb_name)
            sha256 = compute_sha256(file_path)
            file_identifier = os.path.splitext(glb_name)[0]

            records.append(
                {
                    "sha256": sha256,
                    "file_identifier": file_identifier,
                    "aesthetic_score": "",
                    "captions": "",
                    "rendered": True,
                    "voxelized": True,
                    "num_voxels": 0,
                    "cond_rendered": False,
                    "local_path": f"{local_path_prefix}/{folder}/{glb_name}",
                    "feature_dinov2_vitl14_reg": True,
                    "ss_latent_ss_enc_conv3d_16l8_fp16": True,
                    "latent_dinov2_vitl14_reg_slat_enc_swin8_B_64l8_fp16": True,
                }
            )

    return pd.DataFrame(records)


def parse_args():
    parser = argparse.ArgumentParser(description="Build metadata CSV from GLB files.")
    parser.add_argument("--raw-dir", required=True, help="Root folder that contains per-sample GLB folders.")
    parser.add_argument("--save-path", required=True, help="Output CSV path.")
    parser.add_argument(
        "--local-path-prefix",
        default="raw",
        help="Prefix used in metadata local_path, e.g. raw or raw_0.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    os.makedirs(os.path.dirname(args.save_path), exist_ok=True)
    metadata = build_metadata(args.raw_dir, args.local_path_prefix)
    metadata.to_csv(args.save_path, index=False)

    print(f"Metadata saved: {args.save_path}")
    print(f"Total models: {len(metadata)}")


if __name__ == "__main__":
    main()
