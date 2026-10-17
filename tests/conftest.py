# -*- coding: utf-8 -*-
"""pytest 共享配置：把项目根目录加入 sys.path，并隔离节假日缓存。"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import holiday  # noqa: E402  （必须在 sys.path 调整之后）


@pytest.fixture(autouse=True)
def _clear_holiday_cache():
    """每个用例前后都清缓存，避免 tmp_path 里的表串味。"""
    holiday.clear_holiday_cache()
    yield
    holiday.clear_holiday_cache()
