#!/usr/bin/env python3
"""
Omni3DEdit Evaluation Script
Supports evaluating both Inference outputs and Source Copy baseline.
Usage examples provided in the README.
"""

import os
import json
import time
import glob
import argparse
import numpy as np
import torch
import torch.nn.functional as F
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Union
from PIL import Image
import pandas as pd
from tqdm import tqdm

# Set EGL backend for headless rendering
os.environ['PYOPENGL_PLATFORM'] = 'egl'

import trimesh
import pyrender
from skimage.metrics import peak_signal_noise_ratio as psnr
from skimage.metrics import structural_similarity as ssim


# ======================================================================
# Core rendering and geometry utilities
# ======================================================================

def generate_camera_poses(center: np.ndarray, radius: float, n_views: int,
                          up: np.ndarray = np.array([0, 1, 0]),
                          yfov: float = np.pi / 3.0) -> List[np.ndarray]:
    poses = []
    for i in range(n_views):
        angle = 2 * np.pi * i / n_views
        eye = center + radius * np.array([np.cos(angle), 0.3, np.sin(angle)])
        z = eye - center
        z /= np.linalg.norm(z)
        x = np.cross(up, z)
        x /= np.linalg.norm(x)
        y = np.cross(z, x)
        mat = np.eye(4)
        mat[:3, 0] = x
        mat[:3, 1] = y
        mat[:3, 2] = z
        mat[:3, 3] = eye
        poses.append(mat)
    return poses

def get_scene_center_and_radius(scene: trimesh.Scene) -> Tuple[np.ndarray, float]:
    bounds = scene.bounds
    if np.any(np.isinf(bounds)) or np.any(np.isnan(bounds)):
        vertices = []
        for geom in scene.geometry.values():
            if isinstance(geom, trimesh.Trimesh):
                vertices.append(geom.vertices)
        if vertices:
            all_verts = np.vstack(vertices)
            center = np.mean(all_verts, axis=0)
            radius = np.max(np.linalg.norm(all_verts - center, axis=1)) * 1.2
        else:
            center = np.zeros(3)
            radius = 1.0
    else:
        center = (bounds[0] + bounds[1]) / 2
        radius = np.linalg.norm(bounds[1] - bounds[0]) * 0.8
    return center.astype(np.float32), float(radius)

def render_views_fixed_poses(
    scene: trimesh.Scene,
    poses: List[np.ndarray],
    img_size: Tuple[int, int] = (512, 512),
    camera_yfov: float = np.pi / 3.0,
) -> Optional[List[Image.Image]]:
    try:
        pr_scene = pyrender.Scene(bg_color=[1, 1, 1, 1])
        directional_light = pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=3.0)
        light_pose = np.eye(4)
        light_pose[:3, 3] = [0, 2, 0]
        pr_scene.add(directional_light, pose=light_pose)

        for geom in scene.geometry.values():
            if isinstance(geom, trimesh.Trimesh):
                try:
                    mesh = pyrender.Mesh.from_trimesh(geom, smooth=False)
                except Exception:
                    mesh = pyrender.Mesh.from_trimesh(geom, smooth=False, material=None)
                pr_scene.add(mesh)

        camera = pyrender.PerspectiveCamera(yfov=camera_yfov)
        renderer = pyrender.OffscreenRenderer(*img_size)

        images = []
        for pose in poses:
            cam_node = pr_scene.add(camera, pose=pose)
            color, _ = renderer.render(pr_scene)
            images.append(Image.fromarray(color))
            pr_scene.remove_node(cam_node)

        renderer.delete()
        return images
    except Exception as e:
        print(f"Rendering failed: {e}")
        return None

