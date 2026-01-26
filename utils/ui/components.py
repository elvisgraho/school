"""
Shared UI Components for Video School.
Reusable widgets for streak display, progress rings, and records.
"""

import streamlit as st
import altair as alt
import pandas as pd
from typing import Dict, List, Optional, Callable, Any


# Milestone thresholds for streak celebrations
MILESTONES = [7, 14, 30, 60, 90, 180, 365]


def render_progress_ring(current: int, goal: int, label: str = "Today", size: int = 100) -> None:
    """Render a circular progress indicator using Altair arc chart."""
    percentage = min((current / goal * 100) if goal > 0 else 0, 100)
    actual_pct = (current / goal * 100) if goal > 0 else 0

    # Determine color based on state
    if actual_pct >= 100:
        ring_color = '#48BB78'  # Green for complete
    elif current == 0:
        ring_color = '#4A4A4A'  # Dim gray for zero
    else:
        ring_color = '#4299E1'  # Blue for in progress

    # Create data for the arc
    data = pd.DataFrame({
        'category': ['completed', 'remaining'],
        'value': [percentage, 100 - percentage],
        'color': [ring_color, '#2D2D2D']
    })

    # Create the donut chart
    chart = alt.Chart(data).mark_arc(
        innerRadius=size // 3,
        outerRadius=size // 2.2,
        cornerRadius=4
    ).encode(
        theta=alt.Theta('value:Q', stack=True),
        color=alt.Color('color:N', scale=None),
        order=alt.Order('category:N', sort='ascending')
    ).properties(
        width=size,
        height=size
    ).configure_view(strokeWidth=0)

    # Display ring with text to the right
    text_color = '#888' if current == 0 else '#fff'
    over_text = f'<div style="font-size: 0.75rem; color: #48BB78; margin-top: 4px;">{int(actual_pct)}% - Overachiever!</div>' if actual_pct >= 200 else ''

    col1, col2 = st.columns([1, 2], gap="small")
    with col1:
        st.altair_chart(chart, width='content')
    with col2:
        st.markdown(f'<div><div style="font-size: 1.8rem; font-weight: 700; color: {text_color};">{current}/{goal}</div><div style="font-size: 0.85rem; color: #888; text-transform: uppercase; letter-spacing: 1px;">{label}</div>{over_text}</div>', unsafe_allow_html=True)


def render_progress_ring_compact(current: int, goal: int, label: str = "Today") -> None:
    """Render a compact progress ring for sidebar or small spaces."""
    percentage = min((current / goal * 100) if goal > 0 else 0, 100)
    actual_pct = (current / goal * 100) if goal > 0 else 0

    # Determine color based on state
    if actual_pct >= 100:
        color = '#48BB78'  # Green for complete
    elif current == 0:
        color = '#4A4A4A'  # Dim gray for zero
    else:
        color = '#4299E1'  # Blue for in progress

    text_color = '#888' if current == 0 else '#fff'

    html = f'''<div style="display: flex; align-items: center; gap: 10px; padding: 8px 0;">
<div style="position: relative; width: 45px; height: 45px;">
<svg viewBox="0 0 36 36" style="transform: rotate(-90deg);">
<path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#2D2D2D" stroke-width="3"/>
<path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="{color}" stroke-width="3" stroke-dasharray="{percentage}, 100"/>
</svg>
</div>
<div><div style="font-size: 1rem; font-weight: 600; color: {text_color};">{current}/{goal}</div><div style="font-size: 0.7rem; color: #888;">{label}</div></div>
</div>'''
    st.markdown(html, unsafe_allow_html=True)


def get_milestone_message(streak: int) -> str:
    """Return milestone message if streak hits a milestone."""
    if streak in MILESTONES:
        messages = {
            7: "One week strong!",
            14: "Two weeks of dedication!",
            30: "One month milestone!",
            60: "Two months of consistency!",
            90: "Quarter year achievement!",
            180: "Half year champion!",
            365: "One year legend!"
        }
        return messages.get(streak, "")
    return ""


