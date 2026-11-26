"""元データ（CSV・Excel）を Parquet に変換する。

方針
- まず全列を文字列として読む（コードや事業所番号の先頭の0を落とさないため）
- datasets/<id>.yaml の columns に従って列名を英字に揃え、型を変換する
- 「未報告又はデータ不備」「－」などの記号は欠損にし、何件あったかを記録する（ゼロにはしない）
- 変換の記録（元ファイルのハッシュ値・件数・欠損の件数）を manifests/ に残す
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from . import __version__, manifest, paths, specs
from .fetch import raw_path


def read_raw(file_spec: dict, path: Path) -> pd.DataFrame:
    fmt = file_spec["format"]
    if fmt == "csv":
        df = pd.read_csv(
            path, dtype=str, encoding=file_spec.get("encoding", "utf-8-sig"), keep_default_na=False
        )
    elif fmt == "xlsx":
        df = pd.read_excel(
            path,
            sheet_name=file_spec.get("sheet", 0),
            header=file_spec.get("header", 0),
            dtype=str,
            engine="calamine",
        )
        if isinstance(df.columns, pd.MultiIndex):
            # 複数行の見出しは「上段_下段」の形でつなぐ（空や Unnamed は除く）
            df.columns = [
                "_".join(str(x).strip() for x in col if str(x).strip() and not str(x).startswith("Unnamed"))
                for col in df.columns
            ]
    else:
        raise NotImplementedError(f"{fmt} はまだ扱えません。展開してから csv/xlsx として登録してください")
    df.columns = [str(c).strip() for c in df.columns]
    # 空文字・空白だけのセルは欠損にする
    return df.apply(lambda s: s.mask(s.fillna("").astype(str).str.strip() == ""))


def apply_columns(df: pd.DataFrame, columns: list[dict], na_values: list[str]) -> tuple[pd.DataFrame, dict]:
    """列名の付け替えと型変換。report に欠損記号の件数・数値にできなかった件数を入れる。"""
    report: dict = {"na_symbols": {}, "unparsed_numbers": {}, "unmapped_columns": []}
    if not columns:
        out = df.copy()
        for col in out.columns:
            n = int(out[col].isin(na_values).sum()) if na_values else 0
            if n:
                report["na_symbols"][col] = n
                out[col] = out[col].mask(out[col].isin(na_values))
        return out, report

    missing = [c["source"] for c in columns if c["source"] not in df.columns]
    if missing:
        raise ValueError(
            "元データに想定した列がありません: "
            + ", ".join(missing)
            + "\n実際の列: "
            + ", ".join(df.columns)
            + "\n（公表元で列名が変わった可能性があります。datasets/ の columns を更新してください）"
        )
    report["unmapped_columns"] = [c for c in df.columns if c not in {x["source"] for x in columns}]

    out = pd.DataFrame(index=df.index)
    for c in columns:
        s = df[c["source"]]
        if na_values:
            n = int(s.isin(na_values).sum())
            if n:
                report["na_symbols"][c["name"]] = n
            s = s.mask(s.isin(na_values))
        if c["type"] in ("int", "float"):
            num = pd.to_numeric(s.str.replace(",", "", regex=False), errors="coerce")
            bad = int((s.notna() & num.isna()).sum())
            if bad:
                report["unparsed_numbers"][c["name"]] = bad
            s = num.astype("Int64") if c["type"] == "int" else num.astype("Float64")
        else:
            s = s.astype("string")
        out[c["name"]] = s
    return out, report


def read_with_spec(dataset_id: str, path: Path, file_key: str | None = None) -> pd.DataFrame:
    """1つのファイルをデータセット定義どおりに読む（サンプルデータの読み込みにも使う）。"""
    ds = specs.load_dataset(dataset_id)
    files = ds.get("files", [])
    fs = dict(next((f for f in files if f["key"] == file_key), files[0]) if files else {})
    if path.suffix.lower() == ".csv" and fs.get("format") != "csv":
        # サンプルなど、元データと形式の違うCSVを同じ列定義で読む場合
        fs = {"format": "csv", "encoding": "utf-8-sig", "na_values": fs.get("na_values", [])}
    df = read_raw(fs, path)
    out, _ = apply_columns(df, ds.get("columns", []), fs.get("na_values", []))
    return out


def write_parquet(df: pd.DataFrame, dest: Path, meta: dict) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    md = dict(table.schema.metadata or {})
    md[b"chiiki_od"] = json.dumps(meta, ensure_ascii=False).encode("utf-8")
    pq.write_table(table.replace_schema_metadata(md), dest, compression="zstd")


def convert_dataset(dataset_id: str) -> Path:
    ds = specs.load_dataset(dataset_id)
    if ds.get("verified") is False:
        print(f"注意: {dataset_id} の列構成は実ファイルで未確認です（{ds.get('verified_note', '')}）")

    man = manifest.load(dataset_id)
    if ds.get("parser"):
        from .parsers import PARSERS

        result = PARSERS[ds["parser"]](ds)
        df, report = result[0], result[1]
        extras = result[2] if len(result) > 2 else {}
    else:
        extras = {}
        frames, report = [], {}
        multi = len(ds["files"]) > 1
        for fs in ds["files"]:
            src = raw_path(dataset_id, fs)
            if not src.exists():
                raise FileNotFoundError(f"{src} がありません。先に `chiiki-od fetch {dataset_id}` を実行してください")
            part, rep = apply_columns(read_raw(fs, src), ds.get("columns", []), fs.get("na_values", []))
            if multi:
                part.insert(0, "source_file", fs["key"])
            frames.append(part)
            report[fs["key"]] = rep
        df = pd.concat(frames, ignore_index=True)

    dest = paths.PROCESSED / f"{ds['output']}.parquet"
    meta = {
        "dataset": dataset_id,
        "source_page": ds["source_page"],
        "attribution": ds["license"]["attribution"],
        "sources": {k: {"url": v["url"], "sha256": v["sha256"]} for k, v in man["files"].items()},
        "converted_at": manifest.now(),
        "converter_version": __version__,
    }
    write_parquet(df, dest, meta)
    extra_paths = {}
    for name, table in extras.items():
        if name == "__codebook__":
            paths.CODEBOOKS.mkdir(parents=True, exist_ok=True)
            cb_path = paths.CODEBOOKS / f"{dataset_id}.csv"
            table.to_csv(cb_path, index=False, encoding="utf-8")
            extra_paths["codebook"] = str(cb_path.relative_to(paths.ROOT))
            print(f"コードブック: {cb_path.relative_to(paths.ROOT)}")
        else:
            p = paths.PROCESSED / f"{ds['output']}__{name}.parquet"
            write_parquet(table, p, {**meta, "table": name})
            extra_paths[name] = str(p.relative_to(paths.ROOT))
            print(f"保存しました: {p.relative_to(paths.ROOT)}（{len(table):,}行）")
    man["output"] = {
        "path": str(dest.relative_to(paths.ROOT)),
        "rows": len(df),
        "columns": list(df.columns),
        "converted_at": meta["converted_at"],
        "converter_version": __version__,
        "extras": extra_paths,
        "report": report,
    }
    manifest.save(dataset_id, man)
    print(f"保存しました: {dest.relative_to(paths.ROOT)}（{len(df):,}行 × {df.shape[1]}列）")
    return dest
