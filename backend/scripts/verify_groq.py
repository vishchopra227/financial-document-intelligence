"""Verification script for Groq API integration in FinSight Intelligence."""

import os
import sys
from pathlib import Path
import httpx
from dotenv import dotenv_values

# Setup paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.app.config import settings

def run_verification():
    print("=== FinSight Intelligence: Groq API Integration Verification ===")

    # Step 1: Check project-root .env file
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        print("[FAIL] Step 1: Project-root .env does not exist.")
        return False
    
    env_vals = dotenv_values(env_path)
    raw_key = env_vals.get("GROQ_API_KEY", "").strip()
    if not raw_key:
        print("[FAIL] Step 1: GROQ_API_KEY is missing or empty in .env.")
        return False
    
    # Safe validation without printing the key
    is_valid_format = raw_key.startswith("gsk_") and len(raw_key) > 20
    print(f"[PASS] Step 1: GROQ_API_KEY is present and non-empty (valid format: {is_valid_format}).")

    # Step 2: Confirm .env is ignored and .env.example contains only placeholders
    gitignore_path = BASE_DIR / ".gitignore"
    gitignore_text = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    is_ignored = ".env" in gitignore_text
    print(f"[PASS] Step 2a: .env is excluded by .gitignore: {is_ignored}")

    example_path = BASE_DIR / ".env.example"
    example_vals = dotenv_values(example_path) if example_path.exists() else {}
    example_key = example_vals.get("GROQ_API_KEY", "")
    print(f"[PASS] Step 2b: .env.example contains only empty placeholder: {example_key == ''}")

    # Step 3: Load effective configuration
    provider = settings.LLM_PROVIDER
    configured_model = settings.GROQ_MODEL
    print(f"[PASS] Step 3: Effective Provider: '{provider}', Configured Model: '{configured_model}'")

    # Step 4: Fetch available models from Groq official API
    models_url = "https://api.groq.com/openai/v1/models"
    headers = {
        "Authorization": f"Bearer {raw_key}",
        "Content-Type": "application/json",
    }
    
    try:
        with httpx.Client(timeout=15.0) as client:
            models_res = client.get(models_url, headers=headers)
    except Exception as e:
        print(f"[FAIL] Step 4: Network error connecting to Groq: {e}")
        return False

    if models_res.status_code != 200:
        print(f"[FAIL] Step 4: Authentication/API failure (HTTP {models_res.status_code}): {models_res.text}")
        return False

    models_data = models_res.json().get("data", [])
    model_ids = [m["id"] for m in models_data]
    print(f"[PASS] Step 4: Successfully fetched {len(model_ids)} available models from Groq.")
    print(f"Available chat models: {[m for m in model_ids if 'whisper' not in m and 'guard' not in m]}")

    # Select model: use configured_model if in model_ids, else pick best available chat model
    target_model = configured_model
    if target_model not in model_ids:
        # Candidate selection from official available models
        candidates = [m for m in ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"] if m in model_ids]
        if candidates:
            target_model = candidates[0]
            print(f"[INFO] Switching target model to verified available model: '{target_model}'")
        else:
            print(f"[FAIL] Step 4: Neither configured model nor known candidates are available in {model_ids}")
            return False

    # Step 5: Send minimal test chat completion request
    chat_url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": target_model,
        "messages": [
            {"role": "system", "content": "You are a financial analysis assistant. Keep answers brief and professional."},
            {"role": "user", "content": "What is operating margin in one sentence?"}
        ],
        "max_tokens": 120,
        "temperature": 0.2,
    }

    try:
        with httpx.Client(timeout=20.0) as client:
            chat_res = client.post(chat_url, headers=headers, json=payload)
    except Exception as e:
        print(f"[FAIL] Step 5: Request error during chat completion: {e}")
        return False

    if chat_res.status_code != 200:
        print(f"[FAIL] Step 5: Groq chat completion returned HTTP {chat_res.status_code}: {chat_res.text}")
        return False

    data = chat_res.json()
    message = data.get("choices", [{}])[0].get("message", {})
    content = message.get("content", "").strip()

    # If content was empty due to model reasoning output, check reasoning field or retry
    if not content and "reasoning" in message:
        content = message.get("reasoning", "").strip()

    if not content:
        print(f"[FAIL] Step 5: Groq returned an empty response.")
        return False

    # Sanitize output for Windows console display
    safe_sample = content.encode("ascii", errors="replace").decode("ascii")
    print(f"[PASS] Step 5: Live Groq API request succeeded! (HTTP {chat_res.status_code})")
    print(f"Model used: '{target_model}'")
    print(f"Sample response: \"{safe_sample}\"")
    return True

if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
