from __future__ import annotations

import random
import re
import time
from importlib.resources import files
from urllib.parse import urlsplit

from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeout, sync_playwright

from .config import allowed_url
from .model import card_record, job_identity, now
from .store import Store

DOM_SCRIPT = files("job_pocket").joinpath("dom.js").read_text("utf-8")


class StopCollection(RuntimeError):
    """A normal, conservative stop. Never automatically retried."""


class NetworkGuard:
    def __init__(self):
        self.active = False
        self.reason: str | None = None

    def observe(self, response):
        if not self.active or self.reason:
            return
        p = urlsplit(response.url)
        if (p.hostname != "www.zhipin.com" or
                response.request.resource_type not in {"document", "xhr", "fetch"}):
            return
        status = response.status
        if status in {401, 403, 429} or 500 <= status <= 599:
            # Do not log query strings, cookies, headers or response bodies.
            self.reason = f"平台返回 HTTP {status}，已停止；不自动重试"

    def check(self):
        if self.reason:
            raise StopCollection(self.reason)


def dom(page, cfg: dict, action: str):
    return page.evaluate(DOM_SCRIPT, {
        "action": action, "selectors": cfg["selectors"], "phrases": cfg["risk_phrases"],
    })


def check_page(page, cfg: dict, network: NetworkGuard, *, allow_login: bool = False):
    network.check()
    if page.is_closed():
        raise StopCollection("浏览器标签页已关闭")
    if not allowed_url(page.url):
        raise StopCollection("页面离开允许的 BOSS 直聘域名")
    path = urlsplit(page.url).path
    if re.search(r"captcha|verify|/safe/|/security|/forbidden", path, re.I):
        raise StopCollection("页面进入安全验证或访问限制流程")
    if not allow_login and re.search(r"/login|/sign(in|up)?(?:/|$)", path, re.I):
        raise StopCollection("登录状态失效，请结束后手动重新登录")
    result = dom(page, cfg, "guard")
    if result["risk"]:
        raise StopCollection("检测到验证或访问限制：" + (result["phrase"] or "可见验证组件"))
    if result["login"] and not allow_login:
        raise StopCollection("出现登录界面，已保存进度；请手动重新登录后再运行")
    network.check()


