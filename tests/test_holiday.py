# -*- coding: utf-8 -*-
"""holiday.py：峰谷判定、节假日表读取、时段边界与快照。"""
import json
from datetime import datetime, timedelta

import pytest

import holiday

# 与 assets/holidays/2026.json 同口径：只收 holiday=true 的法定节假日自然日。
# 2026-09-25~27 中秋，2026-10-01~07 国庆。
HOLIDAY_DAYS_2026 = [
    {"date": f"2026-09-{d:02d}", "name": "中秋节"} for d in (25, 26, 27)
] + [
    {"date": f"2026-10-{d:02d}", "name": "国庆节"} for d in range(1, 8)
]
INFO_2026 = {
    "dates": {d["date"] for d in HOLIDAY_DAYS_2026},
    "names": {d["date"]: d["name"] for d in HOLIDAY_DAYS_2026},
    "year": 2026,
    "source": "test",
}


def write_table(path, days, year=2026, source=None):
    """写一份节假日表到 tmp_path，返回路径字符串。"""
    payload = {"year": year, "holidays": days}
    if source is not None:
        payload["source"] = source
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(path)


@pytest.fixture
def holiday_dirs(tmp_path):
    app = tmp_path / "app"
    hol = tmp_path / "holidays"
    app.mkdir()
    hol.mkdir()
    return app, hol


# ---------------------------------------------------------------- 读取与缓存

def test_load_holidays_from_explicit_path(holiday_dirs):
    app, hol = holiday_dirs
    path = write_table(hol / "custom.json", HOLIDAY_DAYS_2026, source="https://example.test/2026")

    info = holiday.load_holidays(2026, path=path, app_dir=app, holiday_dir=hol)

    assert info["year"] == 2026
    assert info["dates"] == INFO_2026["dates"]
    assert info["names"]["2026-10-01"] == "国庆节"
    assert info["source"] == "https://example.test/2026"


def test_load_holidays_from_app_dir(holiday_dirs):
    app, hol = holiday_dirs
    write_table(app / "holidays.json", [{"date": "2026-01-01", "name": "元旦"}])

    info = holiday.load_holidays(2026, app_dir=app, holiday_dir=hol)

    assert info["dates"] == {"2026-01-01"}


def test_load_holidays_from_bundled_year_file(holiday_dirs):
    app, hol = holiday_dirs
    write_table(hol / "2026.json", [{"date": "2026-05-01", "name": "劳动节"}])

    info = holiday.load_holidays(2026, app_dir=app, holiday_dir=hol)

    assert info["dates"] == {"2026-05-01"}


def test_explicit_path_wins_over_app_and_bundled(holiday_dirs):
    app, hol = holiday_dirs
    write_table(hol / "2026.json", [{"date": "2026-03-01", "name": "打包表"}])
    write_table(app / "holidays.json", [{"date": "2026-02-01", "name": "用户表"}])
    explicit = write_table(hol / "explicit.json", [{"date": "2026-04-01", "name": "显式表"}])

    info = holiday.load_holidays(2026, path=explicit, app_dir=app, holiday_dir=hol)

    assert info["dates"] == {"2026-04-01"}


def test_year_mismatch_is_ignored(holiday_dirs):
    app, hol = holiday_dirs
    write_table(hol / "2026.json", [{"date": "2025-01-01"}], year=2025)

    assert holiday.load_holidays(2026, app_dir=app, holiday_dir=hol) is None


def test_missing_table_returns_none(holiday_dirs):
    app, hol = holiday_dirs

    assert holiday.load_holidays(2027, app_dir=app, holiday_dir=hol) is None


def test_malformed_json_returns_none_without_raising(holiday_dirs):
    app, hol = holiday_dirs
    (hol / "2026.json").write_text("{not valid json", encoding="utf-8")

    assert holiday.load_holidays(2026, app_dir=app, holiday_dir=hol) is None


def test_non_object_json_returns_none(holiday_dirs):
    app, hol = holiday_dirs
    (hol / "2026.json").write_text("[1, 2, 3]", encoding="utf-8")

    assert holiday.load_holidays(2026, app_dir=app, holiday_dir=hol) is None


def test_missing_name_falls_back(holiday_dirs):
    app, hol = holiday_dirs
    write_table(hol / "2026.json", [{"date": "2026-01-01"}])

    info = holiday.load_holidays(2026, app_dir=app, holiday_dir=hol)

    assert info["names"]["2026-01-01"] == "节假日"


