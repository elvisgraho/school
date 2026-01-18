"""
Practice Room (Video Player) for Guitar Shed.
Optimized for smooth playback and responsive controls.
"""

import streamlit as st
import os
import urllib.parse
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

    # Top bar: Back button aligned with title
    st.button("← Back to Library", on_click=clear_lesson)
    st.markdown(f"### {lesson['title']}")

    # Video Player
    video_path = lesson.get('filepath', '')
    if video_path and os.path.exists(video_path):
        st.video(video_path)
    else:
        st.error(f"Video file not found: {lesson.get('filename', 'Unknown')}")
        st.caption(f"Expected path: {video_path}")
        st.info("The file may have been moved or deleted. Try syncing your library again.")
        return

    # Metadata and actions row
    current_status = lesson['status']
    status_color = STATUS_COLORS.get(current_status, '#888')

    # Combined metadata + buttons in one clean row
    st.markdown(f"""
        <div style="display: flex; justify-content: space-between; align-items: center;
                    padding: 8px 0; margin-bottom: 8px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="color: #aaa;">By</span>
                <span style="color: #fff; font-weight: 500;">{lesson['author']}</span>
                <span style="color: #555;">|</span>
                <span style="color: #aaa;">{lesson['lesson_date']}</span>
                <span style="color: #555;">|</span>
                <span style="background: {status_color}22; color: {status_color};
                            padding: 2px 8px; border-radius: 4px; font-size: 0.85rem;">
                    {current_status}
                </span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Action buttons - compact row
    youtube_query = urllib.parse.quote_plus(lesson['title'])
    youtube_url = f"https://www.youtube.com/results?search_query={youtube_query}"

    if current_status == 'New':
        cols = st.columns([1, 1, 3])
        with cols[0]:
            st.button("Start Practice", type="primary", on_click=update_status_callback,
                      args=(db, lesson['id'], 'In Progress'), use_container_width=True)
        with cols[1]:
            st.link_button("YouTube", youtube_url, use_container_width=True)
    elif current_status == 'In Progress':
        cols = st.columns([1, 1, 1, 2])
        with cols[0]:
            st.button("Mark Completed", type="primary", on_click=update_status_callback,
                      args=(db, lesson['id'], 'Completed'), use_container_width=True)
        with cols[1]:
            st.button("Reset to New", on_click=update_status_callback,
                      args=(db, lesson['id'], 'New'), use_container_width=True)
        with cols[2]:
            st.link_button("YouTube", youtube_url, use_container_width=True)
    else:  # Completed
        cols = st.columns([1, 1, 1, 2])
        with cols[0]:
            st.button("Practice Again", type="primary", on_click=update_status_callback,
                      args=(db, lesson['id'], 'In Progress'), use_container_width=True)
        with cols[1]:
            st.button("Reset to New", on_click=update_status_callback,
                      args=(db, lesson['id'], 'New'), use_container_width=True)
        with cols[2]:
            st.link_button("YouTube", youtube_url, use_container_width=True)
