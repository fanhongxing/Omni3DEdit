# PartNet-Mobility Pipeline

This folder is a cleaned and shareable version of the articulation data pipeline.

## What This Pipeline Produces

Given PartNet-Mobility-style sample folders, this pipeline generates:

1. Modified URDF variants (`mobility_mod_*.urdf`)
2. Converted GLB files (`mobility.glb`, `mobility_mod_*.glb`)
3. Metadata table (`metadata.csv` with SHA256)
4. Rendered image views (`*_view0.png`, `*_view1.png`, ...)
5. Text edit instructions (`instructions.json`)
6. Training pairs (`pair.csv`)

## Scripts and Order

Run scripts in this order:

1. `01_generate_modified_urdf.py`
2. `02_convert_urdf_to_glb_blender.py`
3. `03_build_metadata_csv.py`
4. `04_render_urdf_views.py`
5. `05_generate_instructions.py`
6. `06_build_pair_csv.py`

## Recommended Directory Layout

Example:

- `dataset/` contains per-sample folders with `mobility.urdf`
- `raw/` stores converted GLB files
- `metadata.csv` and `pair.csv` are generated outputs

A sample folder can look like:

- `dataset/1001/mobility.urdf`
- `dataset/1001/mobility_mod_0.urdf`
- `dataset/1001/mobility_mod_1.urdf`
- `dataset/1001/mobility_mod_2.urdf`
- `dataset/1001/1001_mobility_view0.png`
- `dataset/1001/1001_mobility_mod_0_view0.png`
- `dataset/1001/instructions.json`

## Environment Setup

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Additional tools:

- Blender (for script 02)
- Phobos Blender addon (for URDF import in script 02)

For instruction generation (script 05), provide Gemini API key via env var:

```bash
export GEMINI_API_KEY="YOUR_KEY"
```

## Usage

### 1) Generate modified URDF files

```bash
python 01_generate_modified_urdf.py \
  --dataset-dir /path/to/dataset \
  --source-name mobility.urdf \
  --output-count 3
```

### 2) Convert URDF to GLB (run with Blender)

```bash
blender --background --python 02_convert_urdf_to_glb_blender.py -- \
  /path/to/dataset /path/to/raw mobility
```

Notes:

- The last argument `mobility` is the URDF filename prefix filter.
- This command converts files like `mobility.urdf`, `mobility_mod_0.urdf`, etc.

### 3) Build metadata.csv

```bash
python 03_build_metadata_csv.py \
  --raw-dir /path/to/raw \
  --save-path /path/to/metadata.csv \
  --local-path-prefix raw
```

### 4) Render URDF views

Save renders into each sample directory:

```bash
python 04_render_urdf_views.py \
  --dataset-dir /path/to/dataset
```

Or save renders to a separate root:

```bash
python 04_render_urdf_views.py \
  --dataset-dir /path/to/dataset \
  --output-dir /path/to/renders
```

### 5) Generate instructions.json

```bash
python 05_generate_instructions.py \
  --dataset-dir /path/to/dataset \
  --model-name gemini-2.5-flash \
  --view-id 0
```

### 6) Build pair.csv

```bash
python 06_build_pair_csv.py \
  --raw-dir /path/to/raw \
  --dataset-dir /path/to/dataset \
  --metadata-csv /path/to/metadata.csv \
  --output-csv /path/to/pair.csv \
  --output-count 3 \
  --instruction-json-list
```

`--instruction-json-list` stores instruction text as JSON list string (compatible with some training loaders).

## Input/Output Contracts

### Script 01

Input:

- `dataset/<id>/mobility.urdf`

Output:

- `dataset/<id>/mobility_mod_0.urdf` ...

### Script 02

Input:

- URDF files from script 01

Output:

- `raw/<id>/mobility.glb`
- `raw/<id>/mobility_mod_0.glb` ...

### Script 03

Input:

- `raw/<id>/*.glb`

Output:

- `metadata.csv` with `sha256` and `local_path`

### Script 04

Input:

- `dataset/<id>/*.urdf`

Output:

- render images named as `<id>_<urdf_stem>_view<k>.png`

### Script 05

Input:

- Original and modified URDF files
- before/after render images for selected `view-id`

Output:

- `dataset/<id>/instructions.json`

### Script 06

Input:

- `raw/<id>/mobility*.glb`
- `metadata.csv`
- `dataset/<id>/instructions.json`

Output:

- `pair.csv` with columns:
  - `source_sha256`
  - `target_sha256`
  - `instruction`

## Common Pitfalls

1. `instructions.json` is empty:
- Ensure script 04 generated both original and modified images for the same `view-id`.

2. Missing hash in pair generation:
- Ensure `--local-path-prefix` in script 03 matches the key format expected by script 06 (`raw/<id>/<file>.glb`).

3. Blender import failure:
- Verify Phobos is installed and can import URDF in Blender.

4. API failures in instruction generation:
- Verify `GEMINI_API_KEY` is set and network access to Gemini API is available.