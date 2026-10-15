#!/usr/bin/env python3
"""Transport-only launcher: longer connections/retries, unchanged C0 requests."""
from pathlib import Path
import runpy
import sys

import httpx
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
POLICY = {"connect_seconds": 30.0, "read_seconds": 180.0,
          "write_seconds": 60.0, "pool_seconds": 60.0, "sdk_max_retries": 5}


def make_client(**kwargs):
    kwargs["timeout"] = httpx.Timeout(connect=POLICY["connect_seconds"], read=POLICY["read_seconds"],
                                      write=POLICY["write_seconds"], pool=POLICY["pool_seconds"])
    kwargs["max_retries"] = POLICY["sdk_max_retries"]
    return OpenAI(**kwargs)


def install():
    sys.path.insert(0, str(ROOT))
    import core.gemini_grounder as stage
    import vlm_query.vlm_agent as guidance
    stage.OpenAI = make_client
    guidance.OpenAI = make_client


if __name__ == "__main__":
    install()
    sys.argv[0] = str(ROOT / "main.py")
    runpy.run_path(str(ROOT / "main.py"), run_name="__main__")
