import streamlit as st

from common import (
    inject_styles,
    render_demo_banner,
    render_header,
    render_patient_select,
    vitals_history_content,
)


st.set_page_config(page_title="Vitals History — VitalStream", layout="wide")

if "vitals_patient_id" not in st.session_state:
    st.session_state.vitals_patient_id = 101
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

if st.button("← Back to Ward", key="vitals_page_back"):
    st.switch_page("app.py")

render_demo_banner()

current_id = st.session_state.get("vitals_patient_id")
patient_id = render_patient_select(
    "Select patient",
    widget_key="vitals_patient_select",
    current_patient_id=current_id,
)
if patient_id is None:
    st.info("No active patients. Enable demo mode or start the producer and processor.")
    st.stop()

st.session_state.vitals_patient_id = patient_id

vitals_history_content(patient_id)
