"""Token Factory LLM client -- thin wrapper around OpenAI-compatible API.

Run directly to verify connectivity:
    python -m copilot.llm
"""

from __future__ import annotations

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Nebius Token Factory endpoint
BASE_URL = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
API_KEY = os.getenv("NEBIUS_API_KEY", "")

# Model IDs on Token Factory
NANO = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
SUPER = "nvidia/nemotron-3-super-120b-a12b"
ULTRA = "nvidia/Nemotron-3-Ultra-550b-a55b"

DEFAULT_MODEL = SUPER


def get_client() -> OpenAI:
    """Return an OpenAI client pointed at Token Factory."""
    # Inside an OpenShell sandbox the gateway injects the real key; any placeholder works.
    managed = "inference.local" in BASE_URL
    if not API_KEY and not managed:
        raise RuntimeError("NEBIUS_API_KEY is not set. Copy .env.example to .env and fill it in.")
    return OpenAI(base_url=BASE_URL, api_key=API_KEY or "openshell-managed")


def chat(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    system: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    """Single-turn chat completion. Returns the assistant message text."""
    client = get_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Hello Nemotron -- run with: python -m copilot.llm
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== Hello Nemotron (Stage 0) ===\n")

    for model_id, label in [(NANO, "Nano 30b"), (SUPER, "Super 120b")]:
        print(f"--- {label} ({model_id}) ---")
        try:
            reply = chat(
                "In one sentence, what makes a great lecture notebook?",
                model=model_id,
                max_tokens=128,
            )
            print(reply)
        except Exception as e:
            print(f"ERROR: {e}")
        print()

    print("Stage 0 complete. If both models replied, Token Factory is working.")
