import json

import pyarrow.parquet as pq
from transformers import AutoTokenizer
from vllm import LLM, SamplingParams

from prompt import build_prompt

MODEL = "openai/gpt-oss-120b"
MAX_PROMPT_TOKENS = 32000

if __name__ == "__main__":   # vLLM's worker processes re-import this file
    tokenizer = AutoTokenizer.from_pretrained(MODEL)
    llm = LLM(model=MODEL, tensor_parallel_size=2)
    sampling_params = SamplingParams(temperature=1.0, top_p=1.0, max_tokens=32000)

    rows = pq.read_table("data/input.parquet").to_pylist()

    records, prompts = [], []
    for row in rows:
        prompt, config = build_prompt(row)
        if prompt is None or len(tokenizer.encode(prompt)) > MAX_PROMPT_TOKENS:
            continue
        records.append({"repo_id": row["repo_id"], "pr_number": row["pr_number"], "config": config, "prompt": prompt})
        prompts.append(tokenizer.apply_chat_template([{"role": "user", "content": prompt}], tokenize=False,
                                                     add_generation_prompt=True, reasoning_effort="high"))

    outputs = llm.generate(prompts, sampling_params)

    with open("data/generation.jsonl", "w") as f:
        for record, output in zip(records, outputs):
            record["generation"] = output.outputs[0].text   # "analysis<thinking>assistantfinal<answer>"
            f.write(json.dumps(record) + "\n")
