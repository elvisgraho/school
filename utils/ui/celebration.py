"""One-shot, click-through lesson and daily goal celebrations."""

import json
from functools import lru_cache
from pathlib import Path

import streamlit as st


@lru_cache(maxsize=1)
def _celebration_template() -> str:
    return Path(__file__).with_name('celebration.html').read_text(encoding='utf-8')


def render_completion_celebration() -> None:
    """Consume the callback event once, after the app has rendered its controls."""
    event = st.session_state.pop('completion_celebration', None)
    if event is None:
        return
    payload = json.dumps({'id': str(event['id']), 'kind': event['kind']})
    payload = payload.replace('<', r'\u003c').replace('>', r'\u003e')
    st.html(
        _celebration_template().replace('__CELEBRATION_EVENT__', payload),
        unsafe_allow_javascript=True,
    )
