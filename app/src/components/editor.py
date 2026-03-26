"""SQL editor component – thin wrapper around streamlit-code-editor.

Reads/writes st.session_state["ide_editor_content"]. Detects submit command.
Returns (query_text, submitted) tuple.
"""

from __future__ import annotations

import logging

import streamlit as st

logger = logging.getLogger(__name__)

_EDITOR_BUTTONS = [
    {
        "name": "Run",
        "feather": "Play",
        "primary": True,
        "hasText": True,
        "showWithIcon": True,
        "commands": ["submit"],
        "style": {"bottom": "0.44rem", "right": "0.4rem"},
    },
    {
        "name": "Clear",
        "feather": "Trash2",
        "primary": False,
        "hasText": True,
        "showWithIcon": True,
        "commands": ["clearContent"],
        "style": {"bottom": "0.44rem", "right": "5rem"},
    },
]

_EDITOR_OPTIONS = {
    "showLineNumbers": True,
    "tabSize": 2,
    "wrap": True,
}


def render_editor() -> tuple[str | None, bool]:
    """Render the Monaco SQL editor.

    Returns:
        (query_text, submitted): query_text is the current editor content,
        submitted is True if the user clicked Run or pressed Ctrl+Enter.
    """
    try:
        from code_editor import code_editor
    except ImportError:
        st.error(
            "The `streamlit-code-editor` package is required but failed to load. "
            "Install it with: `pip install streamlit-code-editor`"
        )
        return None, False

    # Read initial content from session state
    initial_content = st.session_state.get("ide_editor_content", "")

    response = code_editor(
        initial_content,
        lang="sql",
        buttons=_EDITOR_BUTTONS,
        options=_EDITOR_OPTIONS,
        height=[10, 30],
        key="ide_code_editor",
    )

    query_text: str | None = None
    submitted = False

    if response:
        # The editor returns text on submit (Run button or Ctrl+Enter)
        text = response.get("text", "")
        resp_type = response.get("type", "")

        if text:
            query_text = text
            st.session_state["ide_editor_content"] = text

        if resp_type == "submit" and text:
            submitted = True

    return query_text, submitted
