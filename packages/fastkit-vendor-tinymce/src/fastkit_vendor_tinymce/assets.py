from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"
MOUNT = "/vendor/tinymce"
ASSETS = [{"name": "tinymce", "kind": "js", "path": "tinymce/tinymce.min.js", "order": 30, "attrs": {"referrerpolicy": "origin"}}]
