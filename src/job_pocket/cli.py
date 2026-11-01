from __future__ import annotations

import argparse
import json
import os
import sqlite3
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

from .config import load_config
from .exporter import export_rows
from .store import Store


@contextmanager
def project_lock(root: Path):
    """One collector/exporter per workspace; no concurrent profile or DB writers."""
    lock = root / ".private" / "run.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError("已有运行锁 .private/run.lock。确认没有其他采集/导出进程后才能删除旧锁。") from None
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(str(os.getpid()))
        yield
    finally:
        lock.unlink(missing_ok=True)


def limited_number(lower: int, upper: int):
    def parse(text: str):
        value = int(text)
        if not lower <= value <= upper:
            raise argparse.ArgumentTypeError(f"请输入 {lower}–{upper}")
        return value
    return parse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="JobPocket · 个人求职信息整理助手（BOSS直聘可见推荐页）")
    parser.add_argument("--workspace", type=Path, default=Path.cwd(), help="本地数据目录的根路径；默认为当前目录")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("collect", help="手动登录后开始/继续采集")
    run.add_argument("--limit", type=limited_number(1, 200), default=200, help="同一数据库累计去重上限，最多200")
    run.add_argument("--cards-only", action="store_true", help="只收卡片，JD保持pending，下次可补采")
    run.add_argument("--config", type=Path, help="本地JSON配置（未指定时使用内置默认值）")
    run.add_argument("--max-minutes", type=limited_number(1, 240), default=120, help="开始采集后的运行时长上限")
    sub.add_parser("export", help="从本地断点重新导出CSV/XLSX，不访问网站")
    sub.add_parser("status", help="查看本地断点和上次停止原因，不访问网站")
    args = parser.parse_args(argv)
    root = args.workspace.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = root / "data" / "jobs.sqlite3"
    store = None
    try:
        if args.command != "collect" and not path.exists():
            raise ValueError("尚无断点数据。请先运行 collect。")
        with project_lock(root):
            cfg = load_config(args.config) if args.command == "collect" else None
            store = Store(path)
            if args.command == "status":
                print(json.dumps({"total": store.count(), "jd_status": dict(Counter(r["jd_status"] for r in store.rows())),
                                  "last_stop_reason": store.get_meta("last_stop_reason"),
                                  "last_stopped_at": store.get_meta("last_stopped_at")}, ensure_ascii=False, indent=2))
            else:
                if args.command == "collect":
                    if store.count() > args.limit:
                        raise ValueError(f"断点已有 {store.count()} 条，limit 不得小于现有数量；新批次请换 --workspace")
                    from .collector import collect
                    print(collect(store, cfg, root / ".private" / "browser-profile", limit=args.limit,
                                  with_jd=not args.cards_only, max_minutes=args.max_minutes))
                csv_path, xlsx_path = export_rows(store.rows(), root / "exports")
                print(f"已导出 {store.count()} 条岗位：\n{csv_path}\n{xlsx_path}")
        return 0
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"无法完成：{exc}")
        print("已写入SQLite的进度仍在。可修复问题后用 export 重新导出。")
        return 1
    except KeyboardInterrupt:
        print("已中断。已写入SQLite的进度仍在；下次运行可继续或使用 export 导出。")
        return 130
    finally:
        if store:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
