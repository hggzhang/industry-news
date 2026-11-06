#!/usr/bin/env python3
"""AI 周报档案编排脚本（配合子代理逐周采集使用）。

用法:
  python3 fetch_news.py weeks            # 列出所有待采集的周（周一日期），一行一个
  python3 fetch_news.py status           # 显示已完成/未完成/异常 统计
  python3 fetch_news.py validate         # 完整性校验（缺周、空文件、省略号、过短）
  python3 fetch_news.py merge            # 按时间顺序合并为 weekly_archive.md

每周报告由采集代理写入 /workspace/weekly_reports/<YYYY-MM-DD>.md
（文件名为该自然周周一的日期，时区 Asia/Shanghai，周一至周日）。
脚本幂等：已存在且校验通过的周会被跳过（断点续传）。
"""
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

TZ_NOTE = "Asia/Shanghai (UTC+8)"
START = date(2024, 12, 30)   # 包含 2025-01-01 的自然周的周一
REPORTS_DIR = Path("/workspace/weekly_reports")
ARCHIVE = Path("/workspace/weekly_archive.md")
MIN_CHARS = 800              # 每周报告最低字符数，低于视为不完整
BAD_MARKERS = ["...", "…", "TODO", "占位符", "待补充", "（略）"]

def last_complete_sunday(today: date) -> date:
    # 本周周一
    this_monday = today - timedelta(days=today.weekday())
    return this_monday - timedelta(days=1)

def all_weeks() -> list[tuple[date, date]]:
    end_sun = last_complete_sunday(date.today())
    weeks = []
    mon = START
    while mon + timedelta(days=6) <= end_sun:
        weeks.append((mon, mon + timedelta(days=6)))
        mon += timedelta(days=7)
    return weeks

def report_path(mon: date) -> Path:
    return REPORTS_DIR / f"{mon.isoformat()}.md"

def check_week(mon: date, sun: date) -> tuple[bool, str]:
    p = report_path(mon)
    if not p.exists():
        return False, "missing"
    text = p.read_text(encoding="utf-8", errors="replace")
    if len(text.strip()) < MIN_CHARS:
        return False, f"too_short({len(text.strip())})"
    for m in BAD_MARKERS:
        if m in text:
            return False, f"bad_marker({m})"
    if mon.strftime("%Y-%m-%d") not in text and f"{mon.month}月" not in text:
        return False, "date_mismatch"
    return True, "ok"

def cmd_weeks():
    REPORTS_DIR.mkdir(exist_ok=True)
    pending = []
    for mon, sun in all_weeks():
        ok, _ = check_week(mon, sun)
        if not ok:
            pending.append(mon.isoformat())
    for m in pending:
        print(m)
    print(f"# pending={len(pending)}", file=sys.stderr)

def cmd_status():
    weeks = all_weeks()
    done, bad = [], []
    for mon, sun in weeks:
        ok, why = check_week(mon, sun)
        (done if ok else bad).append((mon.isoformat(), why))
    print(f"total_weeks={len(weeks)} done={len(done)} pending={len(bad)}")
    for mon, why in bad:
        print(f"  PENDING {mon}  ({why})")

def cmd_validate():
    weeks = all_weeks()
    problems = []
    for mon, sun in weeks:
        ok, why = check_week(mon, sun)
        if not ok:
            problems.append(f"{mon} ~ {sun}: {why}")
    if problems:
        print(f"FAIL: {len(problems)} week(s) incomplete:")
        for p in problems:
            print("  " + p)
        sys.exit(1)
    print(f"PASS: all {len(weeks)} weeks complete, no ellipsis/placeholders.")

def cmd_merge():
    weeks = all_weeks()
    missing = [mon.isoformat() for mon, _ in weeks if not check_week(mon, _)[0]]
    if missing:
        print(f"REFUSING to merge: {len(missing)} incomplete weeks: {missing}")
        sys.exit(1)
    parts = [
        "# AI 周报档案｜2024-12-30 至 2026-11-01\n",
        f"**统计周期：** 每自然周周一 00:00 至周日 23:59:59（时区 {TZ_NOTE}）\n",
        f"**周数：** {len(weeks)}\n\n---\n",
    ]
    for mon, sun in weeks:
        text = report_path(mon).read_text(encoding="utf-8").strip()
        parts.append(text + "\n\n---\n")
    ARCHIVE.write_text("\n".join(parts), encoding="utf-8")
    print(f"Merged {len(weeks)} weeks -> {ARCHIVE} ({ARCHIVE.stat().st_size} bytes)")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"weeks": cmd_weeks, "status": cmd_status,
     "validate": cmd_validate, "merge": cmd_merge}[cmd]()
