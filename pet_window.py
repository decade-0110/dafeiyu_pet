# -*- coding: utf-8 -*-
"""窗口、动画与 Qt 控件：菜单 / 浮层 / 面板 / PetWindow。"""
import ctypes
import math
import os
import random
import subprocess
import sys
import threading
from datetime import datetime

import psutil

try:
    import pynvml
    pynvml.nvmlInit()
    GPU_AVAILABLE = True
except Exception:
    GPU_AVAILABLE = False

from PySide6.QtCore import (Qt, QTimer, QPoint, QPointF, QRectF, QSize,
                            QByteArray, QEasingCurve, QPropertyAnimation,
                            QParallelAnimationGroup, Property)
from PySide6.QtGui import (QPainter, QPixmap, QFont, QColor, QIcon, QFontMetrics,
                           QGuiApplication, QPainterPath, QPen)
from PySide6.QtWidgets import (QApplication, QWidget, QMenu, QSystemTrayIcon,
                               QMessageBox, QInputDialog, QLineEdit,
                               QHBoxLayout, QPushButton, QFrame, QDialog,
                               QToolButton, QLabel, QWidgetAction,
                               QGraphicsDropShadowEffect)
from PySide6.QtSvg import QSvgRenderer

import bubble
from bubble import (ACCENT_BG, ACCENT_HOVER, BUBBLE_FONT_PX, Cooldown,
                    DRAG_LINES, FOOD_LINES, FOODS, INNER_LINES, LACE_DEEP,
                    LACE_INSET, LACE_LIGHT, LACE_MARGIN, LACE_MID, LINES,
                    PANEL_BOTTOM, PANEL_EDGE, PANEL_TOP, REACT_LINES,
                    TEXT_DARK, TEXT_GRADIENT, TEXT_MUTED, UI_FONT_PT,
                    LinePicker, cute_font, draw_cute_text, draw_lace_frame,
                    draw_snowflake, draw_speech_bubble, draw_tail_icon,
                    is_duplicate, lace_tail_icon, ui_font_chain)
from config import (APP_DIR, CONFIG_PATH, HOLIDAY_DIR, PYTHONW, SPRITE_DIR,
                    load_config, save_config)
from outfit import (DEFAULT_OUTFIT, OUTFIT_DEFAULT_LINES, OUTFIT_LINES,
                    SIZE_LEVELS, discover_outfits, load_sprites,
                    sprites_at_height)
from ai_chat import build_messages, chat_reply
from weather import weather_text
from balance import (BALANCE_ERRORS, balance_panel_rows, balance_summary_text,
                     fetch_balance)
from holiday import PRICE_FACTOR_OFF, price_say_text, price_snapshot, rate_text

BUBBLE_H = 56
MARGIN = 4
SPEED = 380.0
TICK = 20
IDLE_SPEECH_COOLDOWN = 30.0    # 秒：空闲时自动冒泡的最小间隔（原 1500 tick）

# ===== 右键菜单 =====
MENU_FONT_PT = 11
MENU_ITEM_PAD_Y = 2
MENU_ITEM_MIN_H = 26
MENU_ICON_SIZE = 16
MENU_ICON_LEFT = 10
MENU_ICON_GAP = 10
MENU_TEXT_LEFT = MENU_ICON_LEFT + MENU_ICON_SIZE + MENU_ICON_GAP
MENU_TEXT_RIGHT = 34
MENU_HOVER_RADIUS = 9
MENU_INDICATOR_W = 2
MENU_SECTION_PT = 10
MENU_GROUP_GAP = 16
MENU_HEADER_H = 30
MENU_TEXT_ANIM_MS = 120
MENU_POPUP_MS = 130
MENU_HIDE_MS = 120
MENU_POPUP_OFFSET = 4
MENU_POPUP_OPACITY = 0.95
MENU_SHADOW_BLUR = 14
MENU_SHADOW_OFFSET = (0, 4)
MENU_SHADOW_ALPHA = 36
MENU_ICON_COLOR = LACE_DEEP
MENU_ICON_HOVER = "#7fb0f0"
MENU_TEXT_NORMAL = TEXT_DARK
MENU_TEXT_HOVER = LACE_DEEP
MENU_TEXT_EXIT = "#9aa8bd"
MENU_SECTION_COLOR = "#8aa4c8"
MENU_SECTION_LINE = "#dbe8fb"
MENU_SUBMENU_DELAY_MS = 200   # 目标值；Qt 实测 SH_Menu_SubMenuPopupDelay 约 225ms，按“约 200ms”处理


def _menu_svg(body):
    """给菜单线性图标套统一的 SVG 外壳，{color} 由绘制时替换。"""
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
            'viewBox="0 0 16 16" fill="none" stroke="{color}" stroke-width="1.5" '
            'stroke-linecap="round" stroke-linejoin="round">' + body + '</svg>')


