from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"
MOUNT = "/vendor/jsoneditor"
ASSETS = [
    {"name": "jsoneditor-css", "kind": "css", "path": "jsoneditor.min.css", "order": 16},
    {"name": "jsoneditor-js", "kind": "js", "path": "jsoneditor.min.js", "order": 35},
]
