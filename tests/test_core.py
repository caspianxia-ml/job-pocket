import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook

from job_pocket.cli import main, project_lock
from job_pocket.collector import NetworkGuard, StopCollection
from job_pocket.config import allowed_url, load_config
from job_pocket.exporter import COLUMNS, export_rows
from job_pocket.model import card_record, job_identity
from job_pocket.store import Store


def record(i=1):
    return card_record({"href": f"/job_detail/test_{i}.html?ka=tracking", "title": "Python开发",
                        "company": "示例公司", "salary": "15-25K·13薪",
                        "requirements": ["1-3年", "本科"]}, "https://www.zhipin.com/web/geek/job-recommend")


@pytest.mark.parametrize("url", ["https://evil.example/job_detail/a.html", "javascript:alert(1)",
                                  "https://www.zhipin.com.evil.example/", "https://user@www.zhipin.com/",
                                  "https://www.zhipin.com:444/", "http://www.zhipin.com/",
                                  "https://www.zhipin.com:bad/", "https://www.zhipin.com/company/a.html"])
def test_identity_rejects_unsafe_or_non_job(url):
    assert job_identity(url) is None


def test_identity_discards_tracking_but_preserves_unique_id():
    assert job_identity("/job_detail/Ab_-09.html?ka=one#two") == (
        "Ab_-09", "https://www.zhipin.com/job_detail/Ab_-09.html")
    assert allowed_url("https://www.zhipin.com/")


def test_store_reopen_dedup_cap_and_pending(tmp_path):
    path = tmp_path / "jobs.sqlite3"
    store = Store(path)
    assert store.add(record(), 200)
    assert not store.add(record(), 200)
    store.update("test_1", jd_status="ok", jd="完整JD")
    for i in range(2, 251):
        store.add(record(i), 999)
    assert store.count() == 200
    store.close()
    store = Store(path)
    assert len(store.pending()) == 199
    assert store.rows()[0]["jd"] == "完整JD"
    assert store.rows()[0]["education"] == "本科"
    assert store.rows()[0]["experience"] == "1-3年"
    store.close()


def test_export_unicode_formula_and_long_jd(tmp_path):
    data = record()
    data.update(title="  =HYPERLINK(\"https://invalid.example\")", company="@SUM(1)", jd="中文职位描述\n" + "测" * 34000)
    a, b = export_rows([data], tmp_path)
    assert a.read_bytes().startswith(b"\xef\xbb\xbf")
    with a.open(encoding="utf-8-sig", newline="") as handle:
        row = list(csv.DictReader(handle))[0]
    assert row["岗位名称"].startswith("'")
    assert row["职位描述JD"] == data["jd"]
    wb = load_workbook(b)
    ws = wb.active
    assert ws.freeze_panes == "A2"
    assert ws["B2"].data_type == "s"
    jd_index = list(COLUMNS).index("jd") + 1
    note_index = list(COLUMNS).index("jd_note") + 1
    assert len(ws.cell(2, jd_index).value) == 32767
    assert "截断" in ws.cell(2, note_index).value
    wb.close()


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
def test_network_latches_restriction(status):
    guard = NetworkGuard()
    guard.active = True
    guard.observe(SimpleNamespace(url="https://www.zhipin.com/wapi/zpgeek/job/list", status=status,
                                  request=SimpleNamespace(resource_type="fetch")))
    guard.observe(SimpleNamespace(url="https://www.zhipin.com/", status=200,
                                  request=SimpleNamespace(resource_type="document")))
    with pytest.raises(StopCollection, match=f"HTTP {status}"):
        guard.check()


@pytest.mark.parametrize("patch", [{"min_delay": 0}, {"max_delay": float("nan")}, {"rest_every": 21},
                                  {"start_url": "https://evil.example/"}, {"selectors": {"unknown": ["a"]}},
                                  {"selectors": {"cards": []}}, {"risk_phrases": []}, {"max_rounds": 500}])
def test_config_cannot_disable_limits(tmp_path, patch):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(patch), encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(cfg)


def test_default_config_and_partial_override(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"selectors": {"feed_roots": ["#my-feed"]}}', encoding="utf-8")
    config = load_config(cfg)
    assert config["selectors"]["feed_roots"] == ["#my-feed"]
    assert config["selectors"]["jd"]
    assert config["min_delay"] >= 5


def test_lock_blocks_second_writer_and_releases(tmp_path):
    with project_lock(tmp_path):
        with pytest.raises(ValueError, match="运行锁"):
            with project_lock(tmp_path):
                pass
    assert not (tmp_path / ".private/run.lock").exists()


def test_cli_local_export_and_limit_validation(tmp_path):
    store = Store(tmp_path / "data/jobs.sqlite3")
    store.add(record(), 200)
    store.close()
    assert main(["--workspace", str(tmp_path), "export"]) == 0
    assert main(["--workspace", str(tmp_path), "status"]) == 0
    with pytest.raises(SystemExit):
        main(["collect", "--limit", "201"])