def render_streak_display(current: int, best: int, recovery_info: Optional[Dict[str, Any]] = None) -> None:
    """Render the enhanced streak display with milestone checks."""
    milestone_msg = get_milestone_message(current)
    is_at_best = recovery_info.get('is_at_best', False) if recovery_info else (current >= best and current > 0)
    days_to_beat = recovery_info.get('days_to_beat', 0) if recovery_info else max(0, best - current + 1)

    # Handle zero-state display
    if current == 0:
        best_text = f' | Best: {best} days' if best > 0 else ''
        html = f'''<div style="background: #2D2D2D; border: 1px solid #3D3D3D; border-radius: 8px; padding: 20px; margin-bottom: 24px;">
<div style="display: flex; align-items: center; gap: 16px;">
<div style="font-size: 2.5rem; opacity: 0.4;">🔥</div>
<div>
<div style="font-size: 1.5rem; font-weight: 600; color: #888; line-height: 1;">Start your streak!</div>
<div style="font-size: 0.85rem; color: #666; margin-top: 4px;">Complete a lesson to begin{best_text}</div>
</div>
</div>
</div>'''
        st.markdown(html, unsafe_allow_html=True)
        return

    # Flame size based on streak (grows larger with longer streaks)
    flame_size = min(2.5 + (current / 30), 4.5)  # 2.5rem to 4.5rem
    day_label = "day" if current == 1 else "days"
    best_text = f' | Best: {best}' if best > 0 else ''

    # Build optional sections
    extras = ''
    if milestone_msg:
        extras += f'<div style="margin-top: 12px; padding: 8px 12px; background: #3D4A3D; border-radius: 4px; color: #48BB78; font-size: 0.85rem;">{milestone_msg}</div>'
    if days_to_beat > 0 and not is_at_best:
        extras += f'<div style="margin-top: 12px; padding: 8px 12px; background: #4A3D3D; border-radius: 4px; color: #F6AD55; font-size: 0.85rem;">{days_to_beat} more days to beat your record!</div>'
    if is_at_best:
        extras += '<div style="margin-top: 12px; padding: 8px 12px; background: #3D4A3D; border-radius: 4px; color: #48BB78; font-size: 0.85rem;">You are at your best streak!</div>'

    html = f'''<div style="background: #2D2D2D; border: 1px solid #3D3D3D; border-radius: 8px; padding: 20px; margin-bottom: 24px;">
<div style="display: flex; align-items: center; gap: 16px;">
<div style="font-size: {flame_size}rem;"><span style="filter: drop-shadow(0 0 8px rgba(246, 173, 85, 0.5));">🔥</span></div>
<div>
<div style="font-size: 2.5rem; font-weight: 700; color: #fff; line-height: 1;">{current} <span style="font-size: 1rem; color: #888; font-weight: 400;">{day_label}</span></div>
<div style="font-size: 0.85rem; color: #888; margin-top: 4px;">Current Streak{best_text}</div>
</div>
</div>
{extras}
</div>'''
    st.markdown(html, unsafe_allow_html=True)


def render_streak_compact(current: int, best: int) -> None:
    """Render a compact streak display for sidebar."""
    if current == 0:
        best_text = f'Best: {best} days' if best > 0 else 'Start today!'
        html = f'<div style="display: flex; align-items: center; gap: 8px; padding: 8px 0;"><span style="font-size: 1.2rem; opacity: 0.4;">🔥</span><div><div style="font-size: 1rem; font-weight: 600; color: #888;">No streak</div><div style="font-size: 0.7rem; color: #666;">{best_text}</div></div></div>'
        st.markdown(html, unsafe_allow_html=True)
        return

    day_label = "day" if current == 1 else "days"
    html = f'<div style="display: flex; align-items: center; gap: 8px; padding: 8px 0;"><span style="font-size: 1.2rem;">🔥</span><div><div style="font-size: 1rem; font-weight: 600; color: #fff;">{current} {day_label}</div><div style="font-size: 0.7rem; color: #888;">Streak (Best: {best})</div></div></div>'
    st.markdown(html, unsafe_allow_html=True)


