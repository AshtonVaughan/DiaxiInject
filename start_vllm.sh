#!/bin/bash
export HF_TOKEN=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
python3 -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-4-Scout-17B-16E-Instruct \
  --max-model-len 8192 \
  --port 8000 \
  --dtype bfloat16 \
  --gpu-memory-utilization 0.95 \
  --enforce-eager \
  2>&1 | tee /root/vllm.log
