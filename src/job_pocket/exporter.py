from __future__ import annotations

import csv
import os
import re
import tempfile
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

COLUMNS = {
    "job_id": "职位ID", "title": "岗位名称", "salary": "薪资原文", "location": "城市区域",
    "experience": "经验", "education": "学历", "requirements": "卡片要求原文", "skills": "技能标签",
    "company": "公司名称", "company_info": "公司标签", "benefits": "福利原文",
    "url": "职位链接", "jd_status": "JD状态", "jd_note": "JD备注", "detail_title": "详情页岗位名称",
    "jd": "职位描述JD", "address": "工作地址", "card_text": "卡片原文", "source_url": "推荐来源页",
    "captured_at": "首次采集时间UTC", "updated_at": "更新时间UTC",
}
INVALID_XML = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]")


def safe_cell(value: object) -> str:
    value = INVALID_XML.sub("", str(value or ""))
    # CSV quoting does not prevent spreadsheet formula execution.
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        value = "'" + value
    return value


def export_rows(rows: list[dict], output: Path) -> tuple[Path, Path]:
    output.mkdir(parents=True, exist_ok=True)
    paths = output / "jobs.csv", output / "jobs.xlsx"
    temps = []
    try:
        for suffix in (".csv", ".xlsx"):
            fd, name = tempfile.mkstemp(dir=output, prefix=".jobs-", suffix=suffix)
            os.close(fd)
            temps.append(Path(name))
        with temps[0].open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(COLUMNS.values())
            writer.writerows([[safe_cell(r.get(k, "")) for k in COLUMNS] for r in rows])
        wb = Workbook()
        ws = wb.active
        ws.title = "推荐岗位"
        ws.append(list(COLUMNS.values()))
        for row in rows:
            values = [safe_cell(row.get(k, "")) for k in COLUMNS]
            clipped = [COLUMNS[k] for k, v in zip(COLUMNS, values) if len(v) > 32767]
            if clipped:
                note_index = list(COLUMNS).index("jd_note")
                values[note_index] += "；XLSX单元格截断：" + ", ".join(clipped) + "；完整内容见CSV/SQLite"
            ws.append([v[:32767] for v in values])
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="176B70")
        for index, key in enumerate(COLUMNS, 1):
            ws.column_dimensions[get_column_letter(index)].width = 65 if key in ("jd", "card_text") else 24
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
            ws.row_dimensions[row[0].row].height = 60
        wb.save(temps[1])
        wb.close()
        # Each output is replaced atomically; a locked Excel file can be re-exported later.
        for temp, dest in zip(temps, paths):
            os.replace(temp, dest)
        return paths
    finally:
        for path in temps:
            path.unlink(missing_ok=True)
