import json
import os
from pathlib import Path


def load_manifest(filename: str = "ai-agent.json") -> dict:
    manifest_path = Path(__file__).parent / filename
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_state_field(state, field: str):
    if state is None:
        return None
    if not hasattr(state, field):
        return None
    value = getattr(state, field)
    if callable(value):
        try:
            return value()
        except TypeError:
            return value
    return value


def normalize_state_key(value):
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) > 0:
        return normalize_state_key(value[0])
    if isinstance(value, dict):
        return normalize_state_key(value.get("name") or value.get("id"))
    if isinstance(value, str):
        return value
    return None


def maybe_rerun():
    rerun = getattr(__import__("streamlit"), "experimental_rerun", None)
    if callable(rerun):
        try:
            rerun()
        except Exception:
            pass
