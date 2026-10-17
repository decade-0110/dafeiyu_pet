# -*- coding: utf-8 -*-
"""模块依赖约束：纯逻辑模块不拉 Qt，网络模块不拉 Qt。"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run_import(code):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["QT_QPA_PLATFORM"] = "offscreen"
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=60,
    )


def test_pure_logic_modules_import_without_qt_or_network():
    code = "\n".join([
        "import sys",
        "import holiday, config",
        "bad = [m for m in sys.modules if m == 'PySide6' or m.startswith('PySide6.')]",
        "assert not bad, bad",
        "assert 'requests' not in sys.modules",
        "print('ok')",
    ])

    result = _run_import(code)

    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_network_modules_import_without_qt():
    code = "\n".join([
        "import sys",
        "import balance, ai_chat, weather",
        "bad = [m for m in sys.modules if m == 'PySide6' or m.startswith('PySide6.')]",
        "assert not bad, bad",
        "assert 'requests' in sys.modules",
        "print('ok')",
    ])

    result = _run_import(code)

    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout
