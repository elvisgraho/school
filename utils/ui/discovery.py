"""
Discovery Tab for Guitar Shed.
"""

import streamlit as st
from .styles import apply_conservative_style
from .callbacks import set_lesson


def render_discovery(db) -> None:
    """Render the Discovery Dashboard."""
    apply_conservative_style()

    # CSS for card buttons
    st.markdown("""
        <style>
        div.stButton > button {
            background: #2D2D2D !important;
            border: 1px solid #3D3D3D !important;
            border-radius: 6px !important;
            padding: 12px 16px !important;
            margin-bottom: 8px !important;
            cursor: pointer !important;
            transition: all 0.15s ease !important;
            text-align: left !important;
            width: 100% !important;
            max-width: 100% !important;
            height: auto !important;
            white-space: pre-wrap !important;
            color: #A0A0A0 !important;
            font-size: 0.85rem !important;
            display: flex !important;
            justify-content: flex-start !important;
            align-items: flex-start !important;
        }
        div.stButton > button > div {
            display: flex !important;
            justify-content: flex-start !important;
            align-items: flex-start !important;
            text-align: left !important;
            width: 100% !important;
        }
        div.stButton > button > div > span {
            text-align: left !important;
            display: block !important;
            width: 100% !important;
        }
        div.stButton > button > div > span > div {
            text-align: left !important;
        }
        div.stButton p {
            text-align: left !important;
            color: #A0A0A0 !important;
            font-size: 0.85rem !important;
            margin: 0 !important;
        }
        div.stButton p::first-line {
            color: #E0E0E0 !important;
            font-weight: 600 !important;
            font-size: 1rem !important;
        }
        div.stButton > button:hover {
            background: #3D3D3D !important;
            border-color: #4D4D4D !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # SECTION 1: IN PROGRESS
    in_progress_lessons = db.get_in_progress_lessons(limit=10)
    if in_progress_lessons:
        st.markdown('<div class="section-label">Continue Watching</div>', unsafe_allow_html=True)
        for lesson in in_progress_lessons:
            lesson_id = lesson['id']
            label = f"{lesson['title']}\n{lesson['author']}"
            st.button(label, key=f"inp_{lesson_id}", use_container_width=True,
                     on_click=set_lesson, args=(lesson_id,))
        st.write("")

    # SECTION 2: LESSONS OF THE DAY
    st.markdown('<div class="section-label">Lessons of the Day</div>', unsafe_allow_html=True)

    lesson_of_day = db.get_lesson_of_day(limit=5)

    if lesson_of_day:
        for lesson in lesson_of_day:
            lesson_id = lesson['id']
            label = f"{lesson['title']}\n{lesson['author']}"
            st.button(label, key=f"day_{lesson_id}", use_container_width=True,
                     on_click=set_lesson, args=(lesson_id,))
    else:
        st.info("Library is empty. Please sync.")

    # SECTION 3: COMPLETED
    st.markdown('<div class="section-label">Completed Lessons</div>', unsafe_allow_html=True)

    completed_lessons, _ = db.get_paginated_lessons(page=1, page_size=10, status_filter=['Completed'])

    if completed_lessons:
        for lesson in completed_lessons:
            lesson_id = lesson['id']
            label = f"{lesson['title']}\n{lesson['author']}"
            st.button(label, key=f"comp_{lesson_id}", use_container_width=True,
                     on_click=set_lesson, args=(lesson_id,))
    else:
        st.caption("No completed lessons yet.")
