# -*- coding: utf-8 -*-
"""bubble.py：台词不连续重复、冷却门、say 去重规则。"""
import random

import bubble


# ---------------------------------------------------------------- 冷却门

def test_cooldown_blocks_until_interval():
    gate = bubble.Cooldown(10)

    assert gate.ready(100) is True
    assert gate.consume(100) is True
    assert gate.ready(109.9) is False
    assert gate.consume(105) is False
    assert gate.remaining(105) == 5
    assert gate.ready(110) is True
    assert gate.consume(110) is True


def test_cooldown_zero_always_allows():
    gate = bubble.Cooldown(0)
    assert gate.consume(1) is True
    assert gate.consume(1) is True


def test_cooldown_never_negative():
    gate = bubble.Cooldown(-5)
    assert gate.seconds == 0
    assert gate.consume(1) is True


def test_cooldown_reset():
    gate = bubble.Cooldown(10)
    assert gate.consume(0) is True
    assert gate.ready(5) is False

    gate.reset()

    assert gate.ready(5) is True
    assert gate.remaining(5) == 0


def test_cooldown_uses_injected_clock():
    now = [0.0]
    gate = bubble.Cooldown(5, clock=lambda: now[0])

    assert gate.consume() is True
    assert gate.consume() is False
    now[0] = 5.0
    assert gate.consume() is True


# ---------------------------------------------------------------- 台词选择

def test_line_picker_never_repeats_consecutively():
    picker = bubble.LinePicker(["a", "b", "c"], rng=random.Random(7))

    picked = [picker.pick() for _ in range(200)]

    assert set(picked) <= {"a", "b", "c"}
    assert all(x != y for x, y in zip(picked, picked[1:]))


def test_line_picker_is_deterministic_with_seeded_rng():
    p1 = bubble.LinePicker(["a", "b", "c", "d"], rng=random.Random(42))
    p2 = bubble.LinePicker(["a", "b", "c", "d"], rng=random.Random(42))

    assert [p1.pick() for _ in range(20)] == [p2.pick() for _ in range(20)]


def test_line_picker_empty_returns_none():
    picker = bubble.LinePicker([])
    assert picker.pick() is None
    assert picker.last is None


def test_line_picker_single_line_repeats():
    picker = bubble.LinePicker(["只有这一句"])
    assert [picker.pick() for _ in range(3)] == ["只有这一句"] * 3


def test_line_picker_all_duplicates_still_returns_line():
    picker = bubble.LinePicker(["x", "x"], rng=random.Random(0))
    assert [picker.pick() for _ in range(3)] == ["x", "x", "x"]


def test_line_picker_cooldown_integrated():
    picker = bubble.LinePicker(["a", "b"], cooldown=10, rng=random.Random(1))

    first = picker.pick(0)
    assert first in {"a", "b"}
    assert picker.pick(9.9) is None
    assert picker.last == first

    second = picker.pick(10)
    assert second in {"a", "b"}
    assert second != first


def test_line_picker_can_share_gate():
    gate = bubble.Cooldown(10)
    p1 = bubble.LinePicker(["a", "b"], gate=gate, rng=random.Random(0))
    p2 = bubble.LinePicker(["c", "d"], gate=gate, rng=random.Random(1))

    assert p1.pick(0) in {"a", "b"}
    assert p2.pick(5) is None          # 共享冷却：p1 刚说过
    assert p2.pick(10) in {"c", "d"}


def test_empty_picker_does_not_consume_gate():
    gate = bubble.Cooldown(10)
    picker = bubble.LinePicker([], gate=gate)

    assert picker.pick(0) is None
    assert gate.ready(0) is True


def test_line_picker_reset_forgets_last():
    picker = bubble.LinePicker(["a", "b"], rng=random.Random(3))
    assert picker.pick() in {"a", "b"}
    assert picker.last is not None

    picker.reset()

    assert picker.last is None
    assert picker.pick() in {"a", "b"}


def test_line_picker_accepts_tuple():
    picker = bubble.LinePicker(("a", "b"), rng=random.Random(0))
    assert picker.pick() in {"a", "b"}


# ---------------------------------------------------------------- say 去重

def test_is_duplicate():
    assert bubble.is_duplicate("你好", "你好") is True
    assert bubble.is_duplicate("你好", "再见") is False
    assert bubble.is_duplicate("你好", "") is False
    assert bubble.is_duplicate("", "") is True          # 与原 say() 行为一致
    assert bubble.is_duplicate("天气晴", "天气晴") is False  # 天气允许连续更新
    assert bubble.is_duplicate("天气雨", "天气晴") is False