def test_result_is_cached_until_cleared(holiday_dirs):
    app, hol = holiday_dirs
    path = hol / "2026.json"
    write_table(path, [{"date": "2026-01-01", "name": "元旦"}])

    first = holiday.load_holidays(2026, app_dir=app, holiday_dir=hol)
    write_table(path, [{"date": "2026-01-01"}, {"date": "2026-01-02"}])
    cached = holiday.load_holidays(2026, app_dir=app, holiday_dir=hol)

    assert cached is first
    assert len(cached["dates"]) == 1

    holiday.clear_holiday_cache()
    refreshed = holiday.load_holidays(2026, app_dir=app, holiday_dir=hol)
    assert len(refreshed["dates"]) == 2


def test_accepts_pathlib_path(tmp_path):
    path = tmp_path / "2026.json"
    write_table(path, [{"date": "2026-01-01"}])

    info = holiday.load_holidays(
        2026, path=path, app_dir=tmp_path / "app", holiday_dir=tmp_path / "hol")

    assert info["dates"] == {"2026-01-01"}
    assert str(info["source"]) == str(path)


# ---------------------------------------------------------------- 峰谷判定

def test_is_china_holiday():
    day = datetime(2026, 10, 1).date()

    assert holiday.is_china_holiday(day, INFO_2026) is True
    assert holiday.is_china_holiday(datetime(2026, 10, 2).date(), INFO_2026) is True
    assert holiday.is_china_holiday(datetime(2026, 10, 8).date(), INFO_2026) is False
    assert holiday.is_china_holiday(day, None) is None


@pytest.mark.parametrize("hour, minute, band, reason", [
    (8, 59, "off", "工作日非高峰时段"),
    (9, 0, "peak", "工作日高峰时段"),
    (11, 59, "peak", "工作日高峰时段"),
    (12, 0, "off", "工作日非高峰时段"),
    (13, 59, "off", "工作日非高峰时段"),
    (14, 0, "peak", "工作日高峰时段"),
    (17, 59, "peak", "工作日高峰时段"),
    (18, 0, "off", "工作日非高峰时段"),
    (23, 59, "off", "工作日非高峰时段"),
])
def test_workday_peak_boundaries(hour, minute, band, reason):
    # 2026-10-08 是周四，且不在节假日表内。
    assert holiday.price_band(datetime(2026, 10, 8, hour, minute), INFO_2026) == (band, reason)


@pytest.mark.parametrize("day, hour", [
    (10, 10),   # 周六 10:00
    (11, 15),   # 周日 15:00
])
def test_weekend_is_off_all_day(day, hour):
    band, reason = holiday.price_band(datetime(2026, 10, day, hour, 0), INFO_2026)
    assert band == "off"
    assert reason == "周末（全天空闲）"


@pytest.mark.parametrize("month, day, name", [
    (10, 1, "国庆节"),
    (10, 7, "国庆节"),
    (9, 25, "中秋节"),
])
def test_legal_holiday_is_off_all_day(month, day, name):
    band, reason = holiday.price_band(datetime(2026, month, day, 10, 0), INFO_2026)
    assert band == "off"
    assert reason == f"{name}（全天空闲）"


def test_makeup_workday_on_weekend_still_off():
    """调休补班日（2026-10-10 周六）按官方规则仍是周末空闲，不能算高峰。"""
    day = datetime(2026, 10, 10, 10, 0)
    assert day.weekday() == 5
    assert day.strftime("%Y-%m-%d") not in INFO_2026["dates"]
    assert holiday.price_band(day, INFO_2026) == ("off", "周末（全天空闲）")


@pytest.mark.parametrize("hour", [9, 10, 15, 17])
def test_missing_current_year_table_degrades_to_unknown(hour):
    """缺当年表时不猜测：工作日本该高峰的时段返回 unknown。"""
    band, reason = holiday.price_band(datetime(2027, 3, 9, hour, 0), None)
    assert band == "unknown"
    assert reason == "缺少今年节假日表，按工作日规则估算"


def test_missing_table_still_knows_weekend():
    assert holiday.price_band(datetime(2027, 3, 13, 10, 0), None) == (
        "off", "周末（全天空闲）")


# ---------------------------------------------------------------- 下一个边界

