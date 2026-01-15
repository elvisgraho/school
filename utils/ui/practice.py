"""
Practice Room (Video Player) for Guitar Shed.
"""

import streamlit as st
import os
from .callbacks import clear_lesson, update_status_callback


def render_practice_room(db) -> None:
    """
    Render the Video Player as a dedicated view.
    This replaces the dashboard view entirely when active.
    """
    lesson_id = st.session_state.get('selected_lesson_id')
    if not lesson_id:
        return

    # Fetch latest lesson data
    lesson = db.get_lesson_by_id(lesson_id)
    
    # Error handling
    if not lesson:
        st.error("Error: Lesson file could not be located.")
        st.session_state.selected_lesson_id = None
        st.button("Return to Library", on_click=clear_lesson)
        return

    # Header
    st.markdown(f"### {lesson['title']}")
    
    # Video Player
    video_path = lesson.get('filepath', '')
    if video_path and os.path.exists(video_path):
        st.video(video_path)
    else:
        st.warning(f"File missing: {lesson.get('filename', 'Unknown')}")

    # Metadata & Controls container
    with st.container():
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown(f"**Author:** {lesson['author']} &nbsp; | &nbsp; **Date:** {lesson['lesson_date']}")
            st.markdown(f"**Current Status:** {lesson['status']}")
        
        with c2:
            # Close button (Top right of controls)
            st.button("Close Player", on_click=clear_lesson, width='stretch')

    st.markdown("---")

    # Action Buttons
    # These are conservative text buttons.
    col_main, col_empty = st.columns([1, 2])
    
    with col_main:
        current_status = lesson['status']
        
        if current_status == 'New':
            st.button("Start Practice (Mark In Progress)", type="primary", 
                     on_click=update_status_callback, args=(db, lesson['id'], 'In Progress'),
                     width='stretch')
                
        elif current_status == 'In Progress':
            st.button("Mark Completed", type="primary", 
                     on_click=update_status_callback, args=(db, lesson['id'], 'Completed'),
                     width='stretch')
                
        elif current_status == 'Completed':
            st.button("Revert to In Progress", 
                     on_click=update_status_callback, args=(db, lesson['id'], 'In Progress'),
                     width='stretch')