def collect(store: Store, cfg: dict, profile, *, limit: int = 200, with_jd: bool = True,
            max_minutes: int = 120) -> str:
    if not 1 <= limit <= 200:
        raise ValueError("limit 必须在 1–200 之间")
    start = time.monotonic()
    network = NetworkGuard()
    reason = "尚未开始"
    context = None
    visited = 0
    store.set_meta("last_started_at", now())
    try:
        with sync_playwright() as playwright:
            try:
                context = playwright.chromium.launch_persistent_context(
                    str(profile), headless=False, accept_downloads=False,
                    viewport={"width": 1360, "height": 900},
                )
                context.set_default_timeout(cfg["timeout_ms"])
                context.on("response", network.observe)
                feed = context.pages[0] if context.pages else context.new_page()
                initial_response = feed.goto(cfg["start_url"], wait_until="domcontentloaded", timeout=cfg["timeout_ms"])
                if initial_response and (initial_response.status in {403, 429} or initial_response.status >= 500):
                    raise StopCollection(f"入口返回 HTTP {initial_response.status}，已停止；不自动重试")
                feed.wait_for_timeout(cfg["render_wait_seconds"] * 1000)
                check_page(feed, cfg, network, allow_login=True)
                print("\n请在打开的【同一个标签页】手动登录，进入你的首页推荐岗位列表。")
                print("只使用你确认允许自动化整理的内容。请勿切到搜索结果、公司页或热门职位。")
                print("如出现验证码/安全验证，请退出本次运行；工具不会处理它。")
                answer = input("确认推荐列表可见后，在这里输入 START 开始（其他输入退出）：").strip()
                if answer != "START":
                    raise StopCollection("用户取消，未开始采集")
                network.active = True
                check_page(feed, cfg, network)
                feed_url = feed.url
                if "/job_detail/" in urlsplit(feed_url).path:
                    raise StopCollection("当前是职位详情页，请手动进入推荐列表后重试")
                # Read once before visiting any JD. Fail closed if the structure does not match.
                preview = dom(feed, cfg, "cards")
                if not preview:
                    raise StopCollection("没有识别到推荐岗位卡片，请检查 CSS 配置；未请求任何 JD")
                source = urlsplit(feed_url)
                store.set_meta("source_page", source.scheme + "://" + source.netloc + source.path)
                detail = context.new_page() if with_jd else None
                # Runtime budget counts collection only, not manual login time.
                start = time.monotonic()

                def check():
                    network.check()
                    if time.monotonic() - start >= max_minutes * 60:
                        raise StopCollection("达到本次运行时长上限")
                    if feed.url != feed_url:
                        raise StopCollection("推荐页地址发生变化，为保持采集范围已停止")
                    check_page(feed, cfg, network)
                    if detail and not detail.is_closed() and detail.url != "about:blank":
                        check_page(detail, cfg, network)

                def pause(seconds: float | None = None):
                    # No parallel requests, no immediate retry; all waits remain interruptible.
                    seconds = seconds if seconds is not None else random.uniform(cfg["min_delay"], cfg["max_delay"])
                    deadline = time.monotonic() + seconds
                    while time.monotonic() < deadline:
                        feed.wait_for_timeout(min(1000, max(1, (deadline - time.monotonic()) * 1000)))
                        check()
                    check()

                def enrich(record: dict):
                    nonlocal visited
                    check()
                    if not detail:
                        return
                    identity = job_identity(record["url"])
                    if not identity:
                        raise StopCollection("待采集职位链接不在允许范围")
                    pause()
                    check()
                    response = detail.goto(record["url"], wait_until="domcontentloaded", timeout=cfg["timeout_ms"])
                    detail.wait_for_timeout(cfg["render_wait_seconds"] * 1000)
                    check()
                    if response and response.status in {404, 410}:
                        store.update(record["job_id"], jd_status="unavailable", jd_note=f"HTTP {response.status}；不重试")
                    else:
                        current = job_identity(detail.url)
                        if current is None or current[0] != record["job_id"]:
                            raise StopCollection("详情页重定向到其他页面，已停止且保留 pending")
                        data = dom(detail, cfg, "detail")
                        check()
                        status = "ok" if data["jd"] else "no_visible_jd"
                        note = "" if data["jd"] else "未发现可见JD：可能为页面变更、下线或未开放；不自动重试"
                        store.update(record["job_id"], **data, jd_status=status, jd_note=note)
                    visited += 1
                    print(f"进度：{store.count()}/{limit} 条去重岗位，已处理 {visited} 个JD", flush=True)
                    if visited % cfg["rest_every"] == 0:
                        print(f"休息 {cfg['rest_seconds']:g} 秒。Ctrl+C 可保存并退出。", flush=True)
                        pause(cfg["rest_seconds"])

                # Pending cards are committed before navigation; risk/timeout never marks them as done.
                if with_jd:
                    for record in store.pending():
                        enrich(record)
                idle = 0
                for round_number in range(cfg["max_rounds"]):
                    check()
                    if store.count() >= limit:
                        reason = f"已达到累计 {limit} 条去重岗位上限"
                        break
                    raw_cards = dom(feed, cfg, "cards")
                    check()
                    added = []
                    for raw in raw_cards:
                        record = card_record(raw, feed_url)
                        if record and store.add(record, limit):
                            added.append(record)
                    if raw_cards and not any(card_record(r, feed_url) for r in raw_cards):
                        raise StopCollection("卡片缺少有效岗位名称或详情链接，请更新 CSS 配置")
                    print(f"列表第 {round_number + 1} 轮：新增 {len(added)} 条，累计 {store.count()}/{limit}", flush=True)
                    if with_jd:
                        for record in added:
                            enrich(record)
                    if store.count() >= limit:
                        reason = f"已达到累计 {limit} 条去重岗位上限"
                        break
                    idle = 0 if added else idle + 1
                    if idle >= cfg["idle_rounds"]:
                        reason = f"连续 {idle} 轮没有新职位，推荐列表可能已到底或无法继续加载"
                        break
                    pause()
                    check()
                    dom(feed, cfg, "scroll")
                    # Without new JD visits, scrolls still have a periodic long rest.
                    if (round_number + 1) % cfg["rest_every"] == 0:
                        pause(cfg["rest_seconds"])
                    else:
                        pause()
                else:
                    reason = "达到列表滚动轮数上限"
            finally:
                if context:
                    context.close()
    except StopCollection as exc:
        reason = str(exc)
    except (KeyboardInterrupt, EOFError):
        reason = "用户中断，已保存已提交的岗位；pending 可在下次继续"
    except PlaywrightTimeout:
        reason = "页面加载或读取超时；已停止且不自动重试，pending 留待下次"
    except PlaywrightError as exc:
        # Selector diagnostics only; avoid logging URLs with authentication parameters.
        message = str(exc)
        reason = next((s for s in ("FEED_AMBIGUOUS", "FEED_MISSING") if s in message), "浏览器或页面操作失败")
        reason += "；已保存进度。检查浏览器安装、页面及 CSS 配置"
    finally:
        store.set_meta("last_stop_reason", reason)
        store.set_meta("last_stopped_at", now())
    return reason
