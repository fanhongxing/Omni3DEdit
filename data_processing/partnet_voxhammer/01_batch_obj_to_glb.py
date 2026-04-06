import argparse
import os
import subprocess
from multiprocessing import Pool


def collect_model_ids(dataset_dir):
    model_ids = []
    for model_id in sorted(os.listdir(dataset_dir)):
        objs_dir = os.path.join(dataset_dir, model_id, "objs")
        if not os.path.isdir(objs_dir):
            continue

        glb_dir = os.path.join(objs_dir, "glbs")
        merged_glb = os.path.join(glb_dir, "model_merged.glb")
        if os.path.exists(merged_glb):
            continue

        model_ids.append(model_id)
    return model_ids


def run_one(args_tuple):
    model_id, dataset_dir, blender_bin, worker_script = args_tuple
    cmd = [
        blender_bin,
        "--background",
        "--python",
        worker_script,
        "--",
        dataset_dir,
        model_id,
    ]
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        print(f"Failed model {model_id}")
        return False


def parse_args():
    parser = argparse.ArgumentParser(description="Batch export OBJ files to GLB with Blender.")
    parser.add_argument("--dataset-dir", required=True, help="Dataset root with per-model folders.")
    parser.add_argument("--blender-bin", required=True, help="Path to Blender executable.")
    parser.add_argument(
        "--worker-script",
        default=os.path.join(os.path.dirname(__file__), "_obj_to_glb_worker_blender.py"),
        help="Worker Blender script path.",
    )
    parser.add_argument("--num-workers", type=int, default=8, help="Number of parallel Blender processes.")
    return parser.parse_args()


def main():
    args = parse_args()

    model_ids = collect_model_ids(args.dataset_dir)
    print(f"Found {len(model_ids)} models to process")
    if not model_ids:
        return

    tasks = [
        (model_id, args.dataset_dir, args.blender_bin, args.worker_script)
        for model_id in model_ids
    ]
    with Pool(args.num_workers) as pool:
        results = pool.map(run_one, tasks)

    success = sum(1 for item in results if item)
    print(f"Finished: {success}/{len(model_ids)} succeeded")


if __name__ == "__main__":
    main()
