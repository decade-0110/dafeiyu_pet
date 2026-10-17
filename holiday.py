# -*- coding: utf-8 -*-
"""峰谷定价与节假日判定（纯标准库，不依赖 Qt / 网络）。

规则来源：https://api-docs.deepseek.com/zh-cn/quick_start/pricing
高峰 = 周一至周五（不含中国法定节假日）9:00-12:00、14:00-18:00；
其余时段（含周末、法定节假日全天）为空闲，空闲价 = 高峰价 x 0.5。
判定按本机本地时间。

pet_window.py 只负责显示，所有判断都在这里，便于 pytest 直接测试。
"""
import json
import os
from datetime import datetime, timedelta

PEAK_WINDOWS = ((9 * 60, 12 * 60), (14 * 60, 18 * 60))
PRICE_FACTOR_OFF = 0.5
RATE_TABLE = (                      # 元 / 百万 tokens（高峰价）
    {"model": "deepseek-flash", "hit": 0.04, "miss": 2.0, "out": 8.0},
    {"model": "deepseek-v4-pro", "hit": 0.30, "miss": 9.0, "out": 27.0},
)

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
HOLIDAY_DIR = os.path.join(PROJECT_DIR, "assets", "holidays")

# 缓存键包含 (年份, 显式路径, app_dir, holiday_dir)，避免换路径后读到旧结果。
# 测试里用 clear_holiday_cache() 隔离；桌宠进程内按年缓存，减少磁盘读取。
_holiday_cache = {}


def clear_holiday_cache():
    """清空节假日表缓存（测试和手动刷新用）。"""
    _holiday_cache.clear()


def _resolve_dirs(app_dir, holiday_dir):
    app_dir = PROJECT_DIR if app_dir is None else app_dir
    holiday_dir = HOLIDAY_DIR if holiday_dir is None else holiday_dir
    return os.path.abspath(app_dir), os.path.abspath(holiday_dir)


def _cache_key(year, path, app_dir, holiday_dir):
    return (year,
            os.path.abspath(path) if path else None,
            app_dir, holiday_dir)


def load_holidays(year, path=None, *, app_dir=None, holiday_dir=None):
    """读取某年节假日表：显式 path → app_dir/holidays.json → holiday_dir/<年>.json。

    返回 {"dates": set("YYYY-MM-DD"), "names": {date: name}, "year": int}；
    读不到返回 None（调用方按「未知年份」处理，不猜测）。
    """
    app_dir, holiday_dir = _resolve_dirs(app_dir, holiday_dir)
    key = _cache_key(year, path, app_dir, holiday_dir)
    if key in _holiday_cache:
        return _holiday_cache[key]

    candidates = []
    if path:
        candidates.append(path)
    candidates.append(os.path.join(app_dir, "holidays.json"))
    candidates.append(os.path.join(holiday_dir, f"{year}.json"))

    for p in candidates:
        if not p or not os.path.exists(p):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if int(data.get("year", year)) != year:
                continue
            days = data.get("holidays", [])
            dates = {d["date"] for d in days if d.get("date")}
            names = {d["date"]: (d.get("name") or "节假日")
                     for d in days if d.get("date")}
            info = {"dates": dates, "names": names, "year": year,
                    "source": data.get("source", p)}
            _holiday_cache[key] = info
            return info
        except Exception as e:
            print(f"[峰谷] 节假日表读取失败 {p}: {e!r}")

    _holiday_cache[key] = None
    return None


def is_china_holiday(day, holiday_info):
    """True/False=确定；None=该年没有数据，无法判定。"""
    if holiday_info is None:
        return None
    return day.strftime("%Y-%m-%d") in holiday_info["dates"]


def price_band(dt, holiday_info):
    """返回 (band, reason)：band 为 peak / off / unknown；reason 说明原因。"""
    if dt.weekday() >= 5:
        return "off", "周末（全天空闲）"
    h = is_china_holiday(dt.date(), holiday_info)
    if h is None:
        return "unknown", "缺少今年节假日表，按工作日规则估算"
    if h is True:
        return "off", f"{holiday_info['names'].get(dt.strftime('%Y-%m-%d'), '节假日')}（全天空闲）"
    mins = dt.hour * 60 + dt.minute
    if any(a <= mins < b for a, b in PEAK_WINDOWS):
        return "peak", "工作日高峰时段"
    return "off", "工作日非高峰时段"


def next_switch(dt, holiday_info):
    """下一个时段边界：返回 (切换时刻, 切换后的band)。按分钟向前扫，最多 8 天。

    逐分钟判定天然覆盖跨天（次日 0 点、周末起止、节假日首尾）。
    """
    cur_band, _ = price_band(dt, holiday_info)
    cur = dt.replace(second=0, microsecond=0)
    for _ in range(8 * 24 * 60):
        cur = cur + timedelta(minutes=1)
        band, _reason = price_band(cur, holiday_info)
        if band != cur_band:
            return cur, band
    return None, cur_band


def fmt_remain(delta):
    """把时间差写成「2 小时 15 分」这种顺口格式。"""
    if delta is None:
        return "—"
    total = max(0, int(delta.total_seconds()))
    h, m = divmod(total // 60, 60)
    if h and m:
        return f"{h} 小时 {m} 分"
    if h:
        return f"{h} 小时"
    return f"{m} 分"


def local_utc_offset_hours():
    """本机相对 UTC 的小时偏移（北京时间返回 8）。"""
    off = datetime.now().astimezone().utcoffset() or timedelta()
    return int(off.total_seconds() // 3600)


def price_snapshot(now=None, holidays=None, holiday_path=None, *,
                   app_dir=None, holiday_dir=None):
    """峰谷时段快照，供气泡与面板共用（纯本地计算，不联网）。"""
    now = now or datetime.now()
    info = holidays if holidays is not None else load_holidays(
        now.year, holiday_path, app_dir=app_dir, holiday_dir=holiday_dir)
    band, reason = price_band(now, info)
    nxt, nxt_band = next_switch(now, info)
    if nxt is not None:
        # 找边界时可能跨天，重新按边界时刻判定更准
        nxt_band, _ = price_band(nxt, info)
    band_text = {"peak": "高峰时段（标准价）", "off": "空闲时段（半价）",
                 "unknown": "时段未知"}[band]
    next_text = "—"
    remain_text = "—"
    if nxt is not None:
        if nxt.date() == now.date():
            next_text = nxt.strftime("%H:%M")
        else:
            next_text = nxt.strftime("%m-%d %H:%M")
        remain_text = fmt_remain(nxt - now)
    return {
        "now": now,
        "offset_hours": local_utc_offset_hours(),
        "band": band,
        "band_text": band_text,
        "reason": reason,
        "next_at": nxt,
        "next_band": nxt_band,
        "next_text": next_text,
        "remain_text": remain_text,
        "holiday_year": info["year"] if info else None,
        "holiday_count": len(info["dates"]) if info else 0,
        "rates": RATE_TABLE,
    }


def price_say_text(snap):
    """气泡播报用的一句话（控制在 30 字内）。"""
    if snap["band"] == "unknown":
        return "时段算不准，缺今年节假日表"
    if snap["band"] == "peak":
        return f"现在是高峰时段，{snap['remain_text']}后半价"
    return f"现在是空闲时段（半价），{snap['remain_text']}后恢复"


def rate_text(value, factor):
    """单价按系数折算出当前生效价，保留合适的位数。"""
    v = value * factor
    if v >= 1:
        return ("%.1f" % v).rstrip("0").rstrip(".")
    return ("%.3f" % v).rstrip("0").rstrip(".")
