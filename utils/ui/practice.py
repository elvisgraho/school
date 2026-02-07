"""
Practice Room (Video Player) for Video School.
Optimized for smooth playback and responsive controls.
"""

import streamlit as st
import os
import urllib.parse
from .callbacks import (
    clear_lesson, update_status_callback, add_tag_callback, remove_tag_callback,
    exit_playlist, playlist_next, playlist_prev, complete_and_next
)

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

    # Detect playlist mode
    playlist_ids = st.session_state.get('playlist_ids', [])
    playlist_index = st.session_state.get('playlist_index', 0)
    is_playlist_mode = len(playlist_ids) > 0
    playlist_total = len(playlist_ids)
    playlist_position = playlist_index

    # Header with playlist progress
    if is_playlist_mode:
        progress_pct = playlist_position / playlist_total
        st.markdown(
            f'<div style="display: flex; justify-content: space-between; align-items: center;">'
            f'<span style="color: #888;">Playlist</span>'
            f'<span style="font-weight: 600;">{playlist_position} / {playlist_total}</span>'
            f'</div>',
            unsafe_allow_html=True
        )
        st.progress(progress_pct)

    st.markdown(f"### {lesson['title']}")

    # Video Player
    video_path = lesson.get('filepath', '')
    if video_path and os.path.exists(video_path):
        st.markdown(
            '<style>video[data-testid="stVideo"] { max-height: 70vh; }</style>',
            unsafe_allow_html=True,
        )
        st.video(video_path)
    else:
        st.error(f"Video file not found: {lesson.get('filename', 'Unknown')}")
        st.caption(f"Expected path: {video_path}")
        st.info("The file may have been moved or deleted. Try syncing your library again.")
        return

    # Metadata and actions row
    current_status = lesson['status']
    status_color = STATUS_COLORS.get(current_status, '#888')

    # Get lesson tags
    lesson_tags = db.get_lesson_tags(lesson_id)
    tags_html = ''
    if lesson_tags:
        tags_html = '<span style="color: #555;">|</span>' + ''.join([
            f'<span style="background: #4a5568; color: #e2e8f0; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; margin-left: 4px;">{tag["name"]}</span>'
            for tag in lesson_tags
        ])

    # Combined metadata + buttons in one clean row
    metadata_html = f'<div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; margin-bottom: 8px;"><div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;"><span style="color: #aaa;">By</span><span style="color: #fff; font-weight: 500;">{lesson["author"]}</span><span style="color: #555;">|</span><span style="color: #aaa;">{lesson["lesson_date"]}</span><span style="color: #555;">|</span><span style="background: {status_color}22; color: {status_color}; padding: 2px 8px; border-radius: 4px; font-size: 0.85rem;">{current_status}</span>{tags_html}</div></div>'
    st.markdown(metadata_html, unsafe_allow_html=True)

    # Action buttons
    youtube_query = urllib.parse.quote_plus(lesson['title'])
    youtube_url = f"https://www.youtube.com/results?search_query={youtube_query}"

    if is_playlist_mode:
        has_prev = playlist_index > 0
        has_next = playlist_index < playlist_total - 1

        # Single unified action row for playlist
        c1, c2, c3, c4, c5 = st.columns([1, 1, 2, 1, 1])

        with c1:
            st.button("Exit", on_click=exit_playlist)
        with c2:
            st.button("Prev", on_click=playlist_prev, disabled=not has_prev)
        with c3:
            # Primary action based on status
            if current_status == 'Completed':
                if has_next:
                    st.button("Next", type="primary", on_click=playlist_next)
                else:
                    st.button("Done", type="primary", on_click=exit_playlist)
            else:
                if has_next:
                    st.button("Complete & Next", type="primary",
                              on_click=complete_and_next, args=(db, lesson['id']))
                else:
                    st.button("Complete", type="primary",
                              on_click=update_status_callback, args=(db, lesson['id'], 'Completed'))
        with c4:
            if has_next and current_status != 'Completed':
                st.button("Skip", on_click=playlist_next)
        with c5:
            st.link_button("YouTube", youtube_url)

        # Up Next preview
        if has_next:
            upcoming_ids = playlist_ids[playlist_index + 1:playlist_index + 3]
            upcoming_titles = []
            for uid in upcoming_ids:
                ul = db.get_lesson_by_id(uid)
                if ul:
                    upcoming_titles.append(ul['title'])
            if upcoming_titles:
                st.caption(f"Next: {upcoming_titles[0]}" + (f" (+{playlist_total - playlist_position - 1} more)" if len(upcoming_titles) > 1 else ""))
    else:
        # Single video mode - clean 3-button layout
        c1, c2, c3 = st.columns(3)

        with c1:
            st.button("← Back", on_click=clear_lesson)
        with c2:
            if current_status == 'New':
                st.button("Start", type="primary",
                          on_click=update_status_callback, args=(db, lesson['id'], 'In Progress'))
            elif current_status == 'In Progress':
                st.button("Complete", type="primary",
                          on_click=update_status_callback, args=(db, lesson['id'], 'Completed'))
            else:
                st.button("Practice Again", type="primary",
                          on_click=update_status_callback, args=(db, lesson['id'], 'In Progress'))
        with c3:
            st.link_button("YouTube", youtube_url)

    # Tag management section
    with st.expander("Manage Tags", expanded=False):
        all_tags = db.get_all_tags()
        current_tag_ids = {tag['id'] for tag in lesson_tags}

        # Add new tag with autocomplete
        existing_tag_names = [t['name'] for t in all_tags]
        col_add1, col_add2 = st.columns([3, 1])
        with col_add1:
            new_tag = st.selectbox(
                "Add tag",
                options=[''] + existing_tag_names + ['+ Create new...'],
                key=f'add_tag_select_{lesson_id}',
                label_visibility='collapsed',
                placeholder='Select or create tag...'
            )
        with col_add2:
            if new_tag == '+ Create new...':
                pass  # Will show text input below
            elif new_tag and new_tag not in [t['name'] for t in lesson_tags]:
                st.button("Add", key=f'add_tag_btn_{lesson_id}',
                         on_click=add_tag_callback, args=(db, lesson_id, new_tag))

        # Show text input for new tag creation
        if new_tag == '+ Create new...':
            col_new1, col_new2 = st.columns([3, 1])
            with col_new1:
                custom_tag = st.text_input("New tag name", key=f'custom_tag_{lesson_id}',
                                          label_visibility='collapsed', placeholder='Enter new tag name...')
            with col_new2:
                if custom_tag and custom_tag.strip():
                    st.button("Create", key=f'create_tag_btn_{lesson_id}',
                             on_click=add_tag_callback, args=(db, lesson_id, custom_tag))

        # Remove existing tags
        if lesson_tags:
            st.caption("Current tags (click to remove):")
            tag_cols = st.columns(min(len(lesson_tags), 4))
            for i, tag in enumerate(lesson_tags):
                with tag_cols[i % 4]:
                    st.button(f"✕ {tag['name']}", key=f'remove_tag_{lesson_id}_{tag["id"]}',
                             on_click=remove_tag_callback, args=(db, lesson_id, tag['id']))