#!/usr/bin/env python3
"""End-to-end stress test for the VitalStream pipeline.

Clears mock data, seeds five test patients, streams scenario vitals into Kafka,
waits for Spark to score them, then validates Postgres, the REST API, and the
clinical rule engine.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

import psycopg2
from confluent_kafka import Producer
from psycopg2.extras import RealDictCursor

ROOT = Path(__file__).resolve().parents[1]
# Import local streamlit/common.py without shadowing the installed streamlit package.
sys.path.insert(0, str(ROOT / "streamlit"))

from common import (  # noqa: E402
    analyze_latest_vitals,
    build_likely_causes_summary,
    build_medical_narrative,
    build_plain_english_summary,
    filter_last_six_hours,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

API_BASE = "http://localhost:8000"
KAFKA_BOOTSTRAP = "localhost:9092"
KAFKA_TOPIC = "patient-vitals"

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "vitalstream",
    "user": "vitalstream",
    "password": "vitalstream",
}

NORMAL_VITALS = {
    "heart_rate": 72.0,
    "respiratory_rate": 16.0,
    "spo2": 98.0,
    "systolic_bp": 118.0,
    "temperature": 37.0,
}

TEST_PATIENTS = [
    {
        "patient_id": 99001,
        "full_name": "Sarah Mitchell",
        "room_number": "ICU-1",
        "sex": "F",
        "age": 67,
        "past_medical_conditions": ["COPD", "Hypertension"],
        "current_medications": ["salbutamol", "amlodipine"],
    },
    {
        "patient_id": 99002,
        "full_name": "James Okafor",
        "room_number": "ICU-2",
        "sex": "M",
        "age": 54,
        "past_medical_conditions": ["Diabetes", "Chronic Kidney Disease"],
        "current_medications": ["metformin", "furosemide"],
    },
    {
        "patient_id": 99003,
        "full_name": "Linda Park",
        "room_number": "ICU-3",
        "sex": "F",
        "age": 71,
        "past_medical_conditions": ["Heart Failure", "Atrial Fibrillation"],
        "current_medications": ["digoxin", "warfarin"],
    },
    {
        "patient_id": 99004,
        "full_name": "Tom Reynolds",
        "room_number": "ICU-4",
        "sex": "M",
        "age": 45,
        "past_medical_conditions": [],
        "current_medications": [],
    },
    {
        "patient_id": 99005,
        "full_name": "Emma Davies",
        "room_number": "ICU-5",
        "sex": "F",
        "age": 38,
        "past_medical_conditions": [],
        "current_medications": [],
    },
]

SCENARIO_NAMES = {
    99001: "Respiratory Failure",
    99002: "Sepsis Pattern",
    99003: "Cardiac Event",
    99004: "Stable Patient",
    99005: "False Alarm",
}

EXPECTATIONS = {
    99001: {"risk_level": "HIGH", "min_score": 7},
    99002: {"risk_level": "HIGH", "min_score": 7},
    99003: {"risk_level": "HIGH", "min_score": 7},
    99004: {"risk_level": "LOW", "max_score": 4},
    99005: {"risk_level": "LOW", "max_score": 4},
}


def now_local() -> datetime:
    return datetime.now().replace(microsecond=0)


def age_to_dob(age: int) -> date:
    return date.today() - timedelta(days=age * 365)


def lerp(start: float, end: float, step: int, total_steps: int) -> float:
    if total_steps <= 1:
        return end
    return start + (end - start) * step / (total_steps - 1)


def reset_database() -> None:
    logger.info("Clearing vitals_scores and replacing patients with test cohort")
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM vitals_scores")
            cur.execute("DELETE FROM patients")
            for patient in TEST_PATIENTS:
                cur.execute(
                    """
                    INSERT INTO patients (
                        patient_id,
                        full_name,
                        room_number,
                        date_of_birth,
                        sex,
                        past_medical_conditions,
                        current_medications
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        patient["patient_id"],
                        patient["full_name"],
                        patient["room_number"],
                        age_to_dob(patient["age"]),
                        patient["sex"],
                        patient["past_medical_conditions"],
                        patient["current_medications"],
                    ),
                )
        conn.commit()
    logger.info("Seeded patients 99001–99005")


