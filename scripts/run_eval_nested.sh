#!/usr/bin/env bash
set -euo pipefail

python evaluation/evaluate.py \
  --mode inference \
  --nested_preds \
  --data_root /path/to/train_data_raw \
  --pred_root /path/to/train_inference_glb \
  --material_base /path/to/3DCoMPaT_Processed \
  --output_dir ./results_nested_inference \
  --datasets partnet partnet_mobility partnet_voxhammer material
