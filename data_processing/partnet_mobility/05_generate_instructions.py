import argparse
import json
import os
import socket
import ssl
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import google.api_core.exceptions as gexc
import google.generativeai as genai
import requests


def parse_urdf(urdf_path):
    tree = ET.parse(urdf_path)
    root = tree.getroot()

    joints = {}
    links = {}

    for joint in root.findall("joint"):
        name = joint.attrib["name"]
        origin = joint.find("origin")
        rpy = origin.attrib.get("rpy", "0 0 0") if origin is not None else "0 0 0"
        xyz = origin.attrib.get("xyz", "0 0 0") if origin is not None else "0 0 0"

        parent = joint.find("parent")
        child = joint.find("child")
        if parent is None or child is None:
            continue

        joints[name] = {
            "xyz": xyz,
            "rpy": rpy,
            "parent": parent.attrib.get("link", ""),
            "child": child.attrib.get("link", ""),
        }

    for link in root.findall("link"):
        link_name = link.attrib.get("name", "")
        visuals = []
        for visual in link.findall("visual"):
            visual_name = visual.attrib.get("name")
            if visual_name:
                visuals.append(visual_name)
        links[link_name] = visuals

    return joints, links


def compute_diff(original_path, modified_path):
    joints_orig, _links_orig = parse_urdf(original_path)
    joints_mod, links_mod = parse_urdf(modified_path)

    diffs = []
    for joint_name, joint_info in joints_orig.items():
        if joint_name not in joints_mod:
            continue

        mod_info = joints_mod[joint_name]
        if joint_info["rpy"] == mod_info["rpy"] and joint_info["xyz"] == mod_info["xyz"]:
            continue

        child = joint_info["child"]
        parent = joint_info["parent"]
        diffs.append(
            {
                "joint": joint_name,
                "orig_xyz": joint_info["xyz"],
                "mod_xyz": mod_info["xyz"],
                "orig_rpy": joint_info["rpy"],
                "mod_rpy": mod_info["rpy"],
                "child_labels": links_mod.get(child, []),
                "parent_labels": links_mod.get(parent, []),
            }
        )

    return diffs


def build_prompt(diffs):
    if not diffs:
        diff_text = "No URDF joint differences detected."
    else:
        lines = []
        for item in diffs:
            lines.append(
                "\n".join(
                    [
                        f"Joint: {item['joint']}",
                        f"- Original xyz: {item['orig_xyz']}",
                        f"- Modified xyz: {item['mod_xyz']}",
                        f"- Original rpy: {item['orig_rpy']}",
                        f"- Modified rpy: {item['mod_rpy']}",
                        f"- Child link semantic labels: {item['child_labels']}",
                        f"- Parent link semantic labels: {item['parent_labels']}",
                    ]
                )
            )
        diff_text = "\n\n".join(lines)

    prompt = f"""
You are given a 3D object editing task.

Here is the URDF change information:
{diff_text}

You are also given two rendered images:
- Image A: before editing
- Image B: after editing

Write one clear natural language instruction for a 3D editing task.
Requirements:
- Be precise and specific.
- If the change involves rotation, describe direction (clockwise/counter-clockwise) and approximate degree.
- If the change involves translation, describe direction and approximate distance.
- If the change involves scaling or deformation, describe the magnitude.
- Mention the affected part explicitly.
- Avoid lighting, shadow, or viewpoint details.
- Output exactly one sentence.
"""
    return prompt.strip()


def safe_generate(model, inputs, max_retries=5, wait_seconds=10):
    for attempt in range(1, max_retries + 1):
        try:
            response = model.generate_content(inputs)
            if response and getattr(response, "candidates", None):
                return response
            raise RuntimeError("Empty response from Gemini")
        except (
            ValueError,
            gexc.ServiceUnavailable,
            gexc.InternalServerError,
            gexc.DeadlineExceeded,
            requests.exceptions.RequestException,
            socket.timeout,
            ssl.SSLEOFError,
            TimeoutError,
        ) as exc:
            print(f"[Retry {attempt}/{max_retries}] {type(exc).__name__}: {exc}")
            if attempt == max_retries:
                return None
            time.sleep(wait_seconds)
        except Exception as exc:
            print(f"[Retry {attempt}/{max_retries}] Unexpected {type(exc).__name__}: {exc}")
            if attempt == max_retries:
                return None
            time.sleep(wait_seconds)
    return None


def make_instruction(model, diffs, before_img, after_img, max_retries, wait_seconds):
    prompt = build_prompt(diffs)

    before_file = genai.upload_file(path=str(before_img))
    after_file = genai.upload_file(path=str(after_img))

    response = safe_generate(
        model,
        inputs=[{"text": prompt}, before_file, after_file],
        max_retries=max_retries,
        wait_seconds=wait_seconds,
    )
    if response is None:
        return ""

    return getattr(response, "text", "").strip()


def process_dataset(dataset_dir, model, view_id, overwrite, max_retries, wait_seconds):
    for folder in sorted(dataset_dir.iterdir()):
        if not folder.is_dir():
            continue

        output_path = folder / "instructions.json"
        if output_path.exists() and not overwrite:
            print(f"Skipping {folder.name}: instructions.json already exists")
            continue

        orig_urdf = folder / "mobility.urdf"
        if not orig_urdf.exists():
            continue

        orig_images = list(folder.glob(f"*_mobility_view{view_id}.png"))
        if not orig_images:
            print(f"Skipping {folder.name}: missing original image for view {view_id}")
            continue
        orig_img = orig_images[0]

        instructions = {}
        for mod_urdf in sorted(folder.glob("mobility_mod_*.urdf")):
            mod_name = mod_urdf.stem
            mod_images = list(folder.glob(f"*_{mod_name}_view{view_id}.png"))
            if not mod_images:
                print(f"Skipping {folder.name}/{mod_name}: missing modified image")
                continue
            mod_img = mod_images[0]

            diffs = compute_diff(orig_urdf, mod_urdf)
            instruction = make_instruction(
                model=model,
                diffs=diffs,
                before_img=orig_img,
                after_img=mod_img,
                max_retries=max_retries,
                wait_seconds=wait_seconds,
            )
            if instruction:
                instructions[mod_name] = instruction
                print(f"{folder.name} {mod_name}: {instruction}")

        if instructions:
            with open(output_path, "w", encoding="utf-8") as file_obj:
                json.dump(instructions, file_obj, indent=2, ensure_ascii=False)
            print(f"Saved {output_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate natural language edit instructions from URDF diffs and images.")
    parser.add_argument("--dataset-dir", required=True, help="Directory with per-sample folders.")
    parser.add_argument("--api-key", default=None, help="Gemini API key. If omitted, reads GEMINI_API_KEY env var.")
    parser.add_argument("--model-name", default="gemini-2.5-flash", help="Gemini model name.")
    parser.add_argument("--view-id", type=int, default=0, help="View index used for before/after images.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing instructions.json.")
    parser.add_argument("--max-retries", type=int, default=5, help="Max retries for API calls.")
    parser.add_argument("--retry-wait", type=int, default=10, help="Seconds to wait between retries.")
    return parser.parse_args()


def main():
    args = parse_args()

    api_key = args.api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing API key. Pass --api-key or set GEMINI_API_KEY.")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(args.model_name)

    process_dataset(
        dataset_dir=Path(args.dataset_dir),
        model=model,
        view_id=args.view_id,
        overwrite=args.overwrite,
        max_retries=args.max_retries,
        wait_seconds=args.retry_wait,
    )


if __name__ == "__main__":
    main()
