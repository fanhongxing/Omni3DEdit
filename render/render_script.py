import os
import subprocess
import json
import math
import multiprocessing
import shutil
import pandas as pd
import argparse

# ---------------------- Configuration ----------------------
# Moved to argument parser for GitHub open-sourcing

# Dataset -> CSV file mapping
CSV_MAP = {
    "material": "test_pair_split1.csv",
    "partnet": "test_pair_split1.csv",
    "partnet_voxhammer": "test_pair_split1.csv",
    "partnet_mobility": "test.csv",
    "animation_test": "test.csv",
}

# ---------------------- Helper Functions ----------------------
def load_metadata(dataset_path, dataset_name, material_base):
    """
    Load metadata.csv and return a dict: sha256 -> (glb_absolute_path, dataset_name)
    For material, special handling; for others, uses local_path.
    """
    metadata_file = os.path.join(dataset_path, "metadata.csv")
    if not os.path.isfile(metadata_file):
        print(f"Warning: metadata.csv not found in {dataset_path}")
        return {}

    df = pd.read_csv(metadata_file)
    sha2info = {}

    if dataset_name == "material":
        # material: use file_identifier to construct full path under material_base
        for _, row in df.iterrows():
            sha256 = row["sha256"]
            file_id = row["file_identifier"]
            if pd.isna(file_id):
                continue
            # Determine subfolder based on suffix
            if file_id.endswith("_0"):
                subfolder = "comp_coarse_0"
            elif file_id.endswith("_0_1"):
                subfolder = "comp_coarse_0_1"
            elif file_id.endswith("_r"):
                subfolder = "comp_coarse_0_r"
            else:
                print(f"Unknown suffix for material file {file_id}, skipping")
                continue
            glb_filename = f"{file_id}.glb"
            glb_path = os.path.join(material_base, subfolder, glb_filename)
            if os.path.exists(glb_path):
                sha2info[sha256] = (glb_path, dataset_name)
            else:
                print(f"Material GLB not found: {glb_path}")
    else:
        # Other datasets: local_path column gives relative path from dataset_path
        for _, row in df.iterrows():
            sha256 = row["sha256"]
            local_path = row["local_path"]
            if pd.isna(local_path):
                continue
            abs_path = os.path.join(dataset_path, local_path)
            if os.path.exists(abs_path):
                sha2info[sha256] = (abs_path, dataset_name)
            else:
                print(f"GLB not found: {abs_path}")

    return sha2info

def collect_all_tasks(train_data_root, material_base):
    """
    Walk through all datasets, read CSVs, collect unique sha256.
    Returns a dict: sha256 -> (glb_path, dataset_name)
    """
    all_tasks = {}  # sha256 -> (glb_path, dataset_name)
    for dataset_name in CSV_MAP.keys():
        dataset_path = os.path.join(train_data_root, dataset_name)
        if not os.path.isdir(dataset_path):
            print(f"Dataset directory not found: {dataset_path}, skipping")
            continue

        # Load metadata for this dataset (sha256 -> glb path + dataset_name)
        sha2info = load_metadata(dataset_path, dataset_name, material_base)
        if not sha2info:
            print(f"No metadata loaded for {dataset_name}, skipping")
            continue

        # Read the CSV file (source/target pairs)
        csv_file = os.path.join(dataset_path, CSV_MAP[dataset_name])
        if not os.path.isfile(csv_file):
            print(f"CSV file not found: {csv_file}, skipping")
            continue

        df_pairs = pd.read_csv(csv_file)
        required_cols = ["source_sha256", "target_sha256"]
        if not all(c in df_pairs.columns for c in required_cols):
            print(f"CSV {csv_file} missing required columns, skipping")
            continue

        for _, row in df_pairs.iterrows():
            src = row["source_sha256"]
            tgt = row["target_sha256"]
            for sha in (src, tgt):
                if sha in sha2info:
                    if sha not in all_tasks:
                        all_tasks[sha] = sha2info[sha]
                else:
                    print(f"Warning: sha256 {sha} from {csv_file} not found in metadata")
    return all_tasks

