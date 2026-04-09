import json
import os
import shutil
import csv
import hashlib
import random
import argparse

def calculate_sha256_from_filename(filename):
    """Calculate SHA256 hash based on the filename."""
    return hashlib.sha256(filename.encode('utf-8')).hexdigest()

def process_filename(filename, is_source=True):
    """Process the filename. Removes the extension for source files; target files remain unchanged."""
    # Remove file extension
    name_without_ext = os.path.splitext(filename)[0]
    
    # Optional logic for target/source files can be uncommented and modified here
    # if not is_source:
    #     return name_without_ext
    # parts = name_without_ext.split('_')
    # ...
    
    return name_without_ext

def process_instruction(instruction, use_varied=True):
    """Process the instruction into a list-formatted string, optionally using varied expressions."""
    if not instruction:
        return '[""]'
    
    # Strip quotes if they exist at the boundaries
    instruction = instruction.strip()
    if (instruction.startswith('"') and instruction.endswith('"')) or \
       (instruction.startswith("'") and instruction.endswith("'")):
        instruction = instruction[1:-1]
    
    # If the instruction is already in list format, return directly
    if instruction.startswith('[') and instruction.endswith(']'):
        return instruction
    
    # Replace the beginning of the instruction if varied expressions are requested
    if use_varied and instruction.lower().startswith('add '):
        instruction = replace_add_instruction(instruction)
    
    # Escape double quotes inside the instruction
    escaped_instruction = instruction.replace('"', '""')
    
    # Return as a list-formatted string
    return f'["{escaped_instruction}"]'

