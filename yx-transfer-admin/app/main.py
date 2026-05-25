from __future__ import annotations

import csv
import io
import re
import zipfile
from typing import Any, Literal
from xml.etree import ElementTree as ET

import httpx
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import settings

app = FastAPI(title="YX Transfer Admin", version="0.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


def _backend_url(path: str) -> str:
    return f"{settings.transfer_api_base.rstrip('/')}/{path.lstrip('/')}"


async def backend_request(method: str, path: str, **kwargs: Any) -> Any:
    timeout = httpx.Timeout(settings.request_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.request(method, _backend_url(path), **kwargs)
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"后端服务不可达: {exc}") from exc
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    content_type = resp.headers.get("content-type", "")
    if "application/json" in content_type:
        return resp.json()
    return resp.text


class CustomerIn(BaseModel):
    account: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    balance: float = 0
    unitPrice: float = 0
    payType: int = 0
    maxCallsPerHour: int = 0
    status: int = 1


class CustomerUpdateIn(BaseModel):
    account: str | None = None
    name: str | None = None
    balance: float | None = None
    unitPrice: float | None = None
    payType: int | None = None
    maxCallsPerHour: int | None = None
    status: int | None = None


class NumberRecordIn(BaseModel):
    customerAcc: str
    number: str
    matchType: Literal[1, 2] = 1
    listType: Literal[1, 2] = 1
    status: int = 1


class CallerAuthIn(BaseModel):
    customerAcc: str
    callerNumber: str
    status: int = 1


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    with open("app/static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "backend": settings.transfer_api_base}


# 客户管理：对应 /transfer/customer
@app.get("/api/customers")
async def customer_page(
    page: int = 1,
    pageSize: int = 10,
    account: str | None = None,
    status: int | None = None,
) -> Any:
    params = {"page": page, "pageSize": pageSize}
    if account:
        params["account"] = account
    if status is not None:
        params["status"] = status
    return await backend_request("GET", "/transfer/customer/page", params=params)


@app.post("/api/customers")
async def customer_add(data: CustomerIn) -> Any:
    return await backend_request("POST", "/transfer/customer/add", json=data.model_dump())


@app.put("/api/customers")
async def customer_update(data: CustomerUpdateIn, id: int | None = None) -> Any:
    payload = data.model_dump(exclude_none=True)
    if id is not None:
        payload["id"] = id
    return await backend_request("PUT", "/transfer/customer/update", json=payload)


@app.delete("/api/customers/{id}")
async def customer_delete(id: int) -> Any:
    return await backend_request("DELETE", "/transfer/customer/delete", params={"id": id})


# 主叫鉴权白名单：对应 /transfer/auth
@app.get("/api/caller-auth")
async def caller_auth_page(
    page: int = 1,
    pageSize: int = 10,
    customerAcc: str | None = None,
    status: int | None = None,
) -> Any:
    params = {"page": page, "pageSize": pageSize}
    if customerAcc:
        params["customerAcc"] = customerAcc
    if status is not None:
        params["status"] = status
    return await backend_request("GET", "/transfer/auth/page", params=params)


@app.post("/api/caller-auth")
async def caller_auth_add(data: CallerAuthIn) -> Any:
    return await backend_request("POST", "/transfer/auth/add", json=data.model_dump())


@app.delete("/api/caller-auth/{id}")
async def caller_auth_delete(id: int) -> Any:
    return await backend_request("DELETE", "/transfer/auth/delete", params={"id": id})


@app.post("/api/caller-auth/sync")
async def caller_auth_sync(customerAcc: str | None = None) -> Any:
    if customerAcc:
        return await backend_request("POST", "/transfer/auth/sync/customer", params={"customerAcc": customerAcc})
    return await backend_request("POST", "/transfer/auth/sync")


# 被叫黑白名单：对应 /transfer/numberlist
@app.get("/api/number-list")
async def number_list_page(
    page: int = 1,
    pageSize: int = 10,
    customerAcc: str | None = None,
    listType: int | None = None,
    matchType: int | None = None,
    number: str | None = None,
    status: int | None = None,
) -> Any:
    params = {"page": page, "pageSize": pageSize}
    for k, v in {"customerAcc": customerAcc, "listType": listType, "matchType": matchType, "number": number, "status": status}.items():
        if v is not None and v != "":
            params[k] = v
    return await backend_request("GET", "/transfer/numberlist/page", params=params)


@app.post("/api/number-list")
async def number_list_add(data: NumberRecordIn) -> Any:
    return await backend_request("POST", "/transfer/numberlist/record/add", json=data.model_dump())


@app.put("/api/number-list/{id}")
async def number_list_update(id: int, data: NumberRecordIn) -> Any:
    payload = data.model_dump()
    payload["id"] = id
    return await backend_request("PUT", "/transfer/numberlist/update", json=payload)


@app.delete("/api/number-list/{id}")
async def number_list_delete(id: int) -> Any:
    return await backend_request("DELETE", f"/transfer/numberlist/delete/{id}")


@app.post("/api/number-list/sync")
async def number_list_sync(customerAcc: str | None = None) -> Any:
    if customerAcc:
        return await backend_request("POST", "/transfer/numberlist/sync/customer", params={"customerAcc": customerAcc})
    return await backend_request("POST", "/transfer/numberlist/sync")


def _xlsx_column_index(cell_ref: str) -> int:
    letters = re.sub(r"[^A-Z]", "", cell_ref.upper())
    index = 0
    for letter in letters:
        index = index * 26 + ord(letter) - ord("A") + 1
    return max(index - 1, 0)


def _parse_xlsx_numbers(raw: bytes) -> list[str]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as workbook:
            shared_strings: list[str] = []
            if "xl/sharedStrings.xml" in workbook.namelist():
                root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
                for item in root.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si"):
                    shared_strings.append("".join(node.text or "" for node in item.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")))

            sheet_name = next((name for name in workbook.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")), None)
            if not sheet_name:
                return []
            root = ET.fromstring(workbook.read(sheet_name))
    except (zipfile.BadZipFile, ET.ParseError, KeyError):
        raise HTTPException(status_code=400, detail="xlsx 文件解析失败，请确认文件格式正确")

    numbers: list[str] = []
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    for row in root.iter(f"{ns}row"):
        values: list[str] = []
        for cell in row.findall(f"{ns}c"):
            value_node = cell.find(f"{ns}v")
            inline_node = cell.find(f"{ns}is/{ns}t")
            value = ""
            if inline_node is not None and inline_node.text:
                value = inline_node.text
            elif value_node is not None and value_node.text:
                value = value_node.text
                if cell.attrib.get("t") == "s":
                    try:
                        value = shared_strings[int(value)]
                    except (ValueError, IndexError):
                        value = ""
            col_index = _xlsx_column_index(cell.attrib.get("r", "A"))
            while len(values) <= col_index:
                values.append("")
            values[col_index] = value
        numbers.extend(_clean_number_tokens(values))
    return numbers


def _clean_number_tokens(tokens: list[str]) -> list[str]:
    headers = {"number", "call_number", "called", "phone", "号码", "被叫号码", "主叫号码"}
    cleaned: list[str] = []
    for token in tokens:
        value = str(token).strip().strip(",")
        if not value or value.lower() in headers:
            continue
        cleaned.append(value)
    return cleaned


def _parse_uploaded_numbers(filename: str | None, raw: bytes) -> list[str]:
    suffix = (filename or "").lower().rsplit(".", 1)[-1]
    if suffix == "xlsx":
        return _parse_xlsx_numbers(raw)

    text = raw.decode("utf-8-sig", errors="ignore")
    if suffix == "csv":
        rows = csv.reader(io.StringIO(text))
        return _clean_number_tokens([cell for row in rows for cell in row[:1]])
    return _clean_number_tokens(text.splitlines())


@app.post("/api/number-list/batch")
async def number_list_batch_add(
    customerAcc: str = Query(...),
    listType: int = Query(1, ge=1, le=2),
    matchType: int = Query(1, ge=1, le=2),
    status: int = Query(1),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    raw = await file.read()
    numbers = _parse_uploaded_numbers(file.filename, raw)

    results = []
    for n in numbers:
        payload = {"customerAcc": customerAcc, "number": n, "matchType": matchType, "listType": listType, "status": status}
        try:
            ret = await backend_request("POST", "/transfer/numberlist/record/add", json=payload)
            ok = str(ret).strip() in {"1", "true", "True", "OK", "ok"}
            results.append({"number": n, "success": ok, "response": ret})
        except HTTPException as exc:
            results.append({"number": n, "success": False, "response": exc.detail})
    return {"total": len(results), "success": sum(1 for r in results if r["success"]), "failed": sum(1 for r in results if not r["success"]), "items": results}


@app.get("/api/number-list/export")
async def number_list_export(
    customerAcc: str | None = None,
    listType: int | None = None,
    matchType: int | None = None,
    status: int | None = None,
) -> StreamingResponse:
    data = await number_list_page(page=1, pageSize=5000, customerAcc=customerAcc, listType=listType, matchType=matchType, status=status)
    rows = data.get("records") or data.get("list") or data.get("data", {}).get("records") or data.get("data", {}).get("list") or []
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id", "customerAcc", "number", "matchType", "listType", "status", "createTime", "updateTime"], extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=number-list.csv"})
