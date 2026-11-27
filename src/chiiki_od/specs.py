"""データセット定義（datasets/*.yaml）と指標カード（indicators/*.yaml）の読み込みと検証。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from . import paths


@cache
def _validator(name: str) -> Draft202012Validator:
    with open(paths.SCHEMAS / name, encoding="utf-8") as f:
        return Draft202012Validator(json.load(f))


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: YAMLの中身が辞書ではありません")
    return data


def _schema_errors(data: dict, schema: str, where: str) -> list[str]:
    errs = []
    for e in sorted(_validator(schema).iter_errors(data), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in e.path) or "(全体)"
        errs.append(f"{where}: {loc}: {e.message}")
    return errs


# ---- データセット ---------------------------------------------------------

def dataset_files() -> list[Path]:
    return sorted(p for p in paths.DATASETS.glob("*.yaml") if not p.name.startswith("_"))


def load_dataset(dataset_id: str) -> dict:
    path = paths.DATASETS / f"{dataset_id}.yaml"
    if not path.exists():
        known = ", ".join(p.stem for p in dataset_files())
        raise FileNotFoundError(f"データセット {dataset_id!r} がありません。登録済み: {known}")
    return _load_yaml(path)


# ---- 指標カード -----------------------------------------------------------

def card_files() -> list[Path]:
    return sorted(p for p in paths.INDICATORS.glob("*.yaml") if not p.name.startswith("_"))


def load_card(card_id: str) -> dict:
    return _load_yaml(paths.INDICATORS / f"{card_id}.yaml")


def on_site(card: dict) -> bool:
    """サイトに出す指標か。カードに hidden_from_site があれば、カタログ・結果・質問窓口から外す。"""
    return not card.get("hidden_from_site")


@dataclass
class CheckResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def check_all() -> CheckResult:
    """全データセット定義と全指標カードを検証する（CIで毎回実行）。"""
    res = CheckResult()
    dataset_ids = set()
    for p in dataset_files():
        d = _load_yaml(p)
        res.errors += _schema_errors(d, "dataset.schema.json", f"datasets/{p.name}")
        if d.get("id") != p.stem:
            res.errors.append(f"datasets/{p.name}: id ({d.get('id')}) がファイル名と一致しません")
        if d.get("verified") is False:
            res.warnings.append(f"datasets/{p.name}: 実ファイルでの列構成の確認が済んでいません")
        dataset_ids.add(p.stem)

    card_ids = {p.stem for p in card_files()}
    for p in card_files():
        c = _load_yaml(p)
        where = f"indicators/{p.name}"
        res.errors += _schema_errors(c, "indicator_card.schema.json", where)
        if c.get("id") != p.stem:
            res.errors.append(f"{where}: id ({c.get('id')}) がファイル名と一致しません")
        script = c.get("script")
        if script and not (paths.ROOT / script).exists():
            res.errors.append(f"{where}: script {script} が見つかりません")
        for part in ("numerator", "denominator"):
            ds = (c.get(part) or {}).get("dataset")
            if ds and ds not in dataset_ids:
                res.errors.append(f"{where}: {part}.dataset {ds!r} が datasets/ にありません")
        for alt in c.get("alternatives") or []:
            if alt.get("id") not in card_ids:
                res.warnings.append(f"{where}: 代替指標 {alt.get('id')!r} はまだカードがありません（作成候補）")
        if c.get("status") == "draft":
            res.warnings.append(f"{where}: status が draft です（レビュー前）")
    return res
