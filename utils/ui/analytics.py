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
    render_progress_ring_compact,
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
    daily_progress = db.get_daily_progress()
    weekly_progress = db.get_weekly_progress()

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

    w1, w2, w3 = st.columns(3)

    with w1:
        render_progress_ring_compact(
            current=daily_progress['completed'],
            goal=daily_progress['goal'],
            label="Daily Goal"
        )

    with w2:
        st.markdown("<div style='font-size: 0.85rem; color: #888; margin-bottom: 6px;'>This Week</div>", unsafe_allow_html=True)
        last_7_days = db.get_last_7_days_activity()
        render_mini_bar_chart(last_7_days, height=60)

    with w3:
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

            # Create a full date range for the year
            if selected_year == current_year:
                date_range = pd.date_range(end=datetime.now(), periods=365)
            else:
                date_range = pd.date_range(start=f'{selected_year}-01-01', end=f'{selected_year}-12-31')

            df_full = pd.DataFrame({'date': date_range})
            df_heat = pd.merge(df_full, df_heat, on='date', how='left').fillna({'count': 0})

            # Extract plotting helpers - use continuous week number from start of range
            start_date = df_heat['date'].min()
            df_heat['week_num'] = (df_heat['date'] - start_date).dt.days // 7
            df_heat['day_index'] = df_heat['date'].dt.weekday
            df_heat['date_str'] = df_heat['date'].dt.strftime('%Y-%m-%d')

            # 4-level color scale: 0 (gray), 2 (light green), 4 (medium green), 6+ (dark green)
            heatmap = alt.Chart(df_heat).mark_rect(stroke='#1a1a1a', strokeWidth=2).encode(
                x=alt.X('week_num:O', axis=None, title=None),
                y=alt.Y('day_index:O', axis=None, title=None, scale=alt.Scale(reverse=True)),
                color=alt.Color('count:Q',
                                scale=alt.Scale(
                                    domain=[0, 2, 4, 6],
                                    range=['#2D2D2D', '#9AE6B4', '#48BB78', '#276749']
                                ),
                                legend=None),
                tooltip=[
                    alt.Tooltip('date:T', title='Date', format='%b %d, %Y'),
                    alt.Tooltip('count:Q', title='Lessons')
                ]
            ).properties(
                height=120,
                title=""
            ).configure_view(strokeWidth=0)

            st.altair_chart(heatmap, width='stretch')

            # Color legend
            st.markdown("""
            <div style="display: flex; gap: 16px; justify-content: center; margin-top: 8px; font-size: 0.75rem; color: #888;">
                <span><span style="display: inline-block; width: 12px; height: 12px; background: #2D2D2D; margin-right: 4px; vertical-align: middle;"></span>0</span>
                <span><span style="display: inline-block; width: 12px; height: 12px; background: #9AE6B4; margin-right: 4px; vertical-align: middle;"></span>2</span>
                <span><span style="display: inline-block; width: 12px; height: 12px; background: #48BB78; margin-right: 4px; vertical-align: middle;"></span>4</span>
                <span><span style="display: inline-block; width: 12px; height: 12px; background: #276749; margin-right: 4px; vertical-align: middle;"></span>6+</span>
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
                x=alt.X('date:T', axis=alt.Axis(format='%b %Y', title=None, grid=False)),
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
            
            chart_bar = alt.Chart(df_m).mark_bar(color='#718096', cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                x=alt.X('month:T', axis=alt.Axis(format='%b', title=None, grid=False)),
                y=alt.Y('count:Q', title=None, axis=alt.Axis(grid=True, tickMinStep=1)),
                tooltip=['month:T', 'count:Q']
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

    selected_date = st.date_input(
        "Select a date",
        value=None,
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
                    use_container_width=True
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
            st.markdown(f"""
            <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #333; padding: 8px 0; font-size: 0.9rem;">
                <span style="color: #E0E0E0; font-weight: 500;">{r['title']}</span>
                <span style="color: #888;">{date_str}</span>
            </div>
            """, unsafe_allow_html=True)
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