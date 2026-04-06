# scripts/run_eval_nested.sh
# 注意加了 --nested_preds 参数
python evaluate.py \
    --mode inference \
    --nested_preds \
    --data_root /path/to/train_data_raw \
    --pred_root /path/to/train_inference_glb \
    --material_base /path/to/3DCoMPaT_Processed \
    --output_dir ./results_nested_inference \
    --datasets partnet partnet_mobility partnet_voxhammer material