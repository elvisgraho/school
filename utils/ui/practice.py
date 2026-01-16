"""
Practice Room (Video Player) for Guitar Shed.
Optimized for smooth playback and responsive controls.
"""

import streamlit as st
import os
from .callbacks import clear_lesson, update_status_callback

# Status display styling
STATUS_COLORS = {
    'New': '#718096',
    'In Progress': '#4299E1',
    'Completed': '#48BB78'
}


def render_practice_room(db) -> None:
    """
    Render the Video Player as a dedicated view.
    This replaces the dashboard view entirely when active.
    """
    lesson_id = st.session_state.get('selected_lesson_id')
    if not lesson_id:
        return

    # Fetch lesson data
    lesson = db.get_lesson_by_id(lesson_id)

    # Error handling
    if not lesson:
        st.error("Lesson not found in database.")
        st.button("Return to Library", on_click=clear_lesson, type="primary")
        return

    # Top bar: Close button and title
    col_back, col_title = st.columns([1, 11])
    with col_back:
        st.button("Back", on_click=clear_lesson, use_container_width=True)
    with col_title:
        st.markdown(f"### {lesson['title']}")

    # Video Player
    video_path = lesson.get('filepath', '')
    if video_path and os.path.exists(video_path):
        st.video(video_path)
    else:
        st.error(f"Video file not found: {lesson.get('filename', 'Unknown')}")
        st.caption(f"Expected path: {video_path}")
        return

    # Metadata row
    status_color = STATUS_COLORS.get(lesson['status'], '#888')
    st.markdown(f"""
        <div style="display: flex; justify-content: space-between; align-items: center;
                    padding: 12px 0; border-bottom: 1px solid #333; margin-bottom: 16px;">
            <div>
                <span style="color: #aaa;">By</span>
                <span style="color: #fff; font-weight: 500;">{lesson['author']}</span>
                <span style="color: #555; margin: 0 8px;">|</span>
                <span style="color: #aaa;">{lesson['lesson_date']}</span>
            </div>
            <div style="background: {status_color}22; color: {status_color};
                        padding: 4px 12px; border-radius: 4px; font-size: 0.85rem; font-weight: 500;">
                {lesson['status']}
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Action buttons based on status
    current_status = lesson['status']
    col_action, col_secondary, _ = st.columns([2, 2, 6])

    with col_action:
        if current_status == 'New':
            st.button(
                "Start Practice",
                type="primary",
                on_click=update_status_callback,
                args=(db, lesson['id'], 'In Progress'),
                use_container_width=True
            )
        elif current_status == 'In Progress':
            st.button(
                "Mark Completed",
                type="primary",
                on_click=update_status_callback,
                args=(db, lesson['id'], 'Completed'),
                use_container_width=True
            )
        elif current_status == 'Completed':
            st.button(
                "Practice Again",
                on_click=update_status_callback,
                args=(db, lesson['id'], 'In Progress'),
                use_container_width=True
            )

    with col_secondary:
        if current_status != 'New':
            st.button(
                "Reset to New",
                on_click=update_status_callback,
                args=(db, lesson['id'], 'New'),
                use_container_width=True
            )
