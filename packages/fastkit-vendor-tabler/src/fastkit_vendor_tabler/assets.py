from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"
MOUNT = "/vendor/tabler"
ASSETS = [
    {"name": "tabler-css", "kind": "css", "path": "tabler.min.css", "order": 10},
    {"name": "tabler-js", "kind": "js", "path": "tabler.min.js", "order": 20},
]
