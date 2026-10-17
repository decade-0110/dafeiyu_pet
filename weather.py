# -*- coding: utf-8 -*-
"""天气查询：中文城市名 → 经纬度 → Open-Meteo 当前天气（不依赖 Qt）。"""
import requests

WEATHER_CN = {
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


def geocode_city(city, cache=None):
    """中文城市名 -> (lat, lon);支持「城市 区县」组合,定位失败返回 (None, None)。"""
    if cache is None:
        cache = {}
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


def weather_text(city, cache=None):
    """返回可直接放进气泡的天气播报；网络/解析异常由调用方兜底。"""
    lat, lon = geocode_city(city, cache)
    if lat is None:
        return f"没找到「{city}」的定位，换个城市名试试"

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

    text = WEATHER_CN.get(code, f"天气代码{code}")
    hum = f"，湿度{humidity}%" if humidity != "" else ""
    return f"{city}今天{temp}°{hum}，天气{text}"