def send_vitals(
    producer: Producer,
    patient_id: int,
    timestamp: datetime,
    vitals: dict[str, float],
) -> None:
    for vital_sign, value in vitals.items():
        payload = {
            "patient_id": str(patient_id),
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "vital_sign": vital_sign,
            "value": float(value),
        }
        producer.produce(
            topic=KAFKA_TOPIC,
            key=str(patient_id).encode("utf-8"),
            value=json.dumps(payload).encode("utf-8"),
        )
    producer.poll(0)


def scenario_respiratory_failure(
    producer: Producer,
    interval: float,
    total_minutes: int,
    stop_event: threading.Event,
) -> None:
    patient_id = 99001
    logger.info("Scenario 1 — Respiratory Failure — patient %s started", patient_id)
    for minute in range(total_minutes):
        if stop_event.is_set():
            return
        vitals = {
            "spo2": round(lerp(97, 84, minute, total_minutes - 1), 1),
            "respiratory_rate": round(lerp(18, 32, minute, total_minutes - 1), 1),
            "heart_rate": round(lerp(75, 125, minute, total_minutes - 1), 1),
            "systolic_bp": 118.0,
            "temperature": 37.1,
        }
        send_vitals(producer, patient_id, now_local(), vitals)
        if minute < total_minutes - 1:
            time.sleep(interval)
    logger.info("Scenario 1 — patient %s finished", patient_id)


def scenario_sepsis(
    producer: Producer,
    interval: float,
    total_minutes: int,
    stop_event: threading.Event,
) -> None:
    patient_id = 99002
    sepsis_minutes = min(12, total_minutes)
    logger.info("Scenario 2 — Sepsis Pattern — patient %s started", patient_id)
    for minute in range(sepsis_minutes):
        if stop_event.is_set():
            return
        vitals = {
            "temperature": round(lerp(37.0, 39.8, minute, sepsis_minutes - 1), 2),
            "heart_rate": round(lerp(80, 135, minute, sepsis_minutes - 1), 1),
            "systolic_bp": round(lerp(120, 88, minute, sepsis_minutes - 1), 1),
            "respiratory_rate": round(lerp(16, 26, minute, sepsis_minutes - 1), 1),
            "spo2": 96.0,
        }
        send_vitals(producer, patient_id, now_local(), vitals)
        if minute < sepsis_minutes - 1:
            time.sleep(interval)
    logger.info("Scenario 2 — patient %s finished", patient_id)


def scenario_cardiac(
    producer: Producer,
    interval: float,
    total_minutes: int,
    stop_event: threading.Event,
) -> None:
    patient_id = 99003
    cardiac_vitals = {
        "heart_rate": 145.0,
        "systolic_bp": 85.0,
        "spo2": 91.0,
        "respiratory_rate": 28.0,
        "temperature": 37.0,
    }
    logger.info("Scenario 3 — Cardiac Event — patient %s started", patient_id)
    send_vitals(producer, patient_id, now_local(), cardiac_vitals)
    for minute in range(1, min(5, total_minutes)):
        if stop_event.is_set():
            return
        send_vitals(producer, patient_id, now_local(), cardiac_vitals)
        time.sleep(interval)
    logger.info("Scenario 3 — patient %s finished", patient_id)


def scenario_stable(
    producer: Producer,
    interval: float,
    total_minutes: int,
    stop_event: threading.Event,
) -> None:
    patient_id = 99004
    logger.info("Scenario 4 — Stable Patient — patient %s started", patient_id)
    for minute in range(total_minutes):
        if stop_event.is_set():
            return
        send_vitals(producer, patient_id, now_local(), dict(NORMAL_VITALS))
        if minute < total_minutes - 1:
            time.sleep(interval)
    logger.info("Scenario 4 — patient %s finished", patient_id)


