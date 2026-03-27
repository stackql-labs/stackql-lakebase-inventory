"""StackQL Cloud Inventory – Streamlit application entrypoint."""

from __future__ import annotations

import base64
import logging
import os
import sys
from pathlib import Path

# Ensure the app/ directory is on sys.path so `src.*` imports resolve
# when Streamlit is launched with `streamlit run src/main.py` from app/
_APP_DIR = str(Path(__file__).resolve().parent.parent)
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import streamlit as st
from dotenv import load_dotenv

# Load .env for local development (no-op in production)
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


def _read_favicon_b64() -> str:
    """Read the favicon.ico and return a base64-encoded data URI."""
    favicon_path = STATIC_DIR / "favicon.ico"
    if favicon_path.exists():
        data = favicon_path.read_bytes()
        return f"data:image/x-icon;base64,{base64.b64encode(data).decode()}"
    return ""


def _inject_custom_css() -> None:
    """Inject custom CSS for branding header and favicon spinner."""
    favicon_uri = _read_favicon_b64()

    st.markdown(f"""
    <style>
    /* Hide the default Streamlit running-man indicator animation */
    [data-testid="stStatusWidget"] {{
        display: none !important;
    }}

    /* Favicon spinner – shown during script reruns */
    @keyframes spin {{
        0% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(360deg); }}
    }}

    /* Custom running indicator using favicon */
    .stApp[data-test-script-state="running"]::after {{
        content: "";
        position: fixed;
        top: 14px;
        right: 14px;
        width: 28px;
        height: 28px;
        background-image: url("{favicon_uri}");
        background-size: contain;
        background-repeat: no-repeat;
        animation: spin 1.2s linear infinite;
        z-index: 999999;
    }}

    /* Top header bar with logo */
    .top-header {{
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 0 0 0.5rem 0;
    }}
    .top-header img {{
        height: 32px;
    }}
    .top-header .title {{
        font-size: 1.3rem;
        font-weight: 600;
        margin: 0;
        padding: 0;
    }}
    </style>
    """, unsafe_allow_html=True)


def _render_header() -> None:
    """Render the top-of-page logo and title."""
    logo_path = STATIC_DIR / "logo.png"
    if logo_path.exists():
        logo_data = base64.b64encode(logo_path.read_bytes()).decode()
        st.markdown(
            f"""
            <div class="top-header">
                <img src="data:image/png;base64,{logo_data}" alt="StackQL Logo">
                <span class="title">Cloud Inventory</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def main() -> None:
    st.set_page_config(
        page_title="StackQL Cloud Inventory",
        page_icon=str(STATIC_DIR / "favicon.ico"),
        layout="wide",
        initial_sidebar_state="expanded",
    )

    _inject_custom_css()
    _render_header()

    # Verify Lakebase connectivity early
    try:
        from src.db.service import DatabaseService
        db_svc = DatabaseService()
        st.session_state["db_service"] = db_svc
    except RuntimeError as exc:
        st.error(f"**Lakebase Connection Error:** {exc}")
        st.stop()

    # Page navigation (paths relative to this script's directory)
    page = st.navigation([
        st.Page("pages/ide.py", title="SQL IDE", icon=":material/code:", default=True),
        st.Page("pages/schedules.py", title="Schedules", icon=":material/schedule:"),
        st.Page("pages/inventory.py", title="Inventory", icon=":material/inventory_2:"),
        st.Page("pages/providers.py", title="Providers", icon=":material/cloud:"),
    ])
    page.run()


if __name__ == "__main__":
    main()
