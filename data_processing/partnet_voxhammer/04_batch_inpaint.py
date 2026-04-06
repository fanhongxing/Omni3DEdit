import argparse
import json
import os
import subprocess
from glob import glob
from multiprocessing import Pool

import numpy as np
from PIL import Image


def ensure_voxhammer_cwd():
    required = ["utils/render_rgb_and_mask.py", "utils/inpaint.py", "inference.py"]
    missing = [path for path in required if not os.path.exists(path)]
    if missing:
        raise RuntimeError(
            "This script must be run from the VoxHammer repository root. "
            f"Missing files: {missing}"
        )


def best_mask_index(mask_files):
    best_idx = None
    best_score = -1
    for mask_path in mask_files:
        file_name = os.path.basename(mask_path)
        idx = int(file_name.split("_")[-1].split(".")[0])
        mask_array = np.array(Image.open(mask_path).convert("L"))
        score = int(np.sum(mask_array > 127))
        if score > best_score:
            best_score = score
            best_idx = idx
    return best_idx, best_score


def load_prompt(prompt_json_path):
    with open(prompt_json_path, "r", encoding="utf-8") as file_obj:
        data = json.load(file_obj)
    if isinstance(data, dict) and "prompt" in data:
        return str(data["prompt"])
    return json.dumps(data, ensure_ascii=False)


def collect_tasks(dataset_dir, output_root):
    tasks = []

    for folder in sorted(os.listdir(output_root)):
        sample_dir = os.path.join(output_root, folder)
        images_dir = os.path.join(sample_dir, "images")
        if not os.path.isdir(images_dir):
            continue

        if os.path.exists(os.path.join(images_dir, "2d_edit.png")):
            continue

        if "_" not in folder:
            continue
        model_id, part_id = folder.split("_", 1)

        prompt_json = os.path.join(dataset_dir, model_id, f"{part_id}.json")
        if not os.path.exists(prompt_json):
            continue

        mask_files = sorted(glob(os.path.join(images_dir, "mask_*.png")))
        if not mask_files:
            continue

        best_idx, _score = best_mask_index(mask_files)
        render_path = os.path.join(images_dir, f"render_{best_idx:04d}.png")
        mask_path = os.path.join(images_dir, f"mask_{best_idx:04d}.png")

        if not (os.path.exists(render_path) and os.path.exists(mask_path)):
            continue

        prompt = load_prompt(prompt_json)
        tasks.append((images_dir, render_path, mask_path, prompt))

    return tasks


def run_task(task_with_gpu):
    (images_dir, render_path, mask_path, prompt), gpu_id = task_with_gpu
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)

    cmd = [
        "python",
        "utils/inpaint.py",
        "--image_path",
        render_path,
        "--mask_path",
        mask_path,
        "--output_dir",
        images_dir,
        "--prompt",
        prompt,
    ]

    try:
        subprocess.run(cmd, check=True, env=env)
        print(f"Inpainted {images_dir}")
        return True
    except subprocess.CalledProcessError as exc:
        print(f"Inpaint failed for {images_dir}: {exc}")
        return False


def parse_args():
    parser = argparse.ArgumentParser(description="Batch run VoxHammer inpaint step.")
    parser.add_argument("--dataset-dir", required=True, help="Dataset root with prompt json files.")
    parser.add_argument("--output-root", required=True, help="Output root created by render step.")
    parser.add_argument("--num-gpus", type=int, default=1, help="Number of GPUs to use.")
    return parser.parse_args()


def main():
    args = parse_args()
    ensure_voxhammer_cwd()

    tasks = collect_tasks(args.dataset_dir, args.output_root)
    print(f"Collected {len(tasks)} inpaint tasks")
    if not tasks:
        return

    gpu_tasks = [(task, idx % args.num_gpus) for idx, task in enumerate(tasks)]
    with Pool(args.num_gpus) as pool:
        results = pool.map(run_task, gpu_tasks)

    success = sum(1 for item in results if item)
    print(f"Inpaint done: {success}/{len(tasks)} succeeded")


if __name__ == "__main__":
    main()
