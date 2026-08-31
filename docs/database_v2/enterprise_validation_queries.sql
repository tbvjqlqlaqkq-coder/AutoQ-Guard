SET search_path TO autoq_guard;

-- 1. 외래키 연결 없이 남은 LOT 장착 이력은 0건이어야 한다.
SELECT count(*) AS orphan_installations
FROM vehicle_part_installation i
LEFT JOIN vehicle v ON v.vehicle_key = i.vehicle_key
LEFT JOIN part_lot l ON l.lot_id = i.lot_id
WHERE v.vehicle_key IS NULL OR l.lot_id IS NULL;

-- 2. 생산일보다 먼저 발생한 보증수리는 0건이어야 한다.
SELECT count(*) AS invalid_claim_dates
FROM warranty_claim c
JOIN vehicle v ON v.vehicle_key = c.vehicle_key
WHERE c.claim_at < v.production_at;

-- 3. LOT 수량보다 장착 차량 수가 큰 항목을 확인한다.
SELECT l.lot_id, l.quantity, count(*) AS installed_count
FROM part_lot l
JOIN vehicle_part_installation i ON i.lot_id = l.lot_id
GROUP BY l.lot_id, l.quantity
HAVING count(*) > l.quantity;

-- 4. 최신 고위험 LOT과 영향 차량 수를 조회한다.
SELECT r.lot_id, r.risk_level, r.risk_score, r.action_code,
       count(i.vehicle_key) AS affected_vehicle_count
FROM latest_lot_risk r
LEFT JOIN vehicle_part_installation i ON i.lot_id = r.lot_id
WHERE r.risk_level IN ('HIGH','CRITICAL')
GROUP BY r.lot_id, r.risk_level, r.risk_score, r.action_code
ORDER BY r.risk_score DESC;

-- 5. 평가 버전별 성능·경제성 비교에 사용할 집계다.
SELECT model_version, risk_level, count(*) AS lot_count,
       avg(risk_score) AS avg_risk_score,
       avg(estimated_direct_roi) AS avg_direct_roi,
       sum(estimated_net_benefit_krw) AS total_net_benefit_krw
FROM risk_assessment
GROUP BY model_version, risk_level
ORDER BY model_version, risk_level;