def render_edit_region_masks(
    edit_region_glb: str,
    poses: List[np.ndarray],
    img_size: Tuple[int, int] = (512, 512),
    camera_yfov: float = np.pi / 3.0,
) -> Optional[List[np.ndarray]]:
    try:
        scene = trimesh.load(edit_region_glb, force="scene")
        pr_scene = pyrender.Scene(bg_color=[0, 0, 0, 0])

        point_light = pyrender.PointLight(color=[1.0, 1.0, 1.0], intensity=2.0)
        light_pose = np.eye(4)
        light_pose[:3, 3] = [0, 2, 0]
        pr_scene.add(point_light, pose=light_pose)

        try:
            material = pyrender.MetallicRoughnessMaterial(
                baseColorFactor=[1.0, 1.0, 1.0, 1.0],
                metallicFactor=0.0,
                roughnessFactor=0.5,
                alphaMode="OPAQUE"
            )
        except Exception:
            material = None

        for geom in scene.geometry.values():
            if isinstance(geom, trimesh.Trimesh):
                try:
                    mesh = pyrender.Mesh.from_trimesh(geom, material=material, smooth=False)
                except Exception:
                    mesh = pyrender.Mesh.from_trimesh(geom, smooth=False)
                pr_scene.add(mesh)

        camera = pyrender.PerspectiveCamera(yfov=camera_yfov)
        renderer = pyrender.OffscreenRenderer(*img_size)

        masks = []
        for pose in poses:
            cam_node = pr_scene.add(camera, pose=pose)
            color, _ = renderer.render(pr_scene)
            gray = np.mean(color, axis=-1) / 255.0
            mask = (gray > 0.5).astype(np.float32)
            masks.append(mask)
            pr_scene.remove_node(cam_node)

        renderer.delete()
        return masks
    except Exception as e:
        print(f"Failed to render masks: {e}")
        return None

def extract_point_cloud(scene: trimesh.Scene, n_points: int = 4096) -> np.ndarray:
    meshes = [geom for geom in scene.geometry.values() if isinstance(geom, trimesh.Trimesh)]
    if not meshes:
        return np.zeros((0, 3), dtype=np.float32)
    combined = trimesh.util.concatenate(meshes)
    pts, _ = trimesh.sample.sample_surface(combined, n_points)
    return pts.astype(np.float32)

def generate_masks_from_diff(
    src_imgs: List[Image.Image],
    tgt_imgs: List[Image.Image],
    threshold: float = 0.05,
) -> List[np.ndarray]:
    masks = []
    for src, tgt in zip(src_imgs, tgt_imgs):
        s = np.array(src.convert("RGB")).astype(np.float32) / 255.0
        t = np.array(tgt.convert("RGB")).astype(np.float32) / 255.0
        diff = np.abs(s - t).mean(axis=-1)
        masks.append((diff > threshold).astype(np.float32))
    return masks


# ======================================================================
# Metrics Classes
# ======================================================================

class CLIPTextImageSimilarity:
    def __init__(self, model_name: str = "ViT-B/32", device: str = "cuda"):
        import open_clip
        self.device = device
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            model_name, pretrained="openai"
        )
        self.tokenizer = open_clip.get_tokenizer(model_name)
        self.model.eval().to(device)

    @torch.no_grad()
    def score(self, images: List[Image.Image], text: str) -> float:
        if not images:
            return 0.0
        imgs = torch.stack([self.preprocess(i) for i in images]).to(self.device)
        tokens = self.tokenizer([text]).to(self.device)
        i_feat = F.normalize(self.model.encode_image(imgs), dim=-1)
        t_feat = F.normalize(self.model.encode_text(tokens), dim=-1)
        return (i_feat @ t_feat.T).squeeze(-1).mean().item()

class DINOImageSimilarity:
    def __init__(self, model_name: str = "facebook/dinov2-base", device: str = "cuda"):
        from transformers import AutoImageProcessor, AutoModel
        self.device = device
        self.processor = AutoImageProcessor.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).eval().to(device)

    @torch.no_grad()
    def score(self, src: List[Image.Image], edit: List[Image.Image]) -> float:
        if not src or not edit or len(src) != len(edit):
            return 0.0
        def encode(imgs):
            inputs = self.processor(images=imgs, return_tensors="pt").to(self.device)
            outputs = self.model(**inputs)
            feat = outputs.last_hidden_state[:, 0]
            return F.normalize(feat, dim=-1)
        src_feat = encode(src)
        edit_feat = encode(edit)
        return (src_feat * edit_feat).sum(dim=-1).mean().item()

