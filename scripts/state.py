"""
JSON state persistence for Edith automation on GitHub Actions.
State files live in state/ and get committed back to the repo after each run
(replaces local SQLite that can't survive on ephemeral runners).
"""
import json, os

STATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state")

def path(name):
    return os.path.join(STATE_DIR, name)

def load(name, default):
    p = path(name)
    if os.path.exists(p):
        try:
            with open(p) as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save(name, data):
    p = path(name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        json.dump(data, f, indent=2)
