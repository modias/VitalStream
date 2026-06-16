import streamlit as st

from common import dashboard


def main() -> None:
    st.set_page_config(
        page_title="VitalStream — ICU Monitor",
        layout="wide",
    )

    if "detail_patient_id" not in st.session_state:
        st.session_state.detail_patient_id = None
    if "vitals_patient_id" not in st.session_state:
        st.session_state.vitals_patient_id = None
    if "use_mock_data" not in st.session_state:
        st.session_state.use_mock_data = False

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
