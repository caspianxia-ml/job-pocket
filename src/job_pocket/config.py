from __future__ import annotations

import json
import math
from importlib.resources import files
from pathlib import Path
from urllib.parse import urlsplit


def allowed_url(url: str) -> bool:
    try:
        p = urlsplit(url)
        return (p.scheme == "https" and p.hostname == "www.zhipin.com"
                and p.port in (None, 443) and not p.username and not p.password)
    except ValueError:
        return False


def defaults() -> dict:
    return json.loads(files("job_pocket").joinpath("defaults.json").read_text("utf-8"))


def load_config(path: Path | None = None) -> dict:
    cfg = defaults()
    if path:
        override = json.loads(path.read_text("utf-8"))
        if not isinstance(override, dict):
            raise ValueError("配置顶层必须是JSON对象")
        unknown = set(override) - set(cfg)
        if unknown:
            raise ValueError(f"未知配置项：{', '.join(sorted(unknown))}")
        for key, value in override.items():
            if key == "selectors":
                if not isinstance(value, dict) or set(value) - set(cfg[key]):
                    raise ValueError("selectors 包含未知字段或不是对象")
                cfg[key].update(value)
            else:
                cfg[key] = value
    if not isinstance(cfg["start_url"], str) or not allowed_url(cfg["start_url"]):
        raise ValueError("start_url 必须是 https://www.zhipin.com 下的地址")
    for key in ("min_delay", "max_delay", "rest_seconds", "render_wait_seconds"):
        v = cfg[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ValueError(f"{key} 必须为有限数字")
    if not 5 <= cfg["min_delay"] <= cfg["max_delay"] <= 300:
        raise ValueError("延时要求 5 ≤ min_delay ≤ max_delay ≤ 300 秒")
    if not 30 <= cfg["rest_seconds"] <= 3600 or not 1 <= cfg["render_wait_seconds"] <= 30:
        raise ValueError("休息需 30–3600 秒；渲染等待需 1–30 秒")
    for key, lower, upper in (("rest_every", 1, 20), ("max_rounds", 1, 100),
                              ("idle_rounds", 1, 5), ("timeout_ms", 1000, 60000)):
        v = cfg[key]
        if type(v) is not int or not lower <= v <= upper:
            raise ValueError(f"{key} 必须为 {lower}–{upper} 的整数")
    for key, selectors in cfg["selectors"].items():
        if not isinstance(selectors, list) or not selectors or not all(isinstance(s, str) and s.strip() for s in selectors):
            raise ValueError(f"selectors.{key} 必须为非空 CSS 字符串数组")
    if not isinstance(cfg["risk_phrases"], list) or not cfg["risk_phrases"] or not all(
        isinstance(s, str) and s.strip() for s in cfg["risk_phrases"]
    ):
        raise ValueError("risk_phrases 必须为非空字符串数组")
    return cfg
