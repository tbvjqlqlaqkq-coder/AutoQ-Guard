BEGIN;

CREATE SCHEMA IF NOT EXISTS autoq_guard;
SET search_path TO autoq_guard;

CREATE TABLE data_load_batch (
    batch_id text PRIMARY KEY,
    source_system text NOT NULL,
    loaded_at timestamptz NOT NULL DEFAULT now(),
    source_hash text NOT NULL,
    load_status text NOT NULL CHECK (load_status IN ('LOADING','READY','BLOCKED')),
    row_count bigint NOT NULL DEFAULT 0 CHECK (row_count >= 0),
    error_count bigint NOT NULL DEFAULT 0 CHECK (error_count >= 0)
);

CREATE TABLE supplier (
    supplier_id text PRIMARY KEY,
    supplier_name text,
    active boolean NOT NULL DEFAULT true
);

CREATE TABLE part (
    part_number text PRIMARY KEY,
    part_name text,
    safety_class text NOT NULL CHECK (safety_class IN ('SAFETY','MAJOR','CONVENIENCE','SOFTWARE')),
    commodity_group text
);

CREATE TABLE process (
    process_id text PRIMARY KEY,
    process_name text,
    plant_code text,
    line_code text
);

CREATE TABLE vehicle (
    vehicle_key text PRIMARY KEY,
    model text NOT NULL,
    production_at timestamptz NOT NULL,
    shipment_status text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE part_lot (
    lot_id text PRIMARY KEY,
    supplier_id text NOT NULL REFERENCES supplier(supplier_id),
    part_number text NOT NULL REFERENCES part(part_number),
    received_at timestamptz NOT NULL,
    quantity integer NOT NULL CHECK (quantity > 0),
    batch_id text NOT NULL REFERENCES data_load_batch(batch_id)
);

CREATE TABLE process_inspection (
    inspection_id text PRIMARY KEY,
    lot_id text NOT NULL REFERENCES part_lot(lot_id),
    process_id text NOT NULL REFERENCES process(process_id),
    measured_at timestamptz NOT NULL,
    process_z numeric(10,4) NOT NULL,
    recheck_rate numeric(8,6) NOT NULL CHECK (recheck_rate BETWEEN 0 AND 1),
    batch_id text NOT NULL REFERENCES data_load_batch(batch_id)
);

CREATE TABLE vehicle_part_installation (
    vehicle_key text NOT NULL REFERENCES vehicle(vehicle_key),
    lot_id text NOT NULL REFERENCES part_lot(lot_id),
    installed_at timestamptz,
    station_code text,
    batch_id text NOT NULL REFERENCES data_load_batch(batch_id),
    PRIMARY KEY (vehicle_key, lot_id)
);

CREATE TABLE warranty_claim (
    claim_id text PRIMARY KEY,
    vehicle_key text NOT NULL REFERENCES vehicle(vehicle_key),
    part_number text REFERENCES part(part_number),
    claim_at timestamptz NOT NULL,
    failure_code text NOT NULL,
    repair_cost_krw numeric(16,2) NOT NULL CHECK (repair_cost_krw >= 0),
    batch_id text NOT NULL REFERENCES data_load_batch(batch_id)
);

CREATE TABLE cost_policy (
    part_number text NOT NULL REFERENCES part(part_number),
    effective_from date NOT NULL,
    effective_to date,
    early_action_cost_krw numeric(16,2) NOT NULL CHECK (early_action_cost_krw >= 0),
    field_repair_cost_krw numeric(16,2) NOT NULL CHECK (field_repair_cost_krw >= 0),
    customer_compensation_krw numeric(16,2) NOT NULL CHECK (customer_compensation_krw >= 0),
    PRIMARY KEY (part_number, effective_from),
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE risk_assessment (
    assessment_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lot_id text NOT NULL REFERENCES part_lot(lot_id),
    assessed_at timestamptz NOT NULL DEFAULT now(),
    model_version text NOT NULL,
    risk_score numeric(8,6) NOT NULL CHECK (risk_score BETWEEN 0 AND 1),
    risk_level text NOT NULL CHECK (risk_level IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    risk_reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
    action_code text NOT NULL,
    estimated_prevented_vehicles numeric(14,2) CHECK (estimated_prevented_vehicles >= 0),
    estimated_avoided_loss_krw numeric(18,2),
    estimated_early_action_cost_krw numeric(18,2),
    estimated_net_benefit_krw numeric(18,2),
    estimated_direct_roi numeric(12,6),
    UNIQUE (lot_id, assessed_at, model_version)
);

CREATE TABLE affected_vehicle (
    assessment_id bigint NOT NULL REFERENCES risk_assessment(assessment_id) ON DELETE CASCADE,
    vehicle_key text NOT NULL REFERENCES vehicle(vehicle_key),
    lot_id text NOT NULL REFERENCES part_lot(lot_id),
    action_code text NOT NULL,
    PRIMARY KEY (assessment_id, vehicle_key, lot_id)
);

CREATE INDEX idx_part_lot_supplier_part ON part_lot(supplier_id, part_number);
CREATE INDEX idx_inspection_lot_time ON process_inspection(lot_id, measured_at DESC);
CREATE INDEX idx_installation_lot ON vehicle_part_installation(lot_id, vehicle_key);
CREATE INDEX idx_claim_vehicle_time ON warranty_claim(vehicle_key, claim_at DESC);
CREATE INDEX idx_risk_level_time ON risk_assessment(risk_level, assessed_at DESC);
CREATE INDEX idx_risk_lot_time ON risk_assessment(lot_id, assessed_at DESC);

CREATE VIEW latest_lot_risk AS
SELECT DISTINCT ON (lot_id)
       assessment_id, lot_id, assessed_at, model_version, risk_score, risk_level,
       action_code, estimated_net_benefit_krw, estimated_direct_roi
FROM risk_assessment
ORDER BY lot_id, assessed_at DESC, assessment_id DESC;

COMMIT;
