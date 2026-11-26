"""リポジトリ内の決まった置き場所。

データ本体（data/raw, data/processed, data/outputs）はGitに入れない。
変換の記録（manifests/）と指標カード（indicators/）はGitに入れる。
"""

from __future__ import annotations

import os
from pathlib import Path

# 環境変数 CHIIKI_OD_ROOT で上書きできる（別の場所にデータを置きたい場合）
ROOT = Path(os.environ.get("CHIIKI_OD_ROOT", Path(__file__).resolve().parents[2]))

DATASETS = ROOT / "datasets"
INDICATORS = ROOT / "indicators"
REFERENCE = ROOT / "reference"
SCHEMAS = ROOT / "schemas"
MANIFESTS = ROOT / "manifests"
CODEBOOKS = ROOT / "codebooks"
SITE = ROOT / "site"
FIXTURES = ROOT / "tests" / "fixtures"

DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
OUTPUTS = DATA / "outputs"


def ensure_dirs() -> None:
    for p in (RAW, PROCESSED, OUTPUTS, MANIFESTS):
        p.mkdir(parents=True, exist_ok=True)
