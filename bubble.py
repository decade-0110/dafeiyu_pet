# -*- coding: utf-8 -*-
"""气泡、台词与绘制基础。

包含：
- 台词池与选择器（Cooldown / LinePicker，不连续重复 + 冷却）；
- 气泡 / 花边 / 字体绘制（Qt）；
- say() 的同句去重规则。
"""
import math
import os
import random
import time

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (QPainter, QPixmap, QFont, QColor, QIcon, QFontMetrics,
                           QPen, QBrush, QLinearGradient, QPainterPath, QFontDatabase)

from config import BUNDLE_DIR

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

# ===== 台词池 =====
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


# ==================== 字体 ====================
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


def ui_font_chain():
    """QSS 用：把优先链串成回退链，Qt 会挑第一个存在的。"""
    return ", ".join("'%s'" % n for n in font_candidates())


# ==================== 绘制 ====================
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


# ==================== 台词选择 ====================
class Cooldown:
    """简单的冷却门：consume() 成功一次后，在 seconds 秒内都返回 False。"""

    def __init__(self, seconds, clock=None):
        self.seconds = max(0.0, float(seconds))
        self._clock = time.monotonic if clock is None else clock
        self._next_at = None

    def _now(self, now):
        return self._clock() if now is None else float(now)

    def ready(self, now=None):
        """冷却是否已结束（不消费）。"""
        return self._next_at is None or self._now(now) >= self._next_at

    def consume(self, now=None):
        """冷却已结束则开始下一轮并返回 True；冷却中返回 False。"""
        now = self._now(now)
        if self._next_at is not None and now < self._next_at:
            return False
        self._next_at = now + self.seconds
        return True

    def remaining(self, now=None):
        """距冷却结束还有多少秒（已结束返回 0）。"""
        if self._next_at is None:
            return 0.0
        return max(0.0, self._next_at - self._now(now))

    def reset(self):
        self._next_at = None


class LinePicker:
    """从台词池里随机挑一句，保证不连续重复；可选冷却门。

    - 只有一个候选时无法避免重复，会一直返回它；
    - lines 为空时返回 None，且不会消费冷却；
    - gate 可与其他 picker 共享，实现全局冷却（桌宠的空闲冒泡就是如此）。
    """

    def __init__(self, lines, rng=None, gate=None, cooldown=0.0, clock=None):
        self.lines = list(lines)
        self._rng = random.Random() if rng is None else rng
        if gate is not None:
            self.gate = gate
        elif cooldown:
            self.gate = Cooldown(cooldown, clock=clock)
        else:
            self.gate = None
        self._last = None

    @property
    def last(self):
        """上一次选中的台词（尚未选过为 None）。"""
        return self._last

    def pick(self, now=None):
        """返回下一句台词；池为空或冷却中返回 None。"""
        if not self.lines:
            return None
        if self.gate is not None and not self.gate.consume(now):
            return None

        if self._last is None:
            candidates = self.lines
        else:
            candidates = [line for line in self.lines if line != self._last]
            if not candidates:
                # 池里全是同一句（或只有一个候选），只能重复
                candidates = self.lines

        line = self._rng.choice(candidates)
        self._last = line
        return line

    def reset(self):
        """忘记上一句（不影响共享的冷却门）。"""
        self._last = None


def is_duplicate(text, last_line):
    """say() 的去重规则：同一句不重复，但「天气…」播报允许连续更新。"""
    return text == last_line and not text.startswith("天气")
