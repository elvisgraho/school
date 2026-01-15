"""
Discovery Tab for Guitar Shed.
"""

import streamlit as st
from .styles import apply_conservative_style
from .callbacks import set_lesson


def render_discovery(db) -> None:
    """Render the Discovery Dashboard."""
    apply_conservative_style()

    # SECTION 1: IN PROGRESS
    in_progress_lessons = db.get_in_progress_lessons(limit=10)
    if in_progress_lessons:
        st.markdown('<div class="section-label">Continue Watching</div>', unsafe_allow_html=True)
        for lesson in in_progress_lessons:
            st.markdown(f"""
            <a href="?lesson={lesson['id']}" style="text-decoration: none;">
                <div class="lesson-card">
                    <div class="lesson-title">{lesson['title']}</div>
                    <div class="lesson-author">{lesson['author']}</div>
                </div>
            </a>
            """, unsafe_allow_html=True)
        st.write("")

    # SECTION 2: LESSONS OF THE DAY
    st.markdown('<div class="section-label">Lessons of the Day</div>', unsafe_allow_html=True)
    
    lesson_of_day = db.get_lesson_of_day(limit=5)
    
    if lesson_of_day:
        for lesson in lesson_of_day:
            st.markdown(f"""
            <a href="?lesson={lesson['id']}" style="text-decoration: none;">
                <div class="lesson-card">
                    <div class="lesson-title">{lesson['title']}</div>
                    <div class="lesson-author">{lesson['author']}</div>
                </div>
            </a>
            """, unsafe_allow_html=True)
    else:
        st.info("Library is empty. Please sync.")

    # SECTION 3: COMPLETED
    st.markdown('<div class="section-label">Completed Lessons</div>', unsafe_allow_html=True)
    
    completed_lessons, _ = db.get_paginated_lessons(page=1, page_size=10, status_filter=['Completed'])
    
    if completed_lessons:
        for lesson in completed_lessons:
            st.markdown(f"""
            <a href="?lesson={lesson['id']}" style="text-decoration: none;">
                <div class="lesson-card">
                    <div class="lesson-title">{lesson['title']}</div>
                    <div class="lesson-author">{lesson['author']}</div>
                </div>
            </a>
            """, unsafe_allow_html=True)
    else:
        st.caption("No completed lessons yet.")

    # Handle click navigation
    if "lesson" in st.query_params:
        lesson_id = int(st.query_params["lesson"])
        set_lesson(lesson_id)
        st.query_params.clear()
