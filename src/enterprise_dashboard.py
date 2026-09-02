"""로컬 전용 자동차 품질 검색 대시보드 서버."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import sqlite3
import webbrowser
from http.cookies import SimpleCookie
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from enterprise_database import search_database
from enterprise_import import apply_transform
from enterprise_security import ROLE_PERMISSIONS, SecurityStore


ALLOWED_FILTERS = {"lot_id", "vin", "supplier_id", "part_number", "risk_level"}
MAPPING_SCHEMAS = {
    "part_lot.csv": ["lot_id", "supplier_id", "part_number", "safety_class", "received_at", "quantity"],
    "process_inspection.csv": ["inspection_id", "lot_id", "process_id", "measured_at", "process_z", "recheck_rate"],
    "vehicle_build.csv": ["vin", "lot_id", "model", "production_at", "shipment_status"],
    "warranty_claim.csv": ["claim_id", "vin", "claim_at", "failure_code", "repair_cost_krw"],
    "cost_master.csv": ["part_number", "early_action_cost_krw", "field_repair_cost_krw", "customer_compensation_krw"],
}
HEADER_ALIASES = {
    "lot_id": ["lot_id", "lot", "부품lot번호", "장착lot", "로트번호"],
    "supplier_id": ["supplier_id", "supplier", "협력사코드", "공급사코드"],
    "part_number": ["part_number", "part_no", "부품번호", "품번"],
    "safety_class": ["safety_class", "안전등급", "중요도"],
    "received_at": ["received_at", "입고일시", "입고일"], "quantity": ["quantity", "입고수량", "수량"],
    "inspection_id": ["inspection_id", "검사번호", "검사id"], "process_id": ["process_id", "공정코드", "공정id"],
    "measured_at": ["measured_at", "검사일시", "측정일시"], "process_z": ["process_z", "공정편차z", "z값"],
    "recheck_rate": ["recheck_rate", "재검률", "재검사율"], "vin": ["vin", "차대번호", "차량키"],
    "model": ["model", "차종", "모델"], "production_at": ["production_at", "생산일시", "생산일"],
    "shipment_status": ["shipment_status", "출고상태"], "claim_id": ["claim_id", "수리접수번호", "청구번호"],
    "claim_at": ["claim_at", "수리일자", "접수일"], "failure_code": ["failure_code", "고장코드", "불량코드"],
    "repair_cost_krw": ["repair_cost_krw", "총수리비", "수리비"],
    "early_action_cost_krw": ["early_action_cost_krw", "출고전조치비"],
    "field_repair_cost_krw": ["field_repair_cost_krw", "출고후수리비"],
    "customer_compensation_krw": ["customer_compensation_krw", "고객보상비"],
}
TRANSFORM_BY_COLUMN = {
    "lot_id":"upper","supplier_id":"upper","part_number":"upper","safety_class":"upper","received_at":"datetime","quantity":"integer",
    "inspection_id":"upper","process_id":"upper","measured_at":"datetime","process_z":"number","recheck_rate":"percent_to_rate",
    "vin":"upper","production_at":"datetime","shipment_status":"upper","claim_id":"upper","claim_at":"datetime",
    "failure_code":"upper","repair_cost_krw":"number","early_action_cost_krw":"number","field_repair_cost_krw":"number",
    "customer_compensation_krw":"number","model":"strip",
}


def _normalized_header(value: str) -> str:
    return "".join(character.lower() for character in value.strip() if character.isalnum() or character == "_")


def mapping_preview(table: str, headers: list[str], filename: str = "") -> dict:
    if table not in MAPPING_SCHEMAS:
        raise ValueError("지원하지 않는 표준 테이블입니다.")
    if not headers or len(headers) > 200:
        raise ValueError("CSV 헤더는 1개 이상 200개 이하여야 합니다.")
    cleaned = [str(value).strip()[:100] for value in headers]
    if any(not value for value in cleaned):
        raise ValueError("비어 있는 CSV 열 이름이 있습니다.")
    normalized = [_normalized_header(value) for value in cleaned]
    if len(set(normalized)) != len(normalized):
        raise ValueError("중복된 CSV 열 이름이 있습니다.")
    suggestions, missing = {}, []
    for canonical in MAPPING_SCHEMAS[table]:
        aliases = {_normalized_header(value) for value in HEADER_ALIASES.get(canonical, [canonical])}
        match = next((header for header, norm in zip(cleaned, normalized) if norm in aliases), None)
        suggestions[canonical] = match
        if match is None:
            missing.append(canonical)
    return {"status": "READY" if not missing else "NEEDS_MAPPING", "filename": filename[:200], "table": table,
            "headers": cleaned, "required_columns": MAPPING_SCHEMAS[table], "suggestions": suggestions,
            "missing": missing, "notice": "원본 파일은 브라우저에서 읽고 헤더만 서버로 전달하며 자동 저장하지 않습니다."}


def validate_staging_payload(payload: dict) -> dict:
    table, filename = str(payload.get("table", "")), str(payload.get("filename", ""))[:200]
    mapping, rows = payload.get("mapping", {}), payload.get("rows", [])
    if table not in MAPPING_SCHEMAS or not isinstance(mapping, dict) or not isinstance(rows, list):
        raise ValueError("표준 테이블·매핑·행 데이터 형식이 올바르지 않습니다.")
    if not rows or len(rows) > 5000:
        raise ValueError("한 번에 검사할 수 있는 데이터는 1~5,000행입니다.")
    required = MAPPING_SCHEMAS[table]
    missing_mapping = [column for column in required if not str(mapping.get(column, "")).strip()]
    if missing_mapping:
        raise ValueError("필수 매핑 누락: " + ", ".join(missing_mapping))
    standardized, issues = [], []
    for row_number, row in enumerate(rows, start=2):
        if not isinstance(row, dict):
            issues.append({"row":row_number,"column":"*","code":"INVALID_ROW","message":"행 형식이 올바르지 않습니다."})
            continue
        target = {}
        for canonical in required:
            source = mapping[canonical]
            raw = str(row.get(source, ""))
            if not raw.strip():
                issues.append({"row":row_number,"column":source,"code":"REQUIRED_EMPTY","message":f"{canonical} 필수값이 비어 있습니다."})
                target[canonical] = ""
                continue
            try:
                target[canonical] = apply_transform(raw, TRANSFORM_BY_COLUMN.get(canonical, "strip"))
            except (ValueError, TypeError) as exc:
                issues.append({"row":row_number,"column":source,"code":"TRANSFORM_FAILED","message":str(exc)})
                target[canonical] = ""
        standardized.append(target)
        if len(issues) >= 200:
            break
    canonical = json.dumps({"table":table,"filename":filename,"mapping":mapping,"rows":standardized},ensure_ascii=False,sort_keys=True,separators=(",",":"))
    token = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {"status":"READY_FOR_APPROVAL" if not issues else "BLOCKED","table":table,"filename":filename,
            "input_rows":len(rows),"checked_rows":len(standardized),"error_count":len(issues),"issues":issues[:20],
            "preview":standardized[:10],"approval_token":token if not issues else None,"standardized_rows":standardized}


def save_approved_staging(result: dict, supplied_token: str, staging_root: Path) -> dict:
    if result["status"] != "READY_FOR_APPROVAL" or supplied_token != result["approval_token"]:
        raise ValueError("검사 결과와 승인번호가 일치하지 않습니다.")
    target_dir = staging_root.resolve() / supplied_token[:16]
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / result["table"]
    with target.open("w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=MAPPING_SCHEMAS[result["table"]]);writer.writeheader();writer.writerows(result["standardized_rows"])
    manifest={"status":"STAGED_NOT_LOADED","approved_at":datetime.now().isoformat(),"approval_token":supplied_token,
              "table":result["table"],"filename":result["filename"],"rows":result["checked_rows"],"staged_file":str(target)}
    (target_dir/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8-sig")
    return manifest


def dashboard_summary(database: Path, pipeline_summary: Path) -> dict:
    if not database.exists():
        raise FileNotFoundError("통합 데이터베이스가 없습니다. 전체 통합 실행을 먼저 진행하세요.")
    connection = sqlite3.connect(database)
    try:
        values = connection.execute("""
            SELECT COUNT(*),
                   SUM(CASE WHEN risk_level='HIGH' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN risk_level='WATCH' THEN 1 ELSE 0 END),
                   COALESCE(SUM(estimated_net_benefit_krw),0)
            FROM lot_risk_result
        """).fetchone()
        affected = connection.execute("SELECT COUNT(*) FROM affected_vehicle").fetchone()[0]
    finally:
        connection.close()
    pipeline = json.loads(pipeline_summary.read_text(encoding="utf-8-sig")) if pipeline_summary.exists() else {}
    public_stage = next(
        (item for item in pipeline.get("stages", []) if item.get("name") == "PUBLIC_EVIDENCE"), {}
    )
    public_result = public_stage.get("result", {}) if isinstance(public_stage.get("result", {}), dict) else {}
    public_files = public_result.get("files", {}) if isinstance(public_result.get("files", {}), dict) else {}
    return {
        "lot_count": values[0], "high_risk_lots": values[1] or 0,
        "watch_lots": values[2] or 0, "affected_vehicle_links": affected,
        "estimated_net_benefit_krw": values[3],
        "pipeline_status": pipeline.get("status", "UNKNOWN"),
        "decision_gate_passed": pipeline.get("decision_gate_passed", False),
        "decision_notice": pipeline.get("decision_notice", "판단 기준 정보를 확인할 수 없습니다."),
        "run_id": pipeline.get("run_id", "UNKNOWN"),
        "public_evidence_status": public_stage.get("status", "NOT_RUN"),
        "public_normalized_rows": public_result.get("normalized_rows", 0),
        "public_error_count": public_result.get("error_count", 0),
        "public_linkage_policy": public_result.get("linkage_policy", "NOT_AVAILABLE"),
        "public_monthly_rows": public_files.get("monthly_panel.csv", {}).get("rows", 0),
        "public_recall_rows": public_files.get("recall_detection_12m.csv", {}).get("rows", 0),
        "public_file_count": len(public_files),
    }


def validated_search(database: Path, params: dict[str, list[str]]) -> list[dict]:
    supplied = {key: values[0] for key, values in params.items() if key in ALLOWED_FILTERS and values and values[0].strip()}
    if any(len(value) > 100 for value in supplied.values()):
        raise ValueError("검색어는 100자 이하여야 합니다.")
    return search_database(database, **supplied)


def model_validation_summary(result_file: Path) -> dict:
    if not result_file.exists():
        return {"status": "NOT_RUN", "message": "모델 비교 결과가 없습니다."}
    result = json.loads(result_file.read_text(encoding="utf-8-sig"))
    labels = {"fixed_rule": "고정 경보규칙", "logistic_regression": "로지스틱 회귀", "random_forest": "랜덤포레스트"}
    models = []
    for key, value in result.get("models", {}).items():
        test = value.get("test", {})
        models.append({
            "id": key, "name": labels.get(key, key), "threshold": value.get("threshold"),
            "precision": test.get("precision", 0), "recall": test.get("recall", 0),
            "f1": test.get("f1", 0), "alerts": test.get("alerts", 0),
            "false_positive": test.get("fp", 0), "false_negative": test.get("fn", 0),
            "cost_units": test.get("cost_units_fp1_fn10", 0),
        })
    selected = min(models, key=lambda item: (item["cost_units"], -item["f1"])) if models else None
    return {
        "status": "READY", "method": result.get("method"), "target": result.get("target"),
        "split": result.get("split", {}), "dataset": result.get("dataset", {}),
        "models": models, "selected_model": selected["id"] if selected else None,
        "decision": "공개데이터에서는 고정 경보규칙 유지, ML 모델은 기업 데이터 재검증 전 보류",
        "notice": "비용단위는 FP=1·FN=10 비교값이며 실제 원화 비용이 아닙니다.",
    }


def make_handler(database: Path, pipeline_summary: Path, model_result: Path | None = None, ui_file: Path | None = None,
                 staging_root: Path | None = None, security: SecurityStore | None = None):
    # 이전 성능시험 호출 형식(database, summary, ui)을 계속 지원합니다.
    if ui_file is None and model_result is not None and model_result.suffix.lower() == ".html":
        ui_file, model_result = model_result, Path("__missing_model_result__.json")
    model_result = model_result or Path("__missing_model_result__.json")
    staging_root = staging_root or database.parent / "import_staging"
    class Handler(BaseHTTPRequestHandler):
        def cookie_token(self) -> str | None:
            cookie = SimpleCookie(); cookie.load(self.headers.get("Cookie", ""))
            return cookie["autoq_session"].value if "autoq_session" in cookie else None

        def current_user(self) -> dict | None:
            return security.session(self.cookie_token()) if security else {"username":"test","role":"ADMIN","permissions":sorted(ROLE_PERMISSIONS["ADMIN"]),"csrf_token":"test"}

        def require(self, permission: str, csrf: bool = False) -> dict | None:
            user = self.current_user()
            if not user:
                self.send_json(401, {"status":"AUTH_REQUIRED","message":"로그인이 필요합니다."})
                return None
            if permission not in user["permissions"]:
                if security: security.audit(user["username"], "ACCESS", "DENIED", self.client_address[0], {"permission":permission,"path":self.path})
                self.send_json(403, {"status":"FORBIDDEN","message":"이 기능을 사용할 권한이 없습니다."})
                return None
            if csrf and self.headers.get("X-CSRF-Token", "") != user["csrf_token"]:
                self.send_json(403, {"status":"FORBIDDEN","message":"요청 보안번호가 올바르지 않습니다."})
                return None
            return user

        def send_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            request = urlparse(self.path)
            try:
                if request.path == "/api/health":
                    self.send_json(200, {"status": "READY", "database_exists": database.exists()})
                elif request.path == "/api/me":
                    user = self.current_user()
                    self.send_json(200 if user else 401, {"status":"READY" if user else "AUTH_REQUIRED", "user":user})
                elif request.path == "/api/summary":
                    if not self.require("VIEW_DASHBOARD"): return
                    self.send_json(200, {"status": "READY", "data": dashboard_summary(database, pipeline_summary)})
                elif request.path == "/api/search":
                    user = self.require("SEARCH")
                    if not user: return
                    rows = validated_search(database, parse_qs(request.query, keep_blank_values=False))
                    if security: security.audit(user["username"], "SEARCH", "SUCCESS", self.client_address[0], {"filters":list(parse_qs(request.query).keys()),"count":len(rows)})
                    self.send_json(200, {"status": "READY", "count": len(rows), "results": rows})
                elif request.path == "/api/model-validation":
                    if not self.require("VIEW_DASHBOARD"): return
                    self.send_json(200, model_validation_summary(model_result))
                elif request.path == "/api/admin/users":
                    if not self.require("MANAGE_USERS"): return
                    self.send_json(200, {"status":"READY","users":security.list_users() if security else []})
                elif request.path == "/api/admin/audit":
                    if not self.require("VIEW_AUDIT"): return
                    self.send_json(200, {"status":"READY","rows":security.audit_rows() if security else []})
                elif request.path in {"/", "/index.html"}:
                    body = ui_file.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("X-Frame-Options", "DENY")
                    self.send_header("Referrer-Policy", "no-referrer")
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_json(404, {"status": "ERROR", "message": "요청한 화면을 찾을 수 없습니다."})
            except (ValueError, FileNotFoundError) as exc:
                self.send_json(400, {"status": "BLOCKED", "message": str(exc)})
            except Exception:
                self.send_json(500, {"status": "ERROR", "message": "서버 처리 중 오류가 발생했습니다."})

        def do_POST(self):
            try:
                endpoint = urlparse(self.path).path
                if endpoint == "/api/login":
                    length = int(self.headers.get("Content-Length", "0"))
                    if "application/json" not in self.headers.get("Content-Type", "") or length <= 0 or length > 4096:
                        raise ValueError("로그인 요청 형식이 올바르지 않습니다.")
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                    result = security.login(str(payload.get("username", "")), str(payload.get("password", "")), self.client_address[0]) if security else None
                    if not result:
                        self.send_json(401, {"status":"DENIED","message":"아이디 또는 비밀번호를 확인하세요. 5회 실패하면 15분 잠깁니다."}); return
                    body = json.dumps({"status":"READY","user":{k:v for k,v in result.items() if k!="token"}}, ensure_ascii=False).encode("utf-8")
                    self.send_response(200); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(body)))
                    self.send_header("Set-Cookie",f"autoq_session={result['token']}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800")
                    self.send_header("Cache-Control","no-store"); self.send_header("X-Frame-Options","DENY"); self.end_headers(); self.wfile.write(body); return
                if endpoint == "/api/logout":
                    user = self.require("VIEW_DASHBOARD", csrf=True)
                    if not user: return
                    if security: security.logout(self.cookie_token(), self.client_address[0])
                    body=b'{"status":"READY"}'; self.send_response(200); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(body))); self.send_header("Set-Cookie","autoq_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"); self.end_headers(); self.wfile.write(body); return
                if endpoint not in {"/api/mapping-preview", "/api/staging-preview", "/api/staging-approve", "/api/admin/users", "/api/admin/user-status"}:
                    self.send_json(404, {"status": "ERROR", "message": "요청한 기능을 찾을 수 없습니다."})
                    return
                permission = "MANAGE_USERS" if endpoint.startswith("/api/admin/") else "IMPORT_APPROVE" if endpoint == "/api/staging-approve" else "IMPORT_PREVIEW"
                user = self.require(permission, csrf=True)
                if not user: return
                content_type = self.headers.get("Content-Type", "")
                length = int(self.headers.get("Content-Length", "0"))
                if "application/json" not in content_type or length <= 0 or length > 5242880:
                    raise ValueError("매핑 요청 형식 또는 크기가 올바르지 않습니다.")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if endpoint == "/api/admin/users":
                    security.create_user(str(payload.get("username", "")), str(payload.get("display_name", "")), str(payload.get("password", "")), str(payload.get("role", "")), user["username"])
                    result = {"status":"READY","users":security.list_users()}
                elif endpoint == "/api/admin/user-status":
                    security.set_active(str(payload.get("username", "")), bool(payload.get("active")), user["username"])
                    result = {"status":"READY","users":security.list_users()}
                elif endpoint == "/api/mapping-preview":
                    result = mapping_preview(str(payload.get("table", "")), payload.get("headers", []), str(payload.get("filename", "")))
                else:
                    checked = validate_staging_payload(payload)
                    result = save_approved_staging(checked, str(payload.get("approval_token", "")), staging_root) if endpoint == "/api/staging-approve" else {key:value for key,value in checked.items() if key != "standardized_rows"}
                self.send_json(200, result)
            except (ValueError, json.JSONDecodeError) as exc:
                self.send_json(400, {"status": "BLOCKED", "message": str(exc)})
            except Exception:
                self.send_json(500, {"status": "ERROR", "message": "매핑 검사 중 오류가 발생했습니다."})

        def log_message(self, format, *args):
            return

    return Handler


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="자동차 품질 위험 대시보드")
    parser.add_argument("--database", type=Path, default=root / "results/enterprise_pipeline/current/03_database/automotive_quality.db")
    parser.add_argument("--summary", type=Path, default=root / "results/enterprise_pipeline/current/pipeline_summary.json")
    parser.add_argument("--model-result", type=Path, default=root / "results/model_validation/model_comparison.json")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    ui_file = root / "ui" / "index.html"
    security = SecurityStore(root / "results" / "security" / "security.db")
    server = ThreadingHTTPServer((args.host, args.port), make_handler(args.database.resolve(), args.summary.resolve(), args.model_result.resolve(), ui_file, root / "results" / "import_staging", security))
    url = f"http://{args.host}:{args.port}"
    print(f"자동차 품질 화면 실행: {url}")
    print(f"초기 관리자 계정 파일: {security.bootstrap_file}")
    print("종료하려면 Ctrl+C를 누르세요.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
