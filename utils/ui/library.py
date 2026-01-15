"""
Library Tab for Guitar Shed.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from .styles import apply_conservative_style
from .callbacks import set_lesson
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode

def render_library(db) -> None:
    """Render the Full Library List optimized for large datasets."""
    apply_conservative_style()
    
    # 1. Controls
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        status_filter = st.selectbox("Status", ['All', 'New', 'In Progress', 'Completed'], key='lib_status')
    with c2:
        years = db.get_years_with_lessons()
        current_year = datetime.now().year
        year_options = ['All'] + (years if years else [current_year])
        selected_year = st.selectbox("Year", year_options, key='lib_year')
    with c3:
        month_options = ['All', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        selected_month = st.selectbox("Month", month_options, key='lib_month')
    
    search = st.text_input("Search", placeholder="Search by title or author...", key='lib_search')
    st.markdown("<hr style='margin: 0.5rem 0; opacity: 0.2;'>", unsafe_allow_html=True)
    
    # Logic for filters
    s_filter = [status_filter] if status_filter != 'All' else None
    y_filter = int(selected_year) if selected_year != 'All' else None
    m_filter = month_options.index(selected_month) if selected_month != 'All' else None
    
    # Fetch Data
    lessons, _ = db.get_paginated_lessons(
        page=1, 
        page_size=20000, 
        status_filter=s_filter, search_query=search,
        year_filter=y_filter, month_filter=m_filter
    )
    
    if not lessons:
        st.info("No lessons found matching criteria.")
        return

    # Prepare DataFrame
    df = pd.DataFrame(lessons)
    df['display_date'] = pd.to_datetime(df['lesson_date']).dt.strftime('%Y-%m-%d')
    cols_to_use = ['id', 'display_date', 'author', 'title', 'status']

    # Prevent SettingWithCopyWarning
    grid_data = df[cols_to_use].copy()
    
    # Build options
    gb = GridOptionsBuilder.from_dataframe(grid_data)
    
    # Date Formatter JS
    date_formatter = JsCode("""
    function(params) {
        if (params.value) {
            return params.value.split('-').reverse().join('-');
        }
        return "";
    }
    """)
    gb.configure_column("display_date", header_name="Date", valueFormatter=date_formatter)

    # Pagination & Layout
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=500)
    gb.configure_grid_options(domLayout='autoHeight') 
    
    # Standard settings
    # --- FIX: Add flex=1 here so columns stretch to fill the table width ---
    gb.configure_default_column(
        sortable=True, 
        filter=True, 
        resizable=True, 
        flex=1,          # <--- Forces columns to fill space
        minWidth=100     # <--- Prevents them from getting too squished
    )
    
    gb.configure_selection(selection_mode='single', use_checkbox=False, pre_selected_rows=[])
    gb.configure_column("id", hide=True)
    
    grid_options = gb.build()
    
    # CSS: Pagination at Top
    custom_css = {
        ".ag-root-wrapper": {"display": "flex", "flex-direction": "column-reverse"},
        ".ag-paging-panel": {"border-top": "0px", "border-bottom": "1px solid #333", "justify-content": "flex-start", "padding-bottom": "10px"}
    }
    
    st.caption(f"Found {len(df)} lessons")

    # Render
    response = AgGrid(
        grid_data,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        allow_unsafe_jscode=True,
        height=None,
        width='100%',
        fit_columns_on_grid_load=True, # <--- Also helps ensure full width on load
        key='library_aggrid',
        theme='streamlit',
        custom_css=custom_css
    )
    
    # Handle selection
    selected_rows = response.get('selected_rows')
    if selected_rows is not None and len(selected_rows) > 0:
        try:
            if isinstance(selected_rows, pd.DataFrame):
                lesson_id = int(selected_rows.iloc[0]['id'])
            else:
                lesson_id = int(selected_rows[0]['id'])
            
            set_lesson(lesson_id)
            st.rerun()
        except Exception:
            pass

def render_library_fullscreen(db) -> None:
    render_library(db)