def replace_add_instruction(instruction):
    """Replace instructions starting with 'add' with synonymous phrases."""
    # List of phrases synonymous with "add"
    add_variations = [
        "add", "include", "attach", "append", "insert",
        "place", "put", "position", "incorporate", "integrate",
        "supplement with", "join with", "combine with", "merge with",
        "augment with", "enhance with", "extend with", "add to the",
        "put on the", "attach to the", "place on the",
    ]
    
    # Extract the content after "add "
    original_text = instruction[4:].strip()
    
    # Randomly select a variation
    variation = random.choice(add_variations)
    
    # If the chosen phrase ends with "the", do not add an extra space
    if variation.endswith("the"):
        return f"{variation} {original_text}"
    else:
        return f"{variation} {original_text}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process PartNet dataset and generate metadata/pair CSVs for Omni3DEdit.")
    parser.add_argument("--json_file", type=str, required=True, help="Path to the input JSON file (e.g., partnet_add_dataset.json)")
    parser.add_argument("--base_dest_path", type=str, required=True, help="Base destination path for the output raw data.")
    parser.add_argument("--parent_dir", type=str, required=True, help="Parent directory containing 'source_models' and 'target_models'.")
    parser.add_argument("--max_items", type=int, default=86598, help="Maximum number of data pairs to process.")
    
    args = parser.parse_args()

    base_dataset_path = os.path.dirname(args.base_dest_path)
    source_models_dir = os.path.join(args.parent_dir, "source_models")
    target_models_dir = os.path.join(args.parent_dir, "target_models")

    # Check if source and target directories exist
    if not os.path.exists(source_models_dir):
        print(f"Error: Source models directory not found at '{source_models_dir}'. Please ensure it exists.")
        exit(1)
    if not os.path.exists(target_models_dir):
        print(f"Error: Target models directory not found at '{target_models_dir}'. Please ensure it exists.")
        exit(1)

    # Create the base destination directory if it doesn't exist
    os.makedirs(args.base_dest_path, exist_ok=True)

    try:
        with open(args.json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: JSON file not found at '{args.json_file}'. Please check the path.")
        exit(1)
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from '{args.json_file}'. Please check the file's content.")
        exit(1)

    metadata = []       # Stores metadata.csv data
    pair_data = []      # Stores pair.csv data
    sha256_cache = {}   # Caches SHA256 hashes to avoid duplicates
    processed_count = 0

    for item in data:
        if processed_count >= args.max_items:
            print(f"\nCompleted processing the first {args.max_items} data pairs. Stopping.")
            break

        original_id = item["original_model_id"]
        instruction = item["instruction"]
        source_model_file = os.path.basename(item["source_model_path"])
        target_model_file = os.path.basename(item["target_model_path"])
        
        # Construct full paths for file operations
        full_source_path = os.path.join(args.parent_dir, item["source_model_path"])
        full_target_path = os.path.join(args.parent_dir, item["target_model_path"])

        print(f"\nProcessing ID: {original_id}")
        print(f"Full source path: {full_source_path}")
        print(f"Full target path: {full_target_path}")

        # Create target directory
        dest_dir = os.path.join(args.base_dest_path, str(original_id))
        os.makedirs(dest_dir, exist_ok=True)
        
        # Get file extensions and processed filenames
        source_ext = os.path.splitext(source_model_file)[1]
        target_ext = os.path.splitext(target_model_file)[1]
        source_file_identifier = process_filename(source_model_file, is_source=True)
        target_file_identifier = process_filename(target_model_file, is_source=False)
        
        # Construct new destination file paths
        new_source_path = os.path.join(dest_dir, source_file_identifier + source_ext)
        new_target_path = os.path.join(dest_dir, target_file_identifier + target_ext)
        
        try:
            # Calculate SHA256 hashes based on filenames
            source_sha256 = calculate_sha256_from_filename(source_file_identifier)
            target_sha256 = calculate_sha256_from_filename(target_file_identifier)
            
            print(f"Source file: {source_file_identifier}, SHA256: {source_sha256}")
            print(f"Target file: {target_file_identifier}, SHA256: {target_sha256}")

            # Check and copy source file
            if not os.path.exists(new_source_path):
                if os.path.exists(full_source_path):
                    shutil.copy(full_source_path, new_source_path)
                    print(f"Successfully copied source model to: {new_source_path}")
                else:
                    print(f"Warning: Source file does not exist, skipping copy: {full_source_path}")
                    continue
            else:
                print(f"Source model already exists at {new_source_path}, skipping copy.")
                
            # Check and copy target file
            if not os.path.exists(new_target_path):
                if os.path.exists(full_target_path):
                    shutil.copy(full_target_path, new_target_path)
                    print(f"Successfully copied target model to: {new_target_path}")
                else:
                    print(f"Warning: Target file does not exist, skipping copy: {full_target_path}")
                    continue
            else:
                print(f"Target model already exists at {new_target_path}, skipping copy.")

            # Construct local paths for metadata
            source_local_path = os.path.join('raw', str(original_id), source_file_identifier + source_ext)
            target_local_path = os.path.join('raw', str(original_id), target_file_identifier + target_ext)

            # Add to metadata list (avoiding duplicates)
            if source_sha256 not in sha256_cache:
                metadata.append([
                    source_sha256, source_file_identifier,
                    "", "", False, False, False, False, source_local_path
                ])
                sha256_cache[source_sha256] = True
                
            if target_sha256 not in sha256_cache:
                metadata.append([
                    target_sha256, target_file_identifier,
                    "", "", False, False, False, False, target_local_path
                ])
                sha256_cache[target_sha256] = True
            
            # Process instruction and add to pair_data list
            processed_instruction = process_instruction(instruction, use_varied=True)
            pair_data.append([source_sha256, target_sha256, processed_instruction])
            
            processed_count += 1
            print(f"Successfully processed ID: {original_id} ({processed_count}/{args.max_items})")
            print(f"Processed instruction: {processed_instruction}")

        except Exception as e:
            print(f"Error processing ID: {original_id}. Details: {e}")

    # Write to metadata.csv
    metadata_csv_path = os.path.join(base_dataset_path, "metadata.csv")
    with open(metadata_csv_path, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["sha256", "file_identifier", "aesthetic_score", "captions", "rendered", "voxelized", "num_voxels", "cond_rendered", "local_path"])
        writer.writerows(metadata)

    # Write to pair.csv
    pair_csv_path = os.path.join(base_dataset_path, "pair.csv")
    with open(pair_csv_path, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["source_sha256", "target_sha256", "instruction"])
        writer.writerows(pair_data)

    print(f"\nProcessing complete. Processed {processed_count} data pairs.")
    print(f"metadata.csv created at: {metadata_csv_path}")
    print(f"pair.csv created at: {pair_csv_path}")
    print(f"Total unique files in metadata.csv: {len(metadata)}")
    print(f"Total data pairs in pair.csv: {len(pair_data)}")