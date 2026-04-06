import argparse
import os
import subprocess
from multiprocessing import Pool

FIXED_JSONS = {"result.json", "result_after_merging.json", "meta.json"}


def ensure_voxhammer_cwd():
    required = ["utils/render_rgb_and_mask.py", "utils/inpaint.py", "inference.py"]
    missing = [path for path in required if not os.path.exists(path)]
    if missing:
        raise RuntimeError(
            "This script must be run from the VoxHammer repository root. "
            f"Missing files: {missing}"
        )


def collect_tasks(dataset_dir, output_root):
    tasks = []

    for model_id in sorted(os.listdir(dataset_dir)):
        model_folder = os.path.join(dataset_dir, model_id)
        if not os.path.isdir(model_folder):
            continue

        glbs_dir = os.path.join(model_folder, "objs", "glbs")
        source_model = os.path.join(glbs_dir, "model_merged.glb")
        if not os.path.exists(source_model):
            continue

        part_jsons = [
            name
            for name in os.listdir(model_folder)
            if name.endswith(".json") and name not in FIXED_JSONS
        ]
        if not part_jsons:
            continue

        for json_name in sorted(part_jsons):
            part_id = os.path.splitext(json_name)[0]
            mask_model = os.path.join(glbs_dir, f"{part_id}.glb")
            if not os.path.exists(mask_model):
                continue

            sample_output = os.path.join(output_root, f"{model_id}_{part_id}")
            if os.path.exists(os.path.join(sample_output, "images", "render_0000.png")):
                continue

            tasks.append((source_model, mask_model, sample_output))

    return tasks


def run_task(task):
    source_model, mask_model, sample_output = task
    os.makedirs(sample_output, exist_ok=True)

    cmd = [
        "python",
        "utils/render_rgb_and_mask.py",
        "--source_model",
        source_model,
        "--mask_model",
        mask_model,
        "--output_dir",
        sample_output,
    ]

    try:
        subprocess.run(cmd, check=True)
        print(f"Rendered {sample_output}")
        return True
    except subprocess.CalledProcessError as exc:
        print(f"Render failed for {sample_output}: {exc}")
        return False


def parse_args():
    parser = argparse.ArgumentParser(description="Batch run VoxHammer render_rgb_and_mask step.")
    parser.add_argument("--dataset-dir", required=True, help="Dataset root with per-model folders.")
    parser.add_argument("--output-root", required=True, help="Output root for per-sample folders.")
    parser.add_argument("--num-workers", type=int, default=8, help="Parallel worker count.")
    return parser.parse_args()


def main():
    args = parse_args()
    ensure_voxhammer_cwd()

    tasks = collect_tasks(args.dataset_dir, args.output_root)
    print(f"Collected {len(tasks)} render tasks")
    if not tasks:
        return

    with Pool(args.num_workers) as pool:
        results = pool.map(run_task, tasks)

    success = sum(1 for item in results if item)
    print(f"Render done: {success}/{len(tasks)} succeeded")


if __name__ == "__main__":
    main()
