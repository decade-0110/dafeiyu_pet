# -*- coding: utf-8 -*-
"""DeepSeek 对话接口（不依赖 Qt；网络请求由调用方放到后台线程）。"""
import requests

DS_BASE_URL = "https://api.deepseek.com/v1"
DS_MODEL = "deepseek-chat"
DS_SYSTEM = "你是桌面宠物大肥鱼，贱兮兮但可爱，每句话不超过25字，偶尔吐槽主人但别真骂人。"


def build_messages(history, user_msg, max_history=40):
    """拼出请求消息：system + 最近历史 + 本轮用户输入。"""
    messages = [{"role": "system", "content": DS_SYSTEM}]
    messages.extend(history[-max_history:])
    messages.append({"role": "user", "content": user_msg})
    return messages


def chat_reply(key, messages, timeout=10):
    """请求一次对话：成功返回 (True, 回复)；失败返回 (False, 气泡错误文案)。"""
    url = f"{DS_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DS_MODEL,
        "messages": messages,
        "max_tokens": 100,
        "temperature": 0.9,
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            reply = resp.json()["choices"][0]["message"]["content"].strip()
            if len(reply) > 30:
                reply = reply[:28] + "…"
            return True, reply
        error_msg = resp.json().get("error", {}).get("message", str(resp.status_code))
        print(f"[DeepSeek] 状态码: {resp.status_code}, 返回: {resp.text}")
        return False, f"API错误: {error_msg[:12]}"
    except requests.exceptions.Timeout:
        return False, "请求超时，检查网络"
    except requests.exceptions.ConnectionError:
        return False, "连接失败，检查网络"
    except Exception as e:
        return False, f"请求失败: {str(e)[:12]}"
