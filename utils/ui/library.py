"""
Library Tab for Guitar Shed.
Optimized for 15k+ video libraries with efficient pagination.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from .styles import apply_conservative_style
from .callbacks import set_lesson
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode

# Page size for AgGrid - balance between performance and usability
GRID_PAGE_SIZE = 100


def _get_filter_hash(status: str, year: str, month: str, search: str, hide_completed: bool = False) -> str:
    """Generate a hash for the current filter state."""
    return f"{status}|{year}|{month}|{search}|{hide_completed}"


def render_library(db) -> None:
    """Render the Full Library List optimized for large datasets."""
    apply_conservative_style()

    # Initialize filter state in session
    if 'lib_filter_hash' not in st.session_state:
        st.session_state.lib_filter_hash = ""

    # 1. Filter Controls
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    with c1:
        status_filter = st.selectbox(
            "Status", ['All', 'New', 'In Progress', 'Completed'], key='lib_status'
        )
    with c2:
        years = db.get_years_with_lessons()
        current_year = datetime.now().year
        year_options = ['All'] + (years if years else [current_year])
        selected_year = st.selectbox("Year", year_options, key='lib_year')
    with c3:
        month_options = ['All', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        selected_month = st.selectbox("Month", month_options, key='lib_month')
    with c4:
        hide_completed = st.checkbox("Hide Completed", key='lib_hide_completed')

    search = st.text_input(
        "Search", placeholder="Search by title or author...", key='lib_search'
    )
    st.markdown("<hr style='margin: 0.5rem 0; opacity: 0.2;'>", unsafe_allow_html=True)

    # Build filter parameters
    # If hide_completed is checked, exclude Completed from results
    if hide_completed:
        if status_filter == 'Completed':
            st.warning("Cannot hide completed when filtering by Completed status.")
            s_filter = ['Completed']
        elif status_filter == 'All':
            s_filter = ['New', 'In Progress']
        else:
            s_filter = [status_filter]
    else:
        s_filter = [status_filter] if status_filter != 'All' else None
    y_filter = int(selected_year) if selected_year != 'All' else None
    m_filter = month_options.index(selected_month) if selected_month != 'All' else None

    # Check if filters changed - reset grid state if so
    current_hash = _get_filter_hash(status_filter, str(selected_year), selected_month, search, hide_completed)
    if current_hash != st.session_state.lib_filter_hash:
        st.session_state.lib_filter_hash = current_hash
        # Force new grid key to reset AgGrid state on filter change
        st.session_state.lib_grid_key = f"library_aggrid_{hash(current_hash)}"

    # Ensure grid key exists
    if 'lib_grid_key' not in st.session_state:
        st.session_state.lib_grid_key = "library_aggrid_default"

    # Fetch data - limit to reasonable size for ag-grid performance with 15k+ libraries
    lessons, total_count = db.get_paginated_lessons(
        page=1,
        page_size=500,  # Limit initial load - ag-grid handles client-side pagination
        status_filter=s_filter,
        search_query=search if search else None,
        year_filter=y_filter,
        month_filter=m_filter
    )

    if not lessons:
        st.info("No lessons found matching criteria.")
        return

    # Prepare DataFrame efficiently
    df = pd.DataFrame(lessons)
    df['display_date'] = pd.to_datetime(df['lesson_date']).dt.strftime('%Y-%m-%d')

    # Only use needed columns
    grid_data = df[['id', 'display_date', 'author', 'title', 'status']].copy()

    # Show count with indicator if results are capped
    if len(df) >= 500:
        st.caption(f"Showing first 500 of {total_count:,} matching lessons. Use filters to narrow results.")
    else:
        st.caption(f"Found {len(df):,} lessons")

    # Build AgGrid options
    gb = GridOptionsBuilder.from_dataframe(grid_data)

    # Date formatter
    date_formatter = JsCode("""
    function(params) {
        if (params.value) {
            return params.value.split('-').reverse().join('-');
        }
        return "";
    }
    """)
    gb.configure_column("display_date", header_name="Date", valueFormatter=date_formatter,
                        width=110, minWidth=100, maxWidth=130)
    gb.configure_column("author", width=150, minWidth=120)
    gb.configure_column("title", flex=2, minWidth=200)
    gb.configure_column("status", width=110, minWidth=100, maxWidth=130)

    # Pagination - smaller page size for better performance
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=GRID_PAGE_SIZE)
    gb.configure_grid_options(
        domLayout='autoHeight',
        rowBuffer=20,  # Buffer for smooth scrolling
        suppressRowClickSelection=False,
        enableCellTextSelection=True,
    )

    # Default column settings
    gb.configure_default_column(
        sortable=True,
        filter=True,
        resizable=True,
    )

    gb.configure_selection(selection_mode='single', use_checkbox=False, pre_selected_rows=[])
    gb.configure_column("id", hide=True)

    grid_options = gb.build()

    # CSS: Pagination at top, cleaner styling
    custom_css = {
        ".ag-root-wrapper": {
            "display": "flex",
            "flex-direction": "column-reverse"
        },
        ".ag-paging-panel": {
            "border-top": "0px",
            "border-bottom": "1px solid #333",
            "justify-content": "flex-start",
            "padding-bottom": "10px"
        },
        ".ag-row": {
            "cursor": "pointer"
        },
        ".ag-row:hover": {
            "background-color": "#2a2a2a !important"
        }
    }

    # Render grid with static key
    response = AgGrid(
        grid_data,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.MODEL_CHANGED,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        allow_unsafe_jscode=True,
        height=None,
        width='100%',
        fit_columns_on_grid_load=True,
        key="library_grid",
        theme='streamlit',
        custom_css=custom_css
    )

    # Handle row selection
    selected_rows = response.get('selected_rows')
    if selected_rows is not None and len(selected_rows) > 0:
        try:
            if isinstance(selected_rows, pd.DataFrame):
                lesson_id = int(selected_rows.iloc[0]['id'])
            else:
                lesson_id = int(selected_rows[0]['id'])

            set_lesson(lesson_id)
            st.rerun()
        except (KeyError, IndexError, TypeError, ValueError):
            pass