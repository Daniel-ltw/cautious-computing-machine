from typing import Any

from rich.text import Text
from textual.widgets import Static
from textual.reactive import reactive

from .state_listener import StateListener

class RoomMapWidget(StateListener, Static):
    """A widget to display a 5x3 ASCII art representation of a single MUD room.

    This widget renders a room's exits (north, south, east, west, up, down)
    and indicates whether it is the player's current room.

    Attributes:
        is_current (reactive[bool]): A reactive attribute that, when True, highlights
            the room as the player's current location.
        room_data (dict[str, Any]): The dictionary containing the room's properties,
            such as its number, name, exits, etc.
    """

    is_current = reactive(False)

    # This widget should not be listening for room events directly.
    # The container will manage its state.
    register_for_room_events = False
    register_for_map_events = False

    # A mapping from cardinal and vertical direction abbreviations to the
    # corresponding grid coordinates (row, column) and character for drawing.
    DRAW_MAP = {
        "N": (0, 2, "|"),
        "S": (2, 2, "|"),
        "E": (1, 4, "-"),
        "W": (1, 0, "-"),
        "U": (0, 4, "/"),
        "D": (2, 0, "/"),
    }
    # Characters used for drawing the room itself.
    ROOM_CHARS = {
        "LEFT": "[",
        "RIGHT": "]",
        "CURRENT": "@",
        "OTHER": "#",
    }

    def __init__(self, room_data: dict[str, Any] | None = None, *args, **kwargs) -> None:
        """Initialize the RoomMapWidget.

        Args:
            room_data (dict[str, Any] | None): The data for the room to be displayed.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super().__init__(*args, **kwargs)
        self.room_data = room_data or {}
        self.update_room_data(self.room_data)

    def on_mount(self) -> None:
        """Set up the widget's initial styles when it is mounted."""
        super().on_mount()
        self.styles.text_align = "center"
        self.styles.vertical_align = "middle"

    def update_room_data(self, data: dict[str, Any]) -> None:
        """Update the room data and trigger a refresh of the widget.

        Args:
            data (dict[str, Any]): The new room data.
        """
        self.room_data = data
        self.tooltip = self._generate_tooltip()
        self.update_content()

    def render(self) -> Text:
        """Render the 5x3 ASCII grid for the room.

        Returns:
            Text: A Rich Text object representing the rendered room.
        """
        if not self.room_data.get("num"):
            return Text("  .  ", justify="center")

        grid = [[' ' for _ in range(5)] for _ in range(3)]

        center_char = self.ROOM_CHARS["CURRENT"] if self.is_current else self.ROOM_CHARS["OTHER"]
        grid[1][1] = self.ROOM_CHARS["LEFT"]
        grid[1][2] = center_char
        grid[1][3] = self.ROOM_CHARS["RIGHT"]

        exits = self.room_data.get("exits", {})
        for exit_dir, (r, c, char) in self.DRAW_MAP.items():
            if exit_dir.lower() in exits:
                grid[r][c] = char

        return Text("\n".join("".join(row) for row in grid), justify="center")

    def update_content(self) -> None:
        """Refresh the widget to reflect the latest room data."""
        self.refresh()

    def watch_is_current(self, is_current: bool) -> None:
        """A reactive watcher that updates the widget's style when it becomes the current room.

        Args:
            is_current (bool): True if this room is the current one, False otherwise.
        """
        if is_current:
            self.styles.color = "magenta"
        else:
            self.styles.color = None  # Reset to default color

    def _on_state_update(self, data: Any) -> None:
        """Handle state updates.

        Note:
            This widget is controlled by its container, so this method is a no-op.

        Args:
            data (Any): The state update data (unused).
        """
        pass

    def _generate_tooltip(self) -> str:
        """Generate a detailed tooltip for the room.

        Returns:
            str: A formatted string with room details.
        """
        if not self.room_data.get("num"):
            return ""

        parts = []
        room_name = self.room_data.get("name", "Unknown")
        room_num = self.room_data.get("num")
        area_name = self.room_data.get("area", "Unknown")
        room_terrain = self.room_data.get("terrain", "Unknown")
        exits = self.room_data.get("exits", {})
        room_details = self.room_data.get("details", "")
        room_coords = self.room_data.get("coords", {})
        npcs = self.room_data.get("npcs", [])

        if room_name and room_name != "Unknown":
            parts.append(f"Room: {room_name} (#{room_num})")
        else:
            parts.append(f"Room #: {room_num}")

        if area_name and area_name != "Unknown":
            parts.append(f"Area: {area_name}")
        if room_terrain and room_terrain != "Unknown":
            parts.append(f"Terrain: {room_terrain}")
        if exits:
            exits_str = ", ".join(exits.keys())
            parts.append(f"Exits: {exits_str}")
        if room_details:
            parts.append(f"Details: {room_details}")
        if room_coords:
            coords_str = ", ".join(f"{k}={v}" for k, v in room_coords.items())
            parts.append(f"Coords: {coords_str}")
        if npcs:
            npcs_str = ", ".join(map(str, npcs))
            parts.append(f"NPCs: {npcs_str}")
        return "\n".join(parts)
