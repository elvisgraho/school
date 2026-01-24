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


def add_tag_callback(db, lesson_id, tag_name):
    """Callback: Add a tag to a lesson (creates tag if needed)."""
    if tag_name and tag_name.strip():
        tag_id = db.get_or_create_tag(tag_name.strip())
        if tag_id:
            db.add_tag_to_lesson(lesson_id, tag_id)


def remove_tag_callback(db, lesson_id, tag_id):
    """Callback: Remove a tag from a lesson."""
    db.remove_tag_from_lesson(lesson_id, tag_id)


def bulk_add_tag_callback(db, lesson_ids, tag_name):
    """Callback: Add a tag to multiple lessons at once."""
    if not tag_name or not tag_name.strip() or not lesson_ids:
        return
    tag_id = db.get_or_create_tag(tag_name.strip())
    if tag_id:
        for lesson_id in lesson_ids:
            db.add_tag_to_lesson(lesson_id, tag_id)
        # Track successful bulk tag for UI feedback
        st.session_state.bulk_tag_success = {
            'tag': tag_name.strip(),
            'count': len(lesson_ids)
        }


def bulk_untag_and_delete_callback(db, tag_id, tag_name):
    """Callback: Remove tag from all lessons and delete the tag."""
    if not tag_id:
        return
    # Delete tag (cascade will remove lesson_tags entries)
    db.delete_tag(tag_id)
    # Track success and signal to clear filter
    st.session_state.bulk_untag_success = {
        'tag': tag_name,
        'deleted': True
    }
    # Clear the tag filter since tag no longer exists
    st.session_state.lib_tags = []
