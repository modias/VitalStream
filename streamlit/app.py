import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import altair as alt
import pandas as pd
import streamlit as st

API_BASE = "http://localhost:8000"
REFRESH_SECONDS = 5

VITAL_RANGES = {
    "heart_rate": {"label": "Heart Rate (bpm)", "low": 60, "high": 100},
    "respiratory_rate": {"label": "Resp Rate (/min)", "low": 12, "high": 20},
    "spo2": {"label": "SpO₂ (%)", "low": 95, "high": 100},
    "systolic_bp": {"label": "Systolic BP (mmHg)", "low": 90, "high": 140},
    "temperature": {"label": "Temperature (°C)", "low": 36.1, "high": 37.2},
}

RISK_STYLES = {
    "LOW": {"bg": "#d4edda", "color": "#155724", "border": "#28a745"},
    "MEDIUM": {"bg": "#fff3cd", "color": "#856404", "border": "#fd7e14"},
    "HIGH": {"bg": "#f8d7da", "color": "#721c24", "border": "#dc3545"},
}

SEVERITY_CHART_COLORS = {
    "normal": "#2563eb",
    "warning": "#fd7e14",
    "critical": "#dc3545",
}

MOCK_PATIENT_PROFILES = {
    101: {
        "news2_score": 2,
        "risk_level": "LOW",
        "vitals": {
            "heart_rate": 72,
            "respiratory_rate": 16,
            "spo2": 98,
            "systolic_bp": 118,
            "temperature": 36.8,
        },
        "trends": {
            "heart_rate": 0.3,
            "respiratory_rate": 0.1,
            "spo2": -0.05,
            "systolic_bp": 0.2,
            "temperature": 0.02,
        },
    },
    102: {
        "news2_score": 5,
        "risk_level": "MEDIUM",
        "vitals": {
            "heart_rate": 98,
            "respiratory_rate": 22,
            "spo2": 94,
            "systolic_bp": 105,
            "temperature": 37.8,
        },
        "trends": {
            "heart_rate": 0.5,
            "respiratory_rate": 0.2,
            "spo2": -0.15,
            "systolic_bp": -0.3,
            "temperature": 0.05,
        },
    },
    103: {
        "news2_score": 8,
        "risk_level": "HIGH",
        "vitals": {
            "heart_rate": 118,
            "respiratory_rate": 26,
            "spo2": 91,
            "systolic_bp": 88,
            "temperature": 38.5,
        },
        "trends": {
            "heart_rate": 0.8,
            "respiratory_rate": 0.4,
            "spo2": -0.25,
            "systolic_bp": -0.5,
            "temperature": 0.08,
        },
    },
}

MOCK_PATIENT_CHARTS = {
    101: {
        "patient_id": 101,
        "full_name": "John Doe",
        "room_number": "4A-12",
        "date_of_birth": "1965-03-12",
        "sex": "M",
        "allergies": ["Penicillin — anaphylaxis"],
        "past_medical_conditions": ["Hypertension", "Type 2 diabetes"],
        "medical_history": (
            "Former smoker (quit 2018). Admitted for routine post-operative monitoring. "
            "No prior ICU stays."
        ),
        "current_medications": ["Metformin 500mg BD", "Lisinopril 10mg OD"],
        "home_address": "42 Oak Lane, Manchester M14 5AB",
        "occupation": "Retired civil engineer",
    },
    102: {
        "patient_id": 102,
        "full_name": "Maria Garcia",
        "room_number": "4A-15",
        "date_of_birth": "1978-07-22",
        "sex": "F",
        "allergies": ["Latex — contact dermatitis", "Sulfa drugs — rash"],
        "past_medical_conditions": ["COPD", "Asthma", "Hypertension"],
        "medical_history": (
            "Long-standing COPD on home oxygen. Prior hospital admission 2024 for "
            "exacerbation. Lives alone."
        ),
        "current_medications": [
            "Salbutamol inhaler PRN",
            "Tiotropium 18mcg OD",
            "Amlodipine 5mg OD",
        ],
        "home_address": "15 Birch Court, Flat 3, Salford M6 8TT",
        "occupation": "Primary school teacher (on sick leave)",
    },
    103: {
        "patient_id": 103,
        "full_name": "Robert Chen",
        "room_number": "4B-03",
        "date_of_birth": "1952-11-03",
        "sex": "M",
        "allergies": ["Aspirin — GI bleed"],
        "past_medical_conditions": [
            "Coronary artery disease",
            "Heart failure (NYHA II)",
            "Chronic kidney disease stage 3",
        ],
        "medical_history": (
            "CABG 2019. Prior ICU admission 2023 for pneumonia. Current smoker — 30 pack-years."
        ),
        "current_medications": [
            "Atorvastatin 40mg OD",
            "Carvedilol 6.25mg BD",
            "Furosemide 40mg OD",
        ],
        "home_address": "88 Cedar Road, Stockport SK4 2NW",
        "occupation": "Self-employed taxi driver",
    },
}


