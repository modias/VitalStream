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
        SELECT DISTINCT ON (patient_id)
            patient_id,
            news2_score,
            risk_level,
            window_start
        FROM vitals_scores
        ORDER BY patient_id, window_start DESC
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