MENU_ICON_SVG = {
    "mode": _menu_svg('<circle cx="8" cy="8" r="5.3"/>'
                      '<path d="M10.4 5.6 9.1 9.1 5.6 10.4 6.9 6.9Z"/>'),
    "size": _menu_svg('<path d="M3 13 13 3"/><path d="M9 3h4v4"/>'
                      '<path d="M7 13H3V9"/>'),
    "outfit": _menu_svg('<path d="M8 6.3V4.8a1.5 1.5 0 1 1 1.5-1.5"/>'
                        '<path d="M3.5 9.2 8 6.3l4.5 2.9"/>'
                        '<path d="M4.8 9.2v2.6h6.4V9.2"/>'),
    "key": _menu_svg('<circle cx="5.2" cy="10.8" r="2.4"/><path d="m7 9 5.2-5.2"/>'
                     '<path d="m10.2 5.8 1.4 1.4"/><path d="m11.8 4.2 1.4 1.4"/>'),
    "city": _menu_svg('<path d="M8 14s4.5-4.4 4.5-8A4.5 4.5 0 0 0 8 1.5 4.5 4.5 0 0 0 3.5 6C3.5 9.6 8 14 8 14Z"/>'
                      '<circle cx="8" cy="6" r="1.6"/>'),
    "weather": _menu_svg('<circle cx="5.5" cy="5.5" r="2.2"/>'
                         '<path d="M5.5 1.5v1M5.5 8.5v1M1.5 5.5h1M8.5 5.5h1"/>'
                         '<path d="M5 12.5h6.2a2.3 2.3 0 0 0 .1-4.6 3.1 3.1 0 0 0-5.6 1.1A2 2 0 0 0 5 12.5Z"/>'),
    "clock": _menu_svg('<circle cx="8" cy="8" r="5.5"/><path d="M8 4.6V8l2.4 1.4"/>'),
    "wallet": _menu_svg('<rect x="2" y="4" width="12" height="9" rx="2"/>'
                        '<path d="M2 6.5h12"/>'
                        '<circle cx="11.4" cy="9.6" r="1" fill="{color}" stroke="none"/>'),
    "eye": _menu_svg('<path d="M1.6 8S4 3.8 8 3.8 14.4 8 14.4 8 12 12.2 8 12.2 1.6 8 1.6 8Z"/>'
                     '<circle cx="8" cy="8" r="2.1"/>'),
    "corners": _menu_svg('<path d="M2.5 6V2.5H6M13.5 6V2.5H10M2.5 10v3.5H6M13.5 10v3.5H10"/>'
                         '<circle cx="8" cy="8" r="1.6"/>'),
    "cursor": _menu_svg('<path d="M3 2.2 12 7l-4.1 1.2L6.5 12Z"/>'
                        '<path d="M3 13.2 7.7 8.5"/>'),
    "pin": _menu_svg('<path d="m9.4 2.4 4.2 4.2-2.3.8-2.1 2.1-1 2.5-4.2-4.2 2.5-1 2.1-2.1Z"/>'
                     '<path d="M2 14 6.5 9.5"/>'),
    "power": _menu_svg('<path d="M8 2v5.2"/><path d="M4.7 4.4a4.8 4.8 0 1 0 6.6 0"/>'),
    "logout": _menu_svg('<path d="M9 2H4.2A2.2 2.2 0 0 0 2 4.2v7.6A2.2 2.2 0 0 0 4.2 14H9"/>'
                        '<path d="m10.8 5.5 2.7 2.5-2.7 2.5"/><path d="M6.2 8h7.3"/>'),
    "mode_walk": _menu_svg('<circle cx="8" cy="3" r="1.2"/>'
                           '<path d="M8 4.5v4M8 6l-2.4 2M8 6l2.4 2"/>'
                           '<path d="M8 8.5 6 12.5M8 8.5l2 4"/>'),
    "mode_follow": _menu_svg('<path d="M8 2.5c2.4 0 4 1.9 4 4.7v1.6a4 4 0 0 1-8 0V7.2c0-2.8 1.6-4.7 4-4.7Z"/>'
                             '<path d="M8 2.5v4"/>'),
    "mode_still": _menu_svg('<rect x="4" y="3" width="2.4" height="10" rx="1"/>'
                            '<rect x="9.6" y="3" width="2.4" height="10" rx="1"/>'),
    "size_s": _menu_svg('<rect x="5" y="5" width="6" height="6" rx="1.5"/>'),
    "size_m": _menu_svg('<rect x="3.5" y="3.5" width="9" height="9" rx="2"/>'),
    "size_l": _menu_svg('<rect x="2" y="2" width="12" height="12" rx="2.5"/>'),
}


