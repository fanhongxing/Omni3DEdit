import argparse
import json
import os
import random
from pathlib import Path

import google.generativeai as genai

FIXED_JSONS = {"result.json", "result_after_merging.json", "meta.json"}


def extract_objs_with_path(node, path=None):
    path = path or []
    objs_map = {}

    current_name = node.get("name", node.get("text", "Unknown"))
    current_path = path + [current_name]

    if "objs" in node:
        for obj_name in node["objs"]:
            objs_map[obj_name] = current_path

    for child in node.get("children", []):
        objs_map.update(extract_objs_with_path(child, current_path))

    return objs_map


def has_generated_prompt_json(model_folder):
    existing_jsons = {file.name for file in model_folder.glob("*.json")}
    return len(existing_jsons - FIXED_JSONS) > 0


def build_prompt(model_name, hierarchy_path):
    return (
        f"Model: {model_name}\\n"
        f"Part hierarchy: {' > '.join(hierarchy_path)}\\n"
        "Task: Provide one concise prompt describing how to edit this part. "
        "The change should be realistic and describe only the final target appearance. "
        "Example output: 'A dog.'"
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Generate per-part text prompts from PartNet hierarchy.")
    parser.add_argument("--dataset-dir", required=True, help="Dataset root with per-model folders.")
    parser.add_argument("--api-key", default=None, help="Gemini API key. If omitted, use GEMINI_API_KEY.")
    parser.add_argument("--model-name", default="gemini-2.5-flash-lite", help="Gemini model name.")
    parser.add_argument("--seed", type=int, default=0, help="Random seed.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing generated part prompt json.")
    parser.add_argument("--limit", type=int, default=None, help="Optional cap on number of model folders.")
    return parser.parse_args()


def main():
    args = parse_args()
    random.seed(args.seed)

    api_key = args.api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing API key. Pass --api-key or set GEMINI_API_KEY.")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(args.model_name)

    dataset_dir = Path(args.dataset_dir)
    model_folders = [
        folder
        for folder in sorted(dataset_dir.iterdir())
        if folder.is_dir() and folder.name.isdigit()
    ]
    if args.limit is not None:
        model_folders = model_folders[: args.limit]

    for model_folder in model_folders:
        if has_generated_prompt_json(model_folder) and not args.overwrite:
            print(f"Skip {model_folder.name}: generated prompt json already exists")
            continue

        result_json_path = model_folder / "result.json"
        if not result_json_path.exists():
            continue

        with open(result_json_path, "r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)

        objs_to_paths = {}
        for root_node in data:
            objs_to_paths.update(extract_objs_with_path(root_node))

        if not objs_to_paths:
            continue

        selected_obj, hierarchy_path = random.choice(list(objs_to_paths.items()))
        model_name = data[0].get("name", "UnknownModel")

        instruction = build_prompt(model_name, hierarchy_path)
        try:
            response = model.generate_content(instruction)
            generated_prompt = response.text.strip()
        except Exception as exc:
            print(f"Gemini failed for {model_folder.name}/{selected_obj}: {exc}")
            continue

        output_path = model_folder / f"{selected_obj}.json"
        with open(output_path, "w", encoding="utf-8") as file_obj:
            json.dump({"prompt": generated_prompt}, file_obj, ensure_ascii=False, indent=2)

        print(f"Saved {output_path}")


if __name__ == "__main__":
    main()
