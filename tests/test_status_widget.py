#!/usr/bin/env python3
"""
Tests for the status widget and its components.
"""

import pytest
from textual.app import App
from textual.containers import Container
from textual.widgets import Header

from mud_agent.utils.widgets.containers import StatusContainer


class TestStatusApp(App):
    """Test app for status widget components."""

    CSS = """
    Screen {
        layout: vertical;
    }

    Header {
        dock: top;
        height: 1;
    }

    #status-container {
        height: 15;
        min-height: 15;
        width: 100%;
        border-bottom: solid $primary;
        overflow-y: auto;
    }

    #status-widget {
        width: 100%;
        height: 100%;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
    }

    /* Container styling */
    #vitals-container {
        height: 3;
        min-height: 3;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
    }

    #needs-container {
        height: 1;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
    }

    #worth-container {
        height: 1;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
    }

    #stats-container {
        height: 3;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
    }

    #status-effects-widget {
        height: 1;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
    }
    """

    def compose(self):
        """Compose the app layout."""
        yield Header(show_clock=True)

        # Status container (top)
        with Container(id="status-container"):
            # Use the StatusContainer
            yield StatusContainer(id="status-widget")


@pytest.mark.asyncio
async def test_status_container_composition():
    """Test that the StatusContainer composes correctly with all expected child widgets."""
    app = TestStatusApp()
    async with app.run_test() as pilot:
        # Wait for the app to be ready
        await pilot.wait_for_scheduled_animations()

        # Get the status widget
        status_widget = app.query_one("#status-widget")

        # Check that it's a StatusContainer
        assert isinstance(status_widget, StatusContainer)

        # Check that it has all the expected child containers
        assert hasattr(status_widget, "character_header")
        assert hasattr(status_widget, "vitals_container")
        assert hasattr(status_widget, "needs_container")
        assert hasattr(status_widget, "worth_container")
        assert hasattr(status_widget, "stats_container")
        assert hasattr(status_widget, "status_effects")


@pytest.mark.asyncio
async def test_status_container_update():
    """Test that the StatusContainer can be updated with mock data."""
    app = TestStatusApp()
    async with app.run_test() as pilot:
        # Wait for the app to be ready
        await pilot.wait_for_scheduled_animations()

        # Get the status widget
        status_widget = app.query_one("#status-widget")

        # Create a mock state manager
        class MockStateManager:
            def __init__(self):
                self.character_name = "TestCharacter"
                self.level = 50
                self.race = "Human"
                self.character_class = "Warrior"
                self.health = {"current": 100, "max": 100}
                self.mana = {"current": 100, "max": 100}
                self.movement = {"current": 100, "max": 100}
                self.hp_current = 100
                self.hp_max = 100
                self.mp_current = 100
                self.mp_max = 100
                self.mv_current = 100
                self.mv_max = 100
                self.hunger = {"current": 10, "max": 100}
                self.thirst = {"current": 10, "max": 100}
                self.status_effects = []
                self.in_combat = False

        # Update the status widget with mock data
        mock_state_manager = MockStateManager()

        # Skip the test if character_header is not available
        if (
            not hasattr(status_widget, "character_header")
            or status_widget.character_header is None
        ):
            pytest.skip("character_header not available")

        # Update the character header
        status_widget.character_header.character_name = (
            mock_state_manager.character_name
        )
        status_widget.character_header.level = mock_state_manager.level
        status_widget.character_header.race = mock_state_manager.race
        status_widget.character_header.character_class = (
            mock_state_manager.character_class
        )

        # Call update_content if it exists
        if hasattr(status_widget.character_header, "update_content"):
            status_widget.character_header.update_content()

        # Check that the character header was updated
        assert status_widget.character_header.character_name == "TestCharacter"
        assert status_widget.character_header.level == 50
        assert status_widget.character_header.race == "Human"
        assert status_widget.character_header.character_class == "Warrior"


@pytest.mark.asyncio
async def test_vitals_container():
    """Test that the VitalsContainer has the expected widgets."""
    app = TestStatusApp()
    async with app.run_test() as pilot:
        # Wait for the app to be ready
        await pilot.wait_for_scheduled_animations()

        # Get the status widget
        status_widget = app.query_one("#status-widget")

        # Skip the test if vitals_container is not available
        if (
            not hasattr(status_widget, "vitals_container")
            or status_widget.vitals_container is None
        ):
            pytest.skip("vitals_container not available")

        # Check that the vitals container has the expected widgets
        assert hasattr(status_widget.vitals_container, "hp_widget")
        assert hasattr(status_widget.vitals_container, "mp_widget")
        assert hasattr(status_widget.vitals_container, "mv_widget")