def scenario_false_alarm(
    producer: Producer,
    interval: float,
    total_minutes: int,
    stop_event: threading.Event,
) -> None:
    patient_id = 99005
    logger.info("Scenario 5 — False Alarm — patient %s started", patient_id)

    bad_vitals = dict(NORMAL_VITALS)
    bad_vitals["heart_rate"] = 140.0
    send_vitals(producer, patient_id, now_local(), bad_vitals)
    time.sleep(interval)

    if stop_event.is_set():
        return

    good_vitals = dict(NORMAL_VITALS)
    good_vitals["heart_rate"] = 75.0
    send_vitals(producer, patient_id, now_local(), good_vitals)

    for minute in range(2, total_minutes):
        if stop_event.is_set():
            return
        send_vitals(producer, patient_id, now_local(), dict(NORMAL_VITALS))
        time.sleep(interval)

    logger.info("Scenario 5 — patient %s finished", patient_id)


def run_scenarios(interval: float, total_minutes: int) -> None:
    producer = Producer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP,
            "client.id": "vitalstream-stress-test",
            "acks": "all",
        }
    )
    stop_event = threading.Event()

    threads = [
        threading.Thread(
            target=scenario_respiratory_failure,
            args=(producer, interval, total_minutes, stop_event),
            name="scenario-99001",
        ),
        threading.Thread(
            target=scenario_sepsis,
            args=(producer, interval, total_minutes, stop_event),
            name="scenario-99002",
        ),
        threading.Thread(
            target=scenario_cardiac,
            args=(producer, interval, total_minutes, stop_event),
            name="scenario-99003",
        ),
        threading.Thread(
            target=scenario_stable,
            args=(producer, interval, total_minutes, stop_event),
            name="scenario-99004",
        ),
        threading.Thread(
            target=scenario_false_alarm,
            args=(producer, interval, total_minutes, stop_event),
            name="scenario-99005",
        ),
    ]

    logger.info(
        "Starting 5 parallel scenarios (%s minutes apart, %s total minutes)",
        interval,
        total_minutes,
    )
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    producer.flush()
    logger.info("All vitals sent to Kafka topic %s", KAFKA_TOPIC)


def fetch_json(path: str) -> list | dict | None:
    url = f"{API_BASE}{path}"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning("API request failed for %s: %s", url, exc)
        return None


def query_latest_scores() -> dict[int, dict]:
    query = """
        SELECT DISTINCT ON (patient_id)
            patient_id,
            news2_score,
            risk_level,
            window_start
        FROM vitals_scores
        WHERE patient_id BETWEEN 99001 AND 99005
        ORDER BY patient_id, window_start DESC
    """
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()
    return {row["patient_id"]: dict(row) for row in rows}


def print_latest_scores(scores: dict[int, dict]) -> None:
    print("\n=== Check 1: Latest vitals_scores (Postgres) ===")
    for patient_id in sorted(scores):
        row = scores[patient_id]
        name = SCENARIO_NAMES[patient_id]
        print(
            f"  Patient {patient_id} ({name}): "
            f"NEWS2={row['news2_score']}, risk={row['risk_level']}, "
            f"window={row['window_start']}"
        )
    missing = [pid for pid in SCENARIO_NAMES if pid not in scores]
    if missing:
        print(f"  WARNING: no scores yet for patients {missing}")


def print_active_patients() -> None:
    print("\n=== Check 2: GET /api/patients/active ===")
    data = fetch_json("/api/patients/active")
    if data is None:
        print("  ERROR: could not reach API")
        return
    print(json.dumps(data, indent=2, default=str))


def print_patient_profile(patient_id: int = 99001) -> None:
    print(f"\n=== Check 3: GET /api/patients/{patient_id}/profile ===")
    data = fetch_json(f"/api/patients/{patient_id}/profile")
    if data is None:
        print("  ERROR: could not reach API")
        return
    print(json.dumps(data, indent=2, default=str))