class MaskedImageQualityMetrics:
    def __init__(self, device: str = "cuda"):
        import lpips
        self.device = device
        self.lpips_fn = lpips.LPIPS(net="alex").eval().to(device)

    def _to_tensor(self, img: Image.Image) -> torch.Tensor:
        arr = np.array(img.convert("RGB")).astype(np.float32) / 127.5 - 1.0
        return torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to(self.device)

    @torch.no_grad()
    def masked_score(self, pred: List[Image.Image], gt: List[Image.Image], edit_masks: List[np.ndarray]) -> Dict[str, float]:
        ps, ss, ls = [], [], []
        for p, g, mask in zip(pred, gt, edit_masks):
            mask_bool = mask.astype(bool)
            mask_inv = ~mask_bool

            pn = np.array(p.convert("RGB"))
            gn = np.array(g.convert("RGB"))

            if mask_inv.sum() == 0:
                continue
            pn_masked = pn[mask_inv]
            gn_masked = gn[mask_inv]
            
            # Handle perfect match edge case
            err = np.mean((gn_masked - pn_masked) ** 2)
            if err == 0:
                ps.append(100.0)
            else:
                ps.append(psnr(gn_masked, pn_masked, data_range=255))

            p_mod = pn.copy()
            g_mod = gn.copy()
            p_mod[mask_bool] = g_mod[mask_bool]
            ss.append(ssim(g_mod, p_mod, channel_axis=-1, data_range=255))
            
            p_img = Image.fromarray(p_mod)
            g_img = Image.fromarray(g_mod)
            ls.append(self.lpips_fn(self._to_tensor(p_img), self._to_tensor(g_img)).item())

        return {
            "Masked PSNR": np.mean(ps) if ps else None,
            "Masked SSIM": np.mean(ss) if ss else None,
            "Masked LPIPS": np.mean(ls) if ls else None
        }

def chamfer_distance(pc1: np.ndarray, pc2: np.ndarray) -> float:
    if len(pc1) == 0 or len(pc2) == 0:
        return float("inf")
    a = torch.from_numpy(pc1).float().unsqueeze(0)
    b = torch.from_numpy(pc2).float().unsqueeze(0)
    d = torch.cdist(a, b)
    return (d.min(2).values.mean() + d.min(1).values.mean()).item()

def region_f1(pred_mask: np.ndarray, gt_mask: np.ndarray, thr: float = 0.5) -> float:
    p = (pred_mask >= thr).astype(bool)
    g = (gt_mask >= thr).astype(bool)
    tp = (p & g).sum()
    fp = (p & ~g).sum()
    fn = (~p & g).sum()
    prec = tp / (tp + fp + 1e-8)
    rec = tp / (tp + fn + 1e-8)
    return 2 * prec * rec / (prec + rec + 1e-8)


# ======================================================================
# Main Evaluator Wrapper
# ======================================================================

class BenchmarkEvaluator:
    def __init__(self, device: str = "cuda", n_views: int = 8, img_size: int = 512):
        self.device = device
        self.n_views = n_views
        self.img_size = (img_size, img_size)
        self.clip = CLIPTextImageSimilarity(device=device)
        self.dino = DINOImageSimilarity(device=device)
        self.iqm_masked = MaskedImageQualityMetrics(device=device)

    def _prepare_fixed_camera(self, src_scene: trimesh.Scene) -> Tuple[List[np.ndarray], float, np.ndarray]:
        center, radius = get_scene_center_and_radius(src_scene)
        poses = generate_camera_poses(center, radius, self.n_views)
        return poses, radius, center

    def _load_scene_safe(self, glb_path: str) -> Optional[trimesh.Scene]:
        try:
            return trimesh.load(glb_path, force="scene")
        except Exception as e:
            print(f"  Error loading {glb_path}: {e}, trying mesh-only...")
            try:
                mesh = trimesh.load(glb_path, force="mesh")
                scene = trimesh.Scene()
                scene.add_geometry(mesh)
                return scene
            except Exception as e2:
                print(f"  Even mesh-only failed: {e2}")
                return None

    def evaluate_glb(self, src_glb: str, edit_glb: str, instruction: str, gt_glb: Optional[str] = None, 
                     edit_region_glb: Optional[str] = None, runtime_sec: float = 0.0) -> Optional[Dict]:
        src_scene = self._load_scene_safe(src_glb)
        edit_scene = self._load_scene_safe(edit_glb)
        if src_scene is None or edit_scene is None: return None

        try:
            poses, _, _ = self._prepare_fixed_camera(src_scene)
        except Exception as e:
            print(f"  Camera preparation failed: {e}")
            return None

        src_imgs = render_views_fixed_poses(src_scene, poses, self.img_size)
        edit_imgs = render_views_fixed_poses(edit_scene, poses, self.img_size)
        if src_imgs is None or edit_imgs is None: return None

        src_pc = extract_point_cloud(src_scene)
        edit_pc = extract_point_cloud(edit_scene)

        results = {
            "CLIP-T": self.clip.score(edit_imgs, instruction),
            "Preserve CD": chamfer_distance(src_pc, edit_pc),
            "Runtime": runtime_sec,
        }

        # Handle Ground Truth evaluation
        edit_masks_gt = None
        if gt_glb is not None:
            gt_scene = self._load_scene_safe(gt_glb)
            if gt_scene is not None:
                gt_imgs = render_views_fixed_poses(gt_scene, poses, self.img_size)
                if gt_imgs is not None:
                    results["DINO-I"] = self.dino.score(gt_imgs, edit_imgs)
                    edit_masks_gt = generate_masks_from_diff(src_imgs, gt_imgs)
            if "DINO-I" not in results: results["DINO-I"] = None
        else:
            results["DINO-I"] = None

        # Prioritize explicit mask GLB if provided
        if edit_region_glb is not None and os.path.exists(edit_region_glb):
            edit_masks_gt = render_edit_region_masks(edit_region_glb, poses, self.img_size)

        if edit_masks_gt is not None:
            masked_scores = self.iqm_masked.masked_score(edit_imgs, src_imgs, edit_masks_gt)
            results.update(masked_scores)
            pred_masks = generate_masks_from_diff(src_imgs, edit_imgs)
            f1s = [region_f1(p, g) for p, g in zip(pred_masks, edit_masks_gt)]
            results["Region-F1"] = float(np.mean(f1s))
        else:
            results.update({"Masked PSNR": None, "Masked SSIM": None, "Masked LPIPS": None, "Region-F1": None})

        return results


