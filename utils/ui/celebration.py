"""One-shot, click-through daily goal celebrations."""

import json
from functools import lru_cache
from pathlib import Path

import streamlit as st


@lru_cache(maxsize=1)
def _celebration_template() -> str:
    source = Path(__file__).with_name('celebration.html').read_text(encoding='utf-8')
    markup, _, script = source.partition('</template>')
    # Streamlit's sanitizer removes scripts containing literal HTML tags.
    # Encode the trusted shadow DOM markup as a JavaScript string instead.
    encoded = json.dumps(markup.removeprefix('<template>')).replace('<', r'\u003c').replace('>', r'\u003e')
    return script.replace('__CELEBRATION_MARKUP__', encoded)


def render_daily_goal_celebration() -> None:
    """Consume the callback event once, after the app has rendered its controls."""
    event = st.session_state.pop('daily_goal_celebration', None)
    if event is None:
        return
    # Only locally generated IDs and integer counts enter this trusted script.
    payload = json.dumps({'id': str(event['id']), 'completed': int(event['completed'])})
    st.html(
        _celebration_template().replace('__CELEBRATION_EVENT__', payload),
        unsafe_allow_javascript=True,
    )
