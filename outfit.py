# -*- coding: utf-8 -*-
"""换装与精灵管理：外观发现、精灵加载、尺寸档位。"""
import json
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from config import OUTFIT_DIR, OUTFIT_MANIFEST, SPRITE_DIR

DEFAULT_OUTFIT = "base"
VIEW_NAMES = ("正面", "侧面", "背面")
SIZE_LEVELS = {"小": 0.55, "中": 0.7, "大": 0.9}
OUTFIT_FALLBACK_NAME = {"base": "深海女仆"}
OUTFIT_LINES = {
    "base": ["深海女仆报到！", "还是这身最自在", "换回来啦，我是大肥鱼本鱼"],
    "winter_cape": ["下雪天当然要穿斗篷～", "雪绒斗篷，暖和！", "你看我尾巴上的雪花"],
    "whale_hood": ["这帽子是不是太大了……", "鲸鱼头套，戴上去就是同类", "围巾有点勒，但可爱"],
}
OUTFIT_DEFAULT_LINES = ["换好衣服啦！", "这身还行吧？"]


def _view_files(directory):
    """目录里实际存在的视图（有母版或任一尺寸变体即可用）。"""
    if not os.path.isdir(directory):
        return []
    found = []
    for name in VIEW_NAMES:
        if os.path.exists(os.path.join(directory, f"{name}.png")):
            found.append(name)
            continue
        if any(os.path.exists(os.path.join(directory, f"{name}_{h}.png"))
               for h in (int(340 * m) for m in SIZE_LEVELS.values())):
            found.append(name)
    return found


def discover_outfits():
    """返回有序外观清单 [{"id","name","dir","views"}]，第一项恒为默认外观 base（深海女仆）。

    - base：sprites/ 下的 正面/侧面/背面
    - 其它：sprites/outfits/<id>/（名字取 manifest.json，缺了就用 id）
    缺少任一视图的外观会被跳过并打印提示，不会让程序崩。
    """
    outfits = []
    base_views = _view_files(SPRITE_DIR)
    if base_views:
        outfits.append({"id": DEFAULT_OUTFIT, "name": OUTFIT_FALLBACK_NAME["base"],
                        "dir": SPRITE_DIR, "views": base_views})

    names = dict(OUTFIT_FALLBACK_NAME)
    try:
        with open(OUTFIT_MANIFEST, "r", encoding="utf-8") as f:
            for item in json.load(f).get("outfits", []):
                if item.get("id") and item.get("name"):
                    names[item["id"]] = item["name"]
    except Exception:
        pass

    if os.path.isdir(OUTFIT_DIR):
        for entry in sorted(os.listdir(OUTFIT_DIR)):
            d = os.path.join(OUTFIT_DIR, entry)
            if not os.path.isdir(d):
                continue
            views = _view_files(d)
            missing = [n for n in VIEW_NAMES if n not in views]
            if missing:
                print(f"[换装] 跳过外观 {entry}：缺少 {'/'.join(missing)}")
                continue
            outfits.append({"id": entry, "name": names.get(entry, entry),
                            "dir": d, "views": views})
    return outfits


def load_sprites(outfits):
    """加载所有外观的精灵：key = (outfit_id, 视图名, 高度)。缺变体就用母版现缩。"""
    sprites = {}
    for o in outfits:
        oid, o_dir = o["id"], o["dir"]
        for name in VIEW_NAMES:
            for mult in SIZE_LEVELS.values():
                h = int(340 * mult)
                sized = os.path.join(o_dir, f"{name}_{h}.png")
                try:
                    if os.path.exists(sized):
                        pix = QPixmap(sized)
                    else:
                        pix = QPixmap(os.path.join(o_dir, f"{name}.png")).scaledToHeight(
                            h, Qt.TransformationMode.SmoothTransformation)
                except Exception as e:
                    print(f"[换装] 读取 {oid}/{name} 失败: {e!r}")
                    continue
                if pix.isNull():
                    print(f"[换装] 跳过空精灵 {oid}/{name}_{h}")
                    continue
                sprites[(oid, name, h)] = pix
    if not sprites:
        print("[换装] 没有可用精灵，检查 sprites/ 目录")
    return sprites


def sprites_at_height(sprites, h, outfit):
    """取某外观在指定高度下的所有视图精灵。"""
    return [p for k, p in sprites.items() if k[0] == outfit and k[2] == h]