def render_worker(task_list, gpu_id, worker_id, args):
    """
    Worker process: render a list of (sha256, glb_path, dataset_name)
    """
    views = [{"yaw": -math.pi/2, "pitch": 0, "radius": 2.0, "fov": 0.8}]
    views_json = json.dumps(views)

    print(f"Worker {worker_id} (GPU {gpu_id}) started with {len(task_list)} tasks.", flush=True)

    for idx, (sha256, glb_path, dataset_name) in enumerate(task_list):
        # Output path inside dataset's own cond_img folder
        out_dir = os.path.join(args.train_data_root, dataset_name, "cond_img")
        os.makedirs(out_dir, exist_ok=True)
        out_png = os.path.join(out_dir, f"{sha256}.png")

        if os.path.exists(out_png):
            print(f"[Worker {worker_id}] Skip existing: {out_png}", flush=True)
            continue

        # Temporary render folder inside the same cond_img (to avoid cross-dataset mixing)
        temp_dir = os.path.join(out_dir, "temp_renders", sha256)
        os.makedirs(temp_dir, exist_ok=True)

        cmd = [
            args.blender_executable,
            "-b",
            "-P", args.script_path,
            "--",
            "--object", glb_path,
            "--output_folder", temp_dir,
            "--views", views_json,
            "--resolution", str(args.resolution),
            "--engine", "CYCLES"
        ]

        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)

        try:
            print(f"[Worker {worker_id}] [{idx+1}/{len(task_list)}] Rendering {sha256} from {glb_path}", flush=True)
            result = subprocess.run(cmd, env=env, timeout=args.render_timeout)

            default_output = os.path.join(temp_dir, "000.png")
            if os.path.exists(default_output):
                os.rename(default_output, out_png)
                print(f"[Worker {worker_id}] Saved: {out_png}", flush=True)
            else:
                print(f"[Worker {worker_id}] Expected output {default_output} not found", flush=True)

        except subprocess.TimeoutExpired:
            print(f"[Worker {worker_id}] TIMEOUT for {sha256}", flush=True)
        except Exception as e:
            print(f"[Worker {worker_id}] EXCEPTION for {sha256}: {e}", flush=True)
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    print(f"Worker {worker_id} finished.", flush=True)

# ---------------------- Main ----------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render 3D assets for Omni3DEdit benchmark.")
    parser.add_argument("--blender_executable", type=str, required=True, help="Path to the Blender executable.")
    parser.add_argument("--script_path", type=str, default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "blender_render.py"), help="Path to blender_render.py script.")
    parser.add_argument("--train_data_root", type=str, required=True, help="Root directory containing the datasets.")
    parser.add_argument("--material_base", type=str, required=True, help="Base directory for 3DCoMPaT processed materials.")
    parser.add_argument("--gpu_ids", type=int, nargs='+', default=[0], help="List of GPU IDs to use for rendering.")
    parser.add_argument("--procs_per_gpu", type=int, default=1, help="Number of processes to run per GPU.")
    parser.add_argument("--render_timeout", type=int, default=300, help="Timeout in seconds for each render task.")
    parser.add_argument("--resolution", type=int, default=512, help="Render resolution.")
    
    args = parser.parse_args()

    if not os.path.isfile(args.blender_executable):
        raise FileNotFoundError(f"Blender executable not found: {args.blender_executable}")
    if not os.path.isfile(args.script_path):
        raise FileNotFoundError(f"Blender script not found: {args.script_path}")

    # Gather all unique rendering tasks
    tasks_dict = collect_all_tasks(args.train_data_root, args.material_base)
    if not tasks_dict:
        print("No rendering tasks found. Exiting.")
        raise SystemExit(1)

    # Convert to list of (sha256, glb_path, dataset_name) for distribution
    task_items = [(sha, path, ds) for sha, (path, ds) in tasks_dict.items()]
    print(f"Found {len(task_items)} unique objects to render.")

    total_procs = len(args.gpu_ids) * args.procs_per_gpu
    chunk_size = math.ceil(len(task_items) / total_procs)

    processes = []
    for i in range(total_procs):
        gpu_idx = i // args.procs_per_gpu
        if gpu_idx >= len(args.gpu_ids):
            break
        gpu_id = args.gpu_ids[gpu_idx]
        start = i * chunk_size
        end = start + chunk_size
        chunk = task_items[start:end]
        if not chunk:
            continue
        p = multiprocessing.Process(target=render_worker, args=(chunk, gpu_id, i, args))
        processes.append(p)
        p.start()

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("KeyboardInterrupt received. Terminating workers...")
        for p in processes:
            if p.is_alive():
                p.terminate()
        for p in processes:
            p.join()

    print("All renders complete.")