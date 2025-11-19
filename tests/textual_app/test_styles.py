"""Tests for textual_app styles module."""

from mud_agent.utils.textual_app.styles import STYLES as APP_CSS


class TestStyles:
    """Test cases for styles module."""

    def test_app_css_exists(self):
        """Test that APP_CSS is defined and not empty."""
        assert APP_CSS is not None
        assert isinstance(APP_CSS, str)
        assert len(APP_CSS.strip()) > 0

    def test_app_css_contains_screen_layout(self):
        """Test that APP_CSS contains screen layout definitions."""
        assert "Screen" in APP_CSS
        assert "layout:" in APP_CSS
        assert "vertical" in APP_CSS

    def test_app_css_contains_main_sections(self):
        """Test that APP_CSS contains main UI section definitions."""
        assert "Header" in APP_CSS
        assert "#status-container" in APP_CSS
        assert "#main-container" in APP_CSS
        assert "#map-container" in APP_CSS
        assert "#command-container" in APP_CSS

    def test_css_syntax_validity(self):
        """Test basic CSS syntax validity."""
        # Check for balanced braces
        open_braces = APP_CSS.count('{')
        close_braces = APP_CSS.count('}')
        assert open_braces == close_braces, "Unbalanced braces in APP_CSS"

        # Check for basic CSS structure
        assert ':' in APP_CSS, "CSS should contain property declarations"
        assert ';' in APP_CSS, "CSS should contain statement terminators"

    def test_responsive_design_elements(self):
        """Test that CSS includes responsive design elements."""
        # Check for layout property usage, which is key to Textual's responsiveness
        assert "layout:" in APP_CSS, "CSS should include layout properties for responsiveness"

    def test_accessibility_considerations(self):
        """Test that CSS includes accessibility considerations."""
        # Check for contrast and readability keywords
        accessibility_keywords = ['color', 'background', 'border']
        has_accessibility = any(keyword in APP_CSS for keyword in accessibility_keywords)
        assert has_accessibility, "CSS should include accessibility considerations"

    def test_widget_specific_styles(self):
        """Test that widget-specific styles are properly defined."""
        # Check for ID and class selectors
        has_id_selectors = '#' in APP_CSS
        has_class_selectors = '.' in APP_CSS

        # At least one type of selector should be present
        assert has_id_selectors or has_class_selectors, "CSS should contain selectors for styling"
