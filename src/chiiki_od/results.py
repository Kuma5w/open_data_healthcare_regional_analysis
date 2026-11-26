"""サイトの「結果を見る」が読むファイルを site/results/ に作る。

  site/results/<id>.json  結果の表（1行ずつ配列）、列の見出し、要約、都道府県計・全国計、注記、入力ファイルのハッシュ
  site/results/<id>.csv   同じ表。列名は計算スクリプトのまま（UTF-8、BOM付き）

数値はすべて Python（指標スクリプトの compute と、このモジュールの要約）が作る。
サイトは、ここで作った値の絞り込み・並べ替え・表示・ダウンロードだけを行う。
元データは公開リポジトリに入れないため、結果は手元の data/processed から作ってコミットする。
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from . import boundaries, codes, manifest, paths, runner, specs

FORMAT = 1
QUANTILES = {"min": 0.0, "p25": 0.25, "median": 0.5, "p75": 0.75, "max": 1.0}


def results_dir() -> Path:
    return paths.SITE / "results"


def script_hash(card: dict) -> str:
    """計算スクリプトのハッシュ（改行コードの違いは無視する）。結果を作った後にスクリプトが変わったかを見分ける。"""
    data = (paths.ROOT / card["script"]).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def _col_type(s: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(s):
        return "string"
    if pd.api.types.is_integer_dtype(s):
        return "integer"
    if pd.api.types.is_numeric_dtype(s):
        return "number"
    return "string"


def _cell(v):
    if v is None or v is pd.NA:
        return None
    if isinstance(v, (bool, np.bool_)):
        return str(bool(v))
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return None if math.isnan(v) else float(v)
    return str(v)


def _round(x, digits: int):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), digits)


def _summary(values: pd.Series, digits: int) -> dict:
    v = values.dropna().astype(float)
    out = {"n": int(len(v)), "n_missing": int(values.isna().sum())}
    if len(v):
        q = v.quantile(list(QUANTILES.values()))
        out |= {k: _round(q.iloc[i], digits) for i, k in enumerate(QUANTILES)}
    return out


def _pooled(df: pd.DataFrame, out: dict, digits: int) -> dict:
    """値のある行の分子・分母をそれぞれ合計し、scale を掛けた値（都道府県計・全国計）。"""
    num, den, scale = out.get("numerator"), out.get("denominator"), out.get("scale")
    if not (num and den and scale):
        return {}
    rows = df[df[out["value"]].notna()]
    n, d = float(rows[num].sum()), float(rows[den].sum())
    return {
        "numerator_sum": _cell(rows[num].sum()),
        "denominator_sum": _cell(rows[den].sum()),
        "pooled": _round(n / d * scale, digits) if d > 0 else None,
    }


def _inputs(card: dict) -> list[dict]:
    out = []
    ids = [card[p]["dataset"] for p in ("numerator", "denominator")] + list(card.get("datasets") or [])
    for ds_id in dict.fromkeys(ids):
        d = specs.load_dataset(ds_id)
        m = manifest.load(ds_id)
        out.append({
            "dataset": ds_id,
            "title": d["title"],
            "publisher": d["publisher"],
            "source_page": d["source_page"],
            "attribution": d["license"]["attribution"],
            "manual_download": any(f.get("manual_download") for f in d.get("files", [])),
            "files": [
                {k: f.get(k) for k in ("url", "as_of", "sha256", "fetched_at", "obtained")} | {"key": key}
                for key, f in (m.get("files") or {}).items()
            ],
        })
    return out


def build(card_id: str, sample: bool = False) -> tuple[dict, pd.DataFrame]:
    """指標を計算し、サイト用の結果（辞書）と、CSVに書く表を返す。"""
    card = specs.load_card(card_id)
    out = card.get("output")
    if not out:
        raise ValueError(f"{card_id}: 指標カードに output がないため、結果を書き出せません（docs/indicator_card_guide.md）")
    df, notes, options = runner.execute(card_id, sample=sample)

    names = [c["name"] for c in out["columns"]]
    if missing := [c for c in names if c not in df.columns]:
        raise ValueError(f"{card_id}: output.columns の列 {missing} が計算結果にありません")
    if extra := [c for c in df.columns if c not in names]:
        raise ValueError(f"{card_id}: 計算結果の列 {extra} を指標カードの output.columns に書いてください")
    for key in ("area_code", "area_name", "value", "numerator", "denominator"):
        if out.get(key) and out[key] not in names:
            raise ValueError(f"{card_id}: output.{key}（{out[key]}）が output.columns にありません")

    df = df[names].reset_index(drop=True)
    full, times, time_col = df, None, out.get("time")
    if time_col:
        # 推移を持つ指標：表・地図・要約は最新の時点の行で作り、時点ごとの値は series に入れる
        if time_col not in names:
            raise ValueError(f"{card_id}: output.time（{time_col}）が output.columns にありません")
        times = sorted(full[time_col].dropna().astype(str).unique())
        df = full[full[time_col].astype(str) == times[-1]].reset_index(drop=True)
    area = df[out["area_code"]]
    if not all(isinstance(v, str) for v in area):
        raise ValueError(f"{card_id}: 地域コードの列 {out['area_code']} は文字列にしてください（先頭の0を保つため）")
    if bad := sorted({v for v in area if v[:2] not in codes.PREFECTURES}):
        raise ValueError(f"{card_id}: 先頭2桁が都道府県コードでない地域コードがあります: {bad[:5]}")

    digits = int(out.get("digits", 1))
    prec = digits + 2  # 要約は表示より2桁多く持つ
    pref = area.str[:2]
    by_pref = {}
    for code, g in df.groupby(pref, sort=True):
        by_pref[code] = {"name": codes.PREFECTURES[code]} | _summary(g[out["value"]], prec) | _pooled(g, out, prec)

    labels = {c["name"]: c for c in out["columns"]}
    doc = {
        "format": FORMAT,
        "indicator": card_id,
        "name": card["name"],
        "card_version": card["version"],
        "script": card["script"],
        "script_sha256": script_hash(card),
        "generated_at": manifest.now(),
        "sample": sample,
        "options": options,
        "output": {k: v for k, v in out.items() if k != "columns"},
        "columns": [
            {"name": n, "label": labels[n]["label"], "unit": labels[n].get("unit"), "type": _col_type(df[n])}
            for n in names
        ],
        "summary": _summary(df[out["value"]], prec),
        "national": _pooled(df, out, prec),
        "by_pref": by_pref,
        "notes": notes,
        "inputs": "tests/fixtures の合成サンプル" if sample else _inputs(card),
        "csv": f"results/{card_id}.csv",
        "rows": [[_cell(v) for v in row] for row in df.itertuples(index=False, name=None)],
    }
    if time_col:
        doc["series"] = _series(full, out, prec, times, time_col)
    return doc, full


def _series(full: pd.DataFrame, out: dict, digits: int, times: list[str], time_col: str) -> dict:
    """時点ごとの全国・都道府県の値と、地域ごとの値の並び。

    全国・都道府県の値は output.time_stat（pooled＝計、median＝中央値、mean＝平均）。
    指定がなければ、分子・分母があれば計、なければ中央値。
    """
    t = full[time_col].astype(str)
    kind = out.get("time_stat") or ("pooled" if _pooled(full.head(1), out, digits) else "median")

    def level(g: pd.DataFrame):
        if g.empty:
            return None
        if kind == "pooled":
            return _pooled(g, out, digits).get("pooled")
        if kind == "mean":
            v = g[out["value"]].dropna().astype(float)
            return _round(v.mean(), digits) if len(v) else None
        return _summary(g[out["value"]], digits).get("median")

    pref = full[out["area_code"]].str[:2]
    by_pref = {code: [level(full[(pref == code) & (t == x)]) for x in times] for code in sorted(pref.unique())}
    piv = full.assign(_t=t).groupby([out["area_code"], "_t"], sort=True)[out["value"]].first().unstack("_t")
    piv = piv.reindex(columns=times)  # 値のない地域も null の並びで残す
    return {
        "time_column": time_col,
        "times": times,
        "kind": kind,
        "national": [level(full[t == x]) for x in times],
        "by_pref": by_pref,
        "areas": {code: [_cell(v) for v in row] for code, row in zip(piv.index, piv.to_numpy(dtype=object), strict=True)},
    }


def _dump(doc: dict) -> str:
    """行は1行ずつ書く（作り直したときの差分を読みやすくする）。"""
    head = {k: v for k, v in doc.items() if k != "rows"} | {"rows": "__ROWS__"}
    text = json.dumps(head, ensure_ascii=False, indent=1)
    rows = ",\n".join(json.dumps(r, ensure_ascii=False) for r in doc["rows"])
    return text.replace('"__ROWS__"', "[\n" + rows + "\n]") + "\n"


def export(card_id: str, sample: bool = False, out_dir: Path | None = None) -> Path:
    if sample and out_dir is None:
        raise ValueError("合成サンプルの結果は site/results に書けません。--out で別のフォルダを指定してください")
    out_dir = Path(out_dir) if out_dir else results_dir()
    doc, df = build(card_id, sample=sample)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{card_id}.json").write_text(_dump(doc), encoding="utf-8")
    df.to_csv(out_dir / f"{card_id}.csv", index=False, encoding="utf-8-sig", lineterminator="\n")
    return out_dir / f"{card_id}.json"


def exportable() -> list[str]:
    return [p.stem for p in specs.card_files() if specs.load_card(p.stem).get("output")]


def status(card: dict, doc: dict) -> list[str]:
    """結果がカード・スクリプトと食い違っている点（古い結果）を返す。"""
    cid = card["id"]
    out = []
    if doc.get("card_version") != card.get("version"):
        out.append(f"指標カードは v{card.get('version')}、結果は v{doc.get('card_version')} で作られています")
    if doc.get("script_sha256") != script_hash(card):
        out.append("計算スクリプトが、結果を作った後に変わっています")
    names = [c["name"] for c in (card.get("output") or {}).get("columns", [])]
    if [c["name"] for c in doc.get("columns", [])] != names:
        out.append("結果の列が指標カードの output.columns と一致しません")
    if out:
        out.append(f"chiiki-od results {cid} で作り直してください")
    return out


def map_warnings(card: dict, doc: dict, geo: dict[str, set[str]]) -> list[str]:
    """サイトの地図に出ない地域・出ない理由を返す（地図の境界は site/geo/。時点は令和8年1月1日の市区町村）。"""
    try:
        ix = [c["name"] for c in doc["columns"]].index(doc["output"]["area_code"])
    except (KeyError, ValueError):
        return []
    cov = boundaries.map_coverage(card.get("unit_of_analysis", ""), [r[ix] for r in doc.get("rows", [])], geo)
    if not cov["shown"]:
        return [f"地図は出ません（{cov['reason']}）"]
    if cov["missing"]:
        eg = "、".join(cov["missing"][:5])
        return [f"地図の境界にない地域コードが{len(cov['missing'])}件あり、地図では値なしになります（例：{eg}）。"
                "境界は令和8年1月1日の市区町村・令和7年度の構想区域です"]
    return []


def check(out_dir: Path | None = None) -> specs.CheckResult:
    """site/results/ の結果を検証する（CIで毎回実行）。"""
    res = specs.CheckResult()
    d = Path(out_dir) if out_dir else results_dir()
    cards = {p.stem: specs.load_card(p.stem) for p in specs.card_files()}
    geo = boundaries.layer_codes()
    found = set()
    for p in sorted(d.glob("*.json")) if d.exists() else []:
        where = f"site/results/{p.name}"
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            res.errors.append(f"{where}: JSONとして読めません（{e}）")
            continue
        cid = doc.get("indicator")
        found.add(cid)
        if cid != p.stem:
            res.errors.append(f"{where}: indicator（{cid}）がファイル名と一致しません")
        if cid not in cards:
            res.errors.append(f"{where}: 指標カード indicators/{cid}.yaml がありません")
            continue
        if doc.get("sample"):
            res.errors.append(f"{where}: 合成サンプルの結果です。公開する結果は実データで作ってください")
        if doc.get("format") != FORMAT:
            res.warnings.append(f"{where}: 形式の版（format {doc.get('format')}）が古い可能性があります")
        if not (d / f"{cid}.csv").exists():
            res.errors.append(f"{where}: 対になる {cid}.csv がありません")
        if len({len(r) for r in doc.get("rows", [])} | {len(doc.get("columns", []))}) > 1:
            res.errors.append(f"{where}: 行の長さが列の数と一致しません")
        res.warnings += [f"{where}: {m}" for m in status(cards[cid], doc)]
        if geo:
            res.warnings += [f"{where}: {m}" for m in map_warnings(cards[cid], doc, geo)]
    for cid, c in cards.items():
        if not c.get("output"):
            res.warnings.append(f"indicators/{cid}.yaml: output がないため、サイトで結果を出せません")
        elif cid not in found:
            res.warnings.append(f"indicators/{cid}.yaml: 結果が site/results にありません（chiiki-od results {cid}）")
    return res