# ======================================================================
# Dataset Utilities
# ======================================================================

def build_material_glb_map(metadata_df: pd.DataFrame, glb_base_dir: str) -> Dict[str, str]:
    mapping = {}
    for _, row in metadata_df.iterrows():
        sha = row["sha256"]
        file_id = row["file_identifier"]
        if not isinstance(file_id, str): continue

        suffix = file_id.split("__")[-1] if "__" in file_id else ""
        subfolder = {"0": "comp_coarse_0", "0_1": "comp_coarse_0_1", "0_r": "comp_coarse_0_r"}.get(suffix, "")
        
        glb_path = os.path.join(glb_base_dir, subfolder, f"{file_id}.glb") if subfolder else os.path.join(glb_base_dir, f"{file_id}.glb")
        
        if os.path.exists(glb_path): mapping[sha] = glb_path
    return mapping

def extract_instruction(inst_str):
    try:
        inst_list = json.loads(inst_str)
        return inst_list[0] if isinstance(inst_list, list) and len(inst_list) > 0 else inst_str
    except:
        return inst_str


# ======================================================================
# Main Execution Entrypoint
# ======================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate 3D Editing Results for Omni3DEdit.")
    
    # Core directories
    parser.add_argument("--data_root", type=str, required=True, help="Path to raw benchmark datasets (e.g., ./data).")
    parser.add_argument("--pred_root", type=str, default="", help="Path to inference generated GLBs (not needed for source_copy).")
    parser.add_argument("--output_dir", type=str, default="./evaluation_results", help="Directory to save evaluation results.")
    
    # Dataset specific paths (optional, used if provided)
    parser.add_argument("--material_base", type=str, default="", help="Path to 3DCoMPaT_Processed for material dataset.")
    parser.add_argument("--mask_root", type=str, default="", help="Path to pre-extracted masks (optional).")
    
    # Evaluation settings
    parser.add_argument("--mode", type=str, choices=["inference", "source_copy"], default="inference", help="Evaluation mode.")
    parser.add_argument("--nested_preds", action="store_true", help="If set, looks for predictions in <src>_<tgt>/output.glb. Otherwise flat <tgt>.glb.")
    parser.add_argument("--datasets", nargs="+", default=["partnet", "partnet_mobility", "partnet_voxhammer", "animation_test", "material"], help="List of datasets to evaluate.")
    
    args = parser.parse_args()

    N_VIEWS, IMG_SIZE = 8, 512
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

    for ds_name in args.datasets:
        print(f"\n{'='*80}\nProcessing dataset: {ds_name} | Mode: {args.mode}\n{'='*80}")
        ds_out_dir = os.path.join(args.output_dir, args.mode, ds_name)
        os.makedirs(ds_out_dir, exist_ok=True)

        ds_root = os.path.join(args.data_root, ds_name)
        meta_csv = os.path.join(ds_root, "metadata.csv")
        test_file = os.path.join(ds_root, "test_pair_split1.csv" if ds_name in ["material", "partnet", "partnet_voxhammer"] else "test.csv")

        if not os.path.exists(meta_csv) or not os.path.exists(test_file):
            print(f"Skipping {ds_name}: Metadata or test file not found in {ds_root}")
            continue

        metadata_df = pd.read_csv(meta_csv)
        sha256_to_glb = {}

        # 1. Build Source GLB mapping
        if ds_name == "material" and args.material_base:
            sha256_to_glb = build_material_glb_map(metadata_df, args.material_base)
        else:
            raw_dir = os.path.join(ds_root, "raw")
            for _, row in metadata_df.iterrows():
                if isinstance(row.get("local_path"), str) and row["local_path"].endswith(".glb"):
                    l_path = row["local_path"][4:] if row["local_path"].startswith("raw/") else row["local_path"]
                    full_path = os.path.join(raw_dir, l_path)
                    if os.path.exists(full_path): sha256_to_glb[row["sha256"]] = full_path

        # 2. Evaluate test pairs
        test_df = pd.read_csv(test_file)
        test_df["instruction"] = test_df["instruction"].apply(extract_instruction)
        evaluator = BenchmarkEvaluator(device=DEVICE, n_views=N_VIEWS, img_size=IMG_SIZE)

        all_results, missing_files, failed_samples = [], [], []

        for _, row in tqdm(test_df.iterrows(), total=len(test_df)):
            src_sha, tgt_sha, instruction = row["source_sha256"], row["target_sha256"], row["instruction"]
            src_glb, gt_glb = sha256_to_glb.get(src_sha), sha256_to_glb.get(tgt_sha)

            # Determine edit_glb path based on mode
            if args.mode == "source_copy":
                edit_glb = src_glb
            else:
                if args.nested_preds:
                    edit_glb = os.path.join(args.pred_root, ds_name, f"{src_sha}_{tgt_sha}", "output.glb")
                else:
                    edit_glb = os.path.join(args.pred_root, ds_name, f"{tgt_sha}.glb")

            # Determine mask path
            edit_region_glb = None
            if args.nested_preds and args.mode == "inference":
                mask_candidate = os.path.join(args.pred_root, ds_name, f"{src_sha}_{tgt_sha}", "mask.glb")
                if os.path.exists(mask_candidate): edit_region_glb = mask_candidate
            
            if edit_region_glb is None and args.mask_root:
                mask_candidate = os.path.join(args.mask_root, ds_name, f"{src_sha}_{tgt_sha}.glb")
                if os.path.exists(mask_candidate): edit_region_glb = mask_candidate

            # Verifications
            if not src_glb: missing_files.append(f"Source missing: {src_sha}"); continue
            if not gt_glb: missing_files.append(f"GT missing: {tgt_sha}"); continue
            if not edit_glb or not os.path.exists(edit_glb): missing_files.append(f"Edit missing: {edit_glb}"); continue

            try:
                t0 = time.perf_counter()
                res = evaluator.evaluate_glb(src_glb, edit_glb, instruction, gt_glb, edit_region_glb)
                if not res:
                    failed_samples.append(f"Failed: {src_sha} -> {tgt_sha}"); continue
                
                res.update({"Runtime": time.perf_counter() - t0, "source_sha256": src_sha, "target_sha256": tgt_sha})
                all_results.append(res)
                
                with open(os.path.join(ds_out_dir, f"{src_sha[:8]}_{tgt_sha[:8]}.json"), "w") as f:
                    json.dump(res, f, indent=2)
            except Exception as e:
                failed_samples.append(f"Error {src_sha}->{tgt_sha}: {e}")

        # 3. Aggregate Results
        if all_results:
            keys = [k for k in all_results[0].keys() if k not in ("source_sha256", "target_sha256")]
            avg = {k: np.mean([r[k] for r in all_results if r.get(k) is not None]) for k in keys}
            
            with open(os.path.join(ds_out_dir, "average_results.txt"), "w") as f:
                f.write(f"Average metrics ({args.mode}) over {len(all_results)} samples:\n")
                for k, v in avg.items(): f.write(f"{k}: {v:.6f}\n" if not np.isnan(v) else f"{k}: N/A\n")
            
            with open(os.path.join(ds_out_dir, "all_results.json"), "w") as f: json.dump(all_results, f, indent=2)

        if missing_files:
            with open(os.path.join(ds_out_dir, "missing_files.txt"), "w") as f: f.write("\n".join(missing_files))
        if failed_samples:
            with open(os.path.join(ds_out_dir, "failed_samples.txt"), "w") as f: f.write("\n".join(failed_samples))