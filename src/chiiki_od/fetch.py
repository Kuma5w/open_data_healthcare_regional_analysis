"""元データのダウンロード（data/raw/<dataset>/ に保存し、ハッシュ値を記録）。"""

from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path

from . import manifest, paths, specs

USER_AGENT = "chiiki-od/0.1 (research; +https://github.com/Kuma5w/open_data_healthcare_regional_analysis)"


def raw_path(dataset_id: str, file_spec: dict) -> Path:
    suffix = {"csv": ".csv", "xlsx": ".xlsx", "zip": ".zip"}[file_spec["format"]]
    return paths.RAW / dataset_id / f"{file_spec['key']}{suffix}"


def fetch_dataset(dataset_id: str, force: bool = False) -> list[Path]:
    ds = specs.load_dataset(dataset_id)
    man = manifest.load(dataset_id)
    saved = []
    for fs in ds.get("files", []):
        url = fs["url"]
        if not url.startswith("http"):
            raise ValueError(f"{dataset_id}/{fs['key']}: URLが未設定です（{url}）。datasets/{dataset_id}.yaml を埋めてください")
        dest = raw_path(dataset_id, fs)
        previous = man["files"].get(fs["key"], {})
        if dest.exists() and not force:
            print(f"既にあります（--force で再取得）: {dest.relative_to(paths.ROOT)}")
            fetched_at = previous.get("fetched_at") or manifest.now()
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            print(f"取得中: {url}")
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as out:
                shutil.copyfileobj(r, out)
            fetched_at = manifest.now()
        man["files"][fs["key"]] = {
            "url": url,
            "as_of": fs.get("as_of"),
            "raw_path": str(dest.relative_to(paths.ROOT)),
            "bytes": dest.stat().st_size,
            "sha256": manifest.sha256(dest),
            "fetched_at": fetched_at,
        }
        saved.append(dest)
    manifest.save(dataset_id, man)
    return saved
