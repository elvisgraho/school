"""
Sidebar component for Video School.
Contains stats, library sync, goals settings, and metronome.
"""

import streamlit as st
import os
from .metronome import render_metronome

# Try to import tkinter (not available in embedded Python)
try:
    import tkinter as tk
    from tkinter import filedialog
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False


def render_sidebar(db, sync_db_func) -> None:
    """Render sidebar with settings and metronome."""
    with st.sidebar:
        st.markdown("<h3 style='color:#ccc; margin-top:0;'>Video School</h3>", unsafe_allow_html=True)
        st.markdown("<hr style='margin: 10px 0; opacity: 0.2'>", unsafe_allow_html=True)

        # Stats with streak and daily progress
        stats = db.get_stats()
        streak_info = db.get_streak_recovery_info()
        daily_progress = db.get_daily_progress()

        c1, c2 = st.columns(2)
        c1.metric("Total", stats.get('total', 0))
        c2.metric("Done", stats.get('completed', 0))
        c3, c4 = st.columns(2)
        c3.metric("In Progress", stats.get('in_progress', 0))
        c4.metric("Streak", f"{streak_info['current']}d")

        # Daily progress indicator
        goal_reached = daily_progress['completed'] >= daily_progress['goal']
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 8px; padding: 8px 0; margin-top: 4px;">
            <span style="font-size: 0.85rem; color: #888;">Today:</span>
            <span style="font-size: 1rem; font-weight: 600; color: {'#48BB78' if goal_reached else '#fff'};">
                {daily_progress['completed']}/{daily_progress['goal']}
            </span>
            {'<span style="font-size: 0.75rem; color: #48BB78; margin-left: 4px;">Goal reached!</span>' if goal_reached else ''}
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<hr style='margin: 10px 0; opacity: 0.2'>", unsafe_allow_html=True)

        # Folder (Tkinter)
        _render_library_sync(db, sync_db_func)

        st.markdown("<hr style='margin: 10px 0; opacity: 0.2'>", unsafe_allow_html=True)

        # Goals Settings
        _render_goals_settings(db)

        st.markdown("<hr style='margin: 10px 0; opacity: 0.2'>", unsafe_allow_html=True)

        # Metronome
        render_metronome()


def _render_library_sync(db, sync_db_func) -> None:
    """Render library location and sync controls."""
    st.markdown("**Library Location**")

    if HAS_TKINTER:
        # Use tkinter file dialog when available
        col_text, col_btn = st.columns([4, 1])
        with col_text:
            path = st.text_input("Folder", value=st.session_state.folder_path,
                               placeholder="Select folder...", label_visibility="collapsed", disabled=True)
        with col_btn:
            if st.button("...", help="Select Folder"):
                root = tk.Tk()
                root.withdraw()
                root.wm_attributes('-topmost', 1)
                selected_folder = filedialog.askdirectory(master=root)
                root.destroy()
                if selected_folder:
                    st.session_state.folder_path = selected_folder
                    st.rerun()
    else:
        # Fallback: editable text input for portable version
        path = st.text_input(
            "Folder",
            value=st.session_state.folder_path,
            placeholder="Paste folder path here...",
            label_visibility="collapsed",
            help="Paste or type the full path to your video folder"
        )
        if path != st.session_state.folder_path:
            st.session_state.folder_path = path
            st.session_state.db_synced = False

    if st.button("Sync Library", type="secondary", use_container_width=True):
        if st.session_state.folder_path and os.path.isdir(st.session_state.folder_path):
            with st.spinner("Scanning..."):
                s = sync_db_func()
                if s:
                    st.success(f"+{s.get('added', 0)} / Updated: {s.get('updated', 0)}")
        else:
            st.error("Invalid path")


def _render_goals_settings(db) -> None:
    """Render goals settings expander."""
    with st.expander("Goals Settings", expanded=False):
        current_daily = db.get_daily_goal()
        current_weekly = db.get_weekly_goal()

        new_daily = st.number_input(
            "Daily Goal (lessons/day)",
            min_value=1,
            max_value=20,
            value=current_daily,
            step=1,
            key="settings_daily_goal"
        )

        new_weekly = st.number_input(
            "Weekly Goal (lessons/week)",
            min_value=1,
            max_value=100,
            value=current_weekly,
            step=1,
            key="settings_weekly_goal"
        )

        if st.button("Save Goals", width='stretch'):
            db.set_setting('daily_goal', str(new_daily))
            db.set_setting('weekly_goal', str(new_weekly))
            st.success("Goals saved!")
            st.rerun()