def render_weekly_progress_bar(current: int, goal: int) -> None:
    """Render a horizontal progress bar for weekly goal."""
    percentage = min((current / goal * 100) if goal > 0 else 0, 100)
    actual_pct = (current / goal * 100) if goal > 0 else 0
    color = '#48BB78' if actual_pct >= 100 else '#4299E1'
    over_text = f'<div style="font-size: 0.75rem; color: #48BB78; margin-top: 4px; text-align: right;">{int(actual_pct)}% complete</div>' if actual_pct > 100 else ''

    html = f'''<div style="margin-bottom: 16px;">
<div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
<span style="font-size: 0.85rem; color: #888;">Weekly Goal</span>
<span style="font-size: 0.85rem; color: #fff; font-weight: 500;">{current}/{goal}</span>
</div>
<div style="background: #2D2D2D; border-radius: 4px; height: 8px; overflow: hidden;">
<div style="background: {color}; width: {percentage}%; height: 100%; border-radius: 4px; transition: width 0.3s;"></div>
</div>
{over_text}
</div>'''
    st.markdown(html, unsafe_allow_html=True)


def render_personal_record_card(title: str, value: Any, subtitle: Optional[str] = None) -> None:
    """Render a personal record card."""
    sub_html = f'<div style="font-size: 0.7rem; color: #666; margin-top: 4px;">{subtitle}</div>' if subtitle else ''
    html = f'<div style="background: #2D2D2D; border: 1px solid #3D3D3D; border-radius: 6px; padding: 16px; text-align: center;"><div style="font-size: 1.5rem; font-weight: 700; color: #fff;">{value}</div><div style="font-size: 0.8rem; color: #888; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px;">{title}</div>{sub_html}</div>'
    st.markdown(html, unsafe_allow_html=True)


def render_mini_bar_chart(data: List[Dict[str, Any]], height: int = 80) -> None:
    """Render a mini bar chart for last 7 days."""
    if not data:
        st.caption("No data available")
        return

    df = pd.DataFrame(data)

    chart = alt.Chart(df).mark_bar(
        color='#4299E1',
        cornerRadiusTopLeft=2,
        cornerRadiusTopRight=2
    ).encode(
        x=alt.X('day:N', axis=alt.Axis(labelAngle=0, title=None), sort=None),
        y=alt.Y('count:Q', axis=alt.Axis(title=None, tickMinStep=1)),
        tooltip=['date:N', 'count:Q']
    ).properties(
        height=height
    ).configure_view(strokeWidth=0)

    st.altair_chart(chart, width='stretch')


def render_trend_indicator(current: int, previous: int, label: str = "vs Last Month") -> None:
    """Render monthly comparison with up/down arrow."""
    if previous > 0:
        change_pct = ((current - previous) / previous) * 100
    else:
        change_pct = 100 if current > 0 else 0

    is_up = current >= previous
    arrow = "↑" if is_up else "↓"
    color = "#48BB78" if is_up else "#F56565"

    html = f'''<div style="background: #2D2D2D; border: 1px solid #3D3D3D; border-radius: 6px; padding: 12px;">
<div style="display: flex; align-items: center; justify-content: space-between;">
<div><div style="font-size: 1.25rem; font-weight: 600; color: #fff;">{current}</div><div style="font-size: 0.75rem; color: #888;">{label}</div></div>
<div style="text-align: right;"><span style="color: {color}; font-size: 1rem; font-weight: 600;">{arrow} {abs(change_pct):.0f}%</span><div style="font-size: 0.7rem; color: #666;">was {previous}</div></div>
</div>
</div>'''
    st.markdown(html, unsafe_allow_html=True)


def render_lesson_button(lesson: Dict[str, Any], key_prefix: str, on_click: Callable, show_time_ago: Optional[str] = None) -> None:
    """Render a styled lesson button."""
    lesson_id = lesson['id']
    label = f"{lesson['title']}\n{lesson['author']}"
    if show_time_ago:
        label += f"\n{show_time_ago}"

    st.button(label, key=f"{key_prefix}_{lesson_id}", width='stretch',
              on_click=on_click, args=(lesson_id,))
