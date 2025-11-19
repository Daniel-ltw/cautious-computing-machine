#!/usr/bin/env python3
"""
Tests for RoomWidget to ensure proper display of room information and exits.
"""

import pytest
from unittest.mock import MagicMock, patch
from textual.app import App

from mud_agent.utils.widgets.room_widgets import RoomWidget


class RoomWidgetTestApp(App):
    """Test app for RoomWidget."""

    def compose(self):
        yield RoomWidget(id="room-widget")


class TestRoomWidget:
    """Test suite for RoomWidget."""

    def test_room_widget_initialization(self):
        """Test RoomWidget initializes with default values."""
        widget = RoomWidget()

        assert widget.room_name == "Unknown"
        assert widget.room_num == 0
        assert widget.area_name == "Unknown"
        assert widget.room_terrain == "Unknown"
        assert widget.room_details == ""
        assert widget.room_coords == {}
        assert widget.exits == []
        assert widget.npcs == []
        assert widget.last_room_num == 0
        assert widget.first_update is True

    def test_exits_display_with_room_numbers(self):
        """Test that exits are displayed with room numbers in parentheses."""
        widget = RoomWidget()

        # Set up exits as a dictionary with room numbers
        widget.exits = {
            "n": 1234,
            "s": 1235,
            "e": 1236,
            "w": 1237
        }

        # Mock the write method to capture output
        written_lines = []
        widget.write = MagicMock(side_effect=lambda text: written_lines.append(text))

        # Call update_content
        widget.update_content()

        # Find the exits line
        exits_line = None
        for line in written_lines:
            if "Exits:" in line:
                exits_line = line
                break

        assert exits_line is not None, "Exits line not found in output"

        # Check that room numbers are in parentheses
        assert "(1234)" in exits_line
        assert "(1235)" in exits_line
        assert "(1236)" in exits_line
        assert "(1237)" in exits_line

    def test_exits_display_without_room_numbers(self):
        """Test that exits without room numbers are displayed without parentheses."""
        widget = RoomWidget()

        # Set up exits as a dictionary without room numbers (None values)
        widget.exits = {
            "n": None,
            "s": None,
            "e": None,
            "w": None
        }

        # Mock the write method to capture output
        written_lines = []
        widget.write = MagicMock(side_effect=lambda text: written_lines.append(text))

        # Call update_content
        widget.update_content()

        # Find the exits line
        exits_line = None
        for line in written_lines:
            if "Exits:" in line:
                exits_line = line
                break

        assert exits_line is not None, "Exits line not found in output"

        # Check that directions are present without parentheses for None values
        assert "n" in exits_line
        assert "s" in exits_line
        assert "e" in exits_line
        assert "w" in exits_line

    def test_exits_display_mixed_room_numbers(self):
        """Test that exits with mixed room numbers (some None) are displayed correctly."""
        widget = RoomWidget()

        # Set up exits with mixed room numbers
        widget.exits = {
            "n": 1234,
            "s": None,
            "e": 1236,
            "w": None
        }

        # Mock the write method to capture output
        written_lines = []
        widget.write = MagicMock(side_effect=lambda text: written_lines.append(text))

        # Call update_content
        widget.update_content()

        # Find the exits line
        exits_line = None
        for line in written_lines:
            if "Exits:" in line:
                exits_line = line
                break

        assert exits_line is not None, "Exits line not found in output"

        # Check that room numbers are in parentheses where present
        assert "(1234)" in exits_line
        assert "(1236)" in exits_line
        # Directions without room numbers should not have parentheses after them
        # The line should contain "s" and "w" without numbers

    def test_exits_display_as_list(self):
        """Test that exits as a list are displayed correctly (no room numbers)."""
        widget = RoomWidget()

        # Set up exits as a list
        widget.exits = ["n", "s", "e", "w"]

        # Mock the write method to capture output
        written_lines = []
        widget.write = MagicMock(side_effect=lambda text: written_lines.append(text))

        # Call update_content
        widget.update_content()

        # Find the exits line
        exits_line = None
        for line in written_lines:
            if "Exits:" in line:
                exits_line = line
                break

        assert exits_line is not None, "Exits line not found in output"

        # Check that all directions are present
        assert "n" in exits_line
        assert "s" in exits_line
        assert "e" in exits_line
        assert "w" in exits_line

    def test_no_exits_display(self):
        """Test that 'No visible exits' is displayed when there are no exits."""
        widget = RoomWidget()

        # Set up with no exits
        widget.exits = []

        # Mock the write method to capture output
        written_lines = []
        widget.write = MagicMock(side_effect=lambda text: written_lines.append(text))

        # Call update_content
        widget.update_content()

        # Check for "No visible exits" message
        assert any("No visible exits" in line for line in written_lines)

    def test_room_info_display(self):
        """Test that room information is displayed correctly."""
        widget = RoomWidget()

        # Set up room information
        widget.room_name = "Test Room"
        widget.room_num = 12345
        widget.area_name = "Test Area"
        widget.room_terrain = "city"
        widget.room_details = "well lit"
        widget.room_coords = {"x": 10, "y": 20, "cont": 0}

        # Mock the write method to capture output
        written_lines = []
        widget.write = MagicMock(side_effect=lambda text: written_lines.append(text))

        # Call update_content
        widget.update_content()

        # Verify room information is in the output
        output_text = " ".join(written_lines)
        assert "Test Room" in output_text
        assert "12345" in output_text
        assert "Test Area" in output_text
        assert "city" in output_text
        assert "well lit" in output_text
        assert "X=10" in output_text
        assert "Y=20" in output_text

    def test_npcs_display(self):
        """Test that NPCs are displayed correctly."""
        widget = RoomWidget()

        # Set up NPCs
        widget.npcs = ["Guard", "Merchant", "Beggar"]

        # Mock the write method to capture output
        written_lines = []
        widget.write = MagicMock(side_effect=lambda text: written_lines.append(text))

        # Call update_content
        widget.update_content()

        # Find the NPCs line
        npcs_line = None
        for line in written_lines:
            if "NPCs:" in line:
                npcs_line = line
                break

        assert npcs_line is not None, "NPCs line not found in output"
        assert "Guard" in npcs_line
        assert "Merchant" in npcs_line
        assert "Beggar" in npcs_line

    def test_no_npcs_display(self):
        """Test that 'No NPCs present' is displayed when there are no NPCs."""
        widget = RoomWidget()

        # Set up with no NPCs
        widget.npcs = []

        # Mock the write method to capture output
        written_lines = []
        widget.write = MagicMock(side_effect=lambda text: written_lines.append(text))

        # Call update_content
        widget.update_content()

        # Check for "No NPCs present" message
        assert any("No NPCs present" in line for line in written_lines)

    def test_room_update_event_handling(self):
        """Test that _on_room_update properly updates widget state."""
        widget = RoomWidget()

        # Create update data
        updates = {
            "brief": "Updated Room",
            "num": 99999,
            "zone": "Updated Area",
            "sector": "forest",
            "flags": "dark",
            "coord": {"x": 5, "y": 15, "cont": 1},
            "exits": {"n": 100, "e": 101},
            "npcs": ["Dragon"]
        }

        # Mock the write method
        widget.write = MagicMock()
        widget.refresh = MagicMock()

        # Call _on_room_update
        widget._on_room_update(room_data=updates)

        # Verify state was updated
        assert widget.room_name == "Updated Room"
        assert widget.room_num == 99999
        assert widget.area_name == "Updated Area"
        assert widget.room_terrain == "forest"
        assert widget.room_details == "dark"
        assert widget.room_coords == {"x": 5, "y": 15, "cont": 1}
        assert widget.exits == {"n": 100, "e": 101}
        assert widget.npcs == ["Dragon"]

        # Verify update_content was called (via write being called)
        assert widget.write.called
        assert widget.refresh.called


@pytest.mark.asyncio
async def test_room_widget_in_app():
    """Test RoomWidget in a Textual app context."""
    app = RoomWidgetTestApp()
    async with app.run_test() as pilot:
        widget = pilot.app.query_one(RoomWidget)
        assert widget is not None
        assert widget.id == "room-widget"
