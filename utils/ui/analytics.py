"""
Analytics Tab for Guitar Shed.
"""

import streamlit as st
import pandas as pd
import altair as alt
from .styles import apply_conservative_style


def render_analytics(db) -> None:
    """Render Analytics."""
    apply_conservative_style()
    
    st.markdown('<div class="section-label">Performance Overview</div>', unsafe_allow_html=True)
    
    stats = db.get_stats()
    streak = db.get_current_streak()
    
    # Simple metric row
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Library", stats['total'])
    c2.metric("Completed", stats['completed'])
    c3.metric("Completion Rate", f"{stats['completion_rate']:.0f}%")
    c4.metric("Current Streak", f"{streak} Days")
    
    st.markdown("---")
    
    # Charts
    c_left, c_right = st.columns(2)
    
    with c_left:
        st.markdown('<div class="section-label">Monthly Volume</div>', unsafe_allow_html=True)
        monthly = db.get_monthly_velocity(months=12)
        if monthly:
            df_m = pd.DataFrame(monthly)
            df_m['month'] = pd.to_datetime(df_m['month'] + '-01')
            
            # Conservative color scheme (Grey/Blue)
            chart = alt.Chart(df_m).mark_bar(color='#4A5568').encode(
                x=alt.X('month:T', axis=alt.Axis(format='%b %Y', title=None)),
                y=alt.Y('count:Q', title=None),
                tooltip=['month:T', 'count:Q']
            ).properties(height=250)
            st.altair_chart(chart, width='stretch')
        else:
            st.caption("No data available.")

    with c_right:
        st.markdown('<div class="section-label">Library Status</div>', unsafe_allow_html=True)
        df_s = pd.DataFrame([
            {'status': 'Unwatched', 'count': stats.get('new', 0)},
            {'status': 'In Progress', 'count': stats.get('in_progress', 0)},
            {'status': 'Completed', 'count': stats['completed']}
        ])
        
        # Horizontal bar chart for better readability
        chart = alt.Chart(df_s).mark_bar().encode(
            y=alt.Y('status:N', title=None, sort=['Unwatched', 'In Progress', 'Completed']),
            x=alt.X('count:Q', title=None),
            color=alt.Color('status:N', scale=alt.Scale(domain=['Unwatched', 'In Progress', 'Completed'],
                                          range=['#A0AEC0', '#4299E1', '#48BB78']),
                          legend=None),
            tooltip=['status', 'count']
        ).properties(height=180)
        st.altair_chart(chart, width='stretch')
