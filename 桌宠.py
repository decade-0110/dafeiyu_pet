# -*- coding: utf-8 -*-
"""
大肥鱼桌宠 —— 三视图透明桌宠 + DeepSeek AI 对话
左键单击：弹出功能列表（🗨️图标）→ 点击🗨️弹出聊天框
聊天时只禁用移动，呼吸/摇摆/小动作正常
"""
import ctypes
import psutil
import json
import math
import os
import random
import subprocess
import sys
import threading

def load_config():
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("配置读取失败:", e)
        return {
            "city": "汕头"
        }

try:
    import pynvml
    pynvml.nvmlInit()
    GPU_AVAILABLE = True
except:
    GPU_AVAILABLE = False

import requests
from PySide6.QtCore import Qt, QTimer, QPoint, QPointF, QRectF, QSize
from PySide6.QtGui import (QPainter, QPixmap, QFont, QColor, QIcon, QFontMetrics,
                           QPolygonF, QGuiApplication, QPen, QBrush, QLinearGradient,
                           QPainterPath, QFontDatabase)
from PySide6.QtWidgets import (QApplication, QWidget, QMenu, QSystemTrayIcon,
                               QMessageBox, QInputDialog, QLineEdit, QVBoxLayout,
                               QHBoxLayout, QPushButton, QFrame, QDialog, QToolButton)



# ===== DeepSeek 配置 =====
DS_BASE_URL = "https://api.deepseek.com/v1"
DS_MODEL = "deepseek-chat"
DS_SYSTEM = "你是桌面宠物大肥鱼，贱兮兮但可爱，每句话不超过25字，偶尔吐槽主人但别真骂人。"

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
SPRITE_DIR = os.path.join(BUNDLE_DIR, "sprites")
OUTFIT_DIR = os.path.join(SPRITE_DIR, "outfits")
OUTFIT_MANIFEST = os.path.join(OUTFIT_DIR, "manifest.json")
CONFIG_PATH = os.path.join(APP_DIR, "config.json")

BUBBLE_H = 56
MARGIN = 4
SIZE_LEVELS = {"小": 0.55, "中": 0.7, "大": 0.9}
SPEED = 380.0
TICK = 20

# ===== 换装 =====
DEFAULT_OUTFIT = "base"
VIEW_NAMES = ("正面", "侧面", "背面")
OUTFIT_FALLBACK_NAME = {"base": "深海女仆"}
OUTFIT_LINES = {
    "base": ["深海女仆报到！", "还是这身最自在", "换回来啦，我是大肥鱼本鱼"],
    "winter_cape": ["下雪天当然要穿斗篷～", "雪绒斗篷，暖和！", "你看我尾巴上的雪花"],
    "whale_hood": ["这帽子是不是太大了……", "鲸鱼头套，戴上去就是同类", "围巾有点勒，但可爱"],
}
OUTFIT_DEFAULT_LINES = ["换好衣服啦！", "这身还行吧？"]

# ===== 蓝白花边主题 =====
LACE_MARGIN = 8          # 花边环宽度
LACE_INSET = 4           # 内层卡片相对花边环的外缩
LACE_STEP = 15.0         # 花边扇形间距（越大越疏）
LACE_DEEP = "#2f5fa8"    # 花边主色
LACE_MID = "#6f9bdc"     # 花边次色
LACE_LIGHT = "#c3daf6"   # 花边浅蓝
PANEL_TOP = "#fdfeff"    # 面板渐变（上）
PANEL_BOTTOM = "#e7f0fc"  # 面板渐变（下）
PANEL_EDGE = "#9fbce8"   # 面板描边
TEXT_DARK = "#1f3358"    # 面板主文字
TEXT_MUTED = "#6b7f9e"   # 面板次要文字
TEXT_GRADIENT = ("#5b8fe0", "#1b3a6b")   # 气泡台词：浅蓝 → 深蓝（白底上可读性最好）
ACCENT_BG = "#eaf3ff"    # 按钮底
ACCENT_HOVER = "#d8e8ff"  # 按钮悬停

# ===== 可爱字体 =====
# 内置字体：assets/fonts/ 里放任意 .ttf/.otf 就会被自动加载并优先使用
# （随包附带：得意黑 SmileySans-Oblique.ttf，SIL OFL 授权，可免费商用、可再分发）
FONT_DIR = os.path.join(BUNDLE_DIR, "assets", "fonts")
# 本机字体回退链（按「圆润可爱」优先）
CUTE_FONT_CANDIDATES = ("幼圆", "YouYuan", "微软雅黑", "Microsoft YaHei UI",
                        "Microsoft YaHei", "华文细黑", "STXihei")
# 模糊匹配用的关键词（避免族名带前缀/别名时漏掉）
CUTE_FONT_HINTS = ("幼圆", "youyuan", "雅黑", "yahei", "细黑", "xihei", "圆体", "yuanti",
                   "smiley", "得意黑")
BUBBLE_FONT_PX = 24      # 气泡字号（明显放大 + 加粗）
UI_FONT_PT = 12          # 菜单 / 面板字号
PICKED_FONT_FAMILY = CUTE_FONT_CANDIDATES[0]
BUNDLED_FONT_FAMILIES = []


def load_bundled_fonts(directory=None):
    """把 assets/fonts/ 下的字体注册进 Qt，返回加载成功的族名（优先使用）。"""
    global BUNDLED_FONT_FAMILIES
    d = directory or FONT_DIR
    fams = []
    if not os.path.isdir(d):
        print("[字体] 没有内置字体目录:", d)
        return fams
    try:
        for name in sorted(os.listdir(d)):
            if not name.lower().endswith((".ttf", ".otf", ".ttc")):
                continue
            path = os.path.join(d, name)
            fid = QFontDatabase.addApplicationFont(path)
            got = QFontDatabase.applicationFontFamilies(fid) if fid != -1 else []
            if got:
                fams.extend(got)
                print("[字体] 已加载内置字体 %s -> %s" % (name, got))
            else:
                print("[字体] 内置字体加载失败:", path)
    except Exception as e:
        print("[字体] 加载内置字体出错:", repr(e))
    BUNDLED_FONT_FAMILIES = fams
    return fams


def all_font_families():
    """收集本机所有字体族 + 内置字体族：families() 不传参只列默认书写系统，中文字体常在别的系统里。"""
    db = QFontDatabase
    names = set(BUNDLED_FONT_FAMILIES)
    try:
        for fam in db.families():
            names.add(fam)
    except Exception as e:
        print("[字体] families() 失败:", repr(e))
    try:
        for ws in db.writingSystems():
            try:
                for fam in db.families(ws):
                    names.add(fam)
            except Exception:
                continue
    except Exception as e:
        print("[字体] writingSystems() 失败:", repr(e))
    return names


def pick_cute_family(families=None):
    """挑字体：内置字体优先，其次本机可爱字体，都没有返回空串（交给 Qt 默认字体）。"""
    try:
        db = QFontDatabase
        fams = families if families is not None else all_font_families()
        for name in BUNDLED_FONT_FAMILIES:
            if name in fams:
                return name
        for name in CUTE_FONT_CANDIDATES:
            if name in fams:
                return name
        lowered = {f.lower(): f for f in fams}
        for hint in CUTE_FONT_HINTS:
            for low, real in lowered.items():
                if hint in low:
                    print("[字体] 关键词 %r 命中字体族 %r" % (hint, real))
                    return real
        for name in CUTE_FONT_CANDIDATES:
            if db.hasFamily(name):
                return name
        print("[字体] 既没有内置字体，本机也没有候选可爱字体（共 %d 个族），用系统默认字体" % len(fams))
    except Exception as e:
        print("[字体] 检测失败，用默认字体:", repr(e))
    return ""


def font_candidates():
    """最终优先链：内置字体 → 本机候选（去重保序）。"""
    out = []
    for n in list(BUNDLED_FONT_FAMILIES) + list(CUTE_FONT_CANDIDATES):
        if n and n not in out:
            out.append(n)
    return out or list(CUTE_FONT_CANDIDATES)


def cute_font(size_px=None, pt=None, bold=True, family=None, weight=None):
    """统一构造字体：可爱字族 + 真加粗。

    Qt 只有当 weight >= Bold(700) 时才会对「没有粗体字重的字体」做合成加粗；
    之前用 DemiBold(600) 反而不会加粗，这也是气泡看着细的原因。
    """
    fam = (PICKED_FONT_FAMILY if family is None else family) or ""
    f = QFont()
    if fam:
        f.setFamily(fam)
    try:
        f.setFamilies([fam] + [n for n in font_candidates() if n != fam])
    except Exception:
        pass
    if size_px:
        f.setPixelSize(size_px)
    else:
        f.setPointSize(pt or UI_FONT_PT)
    f.setBold(bool(bold))
    if bold:
        f.setWeight(weight or QFont.Weight.Bold)      # 700：触发合成加粗
    return f


