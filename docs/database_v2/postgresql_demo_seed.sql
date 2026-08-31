SET search_path TO autoq_guard;

INSERT INTO data_load_batch(batch_id,source_system,source_hash,load_status,row_count,error_count)
VALUES ('DEMO_MIGRATION_V1','SQLITE_V1_DEMO','7fbc7608c0bd6a47e9ad689ce420ececa16c38950c1ed68b6f0e7ad5e775221f','READY',4,0)
ON CONFLICT (batch_id) DO NOTHING;

INSERT INTO supplier(supplier_id,supplier_name) VALUES ('SUP-DEMO-01','DEMO SUPPLIER')
ON CONFLICT (supplier_id) DO NOTHING;
INSERT INTO part(part_number,part_name,safety_class,commodity_group)
VALUES ('HECU-DEMO','HECU DEMO','SAFETY','BRAKE') ON CONFLICT (part_number) DO NOTHING;
INSERT INTO process(process_id,process_name,plant_code,line_code)
VALUES ('ASSEMBLY-01','ASSEMBLY','DEMO','LINE-01') ON CONFLICT (process_id) DO NOTHING;
INSERT INTO vehicle(vehicle_key,model,production_at,shipment_status)
VALUES ('VH_DEMO_001','DEMO-MODEL','2026-01-12 10:00:00+09','SHIPPED')
ON CONFLICT (vehicle_key) DO NOTHING;
INSERT INTO part_lot(lot_id,supplier_id,part_number,received_at,quantity,batch_id)
VALUES ('LOT-DEMO-001','SUP-DEMO-01','HECU-DEMO','2026-01-10 08:30:00+09',80,'DEMO_MIGRATION_V1')
ON CONFLICT (lot_id) DO NOTHING;
INSERT INTO process_inspection(inspection_id,lot_id,process_id,measured_at,process_z,recheck_rate,batch_id)
VALUES ('INSP-DEMO-001','LOT-DEMO-001','ASSEMBLY-01','2026-01-11 09:10:00+09',2.35,0.08,'DEMO_MIGRATION_V1')
ON CONFLICT (inspection_id) DO NOTHING;
INSERT INTO vehicle_part_installation(vehicle_key,lot_id,installed_at,station_code,batch_id)
VALUES ('VH_DEMO_001','LOT-DEMO-001','2026-01-12 10:00:00+09','DEMO-STATION','DEMO_MIGRATION_V1')
ON CONFLICT (vehicle_key,lot_id) DO NOTHING;
INSERT INTO warranty_claim(claim_id,vehicle_key,part_number,claim_at,failure_code,repair_cost_krw,batch_id)
VALUES ('CLAIM-DEMO-001','VH_DEMO_001','HECU-DEMO','2026-02-15 00:00:00+09','ABS-WARNING',485000,'DEMO_MIGRATION_V1')
ON CONFLICT (claim_id) DO NOTHING;
INSERT INTO cost_policy(part_number,effective_from,early_action_cost_krw,field_repair_cost_krw,customer_compensation_krw)
VALUES ('HECU-DEMO','1970-01-01',210000,485000,50000)
ON CONFLICT (part_number,effective_from) DO NOTHING;
INSERT INTO risk_assessment(lot_id,assessed_at,model_version,risk_score,risk_level,risk_reasons,action_code,
 estimated_prevented_vehicles,estimated_avoided_loss_krw,estimated_early_action_cost_krw,estimated_net_benefit_krw,estimated_direct_roi)
SELECT 'LOT-DEMO-001','2026-08-05 00:00:00+09','rule_v1_migrated',0.65,'HIGH',
       '["공정편차 2.35σ≥2","재검률 8.0%≥7%","보증수리 1건","안전 핵심부품 가중치"]'::jsonb,
       'URGENT_SAFETY_REVIEW',0.65,347750,136500,211250,1.547619
WHERE NOT EXISTS (SELECT 1 FROM risk_assessment WHERE lot_id='LOT-DEMO-001' AND model_version='rule_v1_migrated');
INSERT INTO affected_vehicle(assessment_id,vehicle_key,lot_id,action_code)
SELECT assessment_id,'VH_DEMO_001','LOT-DEMO-001','URGENT_SAFETY_REVIEW'
FROM risk_assessment WHERE lot_id='LOT-DEMO-001' AND model_version='rule_v1_migrated'
ON CONFLICT DO NOTHING;
