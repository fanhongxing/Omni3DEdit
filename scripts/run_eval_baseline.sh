#!/usr/bin/env bash
set -euo pipefail

python evaluation/evaluate.py \
  --mode source_copy \
  --data_root /path/to/train_data_raw \
  --material_base /path/to/3DCoMPaT_Processed \
  --mask_root /path/to/testpart_glb \
  --output_dir ./results_source_copy \
  --datasets material partnet partnet_mobility partnet_voxhammer
