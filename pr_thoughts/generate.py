import json

import pyarrow.parquet as pq
from transformers import AutoTokenizer
from vllm import LLM, SamplingParams

from prompt import should_process, build_prompt

MODEL = "Qwen/Qwen3.5-397B-A17B"
MAX_PROMPT_TOKENS = 32000

if __name__ == "__main__":   # vLLM's worker processes re-import this file
    tokenizer = AutoTokenizer.from_pretrained(MODEL)
    llm = LLM(model=MODEL, tensor_parallel_size=8, max_model_len=48100)
    sampling_params = SamplingParams(temperature=0.6, top_p=0.95, top_k=20, max_tokens=16000)

    rows = pq.read_table("data/input.parquet").to_pylist()

    records, prompts = [], []
    for row in rows:
        if not should_process(row):
            continue
        prompt, knobs = build_prompt(row)
        if len(tokenizer.encode(prompt)) > MAX_PROMPT_TOKENS:
            continue
        records.append({"repo_id": row["repo_id"], "pr_number": row["pr_number"], "knobs": knobs, "prompt": prompt})
        prompts.append(tokenizer.apply_chat_template([{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True))

    outputs = llm.generate(prompts, sampling_params)

    with open("data/generation.jsonl", "w") as f:
        for record, output in zip(records, outputs):
            record["generation"] = output.outputs[0].text   # thinking, then </think>, then the answer
            f.write(json.dumps(record) + "\n")
