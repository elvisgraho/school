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
    # Only show if there are items
    in_progress_lessons = db.get_in_progress_lessons(limit=10)
    if in_progress_lessons:
        st.markdown('<div class="section-label">Continue Watching</div>', unsafe_allow_html=True)
        for lesson in in_progress_lessons:
            with st.container():
                c1, c2 = st.columns([6, 2])
                with c1:
                    st.markdown(f"**{lesson['title']}**<br><span class=\"lesson-author\">{lesson['author']}</span>", unsafe_allow_html=True)
                with c2:
                    st.button("Resume", key=f"cont_{lesson['id']}", 
                              on_click=set_lesson, args=(lesson['id'],), width='stretch')
                st.markdown("---")
    
    # SECTION 2: LESSONS OF THE DAY
    st.markdown('<div class="section-label">Lessons of the Day</div>', unsafe_allow_html=True)
    
    lesson_of_day = db.get_lesson_of_day(limit=5)
    
    if lesson_of_day:
        for lesson in lesson_of_day:
            c1, c2 = st.columns([6, 2])
            with c1:
                st.markdown(f"**{lesson['title']}**<br><span class=\"lesson-author\">{lesson['author']}</span>", unsafe_allow_html=True)
            with c2:
                st.button("Open", key=f"lod_{lesson['id']}", 
                          on_click=set_lesson, args=(lesson['id'],), width='stretch')
    else:
        st.info("Library is empty. Please sync.")

    st.markdown("---")

    # SECTION 3: COMPLETED (was Rediscover)
    st.markdown('<div class="section-label">Completed Lessons</div>', unsafe_allow_html=True)
    
    completed_lessons, _ = db.get_paginated_lessons(page=1, page_size=10, status_filter=['Completed'])
    
    if completed_lessons:
        for lesson in completed_lessons:
            c1, c2 = st.columns([6, 2])
            with c1:
                st.markdown(f"**{lesson['title']}**<br><span class=\"lesson-author\">{lesson['author']}</span>", unsafe_allow_html=True)
            with c2:
                st.button("Review", key=f"comp_{lesson['id']}", 
                          on_click=set_lesson, args=(lesson['id'],), width='stretch')
    else:
        st.caption("No completed lessons yet.")
