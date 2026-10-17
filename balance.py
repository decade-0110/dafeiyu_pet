# -*- coding: utf-8 -*-
"""DeepSeek 余额接口与展示文本（不依赖 Qt）。"""
import requests

BALANCE_URL = "https://api.deepseek.com/user/balance"
BALANCE_ERRORS = {
    "nokey": "先设置 Key 才能查余额",
    "auth": "Key 好像失效了，重新设一个",
    "insufficient": "余额不够了，该充值啦",
    "rate": "问得太勤了，歇一会儿再查",
    "server": "官方服务好像不太稳，等会儿再试",
    "timeout": "查余额超时了，网络不太行",
    "network": "连不上官方接口，检查下网络",
    "parse": "返回的东西看不懂，稍后再试",
}


def parse_balance(payload):
    """解析 /user/balance 响应为便于展示的结构；字段缺失/非数字都不会抛。"""
    infos = []
    for item in (payload or {}).get("balance_infos", []) or []:
        def _num(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                return None
        infos.append({
            "currency": item.get("currency", "?"),
            "total": _num(item.get("total_balance")),
            "granted": _num(item.get("granted_balance")),
            "topped": _num(item.get("topped_up_balance")),
        })
    return {"is_available": bool((payload or {}).get("is_available", False)), "infos": infos}


def money_text(value, currency="CNY"):
    """金额格式化：￥12.34 / $3.20；拿不到数字时返回「—」。"""
    if value is None:
        return "—"
    sign = {"CNY": "￥", "USD": "$"}.get(currency, f"{currency} ")
    return f"{sign}{value:,.2f}"


def balance_summary_text(parsed):
    """气泡播报用的一句话。"""
    if not parsed["infos"]:
        return "没查到余额信息"
    infos = parsed["infos"]
    main = next((i for i in infos if i["currency"] == "CNY"), infos[0])
    txt = f"余额 {money_text(main['total'], main['currency'])}"
    return txt + ("，还能撑" if parsed["is_available"] else "，快没啦")


def balance_panel_rows(parsed):
    """面板用：(标签, 值) 列表，多币种时每个币种一组。"""
    rows = [("可用状态", "充足" if parsed["is_available"] else "不足")]
    for info in parsed["infos"]:
        cur = info["currency"]
        prefix = "" if len(parsed["infos"]) == 1 else f"[{cur}] "
        rows.append((f"{prefix}总额", money_text(info["total"], cur)))
        rows.append((f"{prefix}充值余额", money_text(info["topped"], cur)))
        if info["granted"]:
            rows.append((f"{prefix}赠送余额", money_text(info["granted"], cur)))
    return rows


def fetch_balance(key, timeout=10):
    """请求余额接口。返回 (ok, parsed 或 错误码字符串)。"""
    if not key:
        return False, "nokey"
    try:
        r = requests.get(BALANCE_URL, headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": "dafeiyu-pet/1.0",
        }, timeout=timeout)
    except requests.exceptions.Timeout:
        return False, "timeout"
    except Exception as e:
        print("[余额] 请求失败:", repr(e))
        return False, "network"
    if r.status_code == 200:
        try:
            return True, parse_balance(r.json())
        except Exception as e:
            print("[余额] 解析失败:", repr(e))
            return False, "parse"
    if r.status_code == 401:
        return False, "auth"
    if r.status_code == 402:
        return False, "insufficient"
    if r.status_code == 429:
        return False, "rate"
    if 500 <= r.status_code < 600:
        return False, "server"
    print(f"[余额] 未预期状态码 {r.status_code}: {r.text[:200]}")
    return False, "server"
