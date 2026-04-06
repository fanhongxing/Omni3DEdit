import argparse
import os
import subprocess
from multiprocessing import Pool


def ensure_voxhammer_cwd():
    required = ["utils/render_rgb_and_mask.py", "utils/inpaint.py", "inference.py"]
    missing = [path for path in required if not os.path.exists(path)]
    if missing:
        raise RuntimeError(
            "This script must be run from the VoxHammer repository root. "
            f"Missing files: {missing}"
        )


def resolve_input_paths(sample_dir):
    normalized_model = os.path.join(sample_dir, "normalize", "model_normalized.glb")
    normalized_mask = os.path.join(sample_dir, "normalize", "mask.glb")
    return normalized_model, normalized_mask


def collect_tasks(output_root):
    tasks = []

    for folder in sorted(os.listdir(output_root)):
        sample_dir = os.path.join(output_root, folder)
        if not os.path.isdir(sample_dir):
            continue

        output_glb = os.path.join(sample_dir, "output.glb")
        if os.path.exists(output_glb):
            continue

        images_dir = os.path.join(sample_dir, "images")
        if not os.path.isdir(images_dir):
            continue
        required_images = [
            os.path.join(images_dir, "2d_render.png"),
            os.path.join(images_dir, "2d_mask.png"),
            os.path.join(images_dir, "2d_edit.png"),
        ]
        if not all(os.path.exists(path) for path in required_images):
            continue

        input_model, mask_glb = resolve_input_paths(sample_dir)
        if not (os.path.exists(input_model) and os.path.exists(mask_glb)):
            print(f"Skip {sample_dir}: missing normalize/model_normalized.glb or normalize/mask.glb")
            continue

        tasks.append((sample_dir, input_model, mask_glb, images_dir))

    return tasks


def run_task(task_with_gpu):
    (sample_dir, input_model, mask_glb, images_dir), gpu_id = task_with_gpu
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)

    cmd = [
        "python",
        "inference.py",
        "--input_model",
        input_model,
        "--mask_glb",
        mask_glb,
        "--output_dir",
        sample_dir,
        "--image_dir",
        images_dir,
    ]

    try:
        subprocess.run(cmd, check=True, env=env)
        print(f"Inference finished for {sample_dir}")
        return True
    except subprocess.CalledProcessError as exc:
        print(f"Inference failed for {sample_dir}: {exc}")
        return False


def parse_args():
    parser = argparse.ArgumentParser(description="Batch run VoxHammer inference step.")
    parser.add_argument("--output-root", required=True, help="Output root created by render step.")
    parser.add_argument("--num-gpus", type=int, default=1, help="Number of GPUs to use.")
    return parser.parse_args()


def main():
    args = parse_args()
    ensure_voxhammer_cwd()

    tasks = collect_tasks(args.output_root)
    print(f"Collected {len(tasks)} inference tasks")
    if not tasks:
        return

    gpu_tasks = [(task, idx % args.num_gpus) for idx, task in enumerate(tasks)]
    with Pool(args.num_gpus) as pool:
        results = pool.map(run_task, gpu_tasks)

    success = sum(1 for item in results if item)
    print(f"Inference done: {success}/{len(tasks)} succeeded")


if __name__ == "__main__":
    main()
