"""サイトと解説チャットボットが読む site/catalog.json を作る。

チャットボットはこのファイル（指標カードとデータセット定義）だけを根拠に回答する。
"""

from __future__ import annotations

import json

from . import manifest, paths, specs


def build() -> dict:
    cards = [specs.load_card(p.stem) for p in specs.card_files()]
    datasets = []
    for p in specs.dataset_files():
        d = specs.load_dataset(p.stem)
        datasets.append(
            {
                "id": d["id"],
                "title": d["title"],
                "publisher": d["publisher"],
                "source_page": d["source_page"],
                "attribution": d["license"]["attribution"],
                "update_frequency": d.get("update_frequency"),
                "verified": d["verified"],
                "columns": [
                    {k: c[k] for k in ("name", "type", "description") if k in c}
                    for c in d.get("columns", [])
                ],
                "notes": d.get("notes", []),
                "related": d.get("related", []),
                "codebook": (
                    f"codebooks/{d['id']}.csv" if (paths.CODEBOOKS / f"{d['id']}.csv").exists() else None
                ),
            }
        )
    catalog = {"generated_at": manifest.now(), "indicators": cards, "datasets": datasets}
    paths.SITE.mkdir(parents=True, exist_ok=True)
    (paths.SITE / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    return catalog
