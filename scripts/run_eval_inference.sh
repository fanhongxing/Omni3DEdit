#!/usr/bin/env bash
set -euo pipefail

python evaluation/evaluate.py \
  --mode inference \
  --data_root /path/to/train_data_raw \
  --pred_root /path/to/train_inference_img_glb \
  --material_base /path/to/3DCoMPaT_Processed \
  --mask_root /path/to/testpart_glb \
  --output_dir ./results_inference \
  --datasets animation_test partnet partnet_mobility partnet_voxhammer material
