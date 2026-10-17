# -*- coding: utf-8 -*-
"""配置读写、默认值合并与运行路径（纯标准库，不依赖 Qt）。

约定：
- 文件不存在：用默认表创建；
- 文件缺字段：按默认表补齐并回写（用户已有的值、未知字段都保留）；
- 文件损坏 / 不是 JSON 对象：返回默认表，但不覆盖原文件（避免二次伤害）。
"""
import copy
import json
import os
import sys

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
    PYTHONW = sys.executable
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = APP_DIR
    # 优先用项目自带 venv 的 pythonw；没有则退回系统 pythonw（和 启动桌宠.bat 保持一致）
    _venv_pw = os.path.join(APP_DIR, ".venv", "Scripts", "pythonw.exe")
    if os.path.exists(_venv_pw):
        PYTHONW = _venv_pw
    else:
        _sys_pw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        PYTHONW = _sys_pw if os.path.exists(_sys_pw) else sys.executable

CONFIG_PATH = os.path.join(APP_DIR, "config.json")
SPRITE_DIR = os.path.join(BUNDLE_DIR, "sprites")
OUTFIT_DIR = os.path.join(SPRITE_DIR, "outfits")
OUTFIT_MANIFEST = os.path.join(OUTFIT_DIR, "manifest.json")
HOLIDAY_DIR = os.path.join(BUNDLE_DIR, "assets", "holidays")

DEFAULT_CONFIG = {
    "mode": "wander",
    "size": 0.7,
    "topmost": True,
    "passthrough": False,
    "autostart": False,
    "x": None,
    "y": None,
    "ds_api_key": "",
    "city": "汕头",
    "outfit": "base",
    "balance_cooldown": 60,
    "holiday_override": "",
}


def merge_defaults(loaded, defaults=None):
    """把 loaded 合并到默认表上：loaded 优先，缺失键补默认值，未知键保留。"""
    defaults = DEFAULT_CONFIG if defaults is None else defaults
    if not isinstance(loaded, dict):
        return copy.deepcopy(defaults)
    merged = copy.deepcopy(defaults)
    merged.update(loaded)
    return merged


def save_config(path, cfg):
    """把配置写成 UTF-8 JSON（保留中文，4 空格缩进），必要时创建父目录。"""
    path = os.fspath(path)
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=4)


def load_json(path, default):
    """兼容旧行为的底层读取：文件不存在则写入 default；读取失败返回 default。"""
    if not os.path.exists(path):
        save_config(path, default)
        return copy.deepcopy(default)

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return copy.deepcopy(default)


def load_config(path, defaults=None):
    """读取配置并合并默认值；缺字段时把补齐后的结果写回文件。"""
    defaults = DEFAULT_CONFIG if defaults is None else defaults

    if not os.path.exists(path):
        cfg = copy.deepcopy(defaults)
        try:
            save_config(path, cfg)
        except OSError:
            pass
        return cfg

    try:
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
    except Exception:
        return copy.deepcopy(defaults)

    if not isinstance(loaded, dict):
        return copy.deepcopy(defaults)

    merged = merge_defaults(loaded, defaults)
    if merged != loaded:
        try:
            save_config(path, merged)
        except OSError:
            pass
    return merged
