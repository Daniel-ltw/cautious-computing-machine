"""Styling and CSS definitions for the MUD Textual App.

This module contains all CSS styling definitions, layout constants,
and visual appearance configurations for the textual interface.
"""

from textual.app import App


# Main CSS for the application
STYLES = """
/* Main Layout - Restored to Original Structure */
Screen {
    layout: vertical;
    background: #0f172a;
    color: #f1f5f9;
}

Header {
    dock: top;
    height: 1;
}

/* Status container styling - matches original */
#status-container {
    height: 10;
    min-height: 10;
    width: 100%;
    border-bottom: solid #3b82f6;
    overflow-y: auto;
    padding: 0 1;
}

#status-widget {
    width: 100%;
    height: 100%;
}

/* Main container - horizontal layout like original */
#main-container {
    layout: horizontal;
    height: 20fr;
}

/* Map container - 40% width like original */
#map-container {
    width: 40%;
    height: 100%;
    border-right: solid #3b82f6;
    overflow-y: auto;
    background: #1e293b;
}

/* Command container - 60% width like original */
#command-container {
    width: 60%;
    height: 100%;
    margin-left: 1;
}

#command-log {
    height: 10fr;
    overflow-y: auto;
    padding: 1;
}

#command-input {
    dock: bottom;
    height: 3;
    border-top: solid #3b82f6;
}

    /* Container styling with explicit heights - from original */
    #vitals-container {
        height: 1;
        min-height: 1;
        margin-bottom: 0;
    }

    #needs-container {
        height: 1;
        min-height: 1;
        margin-bottom: 0;
    }

    #worth-container {
        height: 1;
        min-height: 1;
        margin-bottom: 1;
    }

    #stats-container {
        height: 3;
        min-height: 3;
        margin-bottom: 0;
    }

    #status-effects-widget {
        height: 1;
        min-height: 1;
    }

    /* Critical display properties for all widgets - from original */
    #status-widget, #vitals-container, #needs-container, #worth-container, #stats-container, #status-effects-widget,
    #hp-widget, #mp-widget, #mv-widget, #hunger-widget, #thirst-widget,
    #gold-widget, #bank-widget, #qp-widget, #tp-widget, #xp-widget,
    #str-widget, #int-widget, #wis-widget, #dex-widget, #con-widget, #luck-widget, #hr-widget, #dr-widget,
    #hp-static, #mp-static, #mv-static, #str-static, #int-static, #wis-static, #dex-static, #con-static, #luck-static, #hr-static, #dr-static,
    #character-header {
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
    }

    /* Character header styling */
    #character-header {
        height: 1;
        min-height: 1;
        margin-bottom: 1;
    }

    /* Individual widget styling - from original */
    #hp-widget, #mp-widget, #mv-widget,
    #hunger-widget, #thirst-widget,
    #gold-widget, #bank-widget, #qp-widget, #tp-widget, #xp-widget,
    #str-widget, #int-widget, #wis-widget, #dex-widget, #con-widget, #luck-widget, #hr-widget, #dr-widget {
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
    }

    /* Hide the StateManager widget */
    StateManager {
        display: none;
    }

    /* Style for pre-formatted text in the map widget */
    .map-pre {
        background: #1e293b;
        color: #f1f5f9;
        padding: 0;
        margin: 0;
    }

    /* Status Widget Styles */
    .status-widget {
        background: #1e293b;
        border: solid #3b82f6;
        padding: 1;
    }

    .vitals-container {
        layout: vertical;
        height: auto;
        background: #1e293b;
    }

    .vitals-widget {
        height: 3;
        margin: 1 0;
        background: #0f172a;
        border: solid #10b981;
    }

    .stats-container {
        layout: vertical;
        height: auto;
        background: #1e293b;
        margin-top: 1;
    }

    .stats-widget {
        height: 3;
        margin: 1 0;
        background: #0f172a;
        border: solid #10b981;
    }

    /* Map Widget Styles */
    .map-widget {
        background: #1e293b;
        border: solid #3b82f6;
        padding: 1;
    }

    .room-info {
        height: auto;
        background: #0f172a;
        border: solid #10b981;
        margin: 1 0;
        padding: 1;
    }

    .map-display {
        height: 1fr;
        background: #0f172a;
        border: solid #10b981;
        margin: 1 0;
    }

    /* Command Input Styles */
    .command-input {
        background: #1e293b;
        border: solid #10b981;
    }

    .command-input:focus {
        border: solid #f59e0b;
    }

    /* Command Log Styles */
    .command-log {
        background: #0f172a;
        color: #f1f5f9;
        scrollbar-gutter: stable;
    }

    /* Loading Screen Styles */
    .loading-screen {
        align: center middle;
        background: #0f172a;
        color: #f1f5f9;
    }

    .loading-spinner {
        color: #10b981;
        text-style: bold;
    }

    /* Progress Bar Styles */
    .progress-bar {
        background: #1e293b;
        color: #10b981;
    }

    .progress-bar > .bar {
        color: #22c55e;
    }

    /* Health/Mana/Movement Bar Colors */
    .health-bar > .bar {
        color: #ef4444;
    }

    .mana-bar > .bar {
        color: #06b6d4;
    }

    .movement-bar > .bar {
        color: #f59e0b;
    }

    /* Text Styling */
    .bold {
        text-style: bold;
    }

    .italic {
        text-style: italic;
    }

    .underline {
        text-style: underline;
    }

    /* Color Classes */
    .text-primary {
        color: #3b82f6;
    }

    .text-secondary {
        color: #64748b;
    }

    .text-accent {
        color: #10b981;
    }

    .text-success {
        color: #22c55e;
    }

    .text-warning {
        color: #f59e0b;
    }

    .text-error {
        color: #ef4444;
    }

    .text-info {
        color: #06b6d4;
    }

    /* Background Classes */
    .bg-primary {
        background: #3b82f6;
    }

    .bg-secondary {
        background: #64748b;
    }

    .bg-accent {
        background: #10b981;
    }

    .bg-success {
        background: #22c55e;
    }

    .bg-warning {
        background: #f59e0b;
    }

    .bg-error {
        background: #ef4444;
    }

    .bg-info {
        background: #06b6d4;
    }

    /* Layout Utilities */
    .center {
        align: center middle;
    }

    .left {
        align: left middle;
    }

    .right {
        align: right middle;
    }

    .top {
        align: center top;
    }

    .bottom {
        align: center bottom;
    }

    /* Spacing Utilities */
    .margin-1 {
        margin: 1;
    }

    .margin-2 {
        margin: 2;
    }

    .padding-1 {
        padding: 1;
    }

    .padding-2 {
        padding: 2;
    }

    /* Border Utilities */
    .border-solid {
        border: solid;
    }

    .border-dashed {
        border: dashed;
    }

    .border-double {
        border: double;
    }

    /* Responsive Design - Note: Textual CSS doesn't support @media queries */
    /* Media queries removed for Textual compatibility */
    """


