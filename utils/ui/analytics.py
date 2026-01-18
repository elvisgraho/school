"""
Analytics Tab for Guitar Shed.
Provides insights into practice consistency, volume, and library progress.
"""

import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
from .styles import apply_conservative_style

def render_analytics(db) -> None:
    """Render Analytics with a focus on consistency and progress trends."""
    apply_conservative_style()
    
    # --- Data Fetching ---
    stats = db.get_stats()
    streak = db.get_current_streak()
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
    c3.metric("Current Streak", f"{streak} Days")
    c4.metric("Active Days (30d)", f"{active_days_count}")
    
    st.markdown("---")

    # --- Section 2: Consistency Heatmap (GitHub Style) ---
    st.markdown('<div class="section-label">Consistency Map (Last 12 Months)</div>', unsafe_allow_html=True)
    
    if activity_365:
        df_heat = pd.DataFrame(activity_365)
        df_heat['date'] = pd.to_datetime(df_heat['date'])
        
        # Create a full date range to fill gaps
        date_range = pd.date_range(end=datetime.now(), periods=365)
        df_full = pd.DataFrame({'date': date_range})
        df_heat = pd.merge(df_full, df_heat, on='date', how='left').fillna({'count': 0})
        
        # Extract plotting helpers
        df_heat['week'] = df_heat['date'].dt.isocalendar().week
        df_heat['year'] = df_heat['date'].dt.year
        # Adjust week to be continuous for plotting across year boundary
        df_heat['week_cont'] = df_heat.apply(lambda x: x['week'] if x['year'] == date_range[-1].year else x['week'] - 52, axis=1)
        df_heat['day_of_week'] = df_heat['date'].dt.day_name()
        df_heat['day_index'] = df_heat['date'].dt.weekday  # 0=Mon, 6=Sun

        heatmap = alt.Chart(df_heat).mark_rect(stroke='#1a1a1a', strokeWidth=2).encode(
            x=alt.X('week_cont:O', axis=None, title=None),
            y=alt.Y('day_index:O', axis=None, title=None, scale=alt.Scale(reverse=True)),
            color=alt.Color('count:Q',
                            scale=alt.Scale(range=['#2D2D2D', '#48BB78', '#2F855A']),
                            legend=None),
            tooltip=[alt.Tooltip('date', title='Date', format='%b %d, %Y'), 'count']
        ).properties(
            height=120,
            title=""
        ).configure_view(strokeWidth=0)
        
        st.altair_chart(heatmap, width='stretch')
        st.caption("Darker squares indicate higher volume of completions.")
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
            {'status': 'Completed', 'count': stats['completed']}
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

    # --- Section 5: Recent History ---
    st.markdown('<div class="section-label">Recently Completed</div>', unsafe_allow_html=True)
    recent = db.get_recent_completions(limit=5)
    if recent:
        for r in recent:
            # Minimalistic row
            date_str = datetime.strptime(r['completed_at'], '%Y-%m-%d %H:%M:%S').strftime('%b %d')
            st.markdown(f"""
            <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #333; padding: 8px 0; font-size: 0.9rem;">
                <span style="color: #E0E0E0; font-weight: 500;">{r['title']}</span>
                <span style="color: #888;">{date_str}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.caption("No recently completed lessons.")