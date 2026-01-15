"""
Helper callbacks for Guitar Shed UI.
"""

import streamlit as st


def set_lesson(lesson_id):
    """Callback: Set lesson ID state."""
    st.session_state.selected_lesson_id = lesson_id


def clear_lesson():
    """Callback: Clear lesson ID state."""
    st.session_state.selected_lesson_id = None


def update_status_callback(db, lesson_id, new_status):
    """Callback: Update DB status without resetting UI state."""
    db.update_status(lesson_id, new_status)
    # Streamlit automatically reruns after this. 
    # Because selected_lesson_id is in session_state, the player will reopen.
