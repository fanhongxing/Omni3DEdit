# Omni3DEdit

### A Unified 3D Editing Benchmark with Region Annotations

[![Project Page](https://img.shields.io/badge/Project-Page-blue?style=for-the-badge&logo=github)](https://fanhongxing.github.io/Omni3DEdit/)
[![Paper](https://img.shields.io/badge/Paper-PDF-red?style=for-the-badge&logo=adobeacrobatreader)](https://arxiv.org/abs/xxxx.xxxxx)

> Hongxing Fan, Haotian Lu, Rui Chen, Weibin Yun, Zehuan Huang, Lu Sheng  
> Beihang University

## Abstract

We present **Omni3DEdit**, a unified benchmark for instruction-guided 3D editing with explicit edited-region annotations containing **128,906** paired source-target 3D assets across five edit families.

## Repository Overview

This repository currently includes:

- dataset construction scripts for multiple data sources
- rendering utilities for conditional images
- evaluation scripts for both baseline and inference outputs

Main folders:

- `data_processing/`: dataset preprocessing pipelines
- `render/`: Blender-based rendering scripts
- `evaluation/`: benchmark metric computation
- `scripts/`: runnable command examples
- `asset/`: static assets for project page / teaser

## Project Structure

```text
Omni3DEdit/
├── README.md
├── requirements.txt
├── asset/
├── data_processing/
│   ├── material/
│   ├── partnet/
│   ├── partnet_mobility/
│   └── partnet_voxhammer/
├── evaluation/
│   └── evaluate.py
├── render/
│   ├── blender_render.py
│   └── render_script.py
└── scripts/
    ├── run_process.sh
    ├── run_eval_baseline.sh
    ├── run_eval_inference.sh
    └── run_eval_nested.sh
```

## Environment Setup

### 1. Create Python environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

### 2. External tools

Some scripts require external software beyond Python packages:

- **Blender**: required by `render/` and several data processing scripts
- **SAPIEN**: required by `data_processing/partnet_mobility/04_render_urdf_views.py`
- **VoxHammer repo**: required by `data_processing/partnet_voxhammer/03/04/06` wrappers

### 3. Optional API key (for instruction generation)

PartNet-Mobility and PartNet-VoxHammer prompt generation scripts use Gemini:

```bash
export GEMINI_API_KEY="YOUR_KEY"
```

## Data Processing

### PartNet pipeline

Script:

- `data_processing/partnet/process_partnet.py`

Example:

```bash
python data_processing/partnet/process_partnet.py \
  --json_file /path/to/partnet_add_dataset.json \
  --base_dest_path /path/to/output/partnet/raw \
  --parent_dir /path/to/partnet_root \
  --max_items 86598
```

Output files (under `base_dest_path` parent directory):

- `metadata.csv`
- `pair.csv`

### PartNet-Mobility pipeline

Recommended order:

1. `01_generate_modified_urdf.py`
2. `02_convert_urdf_to_glb_blender.py`
3. `03_build_metadata_csv.py`
4. `04_render_urdf_views.py`
5. `05_generate_instructions.py`
6. `06_build_pair_csv.py`

### PartNet-VoxHammer pipeline

Recommended order:

1. `01_batch_obj_to_glb.py`
2. `02_generate_part_prompts.py`
3. `03_batch_render_rgb_mask.py` (run inside VoxHammer root)
4. `04_batch_inpaint.py` (run inside VoxHammer root)
5. `05_batch_normalize_blender.py`
6. `06_batch_inference.py` (run inside VoxHammer root)

Run the following scripts under `data_processing/partnet_mobility/` and
`data_processing/partnet_voxhammer/` directly, and install dependencies from
the root `requirements.txt`.

### Material subset usage

The `material` subset in this repository currently provides metadata and pair
definitions, and is mainly consumed during evaluation.

Available files under `data_processing/material/`:

- `data/pair.csv`: source-target instruction pairs
- `data/comp_coarse_0.json`, `data/comp_coarse_0_1.json`, `data/comp_coarse_0_r.json`: style jsons
- `metadata/`: class hierarchy and split metadata
- `loaders/utils3D/`: GLTF/material helper utilities

Practical workflow:

1. Prepare the benchmark dataset root with a `material/` folder containing
   `metadata.csv` and test split CSV (same format as evaluator expects).
2. Prepare `--material_base` pointing to 3DCoMPaT processed GLBs.
3. Run evaluation with `--datasets material` (or include it in multi-dataset runs).

Minimal example:

```bash
python evaluation/evaluate.py \
  --mode inference \
  --data_root /path/to/train_data_raw \
  --pred_root /path/to/train_inference_img_glb \
  --material_base /path/to/3DCoMPaT_Processed \
  --output_dir ./results_material \
  --datasets material
```

Note: this repository does not yet include a standalone end-to-end material
construction script analogous to `data_processing/partnet/process_partnet.py`.

## Rendering Conditional Images

Use `render/render_script.py` to batch render unique GLBs referenced by benchmark pairs:

```bash
python render/render_script.py \
  --blender_executable /path/to/blender \
  --train_data_root /path/to/train_data_raw \
  --material_base /path/to/3DCoMPaT_Processed \
  --gpu_ids 0 1 \
  --procs_per_gpu 1 \
  --resolution 512
```

Outputs are saved to each dataset's `cond_img/` folder.

## Evaluation

Core evaluator: `evaluation/evaluate.py`

Supported evaluation modes:

- `source_copy`: baseline where prediction is source mesh itself
- `inference`: evaluate model-generated outputs

### Run baseline evaluation

```bash
python evaluation/evaluate.py \
  --mode source_copy \
  --data_root /path/to/train_data_raw \
  --material_base /path/to/3DCoMPaT_Processed \
  --mask_root /path/to/testpart_glb \
  --output_dir ./results_source_copy \
  --datasets material partnet partnet_mobility partnet_voxhammer
```

### Run inference evaluation

```bash
python evaluation/evaluate.py \
  --mode inference \
  --data_root /path/to/train_data_raw \
  --pred_root /path/to/train_inference_img_glb \
  --material_base /path/to/3DCoMPaT_Processed \
  --mask_root /path/to/testpart_glb \
  --output_dir ./results_inference \
  --datasets animation_test partnet partnet_mobility partnet_voxhammer material
```

### Run nested-output inference evaluation

Use this mode when predictions are stored as:
`<pred_root>/<dataset>/<source_sha256>_<target_sha256>/output.glb`

```bash
python evaluation/evaluate.py \
  --mode inference \
  --nested_preds \
  --data_root /path/to/train_data_raw \
  --pred_root /path/to/train_inference_glb \
  --material_base /path/to/3DCoMPaT_Processed \
  --output_dir ./results_nested_inference \
  --datasets partnet partnet_mobility partnet_voxhammer material
```

## Evaluation Outputs

For each dataset, results are saved under:

- `<output_dir>/<mode>/<dataset>/all_results.json`
- `<output_dir>/<mode>/<dataset>/average_results.txt`
- `<output_dir>/<mode>/<dataset>/missing_files.txt` (if any)
- `<output_dir>/<mode>/<dataset>/failed_samples.txt` (if any)

## Notes and Limitations

- `evaluation/evaluate.py` uses GPU by default when CUDA is available.
- `pyrender` headless rendering relies on EGL (`PYOPENGL_PLATFORM=egl` is set in code).
- Some pipeline wrappers assume specific upstream repositories and folder layouts.
- The paper badge currently contains a placeholder arXiv ID (`xxxx.xxxxx`).

## Citation

```bibtex
@inproceedings{fan2026omni3dedit,
  title     = {Omni3DEdit: A Unified 3D Editing Benchmark with Region Annotations},
  author    = {Fan, Hongxing and Lu, Haotian and Chen, Rui and Yun, Weibin and Huang, Zehuan and Sheng, Lu},
  year      = {2026}
}
```
