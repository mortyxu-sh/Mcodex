import io
import zipfile

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import main


client = TestClient(main.app)


def make_xlsx(values: list[str]) -> bytes:
    shared = "".join(f"<si><t>{value}</t></si>" for value in values)
    cells = "".join(f'<row r="{idx + 1}"><c r="A{idx + 1}" t="s"><v>{idx}</v></c></row>' for idx, _ in enumerate(values))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "")
        zf.writestr("xl/sharedStrings.xml", f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">{shared}</sst>')
        zf.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{cells}</sheetData></worksheet>')
    return buf.getvalue()


def test_customer_update_sends_id_and_excludes_empty_fields(monkeypatch):
    captured = {}

    async def fake_backend_request(method, path, **kwargs):
        captured.update({"method": method, "path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(main, "backend_request", fake_backend_request)
    resp = client.put("/api/customers?id=7", json={"name": "测试客户", "status": 0})

    assert resp.status_code == 200
    assert captured["method"] == "PUT"
    assert captured["path"] == "/transfer/customer/update"
    assert captured["json"] == {"name": "测试客户", "status": 0, "id": 7}


def test_parse_uploaded_numbers_from_csv_and_xlsx():
    assert main._parse_uploaded_numbers("numbers.csv", b"number\n13800138000\n,ignored\n13900139000\n") == ["13800138000", "13900139000"]
    assert main._parse_uploaded_numbers("numbers.xlsx", make_xlsx(["号码", "13800138000", "13900139000"])) == ["13800138000", "13900139000"]


def test_batch_import_returns_failure_details(monkeypatch):
    async def fake_backend_request(method, path, **kwargs):
        number = kwargs["json"]["number"]
        if number == "13900139000":
            raise HTTPException(status_code=409, detail="duplicate")
        return True

    monkeypatch.setattr(main, "backend_request", fake_backend_request)
    resp = client.post(
        "/api/number-list/batch?customerAcc=c001&listType=1&matchType=1",
        files={"file": ("numbers.txt", b"13800138000\n13900139000\n", "text/plain")},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["success"] == 1
    assert data["failed"] == 1
    assert data["items"][1]["response"] == "duplicate"
