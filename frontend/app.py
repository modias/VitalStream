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


def get_mock_active_patients() -> list[dict]:
    now = datetime.now(timezone.utc)
    return [
        {
            "patient_id": patient_id,
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


def format_timestamp(value) -> str:
    if value is None:
        return "—"
    ts = pd.to_datetime(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.strftime("%Y-%m-%d %H:%M:%S")


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
        .news2-score {
            font-size: 2.5rem;
            font-weight: 700;
            line-height: 1;
            margin: 0.5rem 0;
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
    card_class = "patient-card high-risk" if risk == "HIGH" else "patient-card"
    patient_id = patient["patient_id"]
    news2 = patient.get("news2_score", "—")
    updated = format_timestamp(patient.get("window_start"))

    st.markdown(
        f"""
        <div class="{card_class}">
            <p class="patient-id-label">Patient ID</p>
            <p style="font-size:1.2rem;font-weight:600;margin:0;">{patient_id}</p>
            <p class="news2-score">{news2}</p>
            <p style="margin:0.25rem 0;font-size:0.8rem;color:#666;">NEWS2 Score</p>
            <span class="risk-badge" style="background:{style['bg']};
                color:{style['color']};border:1px solid {style['border']};">
                {risk}
            </span>
            <p class="updated-label">Last updated: {updated}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("View Details", key=f"patient_{patient_id}", use_container_width=True):
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
        if trend == "worsening":
            problem = f"{problem} ({trend})"

    return {
        "column": column,
        "label": meta["label"],
        "value": value,
        "score": score,
        "severity": severity,
        "problem": problem,
        "detail": detail,
        "trend": trend,
    }


def analyze_latest_vitals(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []

    latest = df.iloc[-1]
    assessments = []
    for column in VITAL_RANGES:
        if column not in df.columns or pd.isna(latest[column]):
            continue
        assessments.append(assess_vital(column, latest[column], df))
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


def render_problems_panel(assessments: list[dict], news2_score, risk_level: str) -> None:
    problems = [a for a in assessments if a["problem"]]
    if not problems:
        st.success("All vitals within normal range.")
        return

    items = "".join(
        f"<li><strong>{a['label'].split('(')[0].strip()}:</strong> "
        f"{a['problem']} — <em>{a['detail']}</em></li>"
        for a in sorted(problems, key=lambda x: -x["score"])
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
        st.markdown(
            f'<p class="vital-problem {css_class}">{assessment["problem"]}</p>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<p class="vital-problem normal">Within normal range</p>',
            unsafe_allow_html=True,
        )


def build_vital_chart(df: pd.DataFrame, column: str, meta: dict, abnormal: bool = False) -> alt.Chart:
    plot_df = df[["window_start", column]].copy()
    y_min = min(plot_df[column].min() * 0.9, meta["low"] * 0.85)
    y_max = max(plot_df[column].max() * 1.1, meta["high"] * 1.15)
    line_color = "#dc3545" if abnormal else "#2563eb"

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


def render_patient_detail(patient_id: int) -> None:
    st.divider()
    st.subheader(f"Patient {patient_id} — Vitals History (Last 6 Hours)")

    history = fetch_patient_history(patient_id)
    df = filter_last_six_hours(history)

    if df.empty:
        st.warning("No vitals data in the last 6 hours for this patient.")
        return

    latest = df.iloc[-1]
    assessments = analyze_latest_vitals(df)
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
            abnormal = assessment is not None and assessment["score"] > 0
            chart = build_vital_chart(df, column, meta, abnormal=abnormal)
            event = st.altair_chart(
                chart,
                on_select="rerun",
                key=f"chart_{patient_id}_{column}",
                use_container_width=True,
            )

            if chart_was_clicked(patient_id, column, event):
                toggle_selected_vital(patient_id, column)

            if get_selected_vital(patient_id) == column:
                render_vital_status(assessment)

    render_problems_panel(assessments, news2_score, risk_level)


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
