"""
Library Tab for Guitar Shed.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from .styles import apply_conservative_style
from .callbacks import set_lesson


def render_library(db) -> None:
    """Render the Full Library List."""
    apply_conservative_style()
    
    # Filter Controls - Row 1: Dropdowns
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        status_filter = st.selectbox("Status", ['All', 'New', 'In Progress', 'Completed'], key='lib_status')
    with c2:
        years = db.get_years_with_lessons()
        current_year = datetime.now().year
        # If database has years, use them, else default to current
        year_options = ['All'] + (years if years else [current_year])
        selected_year = st.selectbox("Year", year_options, key='lib_year')
    with c3:
        month_options = ['All', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        selected_month = st.selectbox("Month", month_options, key='lib_month')
    
    # Row 2: Search field (full width)
    search = st.text_input("Search", placeholder="Search by title or author...", key='lib_search')
    
    # Add a thin separator
    st.markdown("<hr style='margin: 0.5rem 0; opacity: 0.2;'>", unsafe_allow_html=True)
    
    # Logic for filters
    s_filter = [status_filter] if status_filter != 'All' else None
    y_filter = int(selected_year) if selected_year != 'All' else None
    m_filter = month_options.index(selected_month) if selected_month != 'All' else None
    
    # Fetch Data
    lessons, _ = db.get_paginated_lessons(
        page=1, page_size=2000, # Large page size for scrolling list
        status_filter=s_filter, search_query=search,
        year_filter=y_filter, month_filter=m_filter
    )
    
    if not lessons:
        st.info("No lessons found matching criteria.")
        return

    # Prepare DataFrame
    df = pd.DataFrame(lessons)
    # Format date for display
    df['display_date'] = pd.to_datetime(df['lesson_date']).dt.strftime('%Y-%m-%d')
    
    # Display Table - Full width, use native browser scrolling
    event = st.dataframe(
        df[['display_date', 'author', 'title', 'status']], 
        width='stretch',
        hide_index=True,
        column_config={
            'display_date': st.column_config.TextColumn('Date', width='small'),
            'author': st.column_config.TextColumn('Author', width='medium'),
            'title': st.column_config.TextColumn('Title', width='large'),
            'status': st.column_config.TextColumn('Status', width='small')
        },
        selection_mode='single-row',
        on_select='rerun',
        key='library_data_table'
    )
    
    # Handle Selection
    if event and len(event.selection['rows']) > 0:
        row_idx = event.selection['rows'][0]
        # Map row index back to lesson ID
        lesson_id = lessons[row_idx]['id']
        set_lesson(lesson_id)
        st.rerun()


def render_library_fullscreen(db) -> None:
    """Render the Full Library List in fullscreen mode."""
    render_library(db)
