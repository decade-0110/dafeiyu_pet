# -*- coding: utf-8 -*-
"""大肥鱼桌宠入口：GUI 启动与 --check / --font-check / --balance-check 自检。"""
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox

import bubble
from balance import (BALANCE_ERRORS, balance_panel_rows, balance_summary_text,
                     fetch_balance)
from config import APP_DIR, CONFIG_PATH, HOLIDAY_DIR, load_json
from holiday import price_snapshot
from outfit import SIZE_LEVELS, VIEW_NAMES, discover_outfits
from pet_window import BUBBLE_H, MARGIN, PetWindow


def check_appearance():
    """自检：列出可用外观 + 每张精灵尺寸 + 各档位窗口宽高（不显示窗口，便于回归验证）。

    用法：python 桌宠.py --check
    """
    app = QApplication.instance() or QApplication(sys.argv)
    outfits = discover_outfits()
    ok = True
    print(f"外观 {len(outfits)} 套：")
    for o in outfits:
        print(f"  - {o['id']}（{o['name']}）目录 {os.path.relpath(o['dir'], APP_DIR)}")
    for o in outfits:
        print(f"\n[{o['id']}]")
        for name in VIEW_NAMES:
            line = [f"    {name}:"]
            for mult in SIZE_LEVELS.values():
                h = int(340 * mult)
                sized = os.path.join(o["dir"], f"{name}_{h}.png")
                src = sized if os.path.exists(sized) else os.path.join(o["dir"], f"{name}.png")
                if not os.path.exists(src):
                    line.append(f" {h}=缺失")
                    ok = False
                    continue
                pix = QPixmap(src)
                if pix.isNull():
                    line.append(f" {h}=空图")
                    ok = False
                    continue
                line.append(f" {h}={pix.width()}x{pix.height()}")
            print("".join(line))
        for label, mult in SIZE_LEVELS.items():
            h = int(340 * mult)
            widths = [QPixmap(os.path.join(o["dir"], f"{n}_{h}.png")).width()
                      if os.path.exists(os.path.join(o["dir"], f"{n}_{h}.png"))
                      else QPixmap(os.path.join(o["dir"], f"{n}.png")).scaledToHeight(
                          h, Qt.TransformationMode.SmoothTransformation).width()
                      for n in VIEW_NAMES]
            win_w = max(widths) + (int(h * 0.062) + 6) * 2
            print(f"    {label}: 精灵宽 {max(widths)} -> 窗口 {win_w}x{h + BUBBLE_H + MARGIN * 2 + 10}")

    # 峰谷时段快照（纯本地计算，不需要 Key、不联网）
    print("\n[峰谷时段]")
    try:
        snap = price_snapshot(app_dir=APP_DIR, holiday_dir=HOLIDAY_DIR)
        print(f"    当前: {snap['band_text']}（{snap['band']}）— {snap['reason']}")
        print(f"    本机时间: {snap['now'].strftime('%Y-%m-%d %H:%M:%S')}（UTC{snap['offset_hours']:+d}）")
        print(f"    距下次切换: {snap['remain_text']} → {snap['next_text']}")
        print(f"    节假日表: {snap['holiday_year']} 年 {snap['holiday_count']} 天"
              if snap["holiday_year"] else "    节假日表: 缺（时段判定降级为未知）")
    except Exception as e:
        print("    峰谷判定失败:", repr(e))
        ok = False

    print("\n结果:", "OK" if ok else "有问题")
    del app
    return 0 if ok else 1


def check_fonts():
    """诊断用：python 桌宠.py --font-check 打印字体情况与最终选择。"""
    app = QApplication.instance() or QApplication(sys.argv)
    bundled = bubble.load_bundled_fonts()
    fams = bubble.all_font_families()
    picked = bubble.pick_cute_family(fams)
    bubble.PICKED_FONT_FAMILY = picked
    print("内置字体族:", bundled or "（无）")
    print("字体族总数:", len(fams))
    print("最终选择:", picked or "（无，将用系统默认字体）")
    print("优先链:", bubble.font_candidates())
    for hint in bubble.CUTE_FONT_HINTS:
        hits = sorted(f for f in fams if hint in f.lower())
        if hits:
            print(f"  含 {hint!r} 的字体: {hits[:6]}")
    bfont = bubble.cute_font(size_px=bubble.BUBBLE_FONT_PX, family=picked or None)
    print("气泡字体:", bfont.family(), "%dpx" % bfont.pixelSize(),
          "字重 %d（>=700 才触发合成加粗）" % bfont.weight())
    print("菜单字体:", bubble.cute_font(pt=bubble.UI_FONT_PT).family(),
          "字重 %d" % bubble.cute_font(pt=bubble.UI_FONT_PT).weight())
    del app
    return 0


def check_balance():
    """诊断用：python 桌宠.py --balance-check 真实请求一次余额接口。

    退出码：0 成功；1 没设 Key；2 请求/解析失败。
    """
    cfg = load_json(CONFIG_PATH, {})
    key = (cfg.get("ds_api_key", "") or "").strip()
    if not key:
        print("没有配置 ds_api_key，先用右键菜单「设置 Key」填一个")
        return 1
    print("正在查询余额…（key 前 8 位：%s…）" % key[:8])
    ok, data = fetch_balance(key)
    if not ok:
        print("查询失败：", BALANCE_ERRORS.get(data, data), f"（错误码 {data}）")
        return 2
    print("可用状态:", "充足" if data["is_available"] else "不足")
    for row in balance_panel_rows(data):
        print(f"    {row[0]}: {row[1]}")
    print("气泡播报:", balance_summary_text(data))
    return 0


def main():
    if "--font-check" in sys.argv:
        sys.exit(check_fonts())
    if "--balance-check" in sys.argv:
        sys.exit(check_balance())
    if "--check" in sys.argv:
        sys.exit(check_appearance())
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    w = PetWindow()
    sys.exit(app.exec())


def run():
    """带图形错误提示的入口（源码与打包后的 exe 共用）。"""
    try:
        main()
    except Exception as ex:
        try:
            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "大肥鱼桌宠出错", str(ex))
        except Exception:
            pass
        raise


if __name__ == "__main__":
    run()
