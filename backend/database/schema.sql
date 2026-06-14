CREATE TABLE IF NOT EXISTS vitals_scores (
    patient_id       INTEGER NOT NULL,
    window_start     TIMESTAMP NOT NULL,
    news2_score      INTEGER NOT NULL,
    risk_level       TEXT NOT NULL,
    heart_rate       DOUBLE PRECISION,
    respiratory_rate DOUBLE PRECISION,
    spo2             DOUBLE PRECISION,
    systolic_bp      DOUBLE PRECISION,
    temperature      DOUBLE PRECISION,
    created_at       TIMESTAMP NOT NULL DEFAULT NOW()
);