def test_next_switch_same_day():
    nxt, band = holiday.next_switch(datetime(2026, 10, 8, 11, 59), INFO_2026)
    assert (nxt, band) == (datetime(2026, 10, 8, 12, 0), "off")

    nxt, band = holiday.next_switch(datetime(2026, 10, 8, 12, 0), INFO_2026)
    assert (nxt, band) == (datetime(2026, 10, 8, 14, 0), "peak")


def test_next_switch_crosses_weekend():
    # 周五 18:00 之后一路空闲，直到周一 9:00。
    nxt, band = holiday.next_switch(datetime(2026, 10, 9, 18, 0), INFO_2026)
    assert (nxt, band) == (datetime(2026, 10, 12, 9, 0), "peak")


def test_next_switch_skips_long_holiday():
    # 9/30 18:00 空闲 → 国庆 7 天 + 周末，直到 10/8 9:00 才转高峰。
    nxt, band = holiday.next_switch(datetime(2026, 9, 30, 18, 0), INFO_2026)
    assert (nxt, band) == (datetime(2026, 10, 8, 9, 0), "peak")


def test_next_switch_without_table_goes_to_weekend():
    nxt, band = holiday.next_switch(datetime(2027, 3, 9, 10, 0), None)
    assert (nxt, band) == (datetime(2027, 3, 13, 0, 0), "off")


@pytest.mark.parametrize("delta, text", [
    (None, "—"),
    (timedelta(seconds=-5), "0 分"),
    (timedelta(seconds=0), "0 分"),
    (timedelta(seconds=59), "0 分"),
    (timedelta(seconds=60), "1 分"),
    (timedelta(minutes=59), "59 分"),
    (timedelta(hours=1), "1 小时"),
    (timedelta(hours=1, minutes=1), "1 小时 1 分"),
    (timedelta(hours=2, minutes=15), "2 小时 15 分"),
])
def test_fmt_remain(delta, text):
    assert holiday.fmt_remain(delta) == text


# ---------------------------------------------------------------- 快照

def test_price_snapshot_peak():
    now = datetime(2026, 9, 30, 10, 30)
    snap = holiday.price_snapshot(now=now, holidays=INFO_2026)

    assert snap["band"] == "peak"
    assert snap["band_text"] == "高峰时段（标准价）"
    assert snap["reason"] == "工作日高峰时段"
    assert snap["next_at"] == datetime(2026, 9, 30, 12, 0)
    assert snap["next_band"] == "off"
    assert snap["next_text"] == "12:00"
    assert snap["remain_text"] == "1 小时 30 分"
    assert snap["holiday_year"] == 2026
    assert snap["holiday_count"] == len(INFO_2026["dates"])
    assert snap["rates"] is holiday.RATE_TABLE
    assert isinstance(snap["offset_hours"], int)


def test_price_snapshot_holiday():
    snap = holiday.price_snapshot(now=datetime(2026, 10, 1, 10, 0), holidays=INFO_2026)

    assert snap["band"] == "off"
    assert snap["reason"] == "国庆节（全天空闲）"
    assert snap["next_at"] == datetime(2026, 10, 8, 9, 0)
    assert snap["next_band"] == "peak"
    assert snap["next_text"] == "10-08 09:00"
    assert snap["remain_text"] != "—"


def test_price_snapshot_unknown_without_table(holiday_dirs):
    app, hol = holiday_dirs
    snap = holiday.price_snapshot(now=datetime(2027, 3, 9, 10, 0),
                                  app_dir=app, holiday_dir=hol)

    assert snap["band"] == "unknown"
    assert snap["band_text"] == "时段未知"
    assert snap["reason"].startswith("缺少今年节假日表")
    assert snap["holiday_year"] is None
    assert snap["holiday_count"] == 0
    assert snap["next_at"] == datetime(2027, 3, 13, 0, 0)
    assert snap["next_band"] == "off"
    assert snap["next_text"] == "03-13 00:00"
    assert holiday.price_say_text(snap) == "时段算不准，缺今年节假日表"


def test_price_say_text():
    assert holiday.price_say_text(
        {"band": "peak", "remain_text": "2 小时"}) == "现在是高峰时段，2 小时后半价"
    assert holiday.price_say_text(
        {"band": "off", "remain_text": "35 分"}) == "现在是空闲时段（半价），35 分后恢复"
    assert holiday.price_say_text({"band": "unknown"}) == "时段算不准，缺今年节假日表"
