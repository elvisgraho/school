"""
UI rendering modules for Guitar Shed.
Redesigned for a conservative, precise, text-first aesthetic.

Submodules:
- styles: CSS styling
- callbacks: Helper callbacks
- practice: Practice room (video player)
- discovery: Discovery tab
- library: Library tab
- analytics: Analytics tab
- components: Shared UI components
- sidebar: Sidebar with stats and settings
- metronome: Metronome component
"""

from .styles import apply_conservative_style, apply_global_styles
from .callbacks import set_lesson, clear_lesson, update_status_callback
from .practice import render_practice_room
from .discovery import render_discovery
from .library import render_library
from .analytics import render_analytics
from .sidebar import render_sidebar
from .metronome import render_metronome
from .components import (
    render_progress_ring,
    render_progress_ring_compact,
    render_streak_display,
    render_streak_compact,
    render_weekly_progress_bar,
    render_personal_record_card,
    render_mini_bar_chart,
    render_trend_indicator,
    get_milestone_message,
)

__all__ = [
    'apply_conservative_style',
    'apply_global_styles',
    'set_lesson',
    'clear_lesson',
    'update_status_callback',
    'render_practice_room',
    'render_discovery',
    'render_library',
    'render_analytics',
    'render_sidebar',
    'render_metronome',
    'render_progress_ring',
    'render_progress_ring_compact',
    'render_streak_display',
    'render_streak_compact',
    'render_weekly_progress_bar',
    'render_personal_record_card',
    'render_mini_bar_chart',
    'render_trend_indicator',
    'get_milestone_message',
]
