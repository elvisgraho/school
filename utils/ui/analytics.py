"""
Analytics Tab for Video School.
Provides insights into practice consistency, volume, and library progress.
Enhanced with interactive heatmap, personal records, and dashboard widgets.
"""

import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
from .styles import apply_conservative_style
from .callbacks import set_lesson
from .components import (
    render_mini_bar_chart,
    render_trend_indicator,
    render_personal_record_card,
)


def render_analytics(db) -> None:
    """Render Analytics with a focus on consistency and progress trends."""
    apply_conservative_style()

    # --- Data Fetching ---
    stats = db.get_stats()
    streak_info = db.get_streak_recovery_info()
    activity_365 = db.get_activity_data(days=365)

    # --- Section 1: Top Level Metrics ---
    st.markdown('<div class="section-label">Snapshot</div>', unsafe_allow_html=True)

    # Calculate "Active Days" (days with at least 1 completion in last 30 days)
    today = datetime.now().date()
    start_30 = today - timedelta(days=30)
    active_days_count = sum(1 for x in activity_365
                            if datetime.strptime(x['date'], '%Y-%m-%d').date() >= start_30)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Library", stats['total'])
    c2.metric("Total Completed", stats['completed'])
    c3.metric("Current Streak", f"{streak_info['current']} Days")
    c4.metric("Active Days (30d)", f"{active_days_count}")

    st.markdown("---")

    # --- Section 1.5: Progress Dashboard Widgets ---
    st.markdown('<div class="section-label">Progress Dashboard</div>', unsafe_allow_html=True)

    st.markdown("<div style='font-size: 0.85rem; color: #888; margin-bottom: 6px;'>This Week</div>", unsafe_allow_html=True)
    last_7_days = db.get_last_7_days_activity()
    render_mini_bar_chart(last_7_days, height=150)

    monthly_comp = db.get_monthly_comparison()
    render_trend_indicator(
        current=monthly_comp['current'],
        previous=monthly_comp['previous'],
        label="This Month"
    )

    st.markdown("---")

    # --- Section 2: Consistency Heatmap (GitHub Style) with Year Navigation ---
    available_years = db.get_available_years_for_heatmap()
    current_year = datetime.now().year

    # Year selection
    col_label, col_select = st.columns([3, 1])
    with col_label:
        st.markdown('<div class="section-label">Consistency Map</div>', unsafe_allow_html=True)
    with col_select:
        if available_years:
            # Add current year if not in list
            if current_year not in available_years:
                available_years = [current_year] + available_years
            selected_year = st.selectbox("Year", available_years, index=0, label_visibility="collapsed")
        else:
            selected_year = current_year

    if activity_365 or selected_year != current_year:
        # Get activity data for selected year
        if selected_year == current_year:
            activity_data = activity_365
        else:
            activity_data = db.get_activity_data_for_year(selected_year)

        if activity_data:
            df_heat = pd.DataFrame(activity_data)
            df_heat['date'] = pd.to_datetime(df_heat['date'])

            # Create a full date range for the year (GitHub style: full weeks)
            if selected_year == current_year:
                # Use today's date explicitly to ensure we include today
                end_date = pd.Timestamp(datetime.now().date())
                # Go back ~52 weeks, starting from Monday
                start_date = end_date - pd.Timedelta(days=364)
                # Align to Monday (weekday 0 in pandas)
                start_date = start_date - pd.Timedelta(days=start_date.weekday())
            else:
                start_date = pd.Timestamp(f'{selected_year}-01-01')
                # Align to Monday
                start_date = start_date - pd.Timedelta(days=start_date.weekday())
                end_date = pd.Timestamp(f'{selected_year}-12-31')

            date_range = pd.date_range(start=start_date, end=end_date)
            df_full = pd.DataFrame({'date': date_range})
            df_heat = pd.merge(df_full, df_heat, on='date', how='left').fillna({'count': 0})
            df_heat['count'] = df_heat['count'].astype(int)

            # GitHub-style: weeks as columns, days as rows
            # Monday = 0 (top), Sunday = 6 (bottom)
            df_heat['day_of_week'] = df_heat['date'].dt.weekday  # Mon=0, Sun=6
            df_heat['week_num'] = ((df_heat['date'] - start_date).dt.days // 7)
            df_heat['month'] = df_heat['date'].dt.strftime('%b')
            df_heat['month_num'] = df_heat['date'].dt.month
            
            # Add date string for selection (Altair needs string for proper selection return)
            df_heat['date_str'] = df_heat['date'].dt.strftime('%Y-%m-%d')

            # Day labels for y-axis (Mon, Wed, Fri visible)
            day_labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            df_heat['day_name'] = df_heat['day_of_week'].apply(lambda x: day_labels[x])

            # Get month positions for labels (first week of each month)
            month_labels = df_heat.groupby('month_num').agg({
                'week_num': 'first',
                'month': 'first'
            }).reset_index()

            # Create selection for clickable days - use encodings for better compatibility
            selection = alt.selection_point(
                name='date_select',
                encodings=['x', 'y'],  # Select by position
                on='click',
                empty=True
            )

            # Main heatmap with click selection (only days with activity are visually interactive)
            heatmap = alt.Chart(df_heat).mark_rect(
                cornerRadius=2,
                stroke='#1a1a1a',
                strokeWidth=1,
                cursor='pointer'
            ).encode(
                x=alt.X('week_num:O', axis=None, title=None),
                y=alt.Y('day_of_week:O',
                        axis=alt.Axis(
                            labels=True,
                            labelExpr="datum.value == 0 ? 'Mon' : datum.value == 2 ? 'Wed' : datum.value == 4 ? 'Fri' : ''",
                            ticks=False,
                            domain=False,
                            labelColor='#666',
                            labelFontSize=10
                        ),
                        title=None),
                color=alt.Color('count:Q',
                                scale=alt.Scale(
                                    type='threshold',
                                    domain=[1, 3, 6, 10],
                                    range=['#2D2D2D', '#0e4429', '#006d32', '#26a641', '#39d353']
                                ),
                                legend=None),
                tooltip=[
                    alt.Tooltip('date:T', title='Date', format='%b %d, %Y'),
                    alt.Tooltip('count:Q', title='Lessons')
                ],
                opacity=alt.condition(
                    alt.datum.count > 0,
                    alt.value(1),
                    alt.value(0.5)  # Dim days with no activity
                )
            ).add_params(
                selection
            ).properties(
                height=110
            )

            # Month labels on top (rendered separately to allow selection on heatmap)
            month_text = alt.Chart(month_labels).mark_text(
                align='left',
                baseline='bottom',
                dy=-5,
                fontSize=10,
                color='#666'
            ).encode(
                x=alt.X('week_num:O', axis=None),
                text='month:N'
            ).properties(height=20)

            # Render month labels (static, no interaction)
            st.altair_chart(month_text.configure_view(strokeWidth=0), width='stretch')

            # Render heatmap with selection callback
            chart_selection = st.altair_chart(
                heatmap.configure_view(strokeWidth=0),
                width='stretch',
                on_select="rerun"
            )
            
            # Handle click on heatmap - set browse_by_date if a day was clicked
            if chart_selection:
                # Selection is nested under chart_selection.selection.date_select
                selection_data = chart_selection.get('selection', {})
                selected_points = selection_data.get('date_select', [])
                
                if selected_points:
                    for selected in selected_points:
                        week_num = selected.get('week_num')
                        day_of_week = selected.get('day_of_week')
                        if week_num is not None and day_of_week is not None:
                            # Find the matching date in our dataframe
                            match = df_heat[
                                (df_heat['week_num'] == week_num) &
                                (df_heat['day_of_week'] == day_of_week)
                            ]
                            if not match.empty:
                                clicked_date = match.iloc[0]['date']
                                if isinstance(clicked_date, pd.Timestamp):
                                    st.session_state['browse_by_date'] = clicked_date.date()
                                break

            # Color legend (GitHub style: Less - More) with click hint
            st.markdown("""
            <div style="display: flex; gap: 4px; justify-content: space-between; align-items: center; margin-top: 4px; font-size: 0.7rem; color: #666;">
                <span style="opacity: 0.7;">Click a day to browse</span>
                <div style="display: flex; gap: 4px; align-items: center;">
                    <span>Less</span>
                    <span style="display: inline-block; width: 10px; height: 10px; background: #161b22; border-radius: 2px;"></span>
                    <span style="display: inline-block; width: 10px; height: 10px; background: #0e4429; border-radius: 2px;"></span>
                    <span style="display: inline-block; width: 10px; height: 10px; background: #006d32; border-radius: 2px;"></span>
                    <span style="display: inline-block; width: 10px; height: 10px; background: #26a641; border-radius: 2px;"></span>
                    <span style="display: inline-block; width: 10px; height: 10px; background: #39d353; border-radius: 2px;"></span>
                    <span>More</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info(f"No completion data for {selected_year}.")
    else:
        st.info("Complete your first lesson to generate the consistency map.")

    st.markdown("---")
    
    # --- Section 3: Progress & Habits (Grid Layout) ---
    c_left, c_right = st.columns([1, 1])
    
    with c_left:
        # 3a. Cumulative Progress
        st.markdown('<div class="section-label">Accumulated Knowledge</div>', unsafe_allow_html=True)
        trend_data = db.get_backlog_trend()

        if trend_data:
            df_trend = pd.DataFrame(trend_data)
            df_trend['date'] = pd.to_datetime(df_trend['date'])

            # Add a baseline point at 0 before first completion for proper area rendering
            first_date = df_trend['date'].min()
            baseline_date = first_date - pd.Timedelta(days=1)
            baseline_row = pd.DataFrame([{
                'date': baseline_date,
                'completed_cumulative': 0,
                'backlog': df_trend['backlog'].iloc[0] + df_trend['completed_cumulative'].iloc[0]
            }])
            df_trend = pd.concat([baseline_row, df_trend], ignore_index=True)

            # Add today if not present (to extend the line to current date)
            today = pd.Timestamp(datetime.now().date())
            if df_trend['date'].max() < today:
                last_cumulative = df_trend['completed_cumulative'].iloc[-1]
                last_backlog = df_trend['backlog'].iloc[-1]
                today_row = pd.DataFrame([{
                    'date': today,
                    'completed_cumulative': last_cumulative,
                    'backlog': last_backlog
                }])
                df_trend = pd.concat([df_trend, today_row], ignore_index=True)

            # Area chart showing accumulation
            chart_trend = alt.Chart(df_trend).mark_area(
                line={'color': '#4299E1'},
                color=alt.Gradient(
                    gradient='linear',
                    stops=[alt.GradientStop(color='#4299E1', offset=0),
                           alt.GradientStop(color='rgba(66, 153, 225, 0.1)', offset=1)],
                    x1=1, x2=1, y1=1, y2=0
                )
            ).encode(
                x=alt.X('date:T', axis=alt.Axis(format='%b %d', title=None, grid=False)),
                y=alt.Y('completed_cumulative:Q', title=None, axis=alt.Axis(grid=True)),
                tooltip=['date:T', 'completed_cumulative:Q']
            ).properties(height=220)

            st.altair_chart(chart_trend, width='stretch')
        else:
            st.caption("No history available.")

    with c_right:
        # 3b. Monthly Velocity (Bar)
        st.markdown('<div class="section-label">Monthly Volume</div>', unsafe_allow_html=True)
        monthly = db.get_monthly_velocity(months=12)
        if monthly:
            df_m = pd.DataFrame(monthly)
            df_m['month'] = pd.to_datetime(df_m['month'] + '-01')
            df_m['label'] = df_m['month'].dt.strftime('%b %Y')

            chart_bar = alt.Chart(df_m).mark_bar(color='#718096', cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                x=alt.X('label:N', axis=alt.Axis(title=None, grid=False), sort=df_m['label'].tolist()),
                y=alt.Y('count:Q', title=None, axis=alt.Axis(grid=True, tickMinStep=1)),
                tooltip=[alt.Tooltip('label:N', title='Month'), alt.Tooltip('count:Q', title='Count')]
            ).properties(height=220)
            st.altair_chart(chart_bar, width='stretch')
        else:
            st.caption("No monthly data available.")

    # --- Section 4: Breakdown & Recent ---
    c3, c4 = st.columns([1, 1])

    with c3:
        st.markdown('<div class="section-label">Library Status</div>', unsafe_allow_html=True)
        df_s = pd.DataFrame([
            {'status': 'Unwatched', 'count': stats.get('new', 0)},
            {'status': 'In Progress', 'count': stats.get('in_progress', 0)},
            {'status': 'Completed', 'count': stats.get('completed', 0)}
        ])
        
        # Horizontal bar chart (Reverted to Bar as requested)
        chart = alt.Chart(df_s).mark_bar().encode(
            y=alt.Y('status:N', title=None, sort=['Unwatched', 'In Progress', 'Completed']),
            x=alt.X('count:Q', title=None),
            color=alt.Color('status:N', scale=alt.Scale(domain=['Unwatched', 'In Progress', 'Completed'],
                                          range=['#A0AEC0', '#4299E1', '#48BB78']),
                          legend=None),
            tooltip=['status', 'count']
        ).properties(height=200)
        st.altair_chart(chart, width='stretch')

    with c4:
        st.markdown('<div class="section-label">Practicing Schedule</div>', unsafe_allow_html=True)
        # Day of week preference
        dow_stats = db.get_day_of_week_stats()
        if dow_stats:
            df_dow = pd.DataFrame(dow_stats)
            # Map index to name for sorting logic 0=Mon
            days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            df_dow['day_name'] = df_dow['day_index'].apply(lambda x: days[int(x)])
            
            chart_dow = alt.Chart(df_dow).mark_bar(color='#A0AEC0').encode(
                x=alt.X('day_name:N', sort=days, title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y('count:Q', title=None),
                tooltip=['day_name', 'count']
            ).properties(height=200)
            st.altair_chart(chart_dow, width='stretch')
        else:
            st.caption("Not enough data.")

    # --- Section 5: Personal Records ---
    st.markdown('<div class="section-label">Personal Records</div>', unsafe_allow_html=True)

    # Compute records (this also updates the database cache)
    records = db.compute_and_update_records()

    r1, r2, r3, r4, r5 = st.columns(5)

    with r1:
        render_personal_record_card(
            "Best Streak",
            f"{records.get('best_streak', {}).get('value', 0)} days",
            None
        )

    with r2:
        day_rec = records.get('most_day', {})
        render_personal_record_card(
            "Most in a Day",
            day_rec.get('value', 0),
            day_rec.get('date', '')
        )

    with r3:
        week_rec = records.get('most_week', {})
        render_personal_record_card(
            "Most in a Week",
            week_rec.get('value', 0),
            f"Week {week_rec.get('week', '')}" if week_rec.get('week') else None
        )

    with r4:
        month_rec = records.get('most_month', {})
        render_personal_record_card(
            "Most in a Month",
            month_rec.get('value', 0),
            month_rec.get('month', '')
        )

    with r5:
        consistent = records.get('most_consistent', {})
        avg_val = consistent.get('avg_per_day')
        render_personal_record_card(
            "Most Consistent",
            f"{avg_val}/day avg" if avg_val is not None else "N/A",
            f"Week {consistent.get('week', '')}" if consistent.get('week') else None
        )

    st.markdown("---")

    # --- Section 6: Browse by Date ---
    st.markdown('<div class="section-label">Browse by Date</div>', unsafe_allow_html=True)

    # Use session state value if set from heatmap click
    default_date = st.session_state.pop('browse_by_date', None)
    
    selected_date = st.date_input(
        "Select a date",
        value=default_date,
        max_value=datetime.now().date(),
        label_visibility="collapsed"
    )

    if selected_date:
        date_str = selected_date.strftime('%Y-%m-%d')
        lessons_on_date = db.get_lessons_completed_on_date(date_str)
        if lessons_on_date:
            st.caption(f"{len(lessons_on_date)} lesson(s) completed on {selected_date.strftime('%b %d, %Y')}")
            for lesson in lessons_on_date:
                st.button(
                    f"{lesson['title']}\n{lesson['author']}",
                    key=f"date_{lesson['id']}",
                    on_click=set_lesson,
                    args=(lesson['id'],),
                    width='stretch'
                )
        else:
            st.caption(f"No lessons completed on {selected_date.strftime('%b %d, %Y')}")
    else:
        st.caption("Select a date to view completed lessons")

    st.markdown("---")

    # --- Section 7: Recent History ---
    st.markdown('<div class="section-label">Recently Completed</div>', unsafe_allow_html=True)
    recent = db.get_recent_completions(limit=5)
    if recent:
        for r in recent:
            try:
                date_str = datetime.strptime(r['completed_at'], '%Y-%m-%d %H:%M:%S.%f').strftime('%b %d')
            except ValueError:
                date_str = datetime.strptime(r['completed_at'], '%Y-%m-%d %H:%M:%S').strftime('%b %d')
            st.button(
                f"{r['title']}\n{r['author']} • {date_str}",
                key=f"recent_{r['id']}",
                on_click=set_lesson,
                args=(r['id'],),
                width='stretch'
            )
    else:
        st.caption("No recently completed lessons.")

    st.markdown("---")

    # --- Section 8: Export Statistics ---
    st.markdown('<div class="section-label">Export</div>', unsafe_allow_html=True)

    col_exp1, col_exp2 = st.columns([1, 3])
    with col_exp1:
        json_data = db.export_statistics_json()
        st.download_button(
            label="Export Statistics (JSON)",
            data=json_data,
            file_name=f"video_shed_stats_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
            key="download_json",
            width='stretch'
        )
    with col_exp2:
        st.caption("Export your practice statistics for backup or analysis with LLMs.")