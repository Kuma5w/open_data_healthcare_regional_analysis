"""指標スクリプト（indicators/<id>.py）を実行する。

指標スクリプトの約束
- load_inputs(sample: bool) -> dict[str, DataFrame]  入力データを読む
- compute(**inputs, **options) -> (DataFrame, list[str])  結果の表と、注記（除外件数など）を返す
数値はこの compute だけが作る。チャットボットやボタン出力も、この関数を呼ぶ。
"""

from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path

import pandas as pd

from . import manifest, paths, specs


def load_module(card_id: str):
    script = paths.INDICATORS / f"{card_id}.py"
    if not script.exists():
        raise FileNotFoundError(f"{script} がありません")
    spec = importlib.util.spec_from_file_location(f"indicators.{card_id}", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def execute(card_id: str, sample: bool = False, **options) -> tuple[pd.DataFrame, list[str], dict]:
    """指標を計算して（結果の表, 注記, 実際に渡したオプション）を返す。ファイルには書かない。"""
    mod = load_module(card_id)
    inputs = mod.load_inputs(sample=sample)
    params = inspect.signature(mod.compute).parameters
    unsupported = [k for k, v in options.items() if v and k not in params]
    if unsupported:
        raise ValueError(f"{card_id} はオプション {', '.join(unsupported)} に対応していません")
    options = {k: v for k, v in options.items() if k in params}
    result, notes = mod.compute(**inputs, **options)
    return result, notes, options


def run(card_id: str, sample: bool = False, **options) -> tuple[pd.DataFrame, list[str], Path]:
    card = specs.load_card(card_id)
    result, notes, options = execute(card_id, sample=sample, **options)

    paths.OUTPUTS.mkdir(parents=True, exist_ok=True)
    stem = card_id + ("_sample" if sample else "") + "".join(f"_{k}" for k, v in options.items() if v)
    out = paths.OUTPUTS / f"{stem}.csv"
    result.to_csv(out, index=False, encoding="utf-8-sig")

    record = {
        "indicator": card_id,
        "card_version": card.get("version"),
        "sample": sample,
        "options": options,
        "run_at": manifest.now(),
        "rows": len(result),
        "notes": notes,
        "inputs": {
            part: manifest.load(card[part]["dataset"]).get("files", {})
            for part in ("numerator", "denominator")
        } if not sample else "tests/fixtures（合成サンプル）",
        "attribution": [
            specs.load_dataset(card[p]["dataset"])["license"]["attribution"]
            for p in ("numerator", "denominator")
        ],
    }
    out.with_suffix(".json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result, notes, out