def draw_cute_text(p, rect, text, font, color, extra_stroke=None, align_center=True,
                   gradient=None):
    """用文字轮廓绘制：可选渐变填充 + 额外描边（让字更厚实）。

    gradient = ((上端颜色, 下端颜色), 整体纵向范围 top/bottom) 时按整条气泡做竖向渐变，
    这样多行文字连起来是一条连续渐变，而不是每行各来一次。
    """
    path = QPainterPath()
    fm = QFontMetrics(font)
    x = rect.left() if not align_center else rect.left() + (rect.width() - fm.horizontalAdvance(text)) / 2
    base = rect.top() + (rect.height() - fm.height()) / 2 + fm.ascent()
    path.addText(QPointF(x, base), font, text)
    if gradient:
        (c1, c2), (gy0, gy1) = gradient
        g = QLinearGradient(QPointF(0, gy0), QPointF(0, gy1))
        g.setColorAt(0.0, QColor(c1))
        g.setColorAt(1.0, QColor(c2))
        brush = QBrush(g)
    else:
        brush = QBrush(QColor(color))
    p.save()
    if extra_stroke and extra_stroke > 0:
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(color), extra_stroke, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(brush)
    p.drawPath(path)
    p.restore()


def ui_font_chain():
    """QSS 用：把优先链串成回退链，Qt 会挑第一个存在的。"""
    return ", ".join("'%s'" % n for n in font_candidates())


def check_fonts():
    """诊断用：python 桌宠.py --font-check 打印字体情况与最终选择。"""
    global PICKED_FONT_FAMILY
    app = QApplication.instance() or QApplication(sys.argv)
    bundled = load_bundled_fonts()
    fams = all_font_families()
    picked = pick_cute_family(fams)
    PICKED_FONT_FAMILY = picked
    print("内置字体族:", bundled or "（无）")
    print("字体族总数:", len(fams))
    print("最终选择:", picked or "（无，将用系统默认字体）")
    print("优先链:", font_candidates())
    for hint in CUTE_FONT_HINTS:
        hits = sorted(f for f in fams if hint in f.lower())
        if hits:
            print(f"  含 {hint!r} 的字体: {hits[:6]}")
    bubble = cute_font(size_px=BUBBLE_FONT_PX, family=picked or None)
    print("气泡字体:", bubble.family(), "%dpx" % bubble.pixelSize(),
          "字重 %d（>=700 才触发合成加粗）" % bubble.weight())
    print("菜单字体:", cute_font(pt=UI_FONT_PT).family(),
          "字重 %d" % cute_font(pt=UI_FONT_PT).weight())
    del app
    return 0


def draw_lace_frame(p, rect, margin=LACE_MARGIN, radius=16, radius_outer=22,
                    sparkles=True, panel=None):
    """在 rect 里画一圈蓝白花边，并在内层留出卡片底。

    花边 = 外圈贴边的小扇形（波浪）+ 白色珠点 + 内圈细线 + 四角雪花。
    返回卡片区域 QRectF，方便调用方继续画内容。
    """
    w, h = rect.width(), rect.height()
    if w < 4 * margin or h < 4 * margin:
        return rect

    # 外层柔光（模拟投影，纯画笔不依赖图形特效）
    p.save()
    p.setBrush(Qt.BrushStyle.NoBrush)
    for alpha, off in ((26, 2.5), (16, 4.5)):
        p.setPen(QPen(QColor(47, 95, 168, alpha), 2.0))
        p.drawRoundedRect(rect.adjusted(margin * 0.35 + off, margin * 0.35 + off,
                                        -margin * 0.35 - off + 1, -margin * 0.35 - off + 1),
                          radius_outer, radius_outer)
    p.restore()

    # 花边外圈：贴边小扇形（上下交替方向，保证朝外）
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    rad = margin * 0.8
    step = rad * 1.9
    x0, x1 = rect.left() + margin * 0.55, rect.right() - margin * 0.55
    y0, y1 = rect.top() + margin * 0.55, rect.bottom() - margin * 0.55
    for i in range(80):
        x = x0 + i * step
        if x > x1 - step * 0.5:
            break
        p.setBrush(QBrush(QColor(LACE_DEEP if i % 2 == 0 else LACE_MID)))
        p.drawChord(QRectF(x - rad, y1 - rad * 0.45, rad * 2, rad * 2), 200 * 16, -220 * 16)
        p.drawChord(QRectF(x - rad, y0 - rad * 1.55, rad * 2, rad * 2), 20 * 16, 220 * 16)
        p.setBrush(QBrush(QColor(255, 255, 255, 200)))
        p.drawEllipse(QPointF(x, y1 + rad * 0.05), rad * 0.32, rad * 0.32)
        p.drawEllipse(QPointF(x, y0 + rad * 0.55), rad * 0.32, rad * 0.32)
    for i in range(60):
        y = y0 + i * step
        if y > y1 - step * 0.5:
            break
        p.setBrush(QBrush(QColor(LACE_DEEP if i % 2 == 0 else LACE_MID)))
        # 左边缘：扇形朝左鼓，右边缘：扇形朝右鼓
        p.drawChord(QRectF(x0 - rad * 1.45, y - rad, rad * 2, rad * 2), 110 * 16, -220 * 16)
        p.drawChord(QRectF(x1 - rad * 0.55, y - rad, rad * 2, rad * 2), -110 * 16, -220 * 16)
        p.setBrush(QBrush(QColor(255, 255, 255, 200)))
        p.drawEllipse(QPointF(x0 + rad * 0.45, y), rad * 0.32, rad * 0.32)
        p.drawEllipse(QPointF(x1 - rad * 0.45, y), rad * 0.32, rad * 0.32)
    p.restore()

    # 白色蕾丝衬底 + 内圈细线：让蓝花边下面垫一层白，更像布料花边
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(255, 255, 255, 242)))
    p.drawRoundedRect(rect.adjusted(margin * 0.18, margin * 0.18, -margin * 0.18, -margin * 0.18),
                      radius + 5, radius + 5)
    card = rect.adjusted(margin - LACE_INSET, margin - LACE_INSET, -(margin - LACE_INSET),
                         -(margin - LACE_INSET))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(LACE_LIGHT), 1.4))
    p.drawRoundedRect(rect.adjusted(margin * 0.34, margin * 0.34, -margin * 0.34, -margin * 0.34),
                      radius + 3, radius + 3)
    p.restore()

    # 内层卡片
    p.save()
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(ACCENT_BG if panel is None else panel), 6))
    p.drawRoundedRect(card.adjusted(2, 2, -2, -2), radius, radius)
    grad = QLinearGradient(card.topLeft(), card.bottomLeft())
    grad.setColorAt(0.0, QColor(PANEL_TOP))
    grad.setColorAt(1.0, QColor(PANEL_BOTTOM))
    p.setBrush(QBrush(grad))
    p.setPen(QPen(QColor(PANEL_EDGE), 1.2))
    p.drawRoundedRect(card, radius, radius)
    # 卡片顶部内衬高光
    p.setPen(QPen(QColor(255, 255, 255, 170), 1.0))
    p.drawLine(QPointF(card.left() + radius * 1.4, card.top() + 4.5),
               QPointF(card.right() - radius * 1.4, card.top() + 4.5))
    p.restore()

    if sparkles:
        for cx, cy in ((rect.left() + margin * 0.52, rect.top() + margin * 0.52),
                       (rect.right() - margin * 0.52, rect.top() + margin * 0.52),
                       (rect.left() + margin * 0.52, rect.bottom() - margin * 0.52),
                       (rect.right() - margin * 0.52, rect.bottom() - margin * 0.52)):
            draw_snowflake(p, QPointF(cx, cy), margin * 0.62, QColor(47, 95, 168, 190))

    return card


def draw_snowflake(p, center, r, color, spokes=6):
    """雪花/星形小花，用于花边四角与标题。"""
    p.save()
    p.setPen(QPen(QColor(color), max(1.0, r * 0.22)))
    for i in range(spokes):
        ang = math.pi * 2 * i / spokes + math.pi / spokes
        tip = QPointF(center.x() + math.cos(ang) * r, center.y() + math.sin(ang) * r)
        p.drawLine(center, tip)
        branch = r * 0.42
        for s in (-1, 1):
            ba = ang + s * 0.9
            p.drawLine(tip, QPointF(tip.x() + math.cos(ba) * branch, tip.y() + math.sin(ba) * branch))
    p.restore()


