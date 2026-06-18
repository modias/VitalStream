#!/usr/bin/env python3
"""Standalone test for LLM clinical reasoning."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PATIENT_ID = 10008454


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    env_path = ROOT / ".env"
    load_env_file(env_path)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        if not env_path.exists():
            print(f"ERROR: .env file not found at {env_path}")
        else:
            print("ERROR: ANTHROPIC_API_KEY is not set in .env or the environment.")
        return 1

    if not env_path.exists():
        env_path.write_text(f"ANTHROPIC_API_KEY={api_key}\n")
        print(f"Created {env_path} from environment variable.")

    try:
        from backend.services.llm_analysis import get_llm_analysis

        print(f"Calling get_llm_analysis for patient {PATIENT_ID}...")
        response = get_llm_analysis(PATIENT_ID)
        print("\n--- Claude response ---")
        print(response)
        print("--- end response ---\n")
        print("LLM TEST PASSED")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
