"""サイトと解説チャットボットが読むファイルを site/ に作る。

- site/catalog.json      指標カードとデータセット定義（チャットボットの主な根拠）
- site/search_index.json docs の節とコードブックの列見出し（チャットボットが検索して根拠に加える）
- catalog.json の results 欄には、site/results/ にある結果の一覧と、カードとの食い違い（古い結果）を載せる

チャットボットはこの2つのファイルだけを根拠に回答する。
"""

from __future__ import annotations

import csv
import json
import re

from . import boundaries, codes, manifest, paths, results, specs

REPO_URL = "https://github.com/Kuma5w/open_data_healthcare_regional_analysis"
PAGES_URL = "https://kuma5w.github.io/open_data_healthcare_regional_analysis/"

# 検索対象にする文書（docs/datasets/*.md は自動で加える）
DOCS = ["docs/indicator_card_guide.md", "reference/README.md", "docs/attribution.md", "docs/site.md"]


def _dataset_entry(d: dict) -> dict:
    return {
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


def _doc_sections(rel: str) -> list[dict]:
    """Markdown を「## 見出し」ごとの節に分ける。"""
    text = (paths.ROOT / rel).read_text(encoding="utf-8")
    title = next((ln[2:].strip() for ln in text.splitlines() if ln.startswith("# ")), rel)
    parts = re.split(r"^## ", text, flags=re.M)
    out = []
    for i, part in enumerate(parts):
        if i == 0:
            heading, body = "概要", re.sub(r"^# .*\n", "", part)
        else:
            heading, _, body = part.partition("\n")
        body = body.strip()
        if body:
            out.append({"type": "doc", "id": f"doc:{rel}#{i}", "title": f"{title} > {heading.strip()}",
                        "source": rel, "text": body})
    return out


def _codebook_entries() -> list[dict]:
    out = []
    for p in sorted(paths.CODEBOOKS.glob("*.csv")):
        with open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                out.append({
                    "type": "col",
                    "id": f"col:{p.stem}.{r['column']}",
                    "dataset": p.stem,
                    "column": r["column"],
                    "title": r["label"],
                    "item": r.get("item") or r["label"],
                    "required": r.get("required") or "",
                    "numeric": r.get("numeric") == "True",
                    "zero_if_blank": r.get("zero_if_blank") == "True",
                    "secret": r.get("secret") == "True",
                })
    return out


def _results_index(cards: list[dict]) -> dict:
    out = {}
    for c in cards:
        p = results.results_dir() / f"{c['id']}.json"
        if not p.exists():
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        out[c["id"]] = {
            "path": f"results/{c['id']}.json",
            "csv": doc.get("csv"),
            "generated_at": doc.get("generated_at"),
            "card_version": doc.get("card_version"),
            "rows": len(doc.get("rows", [])),
            "stale": results.status(c, doc),
        }
    return out


def build() -> dict:
    cards = [specs.load_card(p.stem) for p in specs.card_files()]
    datasets = [_dataset_entry(specs.load_dataset(p.stem)) for p in specs.dataset_files()]
    catalog = {
        "generated_at": manifest.now(),
        "repo_url": REPO_URL,
        "pages_url": PAGES_URL,
        "indicators": cards,
        "datasets": datasets,
        "results": _results_index(cards),
        "prefectures": codes.PREFECTURES,
        # 地図の境界（scripts/make_boundaries.py が site/geo/ に作る）。新しい時点が先
        "geo": boundaries.load_index(),
    }

    docs = [*DOCS, *(str(p.relative_to(paths.ROOT)) for p in sorted((paths.ROOT / "docs" / "datasets").glob("*.md")))]
    index = [s for rel in docs if (paths.ROOT / rel).exists() for s in _doc_sections(rel)]
    index += _codebook_entries()

    paths.SITE.mkdir(parents=True, exist_ok=True)
    (paths.SITE / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    (paths.SITE / "search_index.json").write_text(
        json.dumps({"generated_at": catalog["generated_at"], "items": index}, ensure_ascii=False, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )
    return catalog
