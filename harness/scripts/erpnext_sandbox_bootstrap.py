#!/usr/bin/env python3
from __future__ import annotations

import http.cookiejar
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

COMPANY = "Bambuddy Sandbox"
COMPANY_ABBR = "BMS"
RAW_ITEM = "RM-WP111-PLA"
PRODUCT_ITEM = "SKU-WP111-CUBE"
DOCTYPE = "Farm Draft Result"


class FrappeApiError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"ERPNext HTTP {status}: {message}")
        self.status = status


class FrappeSession:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict | None = None,
        form: dict[str, str] | None = None,
    ) -> dict:
        if payload is not None and form is not None:
            raise ValueError("payload and form are mutually exclusive")
        headers = {"Accept": "application/json"}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        elif form is not None:
            data = urllib.parse.urlencode(form).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=120) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode()
            try:
                body = json.loads(raw)
                message = body.get("exception") or body.get("message") or body.get("exc_type") or "request failed"
            except json.JSONDecodeError:
                message = "non-JSON response"
            raise FrappeApiError(exc.code, str(message)) from exc

    def login(self, user: str, password: str) -> None:
        response = self.request("/api/method/login", method="POST", form={"usr": user, "pwd": password})
        if response.get("message") != "Logged In":
            raise RuntimeError("ERPNext sandbox login failed")

    def get_resource(self, doctype: str, name: str) -> dict | None:
        path = f"/api/resource/{urllib.parse.quote(doctype, safe='')}/{urllib.parse.quote(name, safe='')}"
        try:
            return self.request(path).get("data")
        except FrappeApiError as exc:
            if exc.status == 404:
                return None
            raise

    def create_resource(self, doctype: str, payload: dict) -> dict:
        path = f"/api/resource/{urllib.parse.quote(doctype, safe='')}"
        return self.request(path, method="POST", payload=payload)["data"]

    def update_resource(self, doctype: str, name: str, payload: dict) -> dict:
        path = f"/api/resource/{urllib.parse.quote(doctype, safe='')}/{urllib.parse.quote(name, safe='')}"
        return self.request(path, method="PUT", payload=payload)["data"]

    def list_resources(self, doctype: str, *, filters: list[list[object]], fields: list[str]) -> list[dict]:
        query = urllib.parse.urlencode(
            {
                "filters": json.dumps(filters, separators=(",", ":")),
                "fields": json.dumps(fields, separators=(",", ":")),
                "limit_page_length": "2",
            }
        )
        path = f"/api/resource/{urllib.parse.quote(doctype, safe='')}?{query}"
        data = self.request(path).get("data")
        if not isinstance(data, list):
            raise RuntimeError(f"ERPNext returned an invalid {doctype} collection")
        return data


