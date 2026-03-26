"""StackQL Cloud Inventory – Streamlit application entrypoint."""

from __future__ import annotations

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


def _init_theme() -> None:
    """Initialise theme toggle in session state."""
    if "app_theme" not in st.session_state:
        st.session_state["app_theme"] = "dark"


def main() -> None:
    st.set_page_config(
        page_title="StackQL Cloud Inventory",
        page_icon=str(STATIC_DIR / "favicon.ico"),
        layout="wide",
        initial_sidebar_state="expanded",
    )

    _init_theme()

    # Verify Lakebase connectivity early
    try:
        from src.db.service import DatabaseService
        db_svc = DatabaseService()
        st.session_state["db_service"] = db_svc
    except RuntimeError as exc:
        st.error(f"**Lakebase Connection Error:** {exc}")
        st.stop()

    # Sidebar navigation
    with st.sidebar:
        logo_file = "logo-white.png" if st.session_state["app_theme"] == "dark" else "logo.png"
        logo_path = STATIC_DIR / logo_file
        if logo_path.exists():
            st.image(str(logo_path), width=180)
        st.title("StackQL Inventory")

        # Theme toggle
        theme = st.toggle(
            "Dark mode",
            value=st.session_state["app_theme"] == "dark",
            key="theme_toggle",
        )
        st.session_state["app_theme"] = "dark" if theme else "light"

        st.divider()

    # Page navigation
    page = st.navigation([
        st.Page("src/pages/ide.py", title="SQL IDE", icon=":material/code:", default=True),
        st.Page("src/pages/schedules.py", title="Schedules", icon=":material/schedule:"),
        st.Page("src/pages/inventory.py", title="Inventory", icon=":material/inventory_2:"),
        st.Page("src/pages/providers.py", title="Providers", icon=":material/cloud:"),
    ])
    page.run()


if __name__ == "__main__":
    main()
