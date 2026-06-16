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

CREATE TABLE IF NOT EXISTS patients (
    patient_id              INTEGER PRIMARY KEY,
    full_name               TEXT NOT NULL,
    room_number             TEXT,
    date_of_birth           DATE,
    sex                     TEXT,
    allergies               TEXT[] NOT NULL DEFAULT '{}',
    past_medical_conditions TEXT[] NOT NULL DEFAULT '{}',
    medical_history         TEXT,
    current_medications     TEXT[] NOT NULL DEFAULT '{}',
    home_address            TEXT,
    occupation              TEXT,
    updated_at              TIMESTAMP NOT NULL DEFAULT NOW()
);

ALTER TABLE patients ADD COLUMN IF NOT EXISTS room_number TEXT;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS home_address TEXT;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS occupation TEXT;

INSERT INTO patients (
    patient_id,
    full_name,
    room_number,
    date_of_birth,
    sex,
    allergies,
    past_medical_conditions,
    medical_history,
    current_medications,
    home_address,
    occupation
) VALUES
(
    101,
    'John Doe',
    '4A-12',
    '1965-03-12',
    'M',
    ARRAY['Penicillin — anaphylaxis'],
    ARRAY['Hypertension', 'Type 2 diabetes'],
    'Former smoker (quit 2018). Admitted for routine post-operative monitoring. No prior ICU stays.',
    ARRAY['Metformin 500mg BD', 'Lisinopril 10mg OD'],
    '42 Oak Lane, Manchester M14 5AB',
    'Retired civil engineer'
),
(
    102,
    'Maria Garcia',
    '4A-15',
    '1978-07-22',
    'F',
    ARRAY['Latex — contact dermatitis', 'Sulfa drugs — rash'],
    ARRAY['COPD', 'Asthma', 'Hypertension'],
    'Long-standing COPD on home oxygen. Prior hospital admission 2024 for exacerbation. Lives alone.',
    ARRAY['Salbutamol inhaler PRN', 'Tiotropium 18mcg OD', 'Amlodipine 5mg OD'],
    '15 Birch Court, Flat 3, Salford M6 8TT',
    'Primary school teacher (on sick leave)'
),
(
    103,
    'Robert Chen',
    '4B-03',
    '1952-11-03',
    'M',
    ARRAY['Aspirin — GI bleed'],
    ARRAY['Coronary artery disease', 'Heart failure (NYHA II)', 'Chronic kidney disease stage 3'],
    'CABG 2019. Prior ICU admission 2023 for pneumonia. Current smoker — 30 pack-years.',
    ARRAY['Atorvastatin 40mg OD', 'Carvedilol 6.25mg BD', 'Furosemide 40mg OD'],
    '88 Cedar Road, Stockport SK4 2NW',
    'Self-employed taxi driver'
)
ON CONFLICT (patient_id) DO NOTHING;

UPDATE patients SET room_number = '4A-12' WHERE patient_id = 101 AND room_number IS NULL;
UPDATE patients SET room_number = '4A-15' WHERE patient_id = 102 AND room_number IS NULL;
UPDATE patients SET room_number = '4B-03' WHERE patient_id = 103 AND room_number IS NULL;
UPDATE patients SET home_address = '42 Oak Lane, Manchester M14 5AB', occupation = 'Retired civil engineer' WHERE patient_id = 101;
UPDATE patients SET home_address = '15 Birch Court, Flat 3, Salford M6 8TT', occupation = 'Primary school teacher (on sick leave)' WHERE patient_id = 102;
UPDATE patients SET home_address = '88 Cedar Road, Stockport SK4 2NW', occupation = 'Self-employed taxi driver' WHERE patient_id = 103;
