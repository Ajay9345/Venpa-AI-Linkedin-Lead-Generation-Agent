from __future__ import annotations

import io
import json

import pandas as pd


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Leads")
        ws = writer.sheets["Leads"]
        for idx, col in enumerate(df.columns, start=1):
            max_len = max(df[col].astype(str).map(len).max() if not df.empty else 0, len(str(col)))
            ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = min(max_len + 4, 60)
        for cell in ws[1]:
            cell.font = cell.font.copy(bold=True)
    return buf.getvalue()


def to_json_bytes(df: pd.DataFrame) -> bytes:
    return json.dumps(df.to_dict(orient="records"), indent=2, ensure_ascii=False).encode("utf-8")
