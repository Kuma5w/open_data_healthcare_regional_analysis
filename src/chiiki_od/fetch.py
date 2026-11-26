"""元データの取得（data/raw/<dataset>/ に保存し、ハッシュ値を記録）。

公表元から直接ダウンロードするほか、手元に保存済みのファイルを取り込むこともできる
（--from-dir）。その場合も、記録には公表元のURLとファイルのハッシュ値を残す。
"""

from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from . import manifest, paths, specs

USER_AGENT = "chiiki-od/0.1 (research; +https://github.com/Kuma5w/open_data_healthcare_regional_analysis)"


def raw_path(dataset_id: str, file_spec: dict) -> Path:
    suffix = {"csv": ".csv", "xlsx": ".xlsx", "zip": ".zip"}[file_spec["format"]]
    return paths.RAW / dataset_id / f"{file_spec['key']}{suffix}"


def _download(url: str, dest: Path) -> None:
    print(f"取得中: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as out:
        shutil.copyfileobj(r, out)


def fetch_dataset(dataset_id: str, force: bool = False, from_dir: str | Path | None = None) -> list[Path]:
    """データセットの全ファイルを data/raw/ に用意する。

    from_dir を指定すると、公表元URLと同じファイル名（例: 001717798.xlsx）のファイルを
    そのフォルダから探して取り込む（ダウンロードしない）。ファイル名が公表元と違う場合は
    datasets/<id>.yaml の local_name に書く。
    """
    ds = specs.load_dataset(dataset_id)
    man = manifest.load(dataset_id)
    saved, missing = [], []
    for fs in ds.get("files", []):
        url = fs["url"]
        if not url.startswith("http"):
            raise ValueError(f"{dataset_id}/{fs['key']}: URLが未設定です（{url}）。datasets/{dataset_id}.yaml を埋めてください")
        dest = raw_path(dataset_id, fs)
        dest.parent.mkdir(parents=True, exist_ok=True)
        previous = man["files"].get(fs["key"], {})
        how = previous.get("obtained", "download")

        if dest.exists() and not force:
            print(f"既にあります（--force で取り直し）: {dest.relative_to(paths.ROOT)}")
            fetched_at = previous.get("fetched_at") or manifest.now()
        elif from_dir is not None:
            src = Path(from_dir) / (fs.get("local_name") or Path(urlparse(url).path).name)
            if not src.exists():
                missing.append(src.name)
                continue
            shutil.copy2(src, dest)
            fetched_at, how = manifest.now(), "local_copy"
            print(f"取り込み: {src} → {dest.relative_to(paths.ROOT)}")
        elif fs.get("manual_download"):
            raise ValueError(
                f"{dataset_id}/{fs['key']} は直接ダウンロードできません。{url} から手動でダウンロードし、"
                f"--from-dir でそのフォルダを指定してください（ファイル名: {fs.get('local_name', '任意')}）"
            )
        else:
            _download(url, dest)
            fetched_at, how = manifest.now(), "download"

        man["files"][fs["key"]] = {
            "url": url,
            "as_of": fs.get("as_of"),
            "raw_path": str(dest.relative_to(paths.ROOT)),
            "bytes": dest.stat().st_size,
            "sha256": manifest.sha256(dest),
            "fetched_at": fetched_at,
            "obtained": how,
        }
        saved.append(dest)
    manifest.save(dataset_id, man)
    if missing:
        raise FileNotFoundError(
            f"{from_dir} に次のファイルがありません: {', '.join(missing)}（公表元のファイル名のまま保存してください）"
        )
    return saved
