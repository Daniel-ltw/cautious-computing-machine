import pytest
from textual.app import App
from mud_agent.utils.widgets.room_widgets import RoomWidget

class RoomWidgetTestApp(App):
    """Test app for RoomWidget."""
    def compose(self):
        yield RoomWidget(id="room-widget")

@pytest.mark.asyncio
async def test_room_widget_interaction():
    """Test interacting with RoomWidget via Pilot."""
    app = RoomWidgetTestApp()
    async with app.run_test() as pilot:
        # Get the widget
        widget = pilot.app.query_one(RoomWidget)
        assert widget.room_name == "Unknown"

        # Simulate a room update
        update_data = {
            "brief": "The Grand Hall",
            "num": 1001,
            "exits": {"n": 1002, "e": 1003},
            "npcs": ["King's Guard"]
        }

        # Trigger the update directly (simulating an event)
        widget._on_room_update(room_data=update_data)

        # Allow any pending events to process
        await pilot.pause()

        # Verify reactive attributes updated
        assert widget.room_name == "The Grand Hall"
        assert widget.room_num == 1001
        assert widget.exits == {"n": 1002, "e": 1003}
        assert widget.npcs == ["King's Guard"]

        # Verify content was written (RichLog stores lines)
        # Note: RichLog lines are complex objects, so we just check count > 0
        # or check if we can convert them to string.
        # For now, just checking reactive state is a strong enough test
        # that the widget processed the data.

        # Tip: You can also use await pilot.press("enter") or pilot.click("#id")
        # to simulate user input if your widget handles events.
