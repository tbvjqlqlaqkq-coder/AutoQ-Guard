"""재현 가능한 기업 파일럿 규모 합성 원본 CSV를 생성한다.

실제 성능을 주장하기 위한 데이터가 아니라 반입·검증·분석·검색 파이프라인의
규모 적합성을 확인하는 기능시험 자료다.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path


FILES = {
    "협력사부품입고.csv": ["부품LOT번호", "협력사코드", "부품번호", "안전등급", "입고일시", "입고수량"],
    "공정검사.csv": ["검사번호", "부품LOT번호", "공정코드", "검사일시", "공정편차Z", "재검률"],
    "차량조립이력.csv": ["차대번호", "장착LOT", "차종", "생산일시", "출고상태"],
    "보증수리.csv": ["수리접수번호", "차대번호", "수리일자", "고장코드", "총수리비"],
    "부품비용기준.csv": ["부품번호", "출고전조치비", "출고후수리비", "고객보상비"],
}

TRUTH_FIELDS = ["lot_id", "is_injected_risk", "injected_reason"]


def _write(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _vin(index: int) -> str:
    # VIN에서 허용되지 않는 I/O/Q를 피한다.
    return f"AGX{index:014d}"


def generate(output_dir: Path, lots: int = 1_000, vehicles: int = 10_000,
             claims: int = 300, seed: int = 20260909) -> dict[str, object]:
    if lots < 1 or vehicles < lots or claims < 1 or claims > vehicles:
        raise ValueError("lots>=1, vehicles>=lots, 1<=claims<=vehicles 조건이 필요합니다")
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    base = datetime(2025, 1, 1, 8, 0, 0)
    classes = ["SAFETY", "POWERTRAIN", "CONVENIENCE", "SOFTWARE"]
    parts = [f"PART-{i:03d}" for i in range(1, 21)]
    risky_lots = {i for i in range(lots) if i % 50 == 0}

    lot_rows, inspection_rows = [], []
    for i in range(lots):
        lot_id = f"LOT-PILOT-{i + 1:05d}"
        received = base + timedelta(hours=9 * i)
        lot_rows.append({"부품LOT번호": lot_id, "협력사코드": f"SUP-{i % 12 + 1:02d}",
                         "부품번호": parts[i % len(parts)], "안전등급": classes[i % len(classes)],
                         "입고일시": received.strftime("%Y-%m-%d %H:%M:%S"),
                         "입고수량": max(10, vehicles // lots + 3)})
        risky = i in risky_lots
        inspection_rows.append({"검사번호": f"INSP-{i + 1:05d}", "부품LOT번호": lot_id,
                                "공정코드": f"PROC-{i % 8 + 1:02d}",
                                "검사일시": (received + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
                                "공정편차Z": f"{rng.uniform(3.05, 3.8) if risky else rng.uniform(0.2, 1.8):.3f}",
                                "재검률": f"{rng.uniform(0.105, 0.16) if risky else rng.uniform(0.005, 0.045):.4f}"})

    vehicle_rows = []
    vins_by_lot = {i: [] for i in range(lots)}
    for i in range(vehicles):
        lot_index, vin = i % lots, _vin(i + 1)
        vins_by_lot[lot_index].append(vin)
        vehicle_rows.append({"차대번호": vin, "장착LOT": f"LOT-PILOT-{lot_index + 1:05d}",
                             "차종": f"MODEL-{i % 4 + 1}",
                             "생산일시": (base + timedelta(hours=9 * lot_index + 12)).strftime("%Y-%m-%d %H:%M:%S"),
                             "출고상태": "FIELD" if i % 3 else "SHIPPED"})

    preferred = [vin for idx in sorted(risky_lots) for vin in vins_by_lot[idx]]
    preferred_set = set(preferred)
    remaining = [row["차대번호"] for row in vehicle_rows if row["차대번호"] not in preferred_set]
    claim_rows = [{"수리접수번호": f"CLAIM-{i + 1:05d}", "차대번호": vin,
                   "수리일자": (base + timedelta(days=370 + i % 120)).strftime("%Y-%m-%d"),
                   "고장코드": f"FAIL-{i % 6 + 1:02d}", "총수리비": 180_000 + (i % 8) * 35_000}
                  for i, vin in enumerate((preferred + remaining)[:claims])]
    cost_rows = [{"부품번호": part, "출고전조치비": 45_000 + i * 1_000,
                  "출고후수리비": 320_000 + i * 12_000, "고객보상비": 80_000 + i * 3_000}
                 for i, part in enumerate(parts)]
    rows_by_file = {"협력사부품입고.csv": lot_rows, "공정검사.csv": inspection_rows,
                    "차량조립이력.csv": vehicle_rows, "보증수리.csv": claim_rows,
                    "부품비용기준.csv": cost_rows}
    for name, fields in FILES.items():
        _write(output_dir / name, fields, rows_by_file[name])
    truth_rows = [{
        "lot_id": f"LOT-PILOT-{i + 1:05d}",
        "is_injected_risk": "1" if i in risky_lots else "0",
        "injected_reason": "PROCESS_Z_AND_RECHECK" if i in risky_lots else "NONE",
    } for i in range(lots)]
    _write(output_dir / "synthetic_ground_truth.csv", TRUTH_FIELDS, truth_rows)
    manifest = {"purpose": "기업 파일럿 규모 기능시험용 합성데이터", "not_real_enterprise_data": True,
                "seed": seed, "lots": lots, "vehicle_links": vehicles,
                "warranty_claims": claims, "injected_process_risk_lots": len(risky_lots)}
    (output_dir / "fixture_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="기업 파일럿 규모 합성 원본 생성")
    parser.add_argument("--output-dir", type=Path, default=Path("results/enterprise_pilot_fixture/raw"))
    parser.add_argument("--lots", type=int, default=1_000)
    parser.add_argument("--vehicles", type=int, default=10_000)
    parser.add_argument("--claims", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20260909)
    args = parser.parse_args()
    print(json.dumps(generate(args.output_dir, args.lots, args.vehicles, args.claims, args.seed), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