class LayoutConstants:
    """Constants for layout dimensions and spacing."""
    
    # Grid dimensions
    GRID_ROWS = 3
    GRID_COLUMNS = 3
    GRID_GUTTER = 1
    
    # Component heights
    HEADER_HEIGHT = 3
    FOOTER_HEIGHT = 3
    COMMAND_INPUT_HEIGHT = 3
    VITALS_WIDGET_HEIGHT = 3
    STATS_WIDGET_HEIGHT = 3
    
    # Spacing
    DEFAULT_MARGIN = 1
    DEFAULT_PADDING = 1
    WIDGET_SPACING = 1
    
    # Responsive breakpoints
    MOBILE_BREAKPOINT = 80


# Layout configuration constants
LAYOUT_CONFIG = {
    "grid_size": (3, 3),
    "grid_gutter": 1,
    "grid_rows": "1fr 8fr 1fr",
    "grid_columns": "1fr 2fr 1fr",
    "header_height": 3,
    "footer_height": 1,
    "sidebar_width": 1,
    "main_content_width": 2,
    "mobile_breakpoint": 80,
}


class ColorScheme:
    """Color scheme definitions for the application."""
    
    # Primary colors
    PRIMARY = "#3b82f6"
    SECONDARY = "#64748b"
    ACCENT = "#10b981"
    
    # Status colors
    SUCCESS = "#22c55e"
    WARNING = "#f59e0b"
    ERROR = "#ef4444"
    INFO = "#06b6d4"
    
    # Background colors
    BACKGROUND = "#0f172a"
    SURFACE = "#1e293b"
    TEXT = "#f1f5f9"
    
    # Vitals colors
    HEALTH_COLOR = ERROR
    MANA_COLOR = INFO
    MOVEMENT_COLOR = WARNING
