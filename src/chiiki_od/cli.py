"""コマンドライン: chiiki-od <サブコマンド>

  chiiki-od check                      データセット定義と指標カードを検証する
  chiiki-od list                       登録済みのデータセットと指標を一覧する
  chiiki-od fetch <dataset> [--from-dir D]  元データを取得する（data/raw/）
  chiiki-od convert <dataset>          Parquetに変換する（data/processed/）
  chiiki-od run <indicator> [--sample] 指標を計算する（data/outputs/）
  chiiki-od results [indicator ...]    サイトに載せる結果を作る（site/results/）
  chiiki-od catalog                    site/catalog.json を作る
"""

from __future__ import annotations

import argparse
import sys

from . import catalog, convert, fetch, results, runner, specs


def _check(_args) -> int:
    res = specs.check_all()
    r2 = results.check()
    res.errors += r2.errors
    res.warnings += r2.warnings
    for w in res.warnings:
        print(f"  注意: {w}")
    for e in res.errors:
        print(f"  エラー: {e}")
    print("OK" if res.ok else f"{len(res.errors)}件のエラー")
    return 0 if res.ok else 1


def _list(_args) -> int:
    print("データセット:")
    for p in specs.dataset_files():
        d = specs.load_dataset(p.stem)
        mark = "" if d["verified"] else "（未確認）"
        print(f"  {d['id']:<28} {d['title']}{mark}")
    print("指標:")
    for p in specs.card_files():
        c = specs.load_card(p.stem)
        print(f"  {c['id']:<28} {c['name']}［{c['status']}］")
    return 0


def _run(args) -> int:
    result, notes, out = runner.run(args.indicator, sample=args.sample, ward_level=args.ward_level)
    if args.sample:
        print("※ 合成サンプルデータでの実行です（実際の値ではありません）")
    print(result.head(20).to_string(index=False))
    for n in notes:
        print(f"注記: {n}")
    print(f"保存しました: {out}")
    return 0


def _results(args) -> int:
    ids = args.indicator or results.exportable()
    for cid in ids:
        out = results.export(cid, sample=args.sample, out_dir=args.out)
        print(f"保存しました: {out} と {out.with_suffix('.csv').name}")
    if not args.sample:
        catalog.build()
        print("site/catalog.json を作り直しました")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="chiiki-od", description="地域医療構想オープンデータ共有基盤")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").set_defaults(func=_check)
    sub.add_parser("list").set_defaults(func=_list)
    f = sub.add_parser("fetch")
    f.add_argument("dataset")
    f.add_argument("--force", action="store_true", help="既にあるファイルも取り直す")
    f.add_argument("--from-dir", help="手元に保存した公表ファイル（公表元と同じファイル名）のフォルダから取り込む")
    f.set_defaults(func=lambda a: (fetch.fetch_dataset(a.dataset, force=a.force, from_dir=a.from_dir), 0)[1])
    c = sub.add_parser("convert")
    c.add_argument("dataset")
    c.set_defaults(func=lambda a: (convert.convert_dataset(a.dataset), 0)[1])
    r = sub.add_parser("run")
    r.add_argument("indicator")
    r.add_argument("--sample", action="store_true", help="tests/fixtures の合成サンプルで実行")
    r.add_argument("--ward-level", action="store_true", help="政令市を区単位のまま出力")
    r.set_defaults(func=_run)
    rs = sub.add_parser("results", help="サイトの「結果を見る」に載せる結果を site/results/ に作る")
    rs.add_argument("indicator", nargs="*", help="指標のid（省略すると output のある全指標）")
    rs.add_argument("--sample", action="store_true", help="合成サンプルで作る（--out が必要）")
    rs.add_argument("--out", help="書き出すフォルダ（既定は site/results）")
    rs.set_defaults(func=_results)
    sub.add_parser("catalog").set_defaults(
        func=lambda a: (catalog.build(), print("site/catalog.json を作りました"), 0)[2]
    )
    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, ValueError, NotImplementedError) as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
