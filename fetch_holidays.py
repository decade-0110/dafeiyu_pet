# -*- coding: utf-8 -*-
"""抓取中国法定节假日，生成桌宠用的节假日快照（用于峰谷定价判定）。

用法：
    python fetch_holidays.py --year 2026              # 写入 assets/holidays/2026.json
    python fetch_holidays.py --year 2027 --out holidays.json   # 写到指定文件

数据来源：https://timor.tech/api/holiday/year/<年>/ （免注册 JSON 接口）
只收录 holiday=true 的法定节假日自然日；调休补班日（holiday=false）不算节假日，
因为官方峰谷规则里「周末 + 法定节假日」都是空闲时段，补班日落在周末仍算空闲。
"""
import argparse
import json
import os
import sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://timor.tech/api/holiday/year/{year}/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def fetch_year(year):
    r = requests.get(API.format(year=year),
                     headers={"User-Agent": UA, "Referer": "https://timor.tech/api/holiday/"},
                     timeout=20)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"接口返回异常：{data.get('code')} {data.get('msg', '')}")
    days = []
    for _, item in sorted(data.get("holiday", {}).items()):
        if item.get("holiday") is True:            # 只收法定节假日；补班日 holiday=false
            days.append({"date": item["date"], "name": item.get("name", "节假日")})
    return days


def main(argv=None):
    ap = argparse.ArgumentParser(description="抓取中国法定节假日快照")
    ap.add_argument("--year", type=int, required=True, help="年份，如 2026")
    ap.add_argument("--out", default="", help="输出文件；默认 assets/holidays/<年>.json")
    a = ap.parse_args(argv)

    out = a.out or os.path.join(HERE, "assets", "holidays", f"{a.year}.json")
    if not os.path.isabs(out):
        out = os.path.join(HERE, out)
    try:
        days = fetch_year(a.year)
    except Exception as e:
        print(f"抓取失败：{e!r}")
        return 1
    if not days:
        print(f"{a.year} 年没有取到节假日数据（可能官方还没公布，接口空表）")
        return 1

    payload = {
        "year": a.year,
        "source": API.format(year=a.year),
        "note": "仅收录 holiday=true 的法定节假日自然日；调休补班日(holiday=false)不算节假日",
        "holidays": days,
    }
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"{a.year} 年节假日 {len(days)} 天 -> {out}")
    for d in days[:5]:
        print("  ", d["date"], d["name"])
    if len(days) > 5:
        print("   ...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
