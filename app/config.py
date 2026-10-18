import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
class Config:
    SECRET_KEY = os.environ.get("SG_SECRET_KEY", "change-this-in-the-lab")
    DATABASE = os.environ.get("SG_DATABASE", str(ROOT / "instance" / "shadowgallery.db"))
    UPLOAD_DIR = os.environ.get("SG_UPLOAD_DIR", "/var/lib/shadowgallery/uploads")
    UPLOAD_TOKEN = os.environ.get("SG_UPLOAD_TOKEN", "worker-token-change-on-deploy")