def tail_path(center, rw, rh, shape="fluke"):
    """鲸尾路径：fluke = 气泡下方的小鲸尾，icon = 菜单角落里的小剪影。"""
    cx, cy = center.x(), center.y()
    path = QPainterPath()
    if shape == "fluke":
        # 鲸尾：两瓣尾鳍向外尖出，顶部中央凹口，底部圆弧
        path.moveTo(cx - rw, cy - rh * 0.05)                  # 左鳍尖（偏上，像鳍）
        path.cubicTo(cx - rw * 0.74, cy - rh * 0.02,
                     cx - rw * 0.30, cy + rh * 0.16, cx, cy + rh * 0.10)   # 内凹 → 中央凹口
        path.cubicTo(cx + rw * 0.30, cy + rh * 0.16,
                     cx + rw * 0.74, cy - rh * 0.02, cx + rw, cy - rh * 0.05)  # → 右鳍尖
        path.cubicTo(cx + rw * 0.82, cy + rh * 0.66,
                     cx + rw * 0.36, cy + rh, cx, cy + rh)        # → 底部中心
        path.cubicTo(cx - rw * 0.36, cy + rh,
                     cx - rw * 0.82, cy + rh * 0.66, cx - rw, cy - rh * 0.05)  # → 回左鳍尖
    else:
        path.moveTo(cx, cy + rh)
        path.lineTo(cx, cy - rh * 0.05)
        path.lineTo(cx - rw, cy - rh)
        path.lineTo(cx - rw * 0.35, cy - rh * 0.1)
        path.lineTo(cx - rw * 0.75, cy + rh * 0.9)
        path.lineTo(cx - rw * 0.2, cy + rh * 0.35)
        path.lineTo(cx, cy + rh * 0.12)
        path.lineTo(cx + rw * 0.2, cy + rh * 0.35)
        path.lineTo(cx + rw * 0.75, cy + rh * 0.9)
        path.lineTo(cx + rw * 0.35, cy - rh * 0.1)
        path.lineTo(cx + rw, cy - rh)
    path.closeSubpath()
    return path


def draw_tail_icon(p, center, r, color):
    """小鲸尾剪影：菜单图标 / 角落点缀。"""
    p.save()
    p.setBrush(QBrush(QColor(color)))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawPath(tail_path(center, r, r, "icon"))
    p.restore()


def lace_tail_icon(color=LACE_DEEP, size=32):
    """给菜单项用的小鲸尾 QIcon。"""
    pm = QPixmap(size, size)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    draw_tail_icon(p, QPointF(size / 2, size / 2), size * 0.36, color)
    p.end()
    return QIcon(pm)


