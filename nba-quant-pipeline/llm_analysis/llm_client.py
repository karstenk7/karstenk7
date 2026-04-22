"""
Thin wrapper around an LLM for text generation.

Supports two backends (selected via LLM_BACKEND env var):
  - "openai"      — calls the OpenAI ChatCompletion API (default)
  - "huggingface" — runs a local causal-LM via HuggingFace Transformers

Set LLM_BACKEND and the relevant keys/model names in your .env:
  LLM_BACKEND=openai
  OPENAI_API_KEY=sk-...
  LLM_MODEL=gpt-4o-mini

  — or —

  LLM_BACKEND=huggingface
  HF_MODEL=mistralai/Mistral-7B-Instruct-v0.2
"""

from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

_BACKEND = os.getenv("LLM_BACKEND", "openai").lower()


def generate(prompt: str, system: Optional[str] = None, max_tokens: int = 1024) -> str:
    """Generate text from a prompt using the configured LLM backend."""
    if _BACKEND == "openai":
        return _generate_openai(prompt, system, max_tokens)
    elif _BACKEND == "huggingface":
        return _generate_hf(prompt, system, max_tokens)
    else:
        raise ValueError(f"Unknown LLM_BACKEND: {_BACKEND!r}. Use 'openai' or 'huggingface'.")


# ── OpenAI ──────────────────────────────────────────────────────────────

def _generate_openai(prompt: str, system: Optional[str], max_tokens: int) -> str:
    import openai

    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.3,
    )
    return resp.choices[0].message.content.strip()


# ── HuggingFace local ──────────────────────────────────────────────────

_hf_pipeline = None


def _get_hf_pipeline():
    global _hf_pipeline
    if _hf_pipeline is None:
        from transformers import pipeline as hf_pipeline

        model_name = os.getenv("HF_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")
        _hf_pipeline = hf_pipeline(
            "text-generation",
            model=model_name,
            device_map="auto",
            torch_dtype="auto",
        )
    return _hf_pipeline


def _generate_hf(prompt: str, system: Optional[str], max_tokens: int) -> str:
    pipe = _get_hf_pipeline()
    full_prompt = ""
    if system:
        full_prompt += f"[INST] <<SYS>>\n{system}\n<</SYS>>\n\n{prompt} [/INST]"
    else:
        full_prompt = f"[INST] {prompt} [/INST]"

    result = pipe(full_prompt, max_new_tokens=max_tokens, do_sample=True, temperature=0.3)
    return result[0]["generated_text"].split("[/INST]")[-1].strip()
