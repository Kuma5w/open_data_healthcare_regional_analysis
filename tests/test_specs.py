"""データセット定義と指標カードがスキーマどおりか（CIで毎回確認）。"""

import yaml

from chiiki_od import paths, specs


def test_all_specs_valid():
    res = specs.check_all()
    assert res.ok, "\n".join(res.errors)


def test_template_matches_schema_shape():
    # テンプレートも、値を埋めればスキーマを満たす形になっていること
    with open(paths.INDICATORS / "_template.yaml", encoding="utf-8") as f:
        tpl = yaml.safe_load(f)
    tpl["script"] = "indicators/example_indicator.py"
    errors = specs._schema_errors(tpl, "indicator_card.schema.json", "_template.yaml")
    assert not errors, "\n".join(errors)


def test_dataset_template_matches_schema():
    # データセット定義のひな形も、そのままでスキーマを満たすこと（docs/data_conversion.md から案内している）
    with open(paths.DATASETS / "_template.yaml", encoding="utf-8") as f:
        tpl = yaml.safe_load(f)
    errors = specs._schema_errors(tpl, "dataset.schema.json", "datasets/_template.yaml")
    assert not errors, "\n".join(errors)
    assert tpl["id"] == tpl["output"]
