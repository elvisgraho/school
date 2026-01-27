"""
Discovery Tab for Video School.
Enhanced with streak display, daily goals, and smart suggestions.
"""

import streamlit as st
from datetime import datetime
from .styles import apply_conservative_style
from .callbacks import set_lesson, start_playlist
from .components import (
    render_streak_display,
    render_progress_ring,
    render_weekly_progress_bar,
)


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

    # SECTION 0: STREAK AND GOALS
    streak_info = db.get_streak_recovery_info()
    daily_progress = db.get_daily_progress()
    weekly_progress = db.get_weekly_progress()

    # Streak Display
    render_streak_display(
        current=streak_info['current'],
        best=streak_info['best'],
        recovery_info=streak_info
    )

    # Daily and Weekly Goals
    render_progress_ring(
        current=daily_progress['completed'],
        goal=daily_progress['goal'],
        label="Today"
    )
    st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)
    render_weekly_progress_bar(
        current=weekly_progress['completed'],
        goal=weekly_progress['goal']
    )

    st.markdown("---")

    # SECTION 1: IN PROGRESS (prioritized)
    in_progress_lessons = db.get_in_progress_lessons(limit=10)
    if in_progress_lessons:
        # Get tags for all lessons efficiently
        lesson_ids = [l['id'] for l in in_progress_lessons]
        lesson_tags_map = db.get_tags_for_lessons(lesson_ids)

        st.markdown('<div class="section-label">Continue Watching</div>', unsafe_allow_html=True)

        # If 2+ videos, clicking any starts a playlist; otherwise play standalone
        use_playlist = len(in_progress_lessons) >= 2

        for lesson in in_progress_lessons:
            lesson_id = lesson['id']
            tags = lesson_tags_map.get(lesson_id, [])
            tags_str = ' · '.join([t['name'] for t in tags]) if tags else ''
            label = f"{lesson['title']}\n{lesson['author']}" + (f"\n{tags_str}" if tags_str else '')
            if use_playlist:
                st.button(label, key=f"inp_{lesson_id}", width='stretch',
                         on_click=start_playlist, args=(lesson_ids, False, lesson_id))
            else:
                st.button(label, key=f"inp_{lesson_id}", width='stretch',
                         on_click=set_lesson, args=(lesson_id,))
        st.write("")

    # SECTION 2: SMART SUGGESTIONS (prioritizes In Progress, then New)
    st.markdown('<div class="section-label">Suggested for You</div>', unsafe_allow_html=True)

    priority_lessons = db.get_priority_suggestions(limit=5)

    if priority_lessons:
        priority_ids = [l['id'] for l in priority_lessons]
        priority_tags_map = db.get_tags_for_lessons(priority_ids)

        for lesson in priority_lessons:
            lesson_id = lesson['id']
            status_badge = "▶ " if lesson['status'] == 'In Progress' else ""
            tags = priority_tags_map.get(lesson_id, [])
            tags_str = ' · '.join([t['name'] for t in tags]) if tags else ''
            label = f"{status_badge}{lesson['title']}\n{lesson['author']}" + (f"\n{tags_str}" if tags_str else '')
            st.button(label, key=f"sug_{lesson_id}", width='stretch',
                     on_click=set_lesson, args=(lesson_id,))
    else:
        st.info("Library is empty. Please sync.")

    st.write("")

    # SECTION 3: TIME TO REVIEW (Spaced Repetition)
    spaced_suggestions = db.get_spaced_repetition_suggestions()
    has_suggestions = any(lessons for lessons in spaced_suggestions.values())

    if has_suggestions:
        st.markdown('<div class="section-label">Time to Review</div>', unsafe_allow_html=True)

        # Collect all lesson IDs for batch tag fetch
        all_review_ids = []
        for lessons in spaced_suggestions.values():
            all_review_ids.extend([l['id'] for l in lessons[:2]])
        review_tags_map = db.get_tags_for_lessons(all_review_ids) if all_review_ids else {}

        interval_labels = {
            '1_week': '1 Week Ago',
            '1_month': '1 Month Ago',
            '3_months': '3 Months Ago',
            '6_months': '6 Months Ago',
            '1_year': '1 Year Ago'
        }

        for interval_key, interval_label in interval_labels.items():
            lessons = spaced_suggestions.get(interval_key, [])
            if lessons:
                st.caption(interval_label)
                for lesson in lessons[:2]:  # Max 2 per interval
                    lesson_id = lesson['id']
                    completed_date = lesson.get('completed_at', '')
                    if completed_date:
                        try:
                            date_obj = datetime.strptime(completed_date, '%Y-%m-%d %H:%M:%S.%f')
                            date_str = date_obj.strftime('%b %d, %Y')
                        except ValueError:
                            try:
                                date_obj = datetime.strptime(completed_date, '%Y-%m-%d %H:%M:%S')
                                date_str = date_obj.strftime('%b %d, %Y')
                            except ValueError:
                                date_str = ''
                    else:
                        date_str = ''
                    tags = review_tags_map.get(lesson_id, [])
                    tags_str = ' · '.join([t['name'] for t in tags]) if tags else ''
                    label = f"{lesson['title']}\n{lesson['author']}" + (f" • {date_str}" if date_str else "") + (f"\n{tags_str}" if tags_str else "")
                    st.button(label, key=f"rev_{interval_key}_{lesson_id}", width='stretch',
                             on_click=set_lesson, args=(lesson_id,))
        st.write("")

    # SECTION 4: RECENTLY COMPLETED
    st.markdown('<div class="section-label">Recently Completed</div>', unsafe_allow_html=True)

    completed_lessons, _ = db.get_paginated_lessons(page=1, page_size=5, status_filter=['Completed'])

    if completed_lessons:
        completed_ids = [l['id'] for l in completed_lessons]
        completed_tags_map = db.get_tags_for_lessons(completed_ids)

        for lesson in completed_lessons:
            lesson_id = lesson['id']
            tags = completed_tags_map.get(lesson_id, [])
            tags_str = ' · '.join([t['name'] for t in tags]) if tags else ''
            label = f"{lesson['title']}\n{lesson['author']}" + (f"\n{tags_str}" if tags_str else '')
            st.button(label, key=f"comp_{lesson_id}", width='stretch',
                     on_click=set_lesson, args=(lesson_id,))
    else:
        st.caption("No completed lessons yet.")
