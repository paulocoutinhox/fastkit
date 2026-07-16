from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"
MOUNT = "/vendor/jquery"
ASSETS = [{"name": "jquery", "kind": "js", "path": "jquery.min.js", "order": 10}]