def _required_env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default or "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _require_loopback(base_url: str) -> None:
    host = (urllib.parse.urlparse(base_url).hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("ERPNext sandbox bootstrap only accepts a loopback URL")


def _ensure_custom_field(api: FrappeSession, fieldname: str, label: str, insert_after: str) -> None:
    name = f"Work Order-{fieldname}"
    if api.get_resource("Custom Field", name) is None:
        api.create_resource(
            "Custom Field",
            {
                "dt": "Work Order",
                "fieldname": fieldname,
                "label": label,
                "fieldtype": "Data",
                "insert_after": insert_after,
            },
        )


def _ensure_draft_doctype(api: FrappeSession) -> None:
    if api.get_resource("DocType", DOCTYPE) is not None:
        return
    api.create_resource(
        "DocType",
        {
            "name": DOCTYPE,
            "module": "Custom",
            "custom": 1,
            "autoname": "format:FDR-{#####}",
            "track_changes": 1,
            "fields": [
                {"fieldname": "farm_event_id", "label": "Farm Event ID", "fieldtype": "Data", "reqd": 1, "unique": 1},
                {"fieldname": "production_request_id", "label": "Production Request ID", "fieldtype": "Int", "reqd": 1},
                {"fieldname": "external_work_order_id", "label": "External Work Order ID", "fieldtype": "Data", "reqd": 1},
                {"fieldname": "production_item", "label": "Production Item", "fieldtype": "Data", "reqd": 1},
                {"fieldname": "quantity_completed", "label": "Quantity Completed", "fieldtype": "Int", "reqd": 1},
                {"fieldname": "completed_at", "label": "Completed At", "fieldtype": "Datetime", "reqd": 1},
                {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "Draft", "default": "Draft", "read_only": 1},
            ],
            "permissions": [
                {
                    "role": "System Manager",
                    "read": 1,
                    "write": 1,
                    "create": 1,
                    "delete": 1,
                    "report": 1,
                    "export": 1,
                    "print": 1,
                    "email": 1,
                    "share": 1,
                }
            ],
        },
    )


def _ensure_item(api: FrappeSession, item_code: str, item_name: str, item_group: str) -> None:
    if api.get_resource("Item", item_code) is None:
        api.create_resource(
            "Item",
            {
                "item_code": item_code,
                "item_name": item_name,
                "item_group": item_group,
                "stock_uom": "Nos",
                "is_stock_item": 1,
            },
        )


def _ensure_bom(api: FrappeSession) -> str:
    matches = api.list_resources("BOM", filters=[["item", "=", PRODUCT_ITEM]], fields=["name", "docstatus"])
    if len(matches) > 1:
        raise RuntimeError("ERPNext sandbox contains multiple synthetic BOMs")
    if matches:
        bom = matches[0]
    else:
        bom = api.create_resource(
            "BOM",
            {
                "item": PRODUCT_ITEM,
                "company": COMPANY,
                "quantity": 1,
                "currency": "KRW",
                "items": [
                    {
                        "item_code": RAW_ITEM,
                        "qty": 1,
                        "uom": "Nos",
                        "stock_uom": "Nos",
                        "conversion_factor": 1,
                        "rate": 100,
                    }
                ],
            },
        )
    if bom.get("docstatus") == 0:
        bom = api.update_resource("BOM", str(bom["name"]), {"docstatus": 1})
    if bom.get("docstatus") != 1:
        raise RuntimeError("Synthetic BOM is not submitted")
    return str(bom["name"])


def _ensure_work_order(api: FrappeSession, bom_name: str) -> str:
    matches = api.list_resources(
        "Work Order",
        filters=[
            ["production_item", "=", PRODUCT_ITEM],
            ["custom_artifact_reference", "=", "fixture-cube-v1"],
        ],
        fields=["name", "docstatus"],
    )
    if len(matches) > 1:
        raise RuntimeError("ERPNext sandbox contains multiple synthetic Work Orders")
    if matches:
        return str(matches[0]["name"])
    work_order = api.create_resource(
        "Work Order",
        {
            "naming_series": "MFG-WO-.YYYY.-",
            "company": COMPANY,
            "production_item": PRODUCT_ITEM,
            "bom_no": bom_name,
            "qty": 1,
            "planned_start_date": "2026-07-10 09:00:00",
            "custom_artifact_reference": "fixture-cube-v1",
            "custom_profile_set_id": "p1p-pla-fixture-v1",
        },
    )
    return str(work_order["name"])


def _write_token(path: Path, token: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(token + "\n")


def main() -> None:
    base_url = _required_env("ERP_BASE_URL", "http://127.0.0.1:8080")
    admin_user = _required_env("ERP_ADMIN_USER", "Administrator")
    admin_password = _required_env("ERP_ADMIN_PASSWORD")
    token_file = Path(_required_env("ERP_TOKEN_FILE", "/tmp/bambuddy-wp111-erp-token"))
    _require_loopback(base_url)

    api = FrappeSession(base_url)
    api.login(admin_user, admin_password)
    if api.get_resource("Item Group", "Products") is None or api.get_resource("UOM", "Nos") is None:
        raise RuntimeError("ERPNext base fixtures are missing; run the documented stage_fixtures bench command first")
    if api.get_resource("Warehouse Type", "Transit") is None:
        api.create_resource("Warehouse Type", {"name": "Transit"})
    if api.get_resource("Company", COMPANY) is None:
        api.create_resource(
            "Company",
            {
                "company_name": COMPANY,
                "abbr": COMPANY_ABBR,
                "default_currency": "KRW",
                "country": "Korea, Republic of",
            },
        )

    _ensure_custom_field(api, "custom_artifact_reference", "Artifact Reference", "production_item")
    _ensure_custom_field(api, "custom_profile_set_id", "Profile Set ID", "custom_artifact_reference")
    _ensure_draft_doctype(api)
    _ensure_item(api, RAW_ITEM, "Synthetic PLA Input", "Raw Material")
    _ensure_item(api, PRODUCT_ITEM, "Synthetic Calibration Cube", "Products")
    bom_name = _ensure_bom(api)
    work_order_name = _ensure_work_order(api, bom_name)

    credentials = api.request(
        "/api/method/frappe.core.doctype.user.user.generate_keys",
        method="POST",
        payload={"user": admin_user},
    ).get("message", {})
    api_key = credentials.get("api_key")
    api_secret = credentials.get("api_secret")
    if not isinstance(api_key, str) or not isinstance(api_secret, str):
        raise RuntimeError("ERPNext did not return sandbox API credentials")
    _write_token(token_file, f"{api_key}:{api_secret}")

    print(
        json.dumps(
            {
                "status": "ok",
                "company": COMPANY,
                "bom": bom_name,
                "work_order_id": work_order_name,
                "draft_doctype": DOCTYPE,
                "token_file": str(token_file),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
