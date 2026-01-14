"""
utils.py

Small collection of utilities: filesystem helpers, JSON atomic write, stable fingerprint,
timestamp generator, and a minimal logger setup helper.

All functions are intentionally lightweight and dependency-free.
"""

from typing import Any, Dict, Optional
from pathlib import Path
import json
import tempfile
import os
import hashlib
from datetime import datetime
import logging


def ensure_dir(path: str) -> str:
    """
    Ensure directory exists; returns the path.
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


def write_json_atomic(path: str, data: Any, indent: int = 2) -> None:
    """
    Write JSON to a temp file and atomically move into place.
    """
    p = Path(path)
    ensure_dir(str(p.parent))
    fd, tmp = tempfile.mkstemp(prefix=p.name, dir=str(p.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=indent, sort_keys=True, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(p))
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def read_json(path: str) -> Optional[Dict]:
    p = Path(path)
    if not p.exists():
        return None
    with p.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def stable_fingerprint(obj: Any, truncate: int = 16) -> str:
    """
    Deterministic fingerprint of a Python object (via JSON canonicalisation).
    """
    s = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return h[:truncate]


def timestamp_iso() -> str:
    """
    Return current UTC ISO timestamp without microseconds.
    """
    return datetime.utcnow().replace(microsecond=0).isoformat()


def setup_basic_logger(name: str = "app", level: int = logging.INFO) -> logging.Logger:
    """
    Return a logger configured with a StreamHandler and a compact formatter.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(level)
    ch = logging.StreamHandler()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    return logger


# demo block
if __name__ == "__main__":
    ensure_dir("tmp_demo")
    write_json_atomic("tmp_demo/test.json", {"a": 1, "b": 2})
    print("fp:", stable_fingerprint({"a":1, "b":2}))
    print("ts:", timestamp_iso())
    log = setup_basic_logger("demo", level=logging.DEBUG)
    log.info("demo logger ready")