def print_clinical_analysis(patient_id: int) -> None:
    name = SCENARIO_NAMES[patient_id]
    print(f"\n=== Check 4: Rule engine — Patient {patient_id} ({name}) ===")

    profile = fetch_json(f"/api/patients/{patient_id}/profile")
    history = fetch_json(f"/api/patients/{patient_id}/vitals-history")
    if not isinstance(profile, dict) or not isinstance(history, list):
        print("  ERROR: could not load profile or history from API")
        return

    df = filter_last_six_hours(history)
    if df.empty:
        print("  WARNING: no vitals history in the last 6 hours")
        return

    assessments = analyze_latest_vitals(df, profile)
    problems = [item for item in assessments if item["score"] > 0]

    print("  Abnormal vitals:")
    if not problems:
        print("    (none — all within normal range)")
    for assessment in problems:
        print(
            f"    - {assessment['label']}: {assessment['problem']} "
            f"(trend: {assessment['trend'] or 'stable'})"
        )
        if assessment.get("causes"):
            print(f"      {assessment['causes']}")

    print("  Trends:")
    for assessment in assessments:
        trend = assessment["trend"] or "stable"
        print(f"    - {assessment['label']}: {trend}")

    causes = build_likely_causes_summary(problems)
    print(f"  Guessed causes: {causes or '(none)'}")
    print(f"  Plain English: {build_plain_english_summary(problems) or '(none)'}")
    print(f"  Medical narrative: {build_medical_narrative(problems) or '(none)'}")


def evaluate_scenario(patient_id: int, scores: dict[int, dict]) -> str:
    expected = EXPECTATIONS[patient_id]
    name = SCENARIO_NAMES[patient_id]

    if patient_id not in scores:
        return f"FAIL — {name} (patient {patient_id}): no score in Postgres"

    actual = scores[patient_id]
    score = actual["news2_score"]
    risk = str(actual["risk_level"]).upper()
    ok = risk == expected["risk_level"]

    if "min_score" in expected:
        ok = ok and score >= expected["min_score"]
    if "max_score" in expected:
        ok = ok and score <= expected["max_score"]

    if ok:
        return f"PASS — {name} (patient {patient_id}): score={score}, risk={risk}"

    detail = []
    if risk != expected["risk_level"]:
        detail.append(f"expected risk {expected['risk_level']}, got {risk}")
    if "min_score" in expected and score < expected["min_score"]:
        detail.append(f"expected score >= {expected['min_score']}, got {score}")
    if "max_score" in expected and score > expected["max_score"]:
        detail.append(f"expected score <= {expected['max_score']}, got {score}")
    return (
        f"FAIL — {name} (patient {patient_id}): score={score}, risk={risk} "
        f"({'; '.join(detail)})"
    )


def run_checks() -> list[str]:
    scores = query_latest_scores()
    print_latest_scores(scores)
    print_active_patients()
    print_patient_profile(99001)
    print_clinical_analysis(99001)
    print_clinical_analysis(99003)

    print("\n=== Scenario Results ===")
    results = [evaluate_scenario(patient_id, scores) for patient_id in sorted(SCENARIO_NAMES)]
    for result in results:
        print(f"  {result}")
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="VitalStream end-to-end stress test")
    parser.add_argument(
        "--interval",
        type=float,
        default=60.0,
        help="Seconds between readings (default: 60)",
    )
    parser.add_argument(
        "--minutes",
        type=int,
        default=21,
        help="Minutes to run gradual scenarios (default: 21, covers minute-20 HIGH)",
    )
    parser.add_argument(
        "--settle",
        type=int,
        default=120,
        help="Seconds to wait for Spark after sending completes (default: 120)",
    )
    parser.add_argument(
        "--skip-send",
        action="store_true",
        help="Skip Kafka seeding and only run validation checks",
    )
    parser.add_argument(
        "--skip-reset",
        action="store_true",
        help="Do not clear vitals_scores / patients before sending",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.skip_send:
        if not args.skip_reset:
            reset_database()
        run_scenarios(interval=args.interval, total_minutes=args.minutes)
        logger.info("Waiting %s seconds for Spark pipeline to settle", args.settle)
        time.sleep(args.settle)

    results = run_checks()
    failures = [result for result in results if result.startswith("FAIL")]
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
