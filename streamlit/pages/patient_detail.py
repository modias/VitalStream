import streamlit as st

from app import (
    MOCK_PATIENT_CHARTS,
    inject_styles,
    render_header,
    render_patient_background_panel,
)


def mock_patient_options() -> dict[str, int]:
    return {
        f"{profile['full_name']} — Room {profile.get('room_number', '—')} (ID {patient_id})": patient_id
        for patient_id, profile in sorted(MOCK_PATIENT_CHARTS.items())
    }


st.set_page_config(page_title="Patient Detail — VitalStream", layout="wide")

if "detail_patient_id" not in st.session_state:
    st.session_state.detail_patient_id = 101
if "use_mock_data" not in st.session_state:
    st.session_state.use_mock_data = True

with st.sidebar:
    st.header("Settings")
    st.checkbox(
        "Demo mode (mock data)",
        key="use_mock_data",
        help="Use sample patients instead of the live API.",
    )

inject_styles()
render_header()

if st.button("← Back to Ward", key="detail_page_back"):
    st.switch_page("app.py")

st.info("Demo mode — showing mock patient background data.")

options = mock_patient_options()
labels = list(options.keys())
current_id = st.session_state.get("detail_patient_id") or 101
default_index = next(
    (index for index, label in enumerate(labels) if options[label] == current_id),
    0,
)

selected_label = st.selectbox("Select patient", labels, index=default_index)
patient_id = options[selected_label]
st.session_state.detail_patient_id = patient_id

profile = MOCK_PATIENT_CHARTS.get(patient_id)
if profile is None:
    st.warning(f"No mock data available for patient {patient_id}.")
    st.stop()

st.subheader(f"Patient {patient_id} — Background & Medical History")
render_patient_background_panel(patient_id, profile)
