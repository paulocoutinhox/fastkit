from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"
MOUNT = "/vendor/tabler-icons"
ASSETS = [
    {"name": "tabler-icons", "kind": "css", "path": "tabler-icons.min.css", "order": 15}
]