def get_mock_active_patients() -> list[dict]:
    now = datetime.now(timezone.utc)
    return [
        {
            "patient_id": patient_id,
            "room_number": MOCK_PATIENT_CHARTS.get(patient_id, {}).get("room_number"),
            "news2_score": profile["news2_score"],
            "risk_level": profile["risk_level"],
            "window_start": (now - timedelta(minutes=5 * index)).isoformat(),
        }
        for index, (patient_id, profile) in enumerate(MOCK_PATIENT_PROFILES.items())
    ]


def get_mock_patient_history(patient_id: int) -> list[dict]:
    profile = MOCK_PATIENT_PROFILES.get(patient_id)
    if profile is None:
        return []

    now = datetime.now(timezone.utc)
    history = []
    for step in range(12):
        window_start = now - timedelta(minutes=30 * (11 - step))
        offset = step - 6
        history.append({
            "patient_id": patient_id,
            "window_start": window_start.isoformat(),
            "news2_score": profile["news2_score"],
            "risk_level": profile["risk_level"],
            "heart_rate": round(profile["vitals"]["heart_rate"] + profile["trends"]["heart_rate"] * offset, 1),
            "respiratory_rate": round(
                profile["vitals"]["respiratory_rate"] + profile["trends"]["respiratory_rate"] * offset, 1
            ),
            "spo2": round(profile["vitals"]["spo2"] + profile["trends"]["spo2"] * offset, 1),
            "systolic_bp": round(profile["vitals"]["systolic_bp"] + profile["trends"]["systolic_bp"] * offset, 1),
            "temperature": round(profile["vitals"]["temperature"] + profile["trends"]["temperature"] * offset, 2),
            "created_at": window_start.isoformat(),
        })
    return history


def fetch_json(url: str) -> list | dict | None:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None


def use_mock_data() -> bool:
    return st.session_state.get("use_mock_data", False)


def fetch_active_patients() -> list[dict]:
    if use_mock_data():
        return get_mock_active_patients()

    data = fetch_json(f"{API_BASE}/api/patients/active")
    return data if isinstance(data, list) else []


def fetch_patient_history(patient_id: int) -> list[dict]:
    if use_mock_data():
        return get_mock_patient_history(patient_id)

    data = fetch_json(f"{API_BASE}/api/patients/{patient_id}/vitals-history")
    return data if isinstance(data, list) else []


def fetch_patient_profile(patient_id: int) -> dict | None:
    if use_mock_data():
        return MOCK_PATIENT_CHARTS.get(patient_id)

    data = fetch_json(f"{API_BASE}/api/patients/{patient_id}/profile")
    if not isinstance(data, dict) or not data.get("found", True):
        return None
    return data


