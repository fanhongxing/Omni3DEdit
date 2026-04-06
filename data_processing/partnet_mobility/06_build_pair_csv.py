import argparse
import json
import os

import pandas as pd
from tqdm import tqdm


def load_name_to_hash(metadata_csv):
    metadata = pd.read_csv(metadata_csv)
    return {str(row["local_path"]): str(row["sha256"]) for _, row in metadata.iterrows()}


def build_pairs(raw_dir, dataset_dir, name_to_hash, output_count, instruction_json_list):
    pairs = []

    for folder in tqdm(sorted(os.listdir(raw_dir)), desc="Processing raw folders"):
        folder_path = os.path.join(raw_dir, folder)
        if not os.path.isdir(folder_path):
            continue

        original_path = os.path.join(folder_path, "mobility.glb")
        if not os.path.exists(original_path):
            print(f"Missing mobility.glb in {folder}")
            continue

        source_key = f"raw/{folder}/mobility.glb"
        source_sha256 = name_to_hash.get(source_key)
        if not source_sha256:
            print(f"Hash not found for {source_key}")
            continue

        instruction_file = os.path.join(dataset_dir, folder, "instructions.json")
        if not os.path.exists(instruction_file):
            print(f"Missing instructions.json in {folder}")
            continue

        with open(instruction_file, "r", encoding="utf-8") as file_obj:
            instruction_data = json.load(file_obj)

        for idx in range(output_count):
            mod_name = f"mobility_mod_{idx}"
            mod_path = os.path.join(folder_path, f"{mod_name}.glb")
            if not os.path.exists(mod_path):
                continue

            target_key = f"raw/{folder}/{mod_name}.glb"
            target_sha256 = name_to_hash.get(target_key)
            if not target_sha256:
                print(f"Hash not found for {target_key}")
                continue

            instruction_text = str(instruction_data.get(mod_name, "")).strip()
            if not instruction_text:
                print(f"No instruction for {folder}/{mod_name}")
                continue

            if instruction_json_list:
                instruction_value = json.dumps([instruction_text], ensure_ascii=False)
            else:
                instruction_value = instruction_text

            pairs.append(
                {
                    "source_sha256": source_sha256,
                    "target_sha256": target_sha256,
                    "instruction": instruction_value,
                }
            )

    return pd.DataFrame(pairs)


def parse_args():
    parser = argparse.ArgumentParser(description="Build source-target instruction pairs CSV.")
    parser.add_argument("--raw-dir", required=True, help="Raw directory with per-sample GLB files.")
    parser.add_argument("--dataset-dir", required=True, help="Dataset directory with per-sample instructions.json.")
    parser.add_argument("--metadata-csv", required=True, help="Metadata CSV generated from raw GLB files.")
    parser.add_argument("--output-csv", required=True, help="Output pair CSV path.")
    parser.add_argument("--output-count", type=int, default=3, help="Number of modified variants per sample.")
    parser.add_argument(
        "--instruction-json-list",
        action="store_true",
        help="Store instruction as JSON list string, e.g. [\"text\"].",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    os.makedirs(os.path.dirname(args.output_csv), exist_ok=True)

    name_to_hash = load_name_to_hash(args.metadata_csv)
    pairs = build_pairs(
        raw_dir=args.raw_dir,
        dataset_dir=args.dataset_dir,
        name_to_hash=name_to_hash,
        output_count=args.output_count,
        instruction_json_list=args.instruction_json_list,
    )
    pairs.to_csv(args.output_csv, index=False)

    print(f"Saved {args.output_csv}, total {len(pairs)} pairs")


if __name__ == "__main__":
    main()
