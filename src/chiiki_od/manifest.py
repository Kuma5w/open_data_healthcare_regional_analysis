"""取得・変換の記録（manifests/<dataset>.json）。

何を、いつ、どのURLから取り、どのハッシュ値のファイルから変換したかを残す。
この記録はGitに入れるので、他の研究者が同じ元データを使っているか確かめられる。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from . import paths


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(dataset_id: str) -> Path:
    return paths.MANIFESTS / f"{dataset_id}.json"


def load(dataset_id: str) -> dict:
    p = _path(dataset_id)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"dataset": dataset_id, "files": {}, "output": None}


def save(dataset_id: str, data: dict) -> None:
    paths.MANIFESTS.mkdir(parents=True, exist_ok=True)
    _path(dataset_id).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
