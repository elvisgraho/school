"""
Library Tab for Guitar Shed.
Optimized for 15k+ video libraries with efficient pagination.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from .styles import apply_conservative_style
from .callbacks import set_lesson, bulk_add_tag_callback, bulk_untag_and_delete_callback
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode

# Page size for AgGrid - balance between performance and usability
GRID_PAGE_SIZE = 100


def render_library(db) -> None:
    """Render the Full Library List optimized for large datasets."""
    apply_conservative_style()

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

    # Tag filter
    all_tags = db.get_all_tags()
    tag_options = {tag['name']: tag['id'] for tag in all_tags}
    selected_tag_names = st.multiselect(
        "Filter by Tags",
        options=list(tag_options.keys()),
        key='lib_tags',
        placeholder="Select tags to filter..."
    )
    selected_tag_ids = [tag_options[name] for name in selected_tag_names] if selected_tag_names else None

    # Clear untag success if tag filter changed
    bulk_untag_success = st.session_state.get('bulk_untag_success')
    if bulk_untag_success:
        if not selected_tag_names or bulk_untag_success.get('tag') not in selected_tag_names:
            st.session_state.bulk_untag_success = None

    search = st.text_input(
        "Search", placeholder="Search by title or author...", key='lib_search'
    )
    transcript_search = st.text_input(
        "Search Transcripts", placeholder="Search in video subtitles...", key='lib_transcript_search'
    )
    st.markdown("<hr style='margin: 0.5rem 0; opacity: 0.2;'>", unsafe_allow_html=True)

    # Determine if we're in transcript search mode
    is_transcript_search = bool(transcript_search and transcript_search.strip())

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

    # Fetch data - use transcript search if active, otherwise regular search
    if is_transcript_search:
        lessons, total_count = db.search_transcripts(
            query=transcript_search.strip(),
            page_size=500,
            status_filter=s_filter,
            year_filter=y_filter,
            month_filter=m_filter,
            tag_ids=selected_tag_ids
        )
    else:
        lessons, total_count = db.get_paginated_lessons(
            page=1,
            page_size=500,  # Limit initial load - ag-grid handles client-side pagination
            status_filter=s_filter,
            search_query=search if search else None,
            year_filter=y_filter,
            month_filter=m_filter,
            tag_ids=selected_tag_ids
        )

    if not lessons:
        st.info("No lessons found matching criteria.")
        return

    # Prepare DataFrame efficiently
    df = pd.DataFrame(lessons)
    df['display_date'] = pd.to_datetime(df['lesson_date']).dt.strftime('%Y-%m-%d')

    # Only use needed columns - add context column only for transcript search
    if is_transcript_search and 'context' in df.columns:
        grid_data = df[['id', 'display_date', 'author', 'title', 'status', 'context']].copy()
    else:
        grid_data = df[['id', 'display_date', 'author', 'title', 'status']].copy()

    # Show count with indicator if results are capped
    if len(df) >= 500:
        st.caption(f"Showing first 500 of {total_count:,} matching lessons. Use filters to narrow results.")
    else:
        st.caption(f"Found {len(df):,} lessons")

    # Bulk tag button - show when there's a search term
    tag_term = transcript_search.strip() if is_transcript_search else search.strip() if search else None
    if tag_term and lessons:
        # Clear success state if search term changed
        bulk_success = st.session_state.get('bulk_tag_success')
        if bulk_success and bulk_success.get('tag') != tag_term:
            st.session_state.bulk_tag_success = None
            bulk_success = None

        lesson_ids = [l['id'] for l in lessons]
        col_tag, col_spacer = st.columns([2, 3])
        with col_tag:
            if bulk_success:
                st.button(
                    f"✓ Tagged {bulk_success['count']} videos as \"{tag_term}\"",
                    key='bulk_tag_btn',
                    disabled=True
                )
            else:
                st.button(
                    f'Tag all {len(lessons)} results as "{tag_term}"',
                    key='bulk_tag_btn',
                    on_click=bulk_add_tag_callback,
                    args=(db, lesson_ids, tag_term)
                )

    # Bulk untag button - show when filtering by exactly one tag
    if selected_tag_names and len(selected_tag_names) == 1:
        tag_name = selected_tag_names[0]
        tag_id = tag_options.get(tag_name)
        bulk_untag_success = st.session_state.get('bulk_untag_success')

        col_untag, col_spacer2 = st.columns([2, 3])
        with col_untag:
            if bulk_untag_success and bulk_untag_success.get('tag') == tag_name:
                st.button(
                    f"✓ Deleted tag \"{tag_name}\"",
                    key='bulk_untag_btn',
                    disabled=True
                )
            else:
                st.button(
                    f'Delete tag "{tag_name}" from all {len(lessons)} videos',
                    key='bulk_untag_btn',
                    on_click=bulk_untag_and_delete_callback,
                    args=(db, tag_id, tag_name),
                    type='secondary'
                )

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
    gb.configure_column("title", flex=1 if is_transcript_search else 2, minWidth=200)
    gb.configure_column("status", width=110, minWidth=100, maxWidth=130)

    # Add context column only for transcript search
    if is_transcript_search:
        gb.configure_column("context", header_name="Match Context", flex=1, minWidth=200,
                            wrapText=True, autoHeight=True)

    # Pagination - smaller page size for better performance
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=GRID_PAGE_SIZE)
    gb.configure_grid_options(
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

    # Render grid with fixed height to avoid autoHeight layout issues
    response = AgGrid(
        grid_data,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.MODEL_CHANGED,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        allow_unsafe_jscode=True,
        height=600,
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
