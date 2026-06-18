from datetime import date, datetime, timedelta, timezone
from typing import Any

import ollama
from psycopg2.extras import RealDictCursor

from backend.database.postgres import get_connection

MODEL = "llama3"


def fahrenheit_to_celsius(f: float) -> float:
    return round((f - 32) * 5 / 9, 1)


def _compute_age(dob: date | None) -> int | None:
    if dob is None:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _format_vitals_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No vitals recorded in the last 6 hours."
    lines = [
        "Time | HR | RR | SpO2 | SBP | Temp(°C) | NEWS2 | Risk",
        "-----|----|----|------|-----|----------|-------|-----",
    ]
    for row in rows:
        temp = row.get("temperature")
        if temp is not None:
            temp = fahrenheit_to_celsius(float(temp))
        lines.append(
            f"{row['window_start']} | {row.get('heart_rate', '—')} | "
            f"{row.get('respiratory_rate', '—')} | {row.get('spo2', '—')} | "
            f"{row.get('systolic_bp', '—')} | {temp if temp is not None else '—'} | "
            f"{row.get('news2_score', '—')} | {row.get('risk_level', '—')}"
        )
    return "\n".join(lines)


def _build_prompt(profile: dict, vitals_rows: list[dict], news2_score, risk_level: str) -> str:
    conditions = ", ".join(profile.get("past_medical_conditions") or []) or "none documented"
    medications = ", ".join(profile.get("current_medications") or []) or "none documented"
    age = _compute_age(profile.get("date_of_birth"))
    age_text = f"{age} years old" if age is not None else "age unknown"
    sex = profile.get("sex") or "unknown"

    return (
        "You are a clinical decision support AI helping ICU doctors. "
        f"Patient background: {age_text}, {sex}, {conditions}, {medications}. "
        f"Their vitals over the last 6 hours:\n{_format_vitals_table(vitals_rows)}\n"
        f"Current NEWS2 score: {news2_score} - {risk_level}. "
        "In 2-3 sentences, explain what might be happening clinically "
        "and what the doctor should check first."
    )


def get_llm_analysis(patient_id: int) -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=6)

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    patient_id, full_name, date_of_birth, sex,
                    past_medical_conditions, current_medications
                FROM patients
                WHERE patient_id = %s
                """,
                (patient_id,),
            )
            profile = cur.fetchone()
            if profile is None:
                raise ValueError(f"Patient {patient_id} not found")

            cur.execute(
                """
                SELECT
                    window_start, news2_score, risk_level,
                    heart_rate, respiratory_rate, spo2,
                    systolic_bp, temperature
                FROM vitals_scores
                WHERE patient_id = %s
                  AND window_start >= %s
                ORDER BY window_start ASC
                """,
                (patient_id, cutoff),
            )
            vitals_rows = [dict(row) for row in cur.fetchall()]

    latest = vitals_rows[-1] if vitals_rows else {}
    news2_score = latest.get("news2_score", "—")
    risk_level = str(latest.get("risk_level", "UNKNOWN")).upper()

    prompt = _build_prompt(dict(profile), vitals_rows, news2_score, risk_level)

    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response["message"]["content"]
