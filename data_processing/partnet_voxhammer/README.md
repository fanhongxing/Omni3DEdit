# PartNet-VoxHammer Pipeline

This folder is a cleaned and shareable pipeline wrapper for PartNet + VoxHammer workflows.

## Important Runtime Constraint

Scripts `03`, `04`, and `06` call VoxHammer commands directly:

- `python utils/render_rgb_and_mask.py`
- `python utils/inpaint.py`
- `python inference.py`

Because these are repository-relative imports, you must run scripts `03`, `04`, and `06` from the VoxHammer repository root.

## Script List

- `_obj_to_glb_worker_blender.py`: Internal Blender worker that exports OBJ to GLB
- `01_batch_obj_to_glb.py`: Parallel launcher for OBJ to GLB conversion
- `02_generate_part_prompts.py`: Generate per-part edit prompt json with Gemini
- `03_batch_render_rgb_mask.py`: Batch render RGB/mask with VoxHammer render utility
- `04_batch_inpaint.py`: Batch inpaint with VoxHammer inpaint utility
- `05_batch_normalize_blender.py`: Batch normalize model/mask GLB pairs with Blender
- `06_batch_inference.py`: Batch 3D inference with VoxHammer `inference.py`

## Recommended Processing Order

1. Run `01_batch_obj_to_glb.py`
2. Run `02_generate_part_prompts.py`
3. Run `03_batch_render_rgb_mask.py` (inside VoxHammer root)
4. Run `04_batch_inpaint.py` (inside VoxHammer root)
5. Run `05_batch_normalize_blender.py`
6. Run `06_batch_inference.py` (inside VoxHammer root)

## Data Assumptions

Dataset root has per-model folders such as:

- `<dataset_dir>/<model_id>/objs/*.obj`
- `<dataset_dir>/<model_id>/result.json`

After step 01:

- `<dataset_dir>/<model_id>/objs/glbs/model_merged.glb`
- `<dataset_dir>/<model_id>/objs/glbs/<part_id>.glb`

After step 02:

- `<dataset_dir>/<model_id>/<part_id>.json` with field `prompt`

After step 03:

- `<output_root>/<model_id>_<part_id>/images/render_*.png`
- `<output_root>/<model_id>_<part_id>/images/mask_*.png`
- `<output_root>/<model_id>_<part_id>/model.glb`
- `<output_root>/<model_id>_<part_id>/mask.glb`

After step 04:

- `<output_root>/<model_id>_<part_id>/images/2d_render.png`
- `<output_root>/<model_id>_<part_id>/images/2d_mask.png`
- `<output_root>/<model_id>_<part_id>/images/2d_edit.png`

After step 06:

- `<output_root>/<model_id>_<part_id>/output.glb`

## Usage Examples

### Step 01: OBJ to GLB (parallel Blender)

```bash
python scripts/partnet_voxhammer_pipeline/01_batch_obj_to_glb.py \
  --dataset-dir /path/to/partnet_data_v0/data_v0 \
  --blender-bin /usr/local/bin/blender \
  --num-workers 8
```

### Step 02: Generate part prompts

```bash
export GEMINI_API_KEY="YOUR_KEY"
python scripts/partnet_voxhammer_pipeline/02_generate_part_prompts.py \
  --dataset-dir /path/to/partnet_data_v0/data_v0 \
  --model-name gemini-2.5-flash-lite
```

### Step 03: Batch render RGB and mask (must run in VoxHammer root)

```bash
cd /path/to/VoxHammer
python /path/to/scripts/partnet_voxhammer_pipeline/03_batch_render_rgb_mask.py \
  --dataset-dir /path/to/partnet_data_v0/data_v0 \
  --output-root /path/to/partnet_data_v0/data_v0/outputs \
  --num-workers 8
```

### Step 04: Batch inpaint (must run in VoxHammer root)

```bash
cd /path/to/VoxHammer
python /path/to/scripts/partnet_voxhammer_pipeline/04_batch_inpaint.py \
  --dataset-dir /path/to/partnet_data_v0/data_v0 \
  --output-root /path/to/partnet_data_v0/data_v0/outputs \
  --num-gpus 4
```

### Step 05: Batch normalization

```bash
blender --background --python scripts/partnet_voxhammer_pipeline/05_batch_normalize_blender.py -- \
  /path/to/partnet_data_v0/data_v0/outputs
```

### Step 06: Batch VoxHammer inference (must run in VoxHammer root)

```bash
cd /path/to/VoxHammer
python /path/to/scripts/partnet_voxhammer_pipeline/06_batch_inference.py \
  --output-root /path/to/partnet_data_v0/data_v0/outputs \
  --num-gpus 4
```

Step 06 requires normalized files:

- `normalize/model_normalized.glb`
- `normalize/mask.glb`

If they are missing, the sample is skipped.

## Notes

- Step 06 is direct batch command execution and does not use HTTP workers.
- If a sample already has the expected output file, that task is skipped.
- Ensure your VoxHammer environment is correctly installed before running steps 03, 04, and 06.