def format_timestamp(value) -> str:
    if value is None:
        return "—"
    ts = pd.to_datetime(value, utc=True)
    return ts.strftime("%Y-%m-%d %H:%M:%S UTC")


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .vitalstream-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.5rem 0 1rem 0;
            border-bottom: 2px solid #e0e0e0;
            margin-bottom: 1.5rem;
        }
        .vitalstream-title {
            font-size: 2rem;
            font-weight: 700;
            color: #1a1a2e;
            margin: 0;
        }
        .vitalstream-time {
            font-size: 1rem;
            color: #666;
        }
        .patient-card {
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 1rem;
            margin-bottom: 0.75rem;
            background: #fafafa;
            transition: box-shadow 0.2s;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.patient-card-box) {
            border: 1px solid #ddd !important;
            border-radius: 10px !important;
            padding: 1rem !important;
            margin-bottom: 0.75rem;
            background: #fafafa !important;
            transition: box-shadow 0.2s;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.patient-card-box):hover {
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.patient-card-high-risk) {
            border: 2px solid #dc3545 !important;
            animation: pulse-border 1.5s ease-in-out infinite;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.patient-card-box)
            div[data-testid="stHorizontalBlock"]:first-of-type
            div[data-testid="column"]:last-child button {
            width: 2rem;
            height: 2rem;
            min-height: 2rem;
            padding: 0;
            border-radius: 50%;
            border: 1px solid #2563eb;
            color: #2563eb;
            background: #fff;
            font-weight: 700;
            font-size: 0.95rem;
            line-height: 1;
            float: right;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.patient-card-box)
            div[data-testid="stHorizontalBlock"]:first-of-type
            div[data-testid="column"]:last-child button:hover {
            background: #eff6ff;
            border-color: #1d4ed8;
            color: #1d4ed8;
        }
        .patient-card:hover {
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .patient-card.high-risk {
            border: 2px solid #dc3545;
            animation: pulse-border 1.5s ease-in-out infinite;
        }
        @keyframes pulse-border {
            0%, 100% { box-shadow: 0 0 0 0 rgba(220, 53, 69, 0.6); }
            50% { box-shadow: 0 0 0 10px rgba(220, 53, 69, 0); }
        }
        .risk-badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.85rem;
            text-transform: uppercase;
        }
        .patient-id-label {
            font-size: 0.85rem;
            color: #666;
            margin: 0;
        }
        .patient-id-value {
            font-size: 1.2rem;
            font-weight: 600;
            margin: 0;
            color: #1a1a2e;
        }
        .patient-room-label {
            font-size: 0.85rem;
            color: #666;
            margin: 0.5rem 0 0 0;
        }
        .patient-room-value {
            font-size: 1rem;
            font-weight: 600;
            margin: 0;
            color: #1a1a2e;
        }
        .news2-line {
            margin: 0.75rem 0 0.5rem 0;
            font-size: 0.85rem;
            font-weight: 600;
            color: #999;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        .news2-line .news2-value {
            font-size: 1.15rem;
            font-weight: 700;
        }
        .updated-label {
            font-size: 0.8rem;
            color: #888;
            margin-top: 0.5rem;
        }
        .vital-problem {
            font-size: 0.78rem;
            font-weight: 600;
            margin-top: 0.5rem;
            padding: 0.35rem 0.5rem;
            border-radius: 6px;
        }
        .vital-problem.critical {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #dc3545;
        }
        .vital-problem.warning {
            background: #fff3cd;
            color: #856404;
            border: 1px solid #fd7e14;
        }
        .vital-problem.normal {
            background: #d4edda;
            color: #155724;
            border: 1px solid #28a745;
        }
        .vital-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.25rem;
        }
        .vital-label {
            font-size: 0.8rem;
            color: #666;
        }
        .vital-value-row {
            font-size: 0.95rem;
        }
        .vital-value-row.warning strong { color: #fd7e14; }
        .vital-value-row.critical strong { color: #dc3545; }
        .vital-trend {
            font-size: 1.1rem;
            font-weight: 700;
            margin-left: 0.35rem;
        }
        .vital-trend.improving { color: #28a745; }
        .vital-trend.worsening  { color: #dc3545; }
        .vital-trend.worsening-warning { color: #fd7e14; }
        .vital-trend.stable     { color: #999; }
        .problems-panel {
            border: 1px solid #dc3545;
            border-radius: 10px;
            padding: 1rem 1.25rem;
            background: #fff5f5;
            margin-bottom: 1.25rem;
        }
        .problems-panel h4 {
            color: #721c24;
            margin: 0 0 0.75rem 0;
        }
        .problems-panel ul {
            margin: 0;
            padding-left: 1.25rem;
        }
        .problems-panel li {
            margin-bottom: 0.35rem;
            color: #333;
        }
        .problem-cause {
            display: block;
            margin-top: 0.15rem;
            font-size: 0.82rem;
            color: #555;
            font-style: italic;
        }
        .profile-screen {
            border: 1px solid #ddd;
            border-radius: 12px;
            padding: 1.5rem 2rem;
            background: #fafafa;
            margin-bottom: 1.5rem;
        }
        .profile-screen h2 {
            margin: 0 0 0.25rem 0;
            color: #1a1a2e;
        }
        .profile-meta {
            color: #666;
            font-size: 0.95rem;
            margin-bottom: 1.5rem;
        }
        .profile-section {
            background: #fff;
            border: 1px solid #e8e8e8;
            border-radius: 10px;
            padding: 1rem 1.25rem;
            margin-bottom: 1rem;
        }
        .profile-section h4 {
            margin: 0 0 0.75rem 0;
            color: #1a1a2e;
            font-size: 1rem;
        }
        .profile-section.allergies {
            border-color: #dc3545;
            background: #fff8f8;
        }
        .profile-section.allergies h4 {
            color: #721c24;
        }
        .profile-section ul {
            margin: 0;
            padding-left: 1.25rem;
        }
        .profile-section li {
            margin-bottom: 0.35rem;
            color: #333;
        }
        .profile-empty {
            color: #888;
            font-style: italic;
            margin: 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.markdown(
        f"""
        <div class="vitalstream-header">
            <p class="vitalstream-title">VitalStream</p>
            <p class="vitalstream-time">{now}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_patient_card(patient: dict) -> None:
    risk = patient.get("risk_level", "LOW").upper()
    style = RISK_STYLES.get(risk, RISK_STYLES["LOW"])
    patient_id = patient["patient_id"]
    room_number = patient.get("room_number") or "—"
    news2 = patient.get("news2_score", "—")
    updated = format_timestamp(patient.get("window_start"))
    risk_marker = "patient-card-high-risk" if risk == "HIGH" else ""

    with st.container(border=True):
        st.markdown(
            f'<span class="patient-card-box {risk_marker}" style="display:none"></span>',
            unsafe_allow_html=True,
        )
        id_col, info_col = st.columns([5, 1])
        with id_col:
            st.markdown(
                f'<p class="patient-id-label">Patient ID</p>'
                f'<p class="patient-id-value">{patient_id}</p>'
                f'<p class="patient-room-label">Room</p>'
                f'<p class="patient-room-value">{room_number}</p>',
                unsafe_allow_html=True,
            )
        with info_col:
            if st.button(
                "ℹ",
                key=f"profile_{patient_id}",
                help="View patient background & medical history",
            ):
                st.session_state.detail_patient_id = patient_id
                st.switch_page("pages/patient_detail.py")

        st.markdown(
            f"""
            <p class="news2-line">
                NEWS2 SCORE:
                <span class="news2-value" style="color:{style['border']};">{news2}</span>
            </p>
            <span class="risk-badge" style="background:{style['bg']};
                color:{style['color']};border:1px solid {style['border']};">
                {risk}
            </span>
            <p class="updated-label">Last updated: {updated}</p>
            """,
            unsafe_allow_html=True,
        )

        if st.button("View Details", key=f"patient_{patient_id}", width="stretch"):
            st.session_state.selected_patient_id = patient_id
            st.rerun()


def render_demo_banner() -> None:
    if use_mock_data():
        st.info("Demo mode — showing mock patient data.")


def render_ward_view(patients: list[dict]) -> None:
    st.subheader("Ward View")

    if not patients:
        st.info("No active patients. Enable demo mode or start the producer and processor.")
        return

    cols = st.columns(3)
    for index, patient in enumerate(patients):
        with cols[index % 3]:
            render_patient_card(patient)


def filter_last_six_hours(history: list[dict]) -> pd.DataFrame:
    if not history:
        return pd.DataFrame()

    df = pd.DataFrame(history)
    df["window_start"] = pd.to_datetime(df["window_start"], utc=True)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
    return df[df["window_start"] >= cutoff].sort_values("window_start")


def assess_heart_rate(value: float) -> tuple[int, str | None]:
    if value <= 40:
        return 3, "Severe bradycardia — heart rate critically low"
    if value <= 50:
        return 1, "Bradycardia — heart rate below normal"
    if value <= 90:
        return 0, None
    if value <= 110:
        return 1, "Mild tachycardia — heart rate elevated"
    if value <= 130:
        return 2, "Tachycardia — heart rate significantly elevated"
    return 3, "Severe tachycardia — heart rate critically high"


def assess_respiratory_rate(value: float) -> tuple[int, str | None]:
    if value <= 8:
        return 3, "Bradypnea — breathing critically slow"
    if value <= 11:
        return 1, "Low respiratory rate — below normal"
    if value <= 20:
        return 0, None
    if value <= 24:
        return 2, "Tachypnea — breathing too fast"
    return 3, "Severe tachypnea — respiratory rate critically high"


def assess_spo2(value: float) -> tuple[int, str | None]:
    if value <= 91:
        return 3, "Hypoxemia — oxygen saturation critically low"
    if value <= 93:
        return 2, "Low SpO₂ — oxygen saturation significantly reduced"
    if value <= 95:
        return 1, "Mild hypoxemia — oxygen saturation below normal"
    return 0, None


def assess_systolic_bp(value: float) -> tuple[int, str | None]:
    if value <= 90:
        return 3, "Hypotension — systolic BP critically low"
    if value <= 100:
        return 2, "Low blood pressure — systolic BP significantly reduced"
    if value <= 110:
        return 1, "Mild hypotension — systolic BP below normal"
    if value <= 219:
        return 0, None
    return 3, "Hypertensive crisis — systolic BP critically high"


def assess_temperature(value: float) -> tuple[int, str | None]:
    if value <= 35.0:
        return 3, "Hypothermia — body temperature critically low"
    if value <= 36.0:
        return 1, "Low temperature — below normal range"
    if value <= 38.0:
        return 0, None
    if value <= 39.0:
        return 1, "Fever — body temperature elevated"
    return 2, "High fever — body temperature significantly elevated"


VITAL_ASSESSORS = {
    "heart_rate": assess_heart_rate,
    "respiratory_rate": assess_respiratory_rate,
    "spo2": assess_spo2,
    "systolic_bp": assess_systolic_bp,
    "temperature": assess_temperature,
}


def profile_context(profile: dict | None) -> dict[str, str]:
    if not profile:
        return {"conditions": "", "history": "", "medications": ""}
    return {
        "conditions": " ".join(profile.get("past_medical_conditions") or []).lower(),
        "history": (profile.get("medical_history") or "").lower(),
        "medications": " ".join(profile.get("current_medications") or []).lower(),
    }


def _has_term(ctx: dict[str, str], *terms: str) -> bool:
    blob = " ".join(ctx.values())
    return any(term.lower() in blob for term in terms)


def _abnormal_columns(assessments: list[dict]) -> set[str]:
    return {a["column"] for a in assessments if a["score"] > 0}


def infer_likely_causes(
    column: str,
    value: float,
    score: int,
    profile: dict | None,
    assessments: list[dict],
) -> str | None:
    if score == 0:
        return None

    ctx = profile_context(profile)
    abnormal = _abnormal_columns(assessments)
    causes: list[str] = []

    has_fever = "temperature" in abnormal
    has_hypoxia = "spo2" in abnormal
    has_hypotension = "systolic_bp" in abnormal
    multi_system = len(abnormal) >= 3

    if column == "temperature":
        if value > 38.0:
            causes.extend(["infection", "viral illness (e.g. cold or flu)", "sepsis"])
            if _has_term(ctx, "pneumonia", "copd", "smok"):
                causes.append("respiratory infection")
        else:
            causes.extend(["exposure to cold", "hypothermia", "sepsis with shock"])

    elif column == "heart_rate":
        if value > 90:
            if has_fever or multi_system:
                causes.append("infection or sepsis")
            causes.extend(["pain or anxiety", "dehydration"])
            if _has_term(ctx, "heart failure", "cabg", "coronary"):
                causes.append("heart failure decompensation")
            if _has_term(ctx, "copd", "asthma"):
                causes.append("respiratory distress")
        else:
            causes.extend(["medication effect", "heart block", "hypothermia"])
            if _has_term(ctx, "carvedilol", "beta"):
                causes.insert(0, "beta-blocker effect")

    elif column == "respiratory_rate":
        if value > 20:
            if has_fever:
                causes.append("pneumonia or chest infection")
            if _has_term(ctx, "copd", "asthma"):
                causes.extend(["COPD exacerbation", "bronchospasm"])
            causes.extend(["anxiety", "pain", "metabolic acidosis"])
            if has_hypoxia:
                causes.append("hypoxia-driven breathing")
        else:
            causes.extend(["sedation", "neurological injury", "respiratory fatigue"])

    elif column == "spo2":
        if _has_term(ctx, "copd", "asthma"):
            causes.extend(["COPD exacerbation", "mucus plugging"])
        if _has_term(ctx, "smok", "pneumonia"):
            causes.append("pneumonia")
        causes.extend(["pneumonia", "fluid in lungs", "atelectasis"])
        if has_fever:
            causes.insert(0, "infection")

    elif column == "systolic_bp":
        if value <= 110:
            if has_fever and multi_system:
                causes.insert(0, "septic shock")
            causes.extend(["dehydration", "blood loss", "medication effect"])
            if _has_term(ctx, "furosemide", "diuretic"):
                causes.insert(0, "diuretic effect")
            if _has_term(ctx, "heart failure"):
                causes.append("heart failure decompensation")
        else:
            causes.extend(["severe pain", "hypertensive emergency", "medication non-adherence"])

    seen: set[str] = set()
    unique: list[str] = []
    for cause in causes:
        key = cause.lower()
        if key not in seen:
            seen.add(key)
            unique.append(cause)

    if not unique:
        return None
    return "Likely causes: " + ", ".join(unique[:3])


def trend_label(column: str, df: pd.DataFrame) -> str | None:
    if column not in df.columns or len(df) < 2:
        return None
    first = df[column].iloc[0]
    last = df[column].iloc[-1]
    if pd.isna(first) or pd.isna(last) or abs(last - first) < 0.5:
        return None
    worsening = (
        (column in {"heart_rate", "respiratory_rate", "temperature"} and last > first)
        or (column in {"spo2", "systolic_bp"} and last < first)
    )
    if worsening:
        return "worsening"
    return "improving"


def trend_arrow_html(trend: str | None, severity: str = "normal") -> str:
    if trend == "improving":
        return '<span class="vital-trend improving" title="Improving over last 6 hours">↗</span>'
    if trend == "worsening":
        worsening_class = "worsening-warning" if severity == "warning" else "worsening"
        return (
            f'<span class="vital-trend {worsening_class}" '
            f'title="Worsening over last 6 hours">↘</span>'
        )
    return '<span class="vital-trend stable" title="Stable over last 6 hours">→</span>'


def format_vital_value(column: str, value: float) -> str:
    if column == "temperature":
        return f"{value:.2f}"
    return f"{value:.1f}"


def render_vital_header(
    column: str,
    meta: dict,
    value: float,
    trend: str | None,
    severity: str = "normal",
) -> None:
    severity_class = severity if severity in {"warning", "critical"} else ""
    st.markdown(
        f"""
        <div class="vital-header">
            <span class="vital-label">{meta["label"]}</span>
            <span class="vital-value-row {severity_class}">
                <strong>{format_vital_value(column, value)}</strong>
                {trend_arrow_html(trend, severity)}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def assess_vital(column: str, value: float, df: pd.DataFrame) -> dict:
    meta = VITAL_RANGES[column]
    score, problem = VITAL_ASSESSORS[column](value)
    trend = trend_label(column, df)
    if score == 0:
        severity = "normal"
    elif score == 1:
        severity = "warning"
    else:
        severity = "critical"

    detail = None
    if problem:
        unit = meta["label"].split("(")[-1].rstrip(")") if "(" in meta["label"] else ""
        detail = f"{value} {unit}".strip()

    return {
        "column": column,
        "label": meta["label"],
        "value": value,
        "score": score,
        "severity": severity,
        "problem": problem,
        "detail": detail,
        "trend": trend,
        "causes": None,
    }


def analyze_latest_vitals(df: pd.DataFrame, profile: dict | None = None) -> list[dict]:
    if df.empty:
        return []

    latest = df.iloc[-1]
    assessments = []
    for column in VITAL_RANGES:
        if column not in df.columns or pd.isna(latest[column]):
            continue
        assessments.append(assess_vital(column, latest[column], df))

    for assessment in assessments:
        if assessment["score"] > 0:
            assessment["causes"] = infer_likely_causes(
                assessment["column"],
                assessment["value"],
                assessment["score"],
                profile,
                assessments,
            )
    return assessments


def vital_selection_key(patient_id: int) -> str:
    return f"selected_vital_{patient_id}"


def get_selected_vital(patient_id: int) -> str | None:
    return st.session_state.get(vital_selection_key(patient_id))


def toggle_selected_vital(patient_id: int, column: str) -> None:
    key = vital_selection_key(patient_id)
    if st.session_state.get(key) == column:
        st.session_state[key] = None
    else:
        st.session_state[key] = column


def chart_was_clicked(patient_id: int, column: str, event) -> bool:
    if not event or not getattr(event, "selection", None):
        return False
    selected = event.selection.get("select") or []
    if not selected:
        return False
    state_key = f"chart_sel_{patient_id}_{column}"
    fingerprint = json.dumps(selected, default=str, sort_keys=True)
    if st.session_state.get(state_key) == fingerprint:
        return False
    st.session_state[state_key] = fingerprint
    return True


def format_problem_item(assessment: dict) -> str:
    label = assessment["label"].split("(")[0].strip()
    cause_html = ""
    if assessment.get("causes"):
        cause_html = f'<span class="problem-cause">{assessment["causes"]}</span>'
    return (
        f"<li><strong>{label}:</strong> "
        f"{trend_arrow_html(assessment['trend'], assessment['severity'])} "
        f"{assessment['problem']} — <em>{assessment['detail']}</em>"
        f"{cause_html}</li>"
    )


def render_problems_panel(assessments: list[dict], news2_score, risk_level: str) -> None:
    problems = [a for a in assessments if a["problem"]]
    if not problems:
        st.success("All vitals within normal range.")
        return

    items = "".join(
        format_problem_item(a) for a in sorted(problems, key=lambda x: -x["score"])
    )
    st.markdown(
        f"""
        <div class="problems-panel">
            <h4>⚠ Active Problems (NEWS2 {news2_score} — {risk_level})</h4>
            <ul>{items}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_vital_status(assessment: dict | None) -> None:
    if assessment is None:
        return
    if assessment["problem"]:
        css_class = "critical" if assessment["severity"] == "critical" else "warning"
        cause_html = (
            f'<span class="problem-cause">{assessment["causes"]}</span>'
            if assessment.get("causes")
            else ""
        )
        st.markdown(
            f'<p class="vital-problem {css_class}">{assessment["problem"]}{cause_html}</p>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<p class="vital-problem normal">Within normal range</p>',
            unsafe_allow_html=True,
        )


def build_vital_chart(df: pd.DataFrame, column: str, meta: dict, severity: str = "normal") -> alt.Chart:
    plot_df = df[["window_start", column]].copy()
    y_min = min(plot_df[column].min() * 0.9, meta["low"] * 0.85)
    y_max = max(plot_df[column].max() * 1.1, meta["high"] * 1.15)
    line_color = SEVERITY_CHART_COLORS.get(severity, SEVERITY_CHART_COLORS["normal"])

    band = (
        alt.Chart(pd.DataFrame({"low": [meta["low"]], "high": [meta["high"]]}))
        .mark_rect(color="green", opacity=0.2)
        .encode(
            y=alt.Y("low:Q"),
            y2=alt.Y2("high:Q"),
        )
    )

    line = (
        alt.Chart(plot_df)
        .mark_line(color=line_color, strokeWidth=2.5)
        .encode(
            x=alt.X("window_start:T", title="Time"),
            y=alt.Y(f"{column}:Q", title=meta["label"], scale=alt.Scale(domain=[y_min, y_max])),
        )
    )

    selection = alt.selection_point(name="select")
    points = (
        alt.Chart(plot_df)
        .mark_point(color=line_color, size=70, filled=True)
        .encode(
            x=alt.X("window_start:T"),
            y=alt.Y(f"{column}:Q"),
            tooltip=[
                alt.Tooltip("window_start:T", title="Time"),
                alt.Tooltip(f"{column}:Q", title=meta["label"]),
            ],
        )
        .add_params(selection)
    )

    return (
        alt.layer(band, line, points)
        .resolve_scale(x="shared", y="shared")
        .properties(title=meta["label"], height=220)
    )


def render_profile_text(value: str | None, empty_label: str) -> str:
    if not value:
        return f'<p class="profile-empty">{empty_label}</p>'
    return f'<p style="margin:0;color:#333;">{value}</p>'


def render_patient_background_panel(patient_id: int, profile: dict) -> None:
    name = profile.get("full_name", f"Patient {patient_id}")
    meta_parts = [f"Patient ID: {patient_id}"]
    if profile.get("room_number"):
        meta_parts.append(f"Room: {profile['room_number']}")
    if profile.get("date_of_birth"):
        meta_parts.append(f"DOB: {format_date(profile['date_of_birth'])}")
    if profile.get("sex"):
        meta_parts.append(f"Sex: {profile['sex']}")

    address_html = render_profile_text(
        profile.get("home_address"),
        "No home address on file.",
    )
    occupation_html = render_profile_text(
        profile.get("occupation"),
        "No occupation on file.",
    )
    allergies_html = render_profile_list(
        profile.get("allergies"),
        "No known drug allergies (NKDA)",
    )
    conditions_html = render_profile_list(
        profile.get("past_medical_conditions"),
        "No documented past medical conditions.",
    )
    medications_html = render_profile_list(
        profile.get("current_medications"),
        "No current medications on file.",
    )
    history = profile.get("medical_history")
    history_html = (
        f"<p style='margin:0;color:#333;'>{history}</p>"
        if history
        else '<p class="profile-empty">No additional medical history documented.</p>'
    )

    st.markdown(
        f"""
        <div class="profile-screen">
            <h2>{name}</h2>
            <p class="profile-meta">{" · ".join(meta_parts)}</p>
            <div class="profile-section">
                <h4>Home Address</h4>
                {address_html}
            </div>
            <div class="profile-section">
                <h4>Occupation</h4>
                {occupation_html}
            </div>
            <div class="profile-section allergies">
                <h4>Allergies</h4>
                {allergies_html}
            </div>
            <div class="profile-section">
                <h4>Past Medical Conditions</h4>
                {conditions_html}
            </div>
            <div class="profile-section">
                <h4>Medical History</h4>
                {history_html}
            </div>
            <div class="profile-section">
                <h4>Current Medications</h4>
                {medications_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_patient_detail(patient_id: int) -> None:
    if st.button("← Back to Ward", key="detail_back"):
        st.session_state.selected_patient_id = None
        st.rerun()

    st.divider()
    st.subheader(f"Patient {patient_id} — Vitals History (Last 6 Hours)")

    history = fetch_patient_history(patient_id)
    df = filter_last_six_hours(history)

    if df.empty:
        st.warning("No vitals data in the last 6 hours for this patient.")
        return

    latest = df.iloc[-1]
    last_updated = format_timestamp(latest.get("window_start"))
    st.markdown(
        f'<p class="updated-label">Last updated: {last_updated}</p>',
        unsafe_allow_html=True,
    )
    profile = fetch_patient_profile(patient_id)
    assessments = analyze_latest_vitals(df, profile)
    assessment_by_column = {a["column"]: a for a in assessments}
    news2_score = latest.get("news2_score", "—")
    risk_level = str(latest.get("risk_level", "UNKNOWN")).upper()

    chart_cols = st.columns(5)
    for index, (column, meta) in enumerate(VITAL_RANGES.items()):
        with chart_cols[index]:
            if column not in df.columns or df[column].isna().all():
                st.caption(meta["label"])
                st.write("No data")
                continue

            assessment = assessment_by_column.get(column)
            trend = assessment["trend"] if assessment else None
            severity = assessment["severity"] if assessment else "normal"
            render_vital_header(column, meta, df[column].iloc[-1], trend, severity)

            chart = build_vital_chart(df, column, meta, severity=severity)
            event = st.altair_chart(
                chart,
                on_select="rerun",
                key=f"chart_{patient_id}_{column}",
                width="stretch",
            )

            if chart_was_clicked(patient_id, column, event):
                toggle_selected_vital(patient_id, column)

            if get_selected_vital(patient_id) == column:
                render_vital_status(assessment)

    render_problems_panel(assessments, news2_score, risk_level)


def format_date(value) -> str:
    if value is None:
        return "—"
    return pd.to_datetime(value).strftime("%d %b %Y")


def render_profile_list(items: list[str] | None, empty_label: str) -> str:
    if not items:
        return f'<p class="profile-empty">{empty_label}</p>'
    list_items = "".join(f"<li>{item}</li>" for item in items)
    return f"<ul>{list_items}</ul>"


@st.fragment(run_every=timedelta(seconds=REFRESH_SECONDS))
def dashboard() -> None:
    inject_styles()
    render_header()
    render_demo_banner()

    render_ward_view(fetch_active_patients())

    selected_id = st.session_state.get("selected_patient_id")
    if selected_id is not None:
        render_patient_detail(selected_id)


def main() -> None:
    st.set_page_config(
        page_title="VitalStream — ICU Monitor",
        layout="wide",
    )

    if "selected_patient_id" not in st.session_state:
        st.session_state.selected_patient_id = None
    if "detail_patient_id" not in st.session_state:
        st.session_state.detail_patient_id = None
    if "use_mock_data" not in st.session_state:
        st.session_state.use_mock_data = True

    with st.sidebar:
        st.header("Settings")
        st.checkbox(
            "Demo mode (mock data)",
            key="use_mock_data",
            help="Use sample patients instead of the live API.",
        )

    dashboard()


if __name__ == "__main__":
    main()
