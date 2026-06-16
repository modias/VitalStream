from typing import Any

from fastapi import FastAPI
from psycopg2.extras import RealDictCursor

from backend.database.postgres import get_connection

app = FastAPI()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/patients/active")
def active_patients() -> list[dict[str, Any]]:
    query = """
        SELECT DISTINCT ON (v.patient_id)
            v.patient_id,
            p.full_name,
            v.news2_score,
            v.risk_level,
            v.window_start,
            p.room_number
        FROM vitals_scores v
        INNER JOIN patients p ON p.patient_id = v.patient_id
        ORDER BY v.patient_id, v.window_start DESC
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()

    return [dict(row) for row in rows]


@app.get("/api/patients/{patient_id}/vitals-history")
def patient_vitals_history(patient_id: int) -> list[dict[str, Any]]:
    query = """
        SELECT
            patient_id,
            window_start,
            news2_score,
            risk_level,
            heart_rate,
            respiratory_rate,
            spo2,
            systolic_bp,
            temperature,
            created_at
        FROM vitals_scores
        WHERE patient_id = %s
        ORDER BY window_start ASC
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (patient_id,))
            rows = cur.fetchall()

    return [dict(row) for row in rows]


@app.get("/api/patients/{patient_id}/profile")
def patient_profile(patient_id: int) -> dict[str, Any]:
    query = """
        SELECT
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
            occupation,
            updated_at
        FROM patients
        WHERE patient_id = %s
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (patient_id,))
            row = cur.fetchone()

    if row is None:
        return {"patient_id": patient_id, "found": False}

    profile = dict(row)
    profile["found"] = True
    if profile.get("date_of_birth") is not None:
        profile["date_of_birth"] = profile["date_of_birth"].isoformat()
    if profile.get("updated_at") is not None:
        profile["updated_at"] = profile["updated_at"].isoformat()
    return profile
