# -*- coding: utf-8 -*-
"""config.py：默认值合并、读写、损坏文件兜底（全部用 tmp_path）。"""
import json
from pathlib import Path

import pytest

import config

ROOT = Path(__file__).resolve().parents[1]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- 默认值合并

def test_missing_file_is_created_with_defaults(tmp_path):
    path = tmp_path / "config.json"

    cfg = config.load_config(path)

    assert cfg == config.DEFAULT_CONFIG
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == config.DEFAULT_CONFIG
    raw = path.read_text(encoding="utf-8")
    assert "汕头" in raw                      # 中文不转义
    assert "\\u6c55" not in raw
    assert '\n    "mode":' in raw             # 4 空格缩进


def test_partial_file_is_merged_and_persisted(tmp_path):
    path = tmp_path / "config.json"
    write_json(path, {"city": "成都", "size": 0.55,
                      "ds_api_key": "sk-test", "custom": 123})

    cfg = config.load_config(path)

    assert cfg["city"] == "成都"
    assert cfg["size"] == 0.55
    assert cfg["ds_api_key"] == "sk-test"
    assert cfg["custom"] == 123               # 未知字段保留
    assert cfg["balance_cooldown"] == 60      # 缺失字段补默认
    assert cfg["outfit"] == "base"
    assert cfg["holiday_override"] == ""

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved == cfg


def test_null_and_false_are_not_replaced_by_defaults(tmp_path):
    path = tmp_path / "config.json"
    write_json(path, {"x": None, "y": None,
                      "topmost": False, "passthrough": True,
                      "ds_api_key": ""})

    cfg = config.load_config(path)

    assert cfg["x"] is None
    assert cfg["y"] is None
    assert cfg["topmost"] is False
    assert cfg["passthrough"] is True
    assert cfg["ds_api_key"] == ""


def test_invalid_json_returns_defaults_without_overwriting(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{broken json", encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    cfg = config.load_config(path)

    assert cfg == config.DEFAULT_CONFIG
    assert path.read_text(encoding="utf-8") == before


def test_non_object_json_returns_defaults_without_overwriting(tmp_path):
    path = tmp_path / "config.json"
    write_json(path, [1, 2, 3])

    cfg = config.load_config(path)

    assert cfg == config.DEFAULT_CONFIG
    assert json.loads(path.read_text(encoding="utf-8")) == [1, 2, 3]


def test_custom_defaults_are_used(tmp_path):
    defaults = {"a": 1, "b": 2}

    missing = tmp_path / "new.json"
    assert config.load_config(missing, defaults) == defaults
    assert json.loads(missing.read_text(encoding="utf-8")) == defaults

    partial = tmp_path / "partial.json"
    write_json(partial, {"b": 3})
    assert config.load_config(partial, defaults) == {"a": 1, "b": 3}


def test_loading_does_not_mutate_default_config(tmp_path):
    path = tmp_path / "config.json"
    cfg = config.load_config(path)
    cfg["city"] = "被改掉"
    cfg["extra"] = True

    assert config.DEFAULT_CONFIG["city"] == "汕头"
    assert "extra" not in config.DEFAULT_CONFIG
    assert config.load_config(path)["city"] == "汕头"


def test_merge_defaults():
    defaults = {"a": 1, "b": 2}
    loaded = {"b": 20, "c": 30}

    merged = config.merge_defaults(loaded, defaults)

    assert merged == {"a": 1, "b": 20, "c": 30}
    assert loaded == {"b": 20, "c": 30}       # 输入不被修改
    assert defaults == {"a": 1, "b": 2}
    assert config.merge_defaults(None, defaults) == defaults
    assert config.merge_defaults(None, defaults) is not defaults


# ---------------------------------------------------------------- 底层读写

def test_load_json_creates_missing_file(tmp_path):
    path = tmp_path / "custom.json"
    default = {"a": 1, "nested": {"b": 2}}

    loaded = config.load_json(path, default)

    assert loaded == default
    assert loaded is not default
    assert json.loads(path.read_text(encoding="utf-8")) == default


def test_load_json_reads_existing_and_falls_back(tmp_path):
    path = tmp_path / "custom.json"
    write_json(path, {"a": 2})
    assert config.load_json(path, {"a": 1}) == {"a": 2}

    path.write_text("not json", encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert config.load_json(path, {"a": 1}) == {"a": 1}
    assert path.read_text(encoding="utf-8") == before


def test_save_config_roundtrip_unicode_and_parents(tmp_path):
    path = tmp_path / "nested" / "deeper" / "config.json"
    value = {"city": "汕头", "emoji": "🐟", "n": 1}

    config.save_config(path, value)

    assert json.loads(path.read_text(encoding="utf-8")) == value
    raw = path.read_text(encoding="utf-8")
    assert "汕头" in raw and "🐟" in raw
    assert "\\u6c55" not in raw


def test_default_config_matches_example_file():
    """config.example.json 是入库模板，必须与代码默认值同步。"""
    example = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    assert example == config.DEFAULT_CONFIG