class _MenuHeader(QWidget):
    """右键菜单顶部的品牌小条：鲸尾 + 大肥鱼 / 菜单。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedHeight(MENU_HEADER_H)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 1, 14, 1)
        lay.setSpacing(8)
        icon = QLabel(self)
        icon.setPixmap(lace_tail_icon(size=22).pixmap(22, 22))
        icon.setFixedSize(22, 22)
        icon.setStyleSheet("background: transparent;")
        title = QLabel("大肥鱼", self)
        title.setFont(cute_font(pt=12, bold=True))
        title.setStyleSheet("color: %s; background: transparent;" % LACE_DEEP)
        sub = QLabel("菜单", self)
        sub.setFont(cute_font(pt=8, bold=False))
        sub.setStyleSheet("color: %s; background: transparent;" % TEXT_MUTED)
        lay.addWidget(icon)
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addStretch(1)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(LACE_LIGHT), 1))
        p.drawLine(14, self.height() - 1, self.width() - 14, self.height() - 1)
        draw_snowflake(p, QPointF(self.width() - 17, self.height() / 2), 4.5,
                       QColor(LACE_MID), spokes=4)
        p.end()


class LaceMenu(QMenu):
    """蓝白花边右键菜单：外圈花边 + 分组标题 + SVG 图标 + 悬停动画。"""

    def __init__(self, parent=None, panel=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlag(Qt.WindowType.NoDropShadowWindowHint, True)
        self.setFont(cute_font(pt=MENU_FONT_PT, bold=True))
        self._panel = panel
        self._hover_color = QColor(MENU_TEXT_NORMAL)
        self._icon_cache = {}
        self._closing = False
        self._popup_group = None
        self._hide_group = None

        self._text_anim = QPropertyAnimation(self, b"hoverColor", self)
        self._text_anim.setDuration(MENU_TEXT_ANIM_MS)
        self._text_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.hovered.connect(self._on_hovered)
        self.aboutToShow.connect(self._reset_hover)

        self._apply_shadow()
        self.setStyleSheet(self._menu_qss())

        if not isinstance(parent, QMenu):
            header = QWidgetAction(self)
            header.setDefaultWidget(_MenuHeader(self))
            header.setEnabled(False)
            self.addAction(header)

    # ---------- 外观参数 ----------
    def _menu_qss(self):
        fm = QFontMetrics(self.font())
        pad_y = max(MENU_ITEM_PAD_Y, (MENU_ITEM_MIN_H - fm.height()) // 2)
        return """
            QMenu {
                background: transparent;
                border: none;
                padding: 7px 10px;
                color: transparent;
                font-family: %s;
                font-size: %dpt;
                font-weight: 700;
            }
            QMenu::item {
                background: transparent;
                padding: %dpx %dpx %dpx %dpx;
                margin: 1px 8px;
                border-radius: %dpx;
                color: transparent;
            }
            QMenu::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #e8f3ff, stop:0.55 #d3e7ff, stop:1 #c7dfff);
                color: transparent;
            }
            QMenu::item:disabled {
                color: transparent;
            }
            QMenu::separator {
                height: %dpx;
                background: transparent;
                margin: 0 8px;
            }
            QMenu::indicator {
                image: none;
                width: 0px;
                height: 0px;
                margin: 0px;
            }
            QMenu::right-arrow {
                image: none;
                width: 0px;
                height: 0px;
            }
        """ % (ui_font_chain(), MENU_FONT_PT,
               pad_y, MENU_TEXT_RIGHT, pad_y, MENU_TEXT_LEFT,
               MENU_HOVER_RADIUS, MENU_GROUP_GAP)

    def _apply_shadow(self):
        effect = QGraphicsDropShadowEffect(self)
        effect.setBlurRadius(MENU_SHADOW_BLUR)
        effect.setOffset(*MENU_SHADOW_OFFSET)
        effect.setColor(QColor(47, 95, 168, MENU_SHADOW_ALPHA))
        self.setGraphicsEffect(effect)
        self._shadow = effect

    # ---------- 动画 ----------
    def _get_hover_color(self):
        return self._hover_color

    def _set_hover_color(self, color):
        self._hover_color = QColor(color)
        self.update()

    hoverColor = Property(QColor, _get_hover_color, _set_hover_color)

    def _reset_hover(self):
        self._text_anim.stop()
        self._hover_color = QColor(MENU_TEXT_NORMAL)
        self.update()

    def _on_hovered(self, action):
        if action is None or action.isSeparator() or isinstance(action, QWidgetAction):
            return
        target = MENU_TEXT_EXIT if self._is_quit(action) else MENU_TEXT_HOVER
        self._text_anim.stop()
        self._text_anim.setStartValue(QColor(MENU_TEXT_NORMAL))
        self._text_anim.setEndValue(QColor(target))
        self._text_anim.start()
        self.update()

    def _stop_menu_animations(self):
        for group in (self._popup_group, self._hide_group):
            if group is not None:
                group.stop()
        self._popup_group = None
        self._hide_group = None

    def showEvent(self, event):
        super().showEvent(event)
        # 自定义分组分隔条比 Qt 默认分隔线高，show 后按最新 sizeHint 再校正一次高度，
        # 否则最后几项会被裁掉（QSS polish 之前算出的高度偏小）。
        hint = self.sizeHint()
        if self.size() != hint:
            self.resize(hint)
        self._closing = False
        self._stop_menu_animations()
        self._reset_hover()
        target = QPoint(self.pos())
        self.setWindowOpacity(MENU_POPUP_OPACITY)
        self.move(target.x(), target.y() + MENU_POPUP_OFFSET)

        group = QParallelAnimationGroup(self)
        opacity = QPropertyAnimation(self, b"windowOpacity", group)
        opacity.setDuration(MENU_POPUP_MS)
        opacity.setStartValue(MENU_POPUP_OPACITY)
        opacity.setEndValue(1.0)
        opacity.setEasingCurve(QEasingCurve.Type.OutCubic)

        pos = QPropertyAnimation(self, b"pos", group)
        pos.setDuration(MENU_POPUP_MS)
        pos.setStartValue(self.pos())
        pos.setEndValue(target)
        pos.setEasingCurve(QEasingCurve.Type.OutCubic)

        group.addAnimation(opacity)
        group.addAnimation(pos)
        self._popup_group = group
        group.start()

    def _hide_submenus(self):
        """父菜单收起时一并淡出已展开的子菜单，避免留下悬浮子菜单。"""
        for action in self.actions():
            sub = action.menu()
            if sub is not None and sub.isVisible():
                sub.hide()

    def hide(self):
        if self._closing or not self.isVisible():
            super().hide()
            return
        self._closing = True
        self._hide_submenus()
        self._stop_menu_animations()

        group = QParallelAnimationGroup(self)
        opacity = QPropertyAnimation(self, b"windowOpacity", group)
        opacity.setDuration(MENU_HIDE_MS)
        opacity.setStartValue(self.windowOpacity())
        opacity.setEndValue(0.0)
        opacity.setEasingCurve(QEasingCurve.Type.InCubic)

        start = QPoint(self.pos())
        pos = QPropertyAnimation(self, b"pos", group)
        pos.setDuration(MENU_HIDE_MS)
        pos.setStartValue(start)
        pos.setEndValue(start + QPoint(0, MENU_POPUP_OFFSET))
        pos.setEasingCurve(QEasingCurve.Type.InCubic)

        group.addAnimation(opacity)
        group.addAnimation(pos)
        group.finished.connect(self._finish_hide)
        self._hide_group = group
        group.start()

    def _finish_hide(self):
        self._hide_group = None
        self._closing = False
        self._hide_submenus()
        self.setWindowOpacity(1.0)
        super().hide()

    # ---------- 分组 / 图标 ----------
    def add_section(self, title):
        """插入一条 10pt 小标题分隔条（不是普通分隔线）。"""
        action = self.addSeparator()
        action.setData(("section", title))
        return action

    @staticmethod
    def _action_data(action):
        data = action.data()
        return data if isinstance(data, tuple) else ()

    def _is_quit(self, action):
        return self._action_data(action)[:1] == ("quit",)

    def _renderer(self, key, color):
        cache_key = (key, color)
        if cache_key not in self._icon_cache:
            svg = MENU_ICON_SVG.get(key)
            if not svg:
                self._icon_cache[cache_key] = None
            else:
                renderer = QSvgRenderer(QByteArray(
                    svg.replace("{color}", color).encode("utf-8")))
                self._icon_cache[cache_key] = renderer if renderer.isValid() else None
        return self._icon_cache[cache_key]

    def _paint_icon(self, p, action, r, active):
        data = self._action_data(action)
        if not data:
            return
        rect = QRectF(r.left() + MENU_ICON_LEFT,
                      r.center().y() - MENU_ICON_SIZE / 2,
                      MENU_ICON_SIZE, MENU_ICON_SIZE)
        if data[0] not in ("icon", "quit"):
            return
        color = MENU_TEXT_EXIT if data[0] == "quit" else (
            MENU_ICON_HOVER if active else MENU_ICON_COLOR)
        renderer = self._renderer(data[1], color)
        if renderer is not None:
            renderer.render(p, rect)

    def _paint_text(self, p, action, r, active):
        if self._is_quit(action):
            color = MENU_TEXT_EXIT
        elif active:
            color = self._hover_color
        else:
            color = QColor(MENU_TEXT_NORMAL)
        text_rect = QRectF(r.left() + MENU_TEXT_LEFT, r.top(),
                           r.width() - MENU_TEXT_LEFT - MENU_TEXT_RIGHT, r.height())
        fm = QFontMetrics(self.font())
        text = fm.elidedText(action.text(), Qt.TextElideMode.ElideRight,
                             max(1, int(text_rect.width())))
        p.save()
        p.setFont(self.font())
        p.setPen(color)
        p.drawText(text_rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), text)
        p.restore()

    def _paint_section(self, p, action):
        data = self._action_data(action)
        if data[:1] != ("section",):
            return
        title = data[1]
        if not title:
            return
        r = self.actionGeometry(action)
        if r.isEmpty():
            return
        font = cute_font(pt=MENU_SECTION_PT, bold=False)
        fm = QFontMetrics(font)
        x = r.left() + 8
        tw = fm.horizontalAdvance(title)
        p.save()
        p.setFont(font)
        p.setPen(QColor(MENU_SECTION_COLOR))
        p.drawText(QRectF(x, r.top(), tw + 4, r.height()),
                   int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), title)
        p.setPen(QPen(QColor(MENU_SECTION_LINE), 1))
        p.drawLine(QPointF(x + tw + 8, r.center().y()),
                   QPointF(r.right() - 8, r.center().y()))
        p.restore()

    def _paint_active_bar(self, p):
        action = self.activeAction()
        if action is None or action.isSeparator() or isinstance(action, QWidgetAction):
            return
        r = self.actionGeometry(action)
        if r.isEmpty():
            return
        bar = QRectF(r.left() + 3, r.top() + 6,
                     MENU_INDICATOR_W, max(2, r.height() - 12))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(MENU_TEXT_HOVER))
        p.drawRoundedRect(bar, MENU_INDICATOR_W / 2, MENU_INDICATOR_W / 2)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        frame = QRectF(self.rect())
        draw_lace_frame(p, frame, radius=14, radius_outer=20, panel=self._panel)
        p.end()
        super().paintEvent(event)

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint_active_bar(p)
        active = self.activeAction()
        for action in self.actions():
            if action.isSeparator():
                self._paint_section(p, action)
                continue
            if isinstance(action, QWidgetAction):
                continue
            r = self.actionGeometry(action)
            if r.isEmpty():
                continue
            is_active = action is active
            self._paint_icon(p, action, r, is_active)
            self._paint_text(p, action, r, is_active)
            cy = r.center().y()
            if action.menu() is not None:
                x = r.right() - 17
                path = QPainterPath()
                path.moveTo(x - 2.4, cy - 4.0)
                path.lineTo(x + 2.4, cy)
                path.lineTo(x - 2.4, cy + 4.0)
                p.setPen(QPen(QColor(LACE_MID), 1.7, Qt.PenStyle.SolidLine,
                              Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(path)
            elif action.isCheckable() and action.isChecked():
                x = r.right() - 17
                path = QPainterPath()
                path.moveTo(x - 4.0, cy + 0.2)
                path.lineTo(x - 1.0, cy + 3.2)
                path.lineTo(x + 5.0, cy - 4.2)
                p.setPen(QPen(QColor(LACE_DEEP), 1.9, Qt.PenStyle.SolidLine,
                              Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(path)
        p.end()


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

    def content_max_height(self):
        """内容区高度上限：按钮面板一行即可；文字面板可覆盖以放开。"""
        return 44

    def content_max_width(self):
        """内容区宽度上限：文字面板可覆盖以限制换行宽度。"""
        return 0                     # 0 = 不限制

    def finish_layout(self):
        """算好尺寸并把标题 / 关闭键 / 内容摆进花边环里。"""
        inner = LACE_MARGIN - LACE_INSET
        if self.lay is not None:
            self.lay.activate()          # 重建按钮后先结算布局，sizeHint 才是新尺寸
        cw = max(48, self.content.sizeHint().width())
        cap = self.content_max_width()
        if cap:
            cw = min(cap, cw)
        ch = min(self.content_max_height(), max(24, self.content.sizeHint().height()))
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


class InfoPanel(LacePanel):
    """通用信息面板：一行行「标签 + 值」，支持每行着色与底部小字。

    定价时段面板与余额面板都用它。为了尺寸稳定，这里**不用 Qt 布局引擎**：
    直接按字号算宽度/高度，并用 setGeometry 显式摆放每个 QLabel。
    （手动摆放 + 动态重建控件的组合下，sizeHint 不可靠，踩过坑。）
    """

    ROW_PT = 10
    FOOT_PT = 8
    ROW_GAP = 4

    def __init__(self, parent=None, title=""):
        super().__init__(parent, title=title)
        self.rows = []                # [(label, value, color), ...]
        self._row_widgets = []        # [(QLabel, QLabel), ...]
        self._footer_text = ""
        self._footer = QLabel(self.content)
        self._footer.setWordWrap(True)
        self._footer.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._footer.setStyleSheet(
            "QLabel{color:%s;font-family:%s;background:transparent;}"
            % (TEXT_MUTED, ui_font_chain()))
        self._footer.hide()
        self._row_font = cute_font(pt=self.ROW_PT, bold=False)
        self._foot_font = cute_font(pt=self.FOOT_PT, bold=False)
        self._footer.setFont(self._foot_font)

    def content_max_height(self):
        return 9999                   # 由 measure() 精确算，不再用基类的 44px 上限

    def rebuild(self, rows, footer=""):
        """rows: [(标签, 值)] 或 [(标签, 值, 颜色)]；footer: 底部小字。"""
        for pair in self._row_widgets:
            for w in pair:
                w.setParent(None)
                w.deleteLater()
        self._row_widgets = []
        self.rows = []
        for row in rows:
            label, value = row[0], row[1]
            color = row[2] if len(row) > 2 and row[2] else TEXT_DARK
            lw = QLabel(str(label), self.content)
            lw.setFont(self._row_font)
            lw.setStyleSheet("QLabel{color:%s;background:transparent;}" % TEXT_MUTED)
            vw = QLabel(str(value), self.content)
            vw.setFont(self._row_font)
            vw.setStyleSheet("QLabel{color:%s;background:transparent;}" % color)
            # 动态新建的控件必须显式可见/置顶：面板已经 show 过时，新子控件不一定会被重绘
            lw.setVisible(True)
            vw.setVisible(True)
            self._row_widgets.append((lw, vw))
            self.rows.append((str(label), str(value), color))
        self._footer_text = footer or ""
        self._footer.setText(self._footer_text)
        self._footer.setVisible(bool(self._footer_text))
        self.finish_layout()
        for pair in self._row_widgets:
            for w in pair:
                w.raise_()
        self._footer.raise_()

    def _extent(self, rows):
        """按字号算出 (表宽, 表高, 底部小字宽, 底部小字高)。"""
        rfm = QFontMetrics(self._row_font)
        ffm = QFontMetrics(self._foot_font)
        lw = max([rfm.horizontalAdvance(r[0]) for r in rows] or [40])
        vw = max([rfm.horizontalAdvance(r[1]) for r in rows] or [40])
        tw = lw + vw + 20
        th = rfm.height() * len(rows) + self.ROW_GAP * max(0, len(rows) - 1)
        fw = fh = 0
        if self._footer_text:
            fw = min(380, max(200, tw + 24))
            fh = ffm.boundingRect(0, 0, fw, 4000, int(Qt.TextFlag.TextWordWrap),
                                  self._footer_text).height()
        return tw, th, fw, fh

    def finish_layout(self):
        inner = LACE_MARGIN - LACE_INSET
        tw, th, fw, fh = self._extent(self.rows)
        cw = max(tw, fw, 140)
        ch = th + (fh + 10 if fh else 0)
        self.setFixedSize(int(cw + inner * 2), int(ch + 24 + inner * 2))
        title_w = self.header.sizeHint().width() + 16
        self.header.setGeometry(inner + 14, inner + 5, title_w, 16)
        self.close_btn.move(self.width() - inner - 26, inner + 3)
        self.content.setGeometry(inner, inner + 24, int(cw), int(ch))

        rfm = QFontMetrics(self._row_font)
        y = 0
        for lw, vw in self._row_widgets:
            lw.setGeometry(0, y, int(cw * 0.55), rfm.height())
            vw.setGeometry(int(cw * 0.45), y, int(cw * 0.55), rfm.height())
            y += rfm.height() + self.ROW_GAP
        if self._footer_text:
            self._footer.setGeometry(0, int(th + 8), int(cw), int(fh) + 2)


class PricingPanel(InfoPanel):
    """峰谷定价面板：当前时段 + 倒计时 + 单价表。"""

    def __init__(self):
        super().__init__(None, title="峰谷时段")

    def show_snapshot(self, snap):
        band_color = {"peak": "#c2410c", "off": "#1f7a4d", "unknown": TEXT_MUTED}[snap["band"]]
        rows = [
            ("当前时段", snap["band_text"], band_color),
            ("本机时间", snap["now"].strftime("%Y-%m-%d %H:%M"), None),
            ("时区", "UTC%+d（按本机时间判定）" % snap["offset_hours"], None),
            ("距今切换", ("还有 %s → %s" % (snap["remain_text"], snap["next_text"]))
             if snap["next_at"] else "—", None),
            ("日期说明", snap["reason"], None),
        ]
        factor = PRICE_FACTOR_OFF if snap["band"] == "off" else 1.0
        price_color = LACE_DEEP if snap["band"] == "off" else TEXT_DARK
        for rate in snap["rates"]:
            rows.append((rate["model"], "%s / %s / %s" % (
                rate_text(rate["hit"], factor),
                rate_text(rate["miss"], factor),
                rate_text(rate["out"], factor)), price_color))
        head = "元/百万 tokens，依次为 命中 / 未命中 / 输出；"
        if snap["holiday_year"]:
            footer = (head + "空闲价 = 高峰价 x %g。节假日表 %d 年（%d 天），官方改价后需更新程序内置价目表。"
                      % (PRICE_FACTOR_OFF, snap["holiday_year"], snap["holiday_count"]))
        else:
            footer = (head + "空闲价 = 高峰价 x %g。没有今年的节假日表，上面按「工作日规则」估算；"
                      "运行 fetch_holidays.py --year <年> 可生成。" % PRICE_FACTOR_OFF)
        self.rebuild(rows, footer)


class BalancePanel(InfoPanel):
    """API 余额面板。"""

    def __init__(self):
        super().__init__(None, title="API 余额")

    def show_balance(self, parsed, footer=""):
        color = "#1f7a4d" if parsed["is_available"] else "#c2410c"
        rows = [(k, v, color if k == "可用状态" else None)
                for k, v in balance_panel_rows(parsed)]
        self.rebuild(rows, footer)

    def show_error(self, code):
        msg = BALANCE_ERRORS.get(code, "查询失败，稍后再试")
        self.rebuild([("状态", msg, "#c2410c")], "点菜单「查看余额」重试。")


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
        self.cfg = load_config(CONFIG_PATH)

        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.cfg.get("topmost", True):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("大肥鱼桌宠")

        # 可爱字体：先加载内置字体，再定下全局字体（面板 / 菜单 / 气泡都跟着用）
        bubble.load_bundled_fonts()
        bubble.PICKED_FONT_FAMILY = bubble.pick_cute_family()
        self.bubble_font = cute_font(size_px=BUBBLE_FONT_PX, bold=True)
        print("[字体] 最终使用: %r | 气泡 %dpx 字重 %d" % (
            bubble.PICKED_FONT_FAMILY, self.bubble_font.pixelSize(), self.bubble_font.weight()))

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
        self.sprites = load_sprites(self.outfits)
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
        self.last_system_check = 0
        self.t = 0
        self.jump_t = 0
        self.dragging = False
        self.drag_offset = None
        self.drag_start_pos = None
        self.last_line = ""
        self.last_press_pos = None

        # 空闲冒泡：两个台词池共用一个 30 秒冷却门，各自保证不连续重复
        self.speech_gate = Cooldown(IDLE_SPEECH_COOLDOWN)
        self.inner_line_picker = LinePicker(INNER_LINES, gate=self.speech_gate)
        self.idle_line_picker = LinePicker(LINES, gate=self.speech_gate)

        # AI 相关
        self.ds_busy = False
        self.chat_history = []  # 对话历史
        self.max_history = 40   # 最多记录40条
        self._say_queue = []    # 后台线程→主线程的气泡消息队列
        self._panel_queue = []  # 后台线程→主线程的面板数据队列

        # 聊天暂停标志
        self.chat_paused = False

        # 功能列表
        self.function_panel = FunctionPanel(self)
        self.food_panel = FoodPanel(self.on_food)
        self.outfit_panel = OutfitPanel(self.set_outfit)
        self.pricing_panel = PricingPanel()
        self.balance_panel = BalancePanel()
        self._balance_result = None      # 上一次成功的余额结果（冷却期内复用）
        self._balance_at = 0.0           # 上一次查询的时间戳（time.time()）
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
    def _sprites_at_height(self, h, outfit=None):
        outfit = outfit or self.outfit
        return sprites_at_height(self.sprites, h, outfit)

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
        messages = build_messages(self.chat_history, user_msg, self.max_history)

        def worker():
            try:
                ok, data = chat_reply(key, messages)
                if ok:
                    # 存入历史
                    self.chat_history.append({"role": "user", "content": user_msg})
                    self.chat_history.append({"role": "assistant", "content": data})
                    if len(self.chat_history) > self.max_history:
                        self.chat_history = self.chat_history[-self.max_history:]
                    self._queue_say(data)
                else:
                    self._queue_say(data)
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

        # 后台线程取回的余额结果，同样回主线程处理
        if self._panel_queue:
            for kind, data in self._panel_queue:
                if kind == "balance":
                    self._on_balance_result(data)
            self._panel_queue.clear()

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
                now = self.t * TICK / 1000.0
                if pick < 0.82:
                    line = self.inner_line_picker.pick(now)
                    if line:
                        self.say(line, inner=True)
                else:
                    line = self.idle_line_picker.pick(now)
                    if line:
                        self.say(line)

    def _queue_say(self, text):
        """后台线程调用：只入队，由主线程 tick 统一弹出显示（线程安全）"""
        self._say_queue.append(text)

    def say(self, text, inner=False):
        if is_duplicate(text, self.last_line):
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

    def _get_weather(self):
        try:
            city = self.cfg.get("city", "汕头")
            cache = getattr(self, "_geo_cache", None)
            if cache is None:
                cache = self._geo_cache = {}
            self.say(weather_text(city, cache))
        except Exception as e:
            print("天气错误:", repr(e))
            self.say("天气获取失败")

    # ---------- 峰谷定价时段 ----------
    def _show_pricing(self):
        """峰谷时段：纯本地计算，零联网零延迟。"""
        snap = price_snapshot(holiday_path=self.cfg.get("holiday_override", "") or None,
                              app_dir=APP_DIR, holiday_dir=HOLIDAY_DIR)
        self.say(price_say_text(snap))
        self.pricing_panel.show_snapshot(snap)
        self.pricing_panel.popup_at(self.x() + self.width() / 2, self.y() + BUBBLE_H)

    # ---------- API 余额 ----------
    def _show_balance(self):
        """查余额：带冷却与缓存，网络请求放后台线程，结果经 _panel_queue 回主线程。"""
        key = (self.cfg.get("ds_api_key", "") or "").strip()
        if not key:
            self.say(BALANCE_ERRORS["nokey"])
            self.balance_panel.show_error("nokey")
            self.balance_panel.popup_at(self.x() + self.width() / 2, self.y() + BUBBLE_H)
            return

        import time as _time
        cooldown = max(0, int(self.cfg.get("balance_cooldown", 60) or 0))
        now = _time.time()
        if self._balance_result is not None and (now - self._balance_at) < cooldown:
            # 冷却期内直接复用上次结果，不再打接口
            self.say(balance_summary_text(self._balance_result))
            self._popup_balance(self._balance_result)
            return

        self._balance_at = now
        self.say("正在查余额…")

        def worker():
            ok, data = fetch_balance(key)
            self._panel_queue.append(("balance", data))

        threading.Thread(target=worker, daemon=True).start()

    def _popup_balance(self, parsed):
        footer = "查询于 %s。余额与赠送额以官方平台为准。" % datetime.now().strftime("%H:%M:%S")
        self.balance_panel.show_balance(parsed, footer)
        self.balance_panel.popup_at(self.x() + self.width() / 2, self.y() + BUBBLE_H)

    def _on_balance_result(self, data):
        """主线程：收到后台线程的余额结果（dict=成功，str=错误码）。"""
        if isinstance(data, str):                 # 错误码
            self.say(BALANCE_ERRORS.get(data, "查询失败，稍后再试"))
            self.balance_panel.show_error(data)
            self._balance_result = None
            self.balance_panel.popup_at(self.x() + self.width() / 2, self.y() + BUBBLE_H)
            return
        self._balance_result = data
        self.say(balance_summary_text(data))
        self._popup_balance(data)

    def _build_menu(self):
        m = LaceMenu(self)
        m.add_section("外观")

        mode_menu = LaceMenu(m, panel=PANEL_BOTTOM)
        mode_action = m.addMenu(mode_menu)
        mode_action.setText("模式")
        mode_action.setData(("icon", "mode"))
        mode_icons = {"wander": "mode_walk", "follow": "mode_follow", "still": "mode_still"}
        for label, key in [("自由散步", "wander"), ("跟随鼠标", "follow"), ("原地待着", "still")]:
            a = mode_menu.addAction(label)
            a.setData(("icon", mode_icons[key]))
            a.setCheckable(True)
            a.setChecked(self.mode == key)
            a.triggered.connect(lambda _, k=key: self.set_mode(k))

        size_menu = LaceMenu(m, panel=PANEL_BOTTOM)
        size_action = m.addMenu(size_menu)
        size_action.setText("大小")
        size_action.setData(("icon", "size"))
        size_icons = {"小": "size_s", "中": "size_m", "大": "size_l"}
        for label, mult in SIZE_LEVELS.items():
            a = size_menu.addAction(label)
            a.setData(("icon", size_icons[label]))
            a.setCheckable(True)
            a.setChecked(abs(self.cur_h - 340 * mult) < 2)
            a.triggered.connect(lambda _, v=mult: self.set_size(v))

        outfit_menu = LaceMenu(m, panel=PANEL_BOTTOM)
        outfit_action = m.addMenu(outfit_menu)
        outfit_action.setText("换装")
        outfit_action.setData(("icon", "outfit"))
        for o in self.outfits:
            a = outfit_menu.addAction(o["name"])
            a.setData(("icon", "outfit"))
            a.setCheckable(True)
            a.setChecked(self.outfit == o["id"])
            a.triggered.connect(lambda _, oid=o["id"]: self.set_outfit(oid))

        m.add_section("功能")
        a = m.addAction("设置 Key", self._set_key_dialog)
        a.setData(("icon", "key"))
        a = m.addAction("设置城市", self._set_city_dialog)
        a.setData(("icon", "city"))
        a = m.addAction("查看天气", self._get_weather)
        a.setData(("icon", "weather"))
        a = m.addAction("查看定价时段", self._show_pricing)
        a.setData(("icon", "clock"))
        a = m.addAction("查看余额", self._show_balance)
        a.setData(("icon", "wallet"))

        m.add_section("窗口")
        a = m.addAction("显示/隐藏", self.toggle_visible)
        a.setData(("icon", "eye"))
        a = m.addAction("回到屏幕内", self.snap_into_screen)
        a.setData(("icon", "corners"))

        m.add_section("行为")
        pa = m.addAction("鼠标穿透（点不到它）")
        pa.setData(("icon", "cursor"))
        pa.setCheckable(True)
        pa.setChecked(self.cfg["passthrough"])
        pa.triggered.connect(lambda on: self.set_passthrough(on))
        ta = m.addAction("窗口置顶")
        ta.setData(("icon", "pin"))
        ta.setCheckable(True)
        ta.setChecked(self.cfg["topmost"])
        ta.triggered.connect(lambda on: self.set_topmost(on))
        aa = m.addAction("开机自启")
        aa.setData(("icon", "power"))
        aa.setCheckable(True)
        aa.setChecked(self.cfg["autostart"])
        aa.triggered.connect(lambda on: self.set_autostart(on))

        m.add_section("系统")
        quit_action = m.addAction("退出", self.quit_app)
        quit_action.setData(("quit", "logout"))
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
            save_config(CONFIG_PATH, self.cfg)
        except Exception as e:
            print("配置保存失败:", repr(e))

    def quit_app(self):
        self.cfg["x"], self.cfg["y"] = self.x(), self.y()
        self._save_cfg()
        self.tray.hide()
        QApplication.quit()
