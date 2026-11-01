"""All network is intercepted. Never logs in to or calls BOSS in tests."""
from contextlib import contextmanager
from pathlib import Path
import os

import pytest
from playwright.sync_api import sync_playwright

import job_pocket.collector as collector
from job_pocket.config import defaults
from job_pocket.store import Store

pytestmark = pytest.mark.browser
FIXTURE = Path(__file__).parent / "fixtures/feed.html"


@pytest.fixture
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel=os.getenv("JOB_POCKET_TEST_CHANNEL") or None)
        page = browser.new_page()
        page.set_content(FIXTURE.read_text("utf-8"))
        yield page
        browser.close()


def test_visible_dom_and_scoped_cards(page):
    rows = collector.dom(page, defaults(), "cards")
    assert len(rows) == 3
    assert rows[0]["title"] == "Python开发工程师"
    assert rows[0]["requirements"] == ["1-3年", "本科"]
    assert rows[0]["skills"] == ["Python", "SQL"]
    assert not collector.dom(page, defaults(), "guard")["risk"]
    page.locator("[data-testid='risk-dialog']").evaluate("e => e.classList.remove('hidden')")
    assert collector.dom(page, defaults(), "guard")["risk"]


def test_ambiguous_feed_fails_closed(page):
    page.evaluate("document.body.append(document.querySelector('.job-list-box').cloneNode(true))")
    with pytest.raises(Exception, match="FEED_AMBIGUOUS"):
        collector.dom(page, defaults(), "cards")


def test_visible_jd_ignores_hidden_text(page):
    page.set_content('<div class="job-sec-text" style="display:none">秘密</div><div class="job-sec-text">公开JD</div>')
    assert collector.dom(page, defaults(), "detail")["jd"] == "公开JD"


def install_offline_browser(monkeypatch, blocked=False, risk_html=False):
    visited = []
    real_sync = sync_playwright

    @contextmanager
    def fake_sync():
        with real_sync() as p:
            class Chromium:
                def launch_persistent_context(self, user_data_dir, **kwargs):
                    kwargs["headless"] = True
                    kwargs["channel"] = os.getenv("JOB_POCKET_TEST_CHANNEL") or None
                    context = p.chromium.launch_persistent_context(user_data_dir, **kwargs)

                    def route_handler(route):
                        url = route.request.url
                        visited.append(url)
                        if "/job_detail/" in url:
                            if blocked:
                                route.fulfill(status=429, content_type="text/html", body="请求过于频繁")
                            elif risk_html:
                                route.fulfill(status=200, content_type="text/html", body='<div data-testid="risk-dialog">安全验证</div>')
                            else:
                                route.fulfill(status=200, content_type="text/html", body='<h1>示例岗位</h1><div class="job-sec-text">这是可见JD\n要求Python</div><div class="location-address">示例地址</div>')
                        else:
                            route.fulfill(status=200, content_type="text/html", body=FIXTURE.read_text("utf-8"))
                    context.route("**/*", route_handler)
                    return context
            yield type("PW", (), {"chromium": Chromium()})()
    monkeypatch.setattr(collector, "sync_playwright", fake_sync)
    monkeypatch.setattr("builtins.input", lambda _: "START")
    return visited


def quick_config():
    cfg = defaults()
    # Test-only accelerated timing, inaccessible through validated user configuration.
    cfg.update(min_delay=0.001, max_delay=0.001, render_wait_seconds=0.001)
    return cfg


def test_end_to_end_cap_dedup_and_details(monkeypatch, tmp_path):
    visited = install_offline_browser(monkeypatch)
    store = Store(tmp_path / "data.sqlite3")
    reason = collector.collect(store, quick_config(), tmp_path / "profile", limit=2)
    assert "累计 2" in reason
    assert store.count() == 2
    assert len(store.pending()) == 0
    assert all(r["jd_status"] == "ok" and r["jd"] for r in store.rows())
    assert sum("/job_detail/" in url for url in visited) == 2
    store.close()


@pytest.mark.parametrize("risk_html", [False, True])
def test_stop_before_second_detail_then_resume(monkeypatch, tmp_path, risk_html):
    visited = install_offline_browser(monkeypatch, blocked=not risk_html, risk_html=risk_html)
    path = tmp_path / "data.sqlite3"
    store = Store(path)
    reason = collector.collect(store, quick_config(), tmp_path / "profile", limit=2)
    assert "验证" in reason if risk_html else "HTTP 429" in reason
    assert store.count() == 2
    assert len(store.pending()) == 2
    assert sum("/job_detail/" in url for url in visited) == 1
    store.close()
    # New process semantics: reopen checkpoint, explicitly rerun after restriction is resolved.
    visited = install_offline_browser(monkeypatch)
    store = Store(path)
    collector.collect(store, quick_config(), tmp_path / "profile", limit=2)
    assert store.count() == 2
    assert not store.pending()
    assert sum("/job_detail/" in url for url in visited) == 2
    store.close()


def test_cards_only_then_complete_jd(monkeypatch, tmp_path):
    visited = install_offline_browser(monkeypatch)
    store = Store(tmp_path / "data.sqlite3")
    collector.collect(store, quick_config(), tmp_path / "profile", limit=2, with_jd=False)
    assert len(store.pending()) == 2
    assert not any("/job_detail/" in u for u in visited)
    collector.collect(store, quick_config(), tmp_path / "profile", limit=2)
    assert not store.pending()
    store.close()


def test_ctrl_c_during_jd_keeps_pending(monkeypatch, tmp_path):
    visited = install_offline_browser(monkeypatch)
    original_dom = collector.dom

    def interrupted(page, cfg, action):
        if action == "detail":
            raise KeyboardInterrupt
        return original_dom(page, cfg, action)

    monkeypatch.setattr(collector, "dom", interrupted)
    store = Store(tmp_path / "data.sqlite3")
    reason = collector.collect(store, quick_config(), tmp_path / "profile", limit=2)
    assert "用户中断" in reason
    assert store.count() == 2
    assert len(store.pending()) == 2
    assert sum("/job_detail/" in url for url in visited) == 1
    store.close()


def test_empty_growth_stops_without_leaving_recommendations(monkeypatch, tmp_path):
    visited = install_offline_browser(monkeypatch)
    store = Store(tmp_path / "data.sqlite3")
    reason = collector.collect(store, quick_config(), tmp_path / "profile", limit=5, with_jd=False)
    assert "连续 3 轮" in reason
    assert store.count() == 2
    assert not any("/job_detail/" in url for url in visited)
    store.close()


def test_login_overlay_after_confirmation_stops(monkeypatch, tmp_path):
    visited = install_offline_browser(monkeypatch)
    original_dom = collector.dom

    def login_now(page, cfg, action):
        result = original_dom(page, cfg, action)
        if action == "guard":
            result["login"] = True
        return result

    monkeypatch.setattr(collector, "dom", login_now)
    store = Store(tmp_path / "data.sqlite3")
    reason = collector.collect(store, quick_config(), tmp_path / "profile", limit=2)
    assert "登录界面" in reason
    assert store.count() == 0
    assert not any("/job_detail/" in url for url in visited)
    store.close()