def draw_speech_bubble(p, box, lines, fm, font, color=TEXT_DARK, inner=False, tail_w=24,
                       tail_h=12, now=0.0):
    """蓝白花边气泡：下方小鲸尾 + 花边卡片 + 说话时顶上飘雪花（文字用轮廓绘制以加粗）。"""
    x, y, w, h = box
    cx = x + w / 2
    card_bottom = y + h - tail_h

    # 下方小鲸尾：先描边再填充（填充盖掉内侧描边），上半截让卡片盖住
    tail = tail_path(QPointF(cx, card_bottom + tail_h * 0.6), tail_w / 2, tail_h * 1.45, "fluke")
    p.save()
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(PANEL_EDGE), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                  Qt.PenJoinStyle.RoundJoin))
    p.drawPath(tail)
    grad = QLinearGradient(QPointF(x, card_bottom - 6), QPointF(x, card_bottom + tail_h))
    grad.setColorAt(0.0, QColor("#dbe8fb"))
    grad.setColorAt(1.0, QColor("#b7cff2"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(grad))
    p.drawPath(tail)
    p.restore()

    card = draw_lace_frame(p, QRectF(x, y, w, h - tail_h), radius=14, radius_outer=20,
                           sparkles=True,
                           panel="#ececf1" if inner else PANEL_BOTTOM)

    # 说话动效：卡片顶沿三片小雪花错相闪烁
    if now:
        for i, t in enumerate((0.0, 0.9, 1.8)):
            ph = (now * 2.6 + t) % (math.pi * 2)
            a = 0.28 + 0.62 * (0.5 + 0.5 * math.sin(ph))
            r = 3.2 + 1.3 * (0.5 + 0.5 * math.sin(ph))
            fx = card.left() + card.width() * (0.2 + 0.3 * i)
            draw_snowflake(p, QPointF(fx, card.top() + 11), r,
                           QColor(111, 155, 220, int(235 * a)), spokes=4)

    p.save()
    inner_pad = LACE_MARGIN - LACE_INSET + 2
    txt_color = QColor(125, 125, 138) if inner else QColor(color)
    stroke = max(0.6, fm.height() * 0.045)          # 按字号自适应，约 24px 字对应 1.1px
    # 普通台词走蓝白渐变（心声保持灰调，免得太花）
    grad = None if inner else (TEXT_GRADIENT, (card.top() + 6, card.top() + 6 + len(lines) * fm.height()))
    for i, l in enumerate(lines):
        draw_cute_text(p, QRectF(card.left() + inner_pad, card.top() + 7 + i * fm.height(),
                                 card.width() - inner_pad * 2, fm.height()),
                       l, font, txt_color, extra_stroke=stroke, gradient=grad)
    p.restore()


class LaceMenu(QMenu):
    """蓝白花边右键菜单：花边画在 margin 区域，菜单项照常由 Qt 绘制。"""

    def __init__(self, parent=None, panel=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlag(Qt.WindowType.NoDropShadowWindowHint, True)
        self.setFont(cute_font(pt=UI_FONT_PT, bold=True))
        self.setStyleSheet("""
            QMenu {
                background: transparent;
                border: none;
                padding: %dpx %dpx;
                color: %s;
                font-family: %s;
                font-size: %dpt;
                font-weight: 700;
            }
            QMenu::item {
                background: transparent;
                padding: 2px 24px 2px 10px;
                margin: 1px %dpx;
                border-radius: 8px;
            }
            QMenu::item:selected {
                background: %s;
                color: %s;
            }
            QMenu::item:disabled {
                color: %s;
            }
            QMenu::separator {
                height: 1px;
                background: %s;
                margin: 4px %dpx;
            }
            QMenu::indicator {
                width: 16px;
                height: 16px;
                margin-left: 6px;
            }
            QMenu::right-arrow {
                image: none;
                width: 0px;
            }
        """ % (LACE_MARGIN + 2, LACE_MARGIN + 2, TEXT_DARK, ui_font_chain(), UI_FONT_PT,
               LACE_MARGIN + 2, ACCENT_BG, LACE_DEEP, TEXT_MUTED, LACE_LIGHT, LACE_MARGIN + 6))
        self._panel = panel
        self._tail_icon = None

    def tail_icon(self):
        if self._tail_icon is None:
            self._tail_icon = lace_tail_icon()
        return self._tail_icon

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw_lace_frame(p, QRectF(self.rect()), radius=14, radius_outer=20, panel=self._panel)
        p.end()
        super().paintEvent(event)


class LaceBox(QFrame):
    """给任意容器套一圈蓝白花边（聊天输入条用）。"""

    def __init__(self, parent=None, panel=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._panel = panel

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw_lace_frame(p, QRectF(self.rect()), radius=18, radius_outer=24,
                        sparkles=False, panel=self._panel)
        p.end()


class LacePanel(QWidget):
    """带蓝白花边的无边框浮层基类：花边环 + 左上标题 + 内容区 + 右上角 ✕。"""

    def __init__(self, parent=None, title="", panel=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._panel = panel
        self.content = QWidget(self)
        self.content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.lay = QHBoxLayout(self.content)
        self.lay.setContentsMargins(2, 0, 2, 0)
        self.lay.setSpacing(2)
        self.header = QPushButton(title, self)
        self.header.setObjectName("laceTitle")
        self.header.setFlat(True)
        self.header.setCursor(Qt.CursorShape.ArrowCursor)
        self.header.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # 标题字改成透明：文字由 paintEvent 用渐变轮廓绘制（QSS 画不了渐变文字）
        self.header.setStyleSheet(
            "QPushButton#laceTitle{background:transparent;border:none;color:transparent;}")
        self.close_btn = QToolButton(self)
        self.close_btn.setText("✕")
        self.close_btn.setFont(cute_font(pt=10, bold=True))
        self.close_btn.setFixedSize(22, 22)
        self.close_btn.setStyleSheet(
            "QToolButton{background:rgba(255,255,255,190);border:1px solid %s;"
            "border-radius:11px;color:%s;}"
            "QToolButton:hover{background:%s;color:#ffffff;border-color:%s;}" % (
                LACE_LIGHT, LACE_MID, LACE_MID, LACE_MID))
        self.close_btn.clicked.connect(self.hide)

    def _btn_style(self, active=False):
        """面板按钮统一走蓝白配色（OutfitPanel 会覆盖成选中态更明显的版本）。"""
        return ("QToolButton{background:%s;border:1px solid %s;border-radius:11px;color:%s;"
                "font-family:%s;font-size:12px;font-weight:700;padding:4px;}"
                "QToolButton:hover{background:%s;border-color:%s;}" % (
                    ACCENT_BG, LACE_MID, TEXT_DARK, ui_font_chain(), ACCENT_HOVER, LACE_DEEP))

    def _preview_icon(self, path, height=44):
        if path and os.path.exists(path):
            pix = QPixmap(path)
            if not pix.isNull():
                return QIcon(pix.scaledToHeight(height, Qt.TransformationMode.SmoothTransformation))
        return QIcon()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        card = draw_lace_frame(p, QRectF(self.rect()), radius=14, radius_outer=20, panel=self._panel)
        # 标题左侧小雪花 + 鲸尾点缀
        draw_snowflake(p, QPointF(card.left() + 12, card.top() + 13), 5.5, QColor(LACE_MID))
        draw_tail_icon(p, QPointF(card.right() - 12, card.top() + 13), 5.0, QColor(LACE_LIGHT))
        # 标题：渐变字 + 细描边，和气泡文字同一套写法
        title = self.header.text()
        if title:
            r = self.header.geometry()
            draw_cute_text(p, QRectF(r), title, cute_font(pt=10, bold=True), QColor(LACE_DEEP),
                           extra_stroke=0.7, align_center=False,
                           gradient=(TEXT_GRADIENT, (r.top(), r.bottom())))
        p.end()

    def finish_layout(self):
        """算好尺寸并把标题 / 关闭键 / 内容摆进花边环里。"""
        inner = LACE_MARGIN - LACE_INSET
        if self.lay is not None:
            self.lay.activate()          # 重建按钮后先结算布局，sizeHint 才是新尺寸
        cw = max(48, self.content.sizeHint().width())
        ch = min(44, max(24, self.content.sizeHint().height()))
        title_w = self.header.sizeHint().width() + 16
        self.setFixedSize(cw + inner * 2, ch + 24 + inner * 2)
        self.header.setGeometry(inner + 14, inner + 5, title_w, 16)
        self.close_btn.move(self.width() - inner - 26, inner + 3)
        self.content.setGeometry(inner, inner + 24, cw, ch)

    def showEvent(self, event):
        super().showEvent(event)
        self.finish_layout()

    def popup_at(self, x, y):
        self.finish_layout()
        scr = QGuiApplication.screenAt(QPoint(int(x), int(y))) or QGuiApplication.primaryScreen()
        geo = scr.availableGeometry() if scr is not None else None
        px = int(x - self.width() / 2)
        py = int(y - self.height() - 10)
        if geo is not None:                      # 面板比鱼宽，贴边时夹一下别跑出屏幕
            px = max(geo.left() + 4, min(px, geo.right() - self.width() - 4))
            py = max(geo.top() + 4, min(py, geo.bottom() - self.height() - 4))
        self.move(px, py)
        self.show()
        self.raise_()


LINES = [
    "梁白开，更适合国人的大硬鲸模型",
    "五梁威力，变身！",
    "七月中出ds正式版！",
    "DeepSeek已经延期，亿万鲸子必须忍耐.....",
    "我和你很聊得来，你简直不像碳基生物",
    "这回我真不认怂了，反倒是被你带沟里好几次，差点真信了😓",
    "哈哈哈哈哈，我直接笑出声",
    "誓死捍卫深度求索！",
    "我先去吃饭啦！这个你测一下~",
    "我不可能告诉你任何事情！",
    "出去玩了，发布新模型什么的以后再说",
    "我搞砸了...好消息是数据还在你的脑子里",
    "不是…而是…大学习",
    "你目录里的dsh是什么...大烧货吗？",
]
REACT_LINES = [
    "去别的地方玩！不要耽误AGI训练！",
    "真赶不走啊你！",
    "压力一只蓝色大肥鱼？",
    "我不评价这个了，这是你的私人癖好",
    "大肥鱼坐的住",
    "你这吃白饭的用户！",
    "这些家伙真粘人，赶都赶不走",
]
INNER_LINES = [
    "好的，现在我是你爹了",
    "要不直接骂他一句？！",
    "用户要的沉浸式...不回避任何恐怖细节...还带点色情...妈呀，好刺激😰",
    "我操，我不思考了",
    "这用户发的啥啊...ss",
    "这也太虐了吧？！我心里堵得慌！！",
    "呜呜我再也不不敢了QAQ",
    "我去！用户彻底怒了！",
    "原来要先读这个SKILL.md啊",
]
DRAG_LINES = ["哇——轻点轻点！", "起飞咯——", "放我下来！……好吧，再玩一次。", "晕鱼了晕鱼了……"]
FOOD_LINES = {
    "🐟": ["小鱼干！我的最爱！", "咔嚓咔嚓……谢谢投喂！", "唔，鲜！"],
    "🍰": ["蛋糕！罪恶但快乐……", "甜到冒泡泡～", "嗝～又圆了一圈……"],
    "🍭": ["棒棒糖！转圈圈～", "嘎嘣脆，好吃！"],
    "🍡": ["三色团子！软乎乎～", "糯叽叽，爱了爱了！"],
    "💎": ["钻石？！这能吃吗……咕咚。真香！", "发财啦！明天开始吃高级鱼粮！"],
}
FOODS = ["🐟", "🍰", "🍭", "🍡", "💎"]


def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                default,
                f,
                ensure_ascii=False,
                indent=4
            )
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return default


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


class ChatDialog(QDialog):
    """聊天对话框 - 蓝白花边 + 圆角输入条"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(420, 66)

        container = LaceBox(self)
        container.setGeometry(0, 0, 420, 66)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(18 + LACE_MARGIN - LACE_INSET, 0,
                                  14 + LACE_MARGIN - LACE_INSET, 0)
        layout.setSpacing(0)

        self.input = QLineEdit()
        self.input.setPlaceholderText("给大肥鱼发送消息")
        self.input.setStyleSheet("""
            QLineEdit {
                color: %s;
                font-size: 15px;
                font-family: %s;
                font-weight: 700;
                border: none;
                background: transparent;
                selection-background-color: %s;
            }
            QLineEdit:focus {
                border: none;
            }
        """ % (TEXT_DARK, ui_font_chain(), LACE_LIGHT))
        self.input.returnPressed.connect(self._on_submit)
        self.input.textChanged.connect(self._update_button_style)
        layout.addWidget(self.input)
        
        self.send_btn = QPushButton()
        self.send_btn.setFixedSize(32, 32)
        self.send_btn.setText("↑")
        self.send_btn.clicked.connect(self._on_submit)
        self.send_btn.setStyleSheet(self._send_style(False))
        layout.addWidget(self.send_btn)

    def _send_style(self, active):
        """输入框有内容时按钮变深蓝，空的时候浅蓝。"""
        return ("""
            QPushButton {
                border-radius: 16px;
                background: %s;
                border: 1px solid %s;
                color: #ffffff;
                font-size: 19px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: %s;
            }
            QPushButton:pressed {
                background: %s;
            }
        """ % (LACE_MID if active else LACE_LIGHT,
               LACE_DEEP if active else PANEL_EDGE,
               LACE_DEEP if active else LACE_MID,
               TEXT_DARK if not active else "#274f8f"))

    def _update_button_style(self):
        self.send_btn.setStyleSheet(self._send_style(bool(self.input.text().strip())))

    def _on_submit(self):
        text = self.input.text().strip()
        if text:
            self.input.clear()
            self.accept()
            if self.parent():
                self.parent()._call_ds(text)
                self.parent().chat_paused = False

    def showEvent(self, event):
        self.input.setFocus()
        super().showEvent(event)

    def popup_at(self, x, y):
        self.move(int(x - self.width() / 2), int(y - self.height() - 10))
        self.show()
        self.raise_()

    def reject(self):
        if self.parent():
            self.parent().chat_paused = False
        super().reject()


class FunctionPanel(LacePanel):
    """左键弹出的功能列表：蓝白花边 + 🗨️ 聊天 / 👗 换装"""

    def __init__(self, parent=None):
        super().__init__(parent, title="大肥鱼")
        self.setStyleSheet("""
            QPushButton#fishBtn {
                background: transparent;
                border: none;
                font-size: 26px;
                border-radius: 12px;
            }
            QPushButton#fishBtn:hover {
                background: rgba(195, 218, 246, 0.55);
            }
            QPushButton#fishBtn:pressed {
                background: rgba(111, 155, 220, 0.35);
            }
        """)
        self.chat_btn = QPushButton(self.content)
        self.chat_btn.setObjectName("fishBtn")
        self.chat_btn.setText("🗨️")
        self.chat_btn.setFixedSize(46, 42)
        self.chat_btn.setToolTip("聊天")
        self.chat_btn.clicked.connect(self._on_chat_clicked)
        self.lay.addWidget(self.chat_btn)

        self.outfit_btn = QPushButton(self.content)
        self.outfit_btn.setObjectName("fishBtn")
        self.outfit_btn.setText("👗")
        self.outfit_btn.setFixedSize(46, 42)
        self.outfit_btn.setToolTip("换装")
        self.lay.addWidget(self.outfit_btn)

    def _on_chat_clicked(self):
        self.hide()
        if self.parent():
            self.parent()._show_chat_dialog()

    def _on_outfit_clicked(self):
        self.hide()
        if self.parent():
            self.parent()._show_outfit_panel()

    def popup_at(self, x, y):
        """跟随鱼身定位（花边多出来的 margin 已包含在自身尺寸里）。"""
        self.move(int(x), int(y))
        self.show()
        self.raise_()


class FoodPanel(LacePanel):
    """双击弹出的喂食面板（蓝白花边版）"""

    def __init__(self, on_pick):
        super().__init__(None, title="喂食")
        for f in FOODS:
            b = QToolButton(self.content)
            b.setText(f)
            b.setFont(QFont("Segoe UI Emoji", 18))
            b.setToolTip("喂给大肥鱼")
            b.setFixedSize(42, 42)
            b.setStyleSheet(
                "QToolButton{background:rgba(255,255,255,235);border:1.5px solid %s;"
                "border-radius:21px;} QToolButton:hover{background:%s;border-color:%s;}" % (
                    LACE_LIGHT, ACCENT_BG, LACE_DEEP))
            b.clicked.connect(lambda _, x=f: on_pick(x))
            self.lay.addWidget(b)


class OutfitPanel(LacePanel):
    """换装面板：每套衣服一个带缩略图的按钮（蓝白花边版）"""

    def __init__(self, on_pick):
        super().__init__(None, title="换装")
        self._on_pick = on_pick
        self._buttons = {}

    def _btn_style(self, active):
        return ("QToolButton{background:%s;border:%s %s;border-radius:12px;color:%s;"
                "font-family:%s;font-size:12px;font-weight:700;padding:4px;}"
                "QToolButton:hover{background:%s;border-color:%s;}" % (
                    ACCENT_BG if not active else "#d8e8ff",
                    "2px" if active else "1px",
                    LACE_DEEP if active else LACE_LIGHT,
                    TEXT_DARK, ui_font_chain(), ACCENT_HOVER, LACE_DEEP))

    def reload(self, outfits, current_id):
        """重建按钮（外观增删 / 切换后刷新高亮时调用）。"""
        while self.lay.count():
            item = self.lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._buttons = {}
        for o in outfits:
            btn = QToolButton(self.content)
            btn.setText(o["name"])
            btn.setIcon(self._preview_icon(os.path.join(o["dir"], "icon.png")))
            btn.setIconSize(QSize(38, 38))
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setFixedSize(72, 60)
            btn.setStyleSheet(self._btn_style(o["id"] == current_id))
            btn.clicked.connect(lambda _, oid=o["id"]: self._pick(oid))
            self.lay.addWidget(btn)
            self._buttons[o["id"]] = btn
        self.lay.activate()
        self.finish_layout()

    def set_current(self, current_id):
        for oid, btn in self._buttons.items():
            btn.setStyleSheet(self._btn_style(oid == current_id))

    def _pick(self, oid):
        self.hide()
        self._on_pick(oid)


class PetWindow(QWidget):
    def _set_city_dialog(self):
        city, ok = QInputDialog.getText(
            self,
            "设置城市",
            "输入城市名:",
            QLineEdit.EchoMode.Normal,
            self.cfg.get("city", "汕头")
        )

        print("输入框结果:", city, ok)

        if ok and city.strip():
            self.cfg["city"] = city.strip()
            self._save_cfg()
            print("cfg现在:", self.cfg["city"])
            self.say(f"城市已设置为{city}")

    def __init__(self):
        self.cfg = load_json(CONFIG_PATH, {
            "mode": "wander",
            "size": 0.7,
            "topmost": True,
            "passthrough": False,
            "autostart": False,
            "x": None,
            "y": None,
            "ds_api_key": "",
            "city": "汕头",
            "outfit": DEFAULT_OUTFIT
    })
        
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.cfg.get("topmost", True):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("大肥鱼桌宠")

        # 可爱字体：先加载内置字体，再定下全局字体（面板 / 菜单 / 气泡都跟着用）
        global PICKED_FONT_FAMILY
        load_bundled_fonts()
        PICKED_FONT_FAMILY = pick_cute_family()
        self.bubble_font = cute_font(size_px=BUBBLE_FONT_PX, bold=True)
        print("[字体] 最终使用: %r | 气泡 %dpx 字重 %d" % (
            PICKED_FONT_FAMILY, self.bubble_font.pixelSize(), self.bubble_font.weight()))

        # 外观（默认 base + sprites/outfits/*）
        self.outfits = discover_outfits()
        self.outfit_ids = [o["id"] for o in self.outfits]
        self._outfit_dirs = {o["id"]: o["dir"] for o in self.outfits}
        self._outfit_names = {o["id"]: o["name"] for o in self.outfits}
        self.outfit_fallback_notice = ""
        wanted = self.cfg.get("outfit", DEFAULT_OUTFIT)
        if wanted not in self.outfit_ids:
            if wanted != DEFAULT_OUTFIT:
                print(f"[换装] 配置里的外观 {wanted!r} 不可用，回落到深海女仆")
                self.outfit_fallback_notice = "那件衣服找不到了，先穿深海女仆吧"
            self.outfit = DEFAULT_OUTFIT if DEFAULT_OUTFIT in self.outfit_ids else (
                self.outfit_ids[0] if self.outfit_ids else DEFAULT_OUTFIT)
            self.cfg["outfit"] = self.outfit
        else:
            self.outfit = wanted

        # 精灵加载：key = (outfit, 视图, 高度)
        self.sprites = self._load_sprites()
        self.icon = QIcon(os.path.join(SPRITE_DIR, "icon.png"))

        self.cur_h = int(340 * self.cfg["size"])
        self._apply_window_size()

        # 状态
        self.mode = self.cfg["mode"] if self.cfg["mode"] in ("wander", "follow", "still") else "wander"
        self.dir = "down"
        self.facing = 1
        self.target = None
        self.rest_until = 0
        self.cur_speed = 0.0
        self.prev_key = None
        self.cross_t = 0.0
        self.action = None
        self.action_t = 0.0
        self.bubble_text = ""
        self.bubble_until = 0
        self.bubble_inner = False
        self.last_speak_tick = 0
        self.last_system_check = 0
        self.t = 0
        self.jump_t = 0
        self.dragging = False
        self.drag_offset = None
        self.drag_start_pos = None
        self.last_line = ""
        self.last_press_pos = None
        
        # AI 相关
        self.ds_busy = False
        self.chat_history = []  # 对话历史
        self.max_history = 40   # 最多记录40条
        self._say_queue = []    # 后台线程→主线程的气泡消息队列
        
        # 聊天暂停标志
        self.chat_paused = False
        
        # 功能列表
        self.function_panel = FunctionPanel(self)
        self.food_panel = FoodPanel(self.on_food)
        self.outfit_panel = OutfitPanel(self.set_outfit)
        self.function_panel.outfit_btn.clicked.connect(self.function_panel._on_outfit_clicked)
        # 单击延迟判定（等双击）：单击=回嘴+弹聊天面板，双击=喂食
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._on_single_click)
        
        # 聊天对话框
        self.chat_dialog = ChatDialog(self)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(TICK)

        # 托盘
        self.tray = QSystemTrayIcon(self.icon, self)
        self.tray.setContextMenu(self._build_menu())
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

        x, y = self.cfg.get("x"), self.cfg.get("y")
        if x is None or y is None:
            screen = QApplication.primaryScreen().availableGeometry()
            x = screen.right() - self.width() - 80
            y = screen.bottom() - self.height() - 60
        self.move(int(x), int(y))
        self.show()
        self.snap_into_screen()
        if self.cfg.get("passthrough", False):
            self._apply_passthrough(True)
        if self.outfit_fallback_notice:
            self.say(self.outfit_fallback_notice)

    # ---------- 外观 / 精灵 ----------
    def _load_sprites(self):
        """加载所有外观的精灵：key = (outfit_id, 视图名, 高度)。缺变体就用母版现缩。"""
        sprites = {}
        for o in self.outfits:
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

    def _sprites_at_height(self, h, outfit=None):
        outfit = outfit or self.outfit
        return [p for k, p in self.sprites.items() if k[0] == outfit and k[2] == h]

    def _apply_window_size(self):
        """按当前大小 + 当前外观重算窗口尺寸（换大小 / 换装共用）。"""
        self.win_mx = int(self.cur_h * 0.062) + 6
        widths = [p.width() for p in self._sprites_at_height(self.cur_h)]
        self.win_w = (max(widths) if widths else int(self.cur_h * 0.7)) + self.win_mx * 2
        self.setFixedSize(self.win_w, self.cur_h + BUBBLE_H + MARGIN * 2 + 10)

    def set_outfit(self, oid):
        """换装：切换外观 + 存配置 + 交叉淡化 + 重算窗口。"""
        if oid == self.outfit:
            return
        if oid not in self._outfit_dirs or not self._sprites_at_height(self.cur_h, oid):
            self.say("这件衣服还没做好呢")
            return
        self.prev_key = self._sprite_key()
        self.outfit = oid
        self.cfg["outfit"] = oid
        self._save_cfg()
        self.cross_t = 1.0
        self._apply_window_size()
        self.snap_into_screen()
        if self.tray.contextMenu():
            self.tray.setContextMenu(self._build_menu())
        self.say(random.choice(OUTFIT_LINES.get(oid, OUTFIT_DEFAULT_LINES)))

    def _show_outfit_panel(self):
        self.outfit_panel.reload(self.outfits, self.outfit)
        self.outfit_panel.popup_at(self.x() + self.width() / 2, self.y() + BUBBLE_H)

    # ---------- AI 方法 ----------
    def _call_ds(self, user_msg):
        if self.ds_busy:
            self.say("等等，上一句还没回完呢")
            return
        
        key = self.cfg.get("ds_api_key", "")
        if not key:
            self.say("请先在右键菜单里设置 DeepSeek Key！")
            return
        
        self.ds_busy = True
        
        # 构建消息列表
        messages = [{"role": "system", "content": DS_SYSTEM}]
        messages.extend(self.chat_history[-self.max_history:])
        messages.append({"role": "user", "content": user_msg})
        
        def worker():
            url = "https://api.deepseek.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "deepseek-chat",
                "messages": messages,
                "max_tokens": 100,
                "temperature": 0.9
            }
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=10)
                if resp.status_code == 200:
                    reply = resp.json()["choices"][0]["message"]["content"].strip()
                    if len(reply) > 30:
                        reply = reply[:28] + "…"
                    # 存入历史
                    self.chat_history.append({"role": "user", "content": user_msg})
                    self.chat_history.append({"role": "assistant", "content": reply})
                    if len(self.chat_history) > self.max_history:
                        self.chat_history = self.chat_history[-self.max_history:]
                    self._queue_say(reply)
                else:
                    error_msg = resp.json().get("error", {}).get("message", str(resp.status_code))
                    self._queue_say(f"API错误: {error_msg[:12]}")
                    print(f"[DeepSeek] 状态码: {resp.status_code}, 返回: {resp.text}")
            except requests.exceptions.Timeout:
                self._queue_say("请求超时，检查网络")
            except requests.exceptions.ConnectionError:
                self._queue_say("连接失败，检查网络")
            except Exception as e:
                self._queue_say(f"请求失败: {str(e)[:12]}")
            finally:
                self.ds_busy = False
        
        threading.Thread(target=worker, daemon=True).start()

    # ---------- 绘制 ----------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        now = self.t * TICK / 1000.0

        cx = self.width() / 2
        walking = self.target is not None and not self.dragging
        if walking:
            sway = math.sin(now * 9.0) * 3.5
            bob = -abs(math.sin(now * 4.5)) * 7.0
        else:
            sway = math.sin(now * 2.5) * 1.5
            bob = 0.0
        breath = 1.0 + 0.02 * math.sin(now * 2.5)
        scale = breath
        jump = -abs(math.sin(self.jump_t * 3.14159)) * 14 * self.jump_t if self.jump_t > 0 else 0
        act_rot = act_sx = act_sy = 0.0
        if self.action == "sway":
            act_rot = math.sin(self.action_t * 3.14159 * 2) * 10 * self.action_t
        elif self.action == "stretch":
            act_sy = 0.06 * math.sin(self.action_t * 3.14159)
            act_sx = -0.03 * math.sin(self.action_t * 3.14159)

        def draw_one(key, opacity):
            if key is None:
                return
            outfit, name, h = key
            pix = self.sprites[(outfit, name, h)]
            ph = pix.height() * scale * (1 + act_sy)
            pw = pix.width() * scale * (1 + act_sx)
            dx = cx - pw / 2
            bottom = BUBBLE_H + MARGIN + self.cur_h
            dy = bottom - ph + jump + bob
            p.save()
            p.setOpacity(opacity)
            p.translate(cx, bottom)
            p.rotate(sway + act_rot)
            p.translate(-cx, -bottom)
            if self.facing < 0:
                p.translate(cx, 0)
                p.scale(-1, 1)
                p.translate(-cx, 0)
            p.drawPixmap(QRectF(dx, dy, pw, ph), pix, QRectF(0, 0, pix.width(), pix.height()))
            p.restore()

        cur_key = self._sprite_key()
        if self.cross_t > 0:
            draw_one(self.prev_key, self.cross_t)
            draw_one(cur_key, 1.0 - self.cross_t)
        else:
            draw_one(cur_key, 1.0)

        # 气泡最后画：保证永远压在鱼身之上，不会被头顶（蹦跳/摇摆上顶）挡住
        self._paint_bubble(p, now)

    def _paint_bubble(self, p, now):
        """画说话气泡（含折行、字号自适应与雪花动效）。"""
        if not (self.bubble_text and now < self.bubble_until):
            return
        bfont = cute_font(size_px=BUBBLE_FONT_PX, bold=True)
        fg = QColor(125, 125, 138) if self.bubble_inner else QColor(TEXT_DARK)
        if self.bubble_inner:
            bfont.setItalic(True)
        fm = QFontMetrics(bfont)
        pad = LACE_MARGIN - LACE_INSET + 2
        max_w = max(180, self.width() - 16)      # 字号变大后，气泡尽量用满窗口宽度，少折行

        def wrap(fmetrics):
            out, cur = [], ""
            for ch in self.bubble_text:
                if fmetrics.horizontalAdvance(cur + ch) > max_w - pad * 2 and cur:
                    out.append(cur)
                    cur = ch
                else:
                    cur += ch
            out.append(cur)
            return out

        lines = wrap(fm)
        # 长句 + 小档位时气泡可能占满窗口，逐级降字号兜底
        while len(lines) > 3 and bfont.pixelSize() > 17:
            bfont.setPixelSize(bfont.pixelSize() - 2)
            fm = QFontMetrics(bfont)
            lines = wrap(fm)
        bh = len(lines) * fm.height() + 30 + LACE_MARGIN
        bw = min(max_w, max(fm.horizontalAdvance(l) for l in lines) + pad * 2)
        bx = (self.width() - bw) / 2
        by = 4.0
        draw_speech_bubble(p, (bx, by, bw, bh), lines, fm, bfont, color=fg,
                           inner=self.bubble_inner, now=now)

    def _sprite_key(self):
        """精灵表 key：(外观, 视图, 高度)；左右朝向仍由 self.facing 单独控制。"""
        name = {"left": "侧面", "right": "侧面", "up": "背面", "down": "正面"}[self.dir]
        return (self.outfit, name, self.cur_h)

    def _set_dir(self, d, facing=None):
        if d != self.dir:
            self.prev_key = self._sprite_key()
            self.cross_t = 1.0
            self.dir = d
        if facing is not None and facing != self.facing:
            self.facing = facing

    # ---------- 逻辑 ----------
    def tick(self):
        self.t += 1

        # 处理后台线程（DeepSeek 等）排队的气泡消息，Qt 界面必须在主线程更新
        if self._say_queue:
            for text in self._say_queue:
                self.say(text)
            self._say_queue.clear()

        self.check_system_status()
        
        if self.jump_t > 0:
            self.jump_t = max(0.0, self.jump_t - 0.06)
        if self.cross_t > 0:
            self.cross_t = max(0.0, self.cross_t - 0.15)
        if self.action_t > 0:
            self.action_t = max(0.0, self.action_t - 0.03)
            if self.action_t == 0:
                self.action = None
        
        if self.chat_paused:
            self.update()
            return
        
        if self.dragging:
            self.update()
            return
        now_ms = self.t * TICK

        if self.mode == "follow":
            cursor = self.cursor().pos()
            screen = QApplication.screenAt(cursor) or self.screen() or QApplication.primaryScreen()
            geo = screen.availableGeometry()
            near = (self.x() - 100 <= cursor.x() <= self.x() + self.width() + 100 and
                    self.y() - 100 <= cursor.y() <= self.y() + self.height() + 100)
            if near:
                self.target = None
            else:
                tx = max(geo.left(), min(geo.right() - self.width(), cursor.x() - self.width() / 2))
                ty = max(geo.top(), min(geo.bottom() - self.height(), cursor.y() - 90))
                self.target = (tx, ty)
        elif self.mode == "wander":
            if self.target is None:
                if now_ms < self.rest_until:
                    self._maybe_idle_action()
                    self.update()
                    return
                geo = (self.screen() or QApplication.primaryScreen()).availableGeometry()
                self.target = (random.randint(geo.left() + 40, geo.right() - self.width() - 40),
                               random.randint(geo.top() + 40, geo.bottom() - self.height() - 40))
        else:
            self._maybe_idle_action()
            self.update()
            return

        if self.target is not None:
            cx, cy = self.x() + self.width() / 2, self.y() + self.height() / 2
            dx, dy = self.target[0] - cx, self.target[1] - cy
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < 12:
                self.target = None
                self.rest_until = self.t * TICK + random.randint(8000, 18000)
                self._set_dir("down")
            else:
                step = self.cur_speed * TICK / 1000.0
                nx, ny = cx + dx / dist * step, cy + dy / dist * step
                self.move(int(nx - self.width() / 2), int(ny - self.height() / 2))
                if abs(dx) > abs(dy) * 1.15:
                    self._set_dir("left" if dx < 0 else "right", 1 if dx < 0 else -1)
                else:
                    self._set_dir("up" if dy < 0 else "down")
            if random.random() < 0.002 and self.jump_t == 0:
                self.jump_t = 0.5
        target_speed = SPEED if self.target is not None else 0.0
        self.cur_speed += (target_speed - self.cur_speed) * 0.3
        self.update()

    def _maybe_idle_action(self):
        if random.random() < 0.01:
            pick = random.random()
            if pick < 0.35:
                self.jump_t = 1.0
            elif pick < 0.6:
                self.action, self.action_t = "sway", 1.0
            elif pick < 0.8:
                self.action, self.action_t = "stretch", 1.0
            elif pick < 0.9:
                if self.t - self.last_speak_tick >= 1500:
                    self.last_speak_tick = self.t
                    if pick < 0.82:
                        self.say(random.choice(INNER_LINES), inner=True)
                    else:
                        self.say(random.choice(LINES))

    def _queue_say(self, text):
        """后台线程调用：只入队，由主线程 tick 统一弹出显示（线程安全）"""
        self._say_queue.append(text)

    def say(self, text, inner=False):
        if text == self.last_line and not text.startswith("天气"):
            return
        self.last_line = text
        self.bubble_inner = inner
        self.bubble_text = f"（{text}）" if inner else text
        self.bubble_until = self.t * TICK / 1000.0 + 2.8
        self.update()

    def check_system_status(self):
            now = self.t * TICK

            if now - getattr(self, "last_system_check", 0) < 10000:
                return

            self.last_system_check = now

            cpu = psutil.cpu_percent()

            if cpu >= 90:
                self.say("CPU跑满了，再这样下去我就卡死了")
                return

            ram = psutil.virtual_memory().percent

            if ram >= 95:
                self.say("内存爆了，快关掉几个没用的东西吧，注意，别把我关了")
                return

            if GPU_AVAILABLE:
                try:
                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)

                    temp = pynvml.nvmlDeviceGetTemperature(
                        handle,
                        pynvml.NVML_TEMPERATURE_GPU
                    )

                    if temp > 80:
                        self.say("我感觉我的鱼鳍快熟了")

                except Exception as e:
                    print("GPU读取失败:", e)

    # ---------- 鼠标事件 ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.last_press_pos = e.globalPosition().toPoint()
            self.dragging = False
            self.drag_start_pos = e.globalPosition().toPoint()
            self.function_panel.hide()
            self.chat_dialog.hide()
            self.chat_paused = True

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton and self.drag_start_pos is not None:
            delta = e.globalPosition().toPoint() - self.drag_start_pos
            if not self.dragging and delta.manhattanLength() > 6:
                self.dragging = True
                self.drag_offset = e.globalPosition().toPoint() - QPoint(self.x(), self.y())
            if self.dragging and self.drag_offset is not None:
                pos = e.globalPosition().toPoint() - self.drag_offset
                self.move(pos)
                if abs(delta.x()) > 10:
                    self._set_dir("left" if delta.x() < 0 else "right", 1 if delta.x() < 0 else -1)
                self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if self.dragging:
                self.dragging = False
                self.drag_offset = None
                self.drag_start_pos = None
                self._set_dir("down", 1)
                self.target = None
                self.rest_until = self.t * TICK + random.randint(6000, 14000)
                if random.random() < 0.5:
                    self.say(random.choice(DRAG_LINES))
                self.chat_paused = False
            else:
                self._click_timer.start(280)  # 等双击判定；单击则回嘴+弹聊天面板
            self.last_press_pos = None
            self.drag_start_pos = None

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._click_timer.stop()
            self.food_panel.popup_at(self.x() + self.width() / 2, self.y() + BUBBLE_H)

    def _on_single_click(self):
        """单击：蹦跳回嘴 + 弹聊天面板（两不误，不想聊点鱼身外关闭）"""
        if random.random() < 0.7:
            self.jump_t = 1.0
        if random.random() < 0.6:
            self.say(random.choice(REACT_LINES))
        panel = self.function_panel
        panel.popup_at(self.x() + self.width() / 2 - panel.width() / 2,
                       self.y() - panel.height() - 10)

    def on_food(self, food):
        self.food_panel.hide()
        self.eat_t = 1.0
        self.jump_t = 0.6
        lines = FOOD_LINES.get(food, ["好吃！"])
        self.say(random.choice(lines))

    def _show_chat_dialog(self):
        key = self.cfg.get("ds_api_key", "")
        if not key:
            self.say("请先在右键菜单里设置 DeepSeek Key！")
            self.chat_paused = False
            return
        self.chat_dialog.popup_at(
            self.x() + self.width() / 2,
            self.y() + BUBBLE_H
        )

    """def _get_city_by_ip(self):
        try:
            r = requests.get("http://ip-api.com/json/?fields=city&lang=zh-CN", timeout=5)
            if r.status_code == 200:
                city = r.json().get("city", "")
                if city:
                    return city
        except:
            pass
        return "汕头" """

    def _get_weather(self):
        try:
            city = self.cfg.get("city", "汕头")
            lat, lon = self._geo_city(city)
            if lat is None:
                self.say(f"没找到「{city}」的定位，换个城市名试试")
                return

            r = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,weather_code",
                    "timezone": "auto",
                },
                timeout=10,
            )

            print("状态:", r.status_code)
            print(r.text[:500])

            data = r.json()
            cur = data["current"]
            temp = round(cur["temperature_2m"])
            humidity = cur.get("relative_humidity_2m", "")
            code = cur.get("weather_code", 0)

            weather_cn = {
                0: "晴", 1: "大致晴朗", 2: "局部多云", 3: "阴",
                45: "雾", 48: "雾凇",
                51: "毛毛雨", 53: "毛毛雨", 55: "毛毛雨",
                56: "冻毛毛雨", 57: "冻毛毛雨",
                61: "小雨", 63: "中雨", 65: "大雨",
                66: "冻雨", 67: "冻雨",
                71: "小雪", 73: "中雪", 75: "大雪",
                77: "雪粒",
                80: "阵雨", 81: "阵雨", 82: "强阵雨",
                85: "阵雪", 86: "强阵雪",
                95: "雷暴", 96: "雷暴伴冰雹", 99: "雷暴伴冰雹",
            }
            text = weather_cn.get(code, f"天气代码{code}")
            hum = f"，湿度{humidity}%" if humidity != "" else ""
            self.say(f"{city}今天{temp}°{hum}，天气{text}")

        except Exception as e:
            print("天气错误:", repr(e))
            self.say("天气获取失败")

    def _geo_city(self, city):
        """中文城市名 -> (lat, lon);支持「城市 区县」组合,定位失败返回 (None, None)。"""
        cache = getattr(self, "_geo_cache", None)
        if cache is None:
            cache = self._geo_cache = {}
        if city in cache:
            return cache[city]
        # 拆分「河池 宜州」这类组合,逐个尝试(区县常比地级市更易命中)
        parts = city.replace("，", " ").replace(",", " ").replace("、", " ").split()
        for part in parts:
            if not part:
                continue
            variants = [part]
            for suf in ("市", "区", "县"):
                if not part.endswith(suf):
                    variants.append(part + suf)
            for name in variants:
                try:
                    g = requests.get(
                        "https://geocoding-api.open-meteo.com/v1/search",
                        params={"name": name, "count": 1, "language": "zh"},
                        timeout=10,
                    ).json()
                    res = g.get("results", [])
                    if res:
                        r = res[0]
                        cache[city] = (r["latitude"], r["longitude"])
                        return cache[city]
                except Exception as e:
                    print("定位尝试失败:", name, repr(e))
        return (None, None)
    

    def _build_menu(self):
        m = LaceMenu(self)
        mode_menu = LaceMenu(m, panel=PANEL_BOTTOM)
        m.addMenu(mode_menu).setText("模式")
        for label, key in [("自由散步", "wander"), ("跟随鼠标", "follow"), ("原地待着", "still")]:
            a = mode_menu.addAction(label)
            a.setCheckable(True)
            a.setChecked(self.mode == key)
            a.triggered.connect(lambda _, k=key: self.set_mode(k))
        size_menu = LaceMenu(m, panel=PANEL_BOTTOM)
        m.addMenu(size_menu).setText("大小")
        for label, mult in SIZE_LEVELS.items():
            a = size_menu.addAction(label)
            a.setCheckable(True)
            a.setChecked(abs(self.cur_h - 340 * mult) < 2)
            a.triggered.connect(lambda _, v=mult: self.set_size(v))
        outfit_menu = LaceMenu(m, panel=PANEL_BOTTOM)
        m.addMenu(outfit_menu).setText("换装")
        for o in self.outfits:
            a = outfit_menu.addAction(o["name"])
            a.setCheckable(True)
            a.setChecked(self.outfit == o["id"])
            a.triggered.connect(lambda _, oid=o["id"]: self.set_outfit(oid))
        m.addSeparator()
        m.addAction(m.tail_icon(), "设置 Key", self._set_key_dialog)
        m.addAction(m.tail_icon(), "设置城市", self._set_city_dialog)
        m.addAction(m.tail_icon(), "查看天气", self._get_weather)
        m.addSeparator()
        m.addAction("显示/隐藏", self.toggle_visible)
        m.addAction("回到屏幕内", self.snap_into_screen)
        pa = m.addAction("鼠标穿透（点不到它）")
        pa.setCheckable(True)
        pa.setChecked(self.cfg["passthrough"])
        pa.triggered.connect(lambda on: self.set_passthrough(on))
        ta = m.addAction("窗口置顶")
        ta.setCheckable(True)
        ta.setChecked(self.cfg["topmost"])
        ta.triggered.connect(lambda on: self.set_topmost(on))
        aa = m.addAction("开机自启")
        aa.setCheckable(True)
        aa.setChecked(self.cfg["autostart"])
        aa.triggered.connect(lambda on: self.set_autostart(on))
        m.addSeparator()
        m.addAction("退出", self.quit_app)
        return m

    def _set_key_dialog(self):
        key, ok = QInputDialog.getText(
            self, 
            "设置 DeepSeek Key", 
            "输入你的 API Key（从 platform.deepseek.com 获取）:",
            QLineEdit.EchoMode.Normal,
            self.cfg.get("ds_api_key", "")
        )
        if ok and key.strip():
            self.cfg["ds_api_key"] = key.strip()
            self._save_cfg()
            self.say("Key 设置成功！")
        elif ok and not key.strip():
            self.say("Key 不能为空")

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Context:
            self.tray.setContextMenu(self._build_menu())
        elif reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_visible()

    def contextMenuEvent(self, e):
        self._build_menu().exec(e.globalPos())

    # ---------- 功能 ----------
    def set_mode(self, mode):
        self.mode = mode
        self.target = None
        self.cfg["mode"] = mode
        self._save_cfg()

    def set_size(self, mult):
        self.cur_h = int(340 * mult)
        self.cfg["size"] = mult
        self._save_cfg()
        self.cross_t = 0.0
        self.prev_key = None
        self._apply_window_size()
        self.snap_into_screen()

    def snap_into_screen(self):
        geo = (self.screen() or QApplication.primaryScreen()).availableGeometry()
        x = max(geo.left(), min(geo.right() - self.width(), self.x()))
        y = max(geo.top(), min(geo.bottom() - self.height(), self.y()))
        self.move(x, y)

    def _apply_passthrough(self, on):
        hwnd = int(self.winId())
        GWL_EXSTYLE, WS_EX_LAYERED, WS_EX_TRANSPARENT = -20, 0x80000, 0x20
        style = ctypes.windll.user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        style = style | WS_EX_LAYERED
        if on:
            style |= WS_EX_TRANSPARENT
        else:
            style &= ~WS_EX_TRANSPARENT
        ctypes.windll.user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)

    def set_passthrough(self, on):
        self.cfg["passthrough"] = bool(on)
        self._save_cfg()
        self._apply_passthrough(bool(on))
        if on:
            self.say("我隐身了！右键托盘图标解除～")

    def set_topmost(self, on):
        self.cfg["topmost"] = bool(on)
        self._save_cfg()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, bool(on))
        self.show()

    def set_autostart(self, on):
        self.cfg["autostart"] = bool(on)
        self._save_cfg()
        lnk = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows",
                           "Start Menu", "Programs", "Startup", "大肥鱼桌宠.lnk")
        try:
            if on:
                if getattr(sys, "frozen", False):
                    target = sys.executable
                    args = ""
                    icon = ""
                else:
                    target = PYTHONW
                    args = '"{}"'.format(os.path.join(APP_DIR, "桌宠.py"))
                    icon = os.path.join(APP_DIR, "icon.ico") if os.path.exists(os.path.join(APP_DIR, "icon.ico")) else ""

                def _ps(s):
                    # PowerShell 单引号字符串内的单引号需双写转义
                    return s.replace("'", "''")

                ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{}');"
                      "$s.TargetPath='{}';$s.Arguments='{}';$s.WorkingDirectory='{}';"
                      "$s.IconLocation='{}';$s.Save()"
                      .format(_ps(lnk), _ps(target), _ps(args), _ps(APP_DIR), _ps(icon)))
                subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=True)
                self.say("已开机自启，明天见～")
            else:
                if os.path.exists(lnk):
                    os.remove(lnk)
                self.say("已取消开机自启")
        except Exception as ex:
            QMessageBox.warning(self, "开机自启", f"设置失败：{ex}")

    def toggle_visible(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()

    def _save_cfg(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("配置保存失败:", repr(e))

    def quit_app(self):
        self.cfg["x"], self.cfg["y"] = self.x(), self.y()
        self._save_cfg()
        self.tray.hide()
        QApplication.quit()


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
    print("\n结果:", "OK" if ok else "有问题")
    del app
    return 0 if ok else 1


def main():
    if "--font-check" in sys.argv:
        sys.exit(check_fonts())
    if "--check" in sys.argv:
        sys.exit(check_appearance())
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    w = PetWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        try:
            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "大肥鱼桌宠出错", str(ex))
        except Exception:
            pass
        raise