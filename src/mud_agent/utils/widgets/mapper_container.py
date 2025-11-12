import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Grid
from textual.widgets import TabbedContent, TabPane
from textual.reactive import reactive

from ..room_entity_extractor import extract_rooms_from_db

from .room_map_widget import RoomMapWidget
from .state_listener import StateListener

from textual.widget import Widget
from textual.widgets import Static

from ...db.models import Room


class MapperContainer(StateListener, Container):
    """Container for arranging RoomMapWidget instances in a grid, centering the current room."""

    GRID_ROWS = 7
    GRID_COLS = 11
    CENTER_ROW = GRID_ROWS // 2
    CENTER_COL = GRID_COLS // 2
    CENTER_Z = 1

    current_room_num = reactive(0)
    register_for_room_events = True
    register_for_map_events = False

    def __init__(self, current_room_num=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._active_widgets = []
        logger = logging.getLogger(__name__)
        logger.info(f"Inspecting self.app: {dir(self.app)}")
        logger.info(f"MapperContainer.__init__ called with current_room_num={current_room_num}")
        if current_room_num is not None:
            logger.info(f"Setting current_room_num to {current_room_num}")
            self.current_room_num = current_room_num
            logger.info(f"After setting: self.current_room_num={self.current_room_num}")

    def compose(self) -> ComposeResult:
        """Compose the widget."""
        with TabbedContent(initial="level-1"):
            for z, name in [(0, "Level -1"), (1, "Level 0"), (2, "Level +1")]:
                with TabPane(name, id=f"level-{z}"):
                    yield Grid(id=f"map-grid-z{z}")

    async def on_mount(self):
        """Load initial data and rebuild widgets when the component is mounted."""
        logger = logging.getLogger(__name__)
        logger.info("MapperContainer.on_mount called")

        for z in [0, 1, 2]:
            try:
                grid = self.query_one(f"#map-grid-z{z}", Grid)
                grid.styles.grid_size_columns = self.GRID_COLS
                grid.styles.grid_size_rows = self.GRID_ROWS
                grid.styles.grid_gutter_vertical = 1
                grid.styles.grid_gutter_horizontal = 0
                grid.styles.align_x = "center"
                grid.styles.align_y = "middle"
                # Create a grid of default room widgets
                for r in range(self.GRID_ROWS):
                    for c in range(self.GRID_COLS):
                        widget = RoomMapWidget(room_data={}, id=f"room-widget-z{z}-r{r}-c{c}")
                        widget.styles.grid_column = c + 1
                        widget.styles.grid_row = r + 1
                        grid.mount(widget)
            except Exception as e:
                logger.error(f"Failed to style or populate grid for z={z}: {e}")

        self._rebuild_widgets()

    def _rebuild_widgets(self):
        """Clear and rebuild the grid of room widgets around the current room."""
        logger = logging.getLogger(__name__)

        # Clear previously active widgets
        for widget in self._active_widgets:
            widget.update_room_data({})
            widget.styles.border = None
            widget.is_current = False
        self._active_widgets = []

        if not self.current_room_num:
            return

        current_room = Room.get(room_number=self.current_room_num).to_info()
        if not current_room:
            logger.warning(f"Current room {self.current_room_num} not found in rooms data.")
            return

        # A map of all rooms to display, with their grid coordinates
        rooms_to_display = {}  # (r, c) -> room_data

        # Add the current room at the center
        rooms_to_display[(self.CENTER_ROW, self.CENTER_COL, self.CENTER_Z)] = current_room

        # Call the adjacents method
        self._update_adjacent_by_depth(
            rooms_to_display,
            current_room,
            self.CENTER_COL,
            self.CENTER_ROW,
            self.CENTER_Z,
            6,
        )

        # Now, update the widgets
        for (r, c, z), room_data in rooms_to_display.items():
            try:
                widget = self.query_one(f"#room-widget-z{z}-r{r}-c{c}", RoomMapWidget)
                logger.debug(f"Updating widget at (r={r}, c={c}, z={z}) with room_num={room_data.get('num')}")
                widget.update_room_data(room_data)
                widget.is_current = (r == self.CENTER_ROW and c == self.CENTER_COL and z == self.CENTER_Z)
                self._active_widgets.append(widget)
            except Exception as e:
                logger.error(f"Failed to update widget at z={z}, r={r}, c={c}: {e}")

    def _on_room_update(self, **kwargs) -> None:
        """Called when the room changes."""
        data = kwargs.get("room_data", {})
        logger = logging.getLogger(__name__)
        new_room_num = data.get("num")
        if new_room_num and new_room_num != self.current_room_num:
            logger.debug(f"Room update received: {new_room_num}")
            self.current_room_num = new_room_num
            # Potentially highlight the current room, but don't rebuild the whole grid
            # self._highlight_current_room()

    def _on_state_update(self, data: Any) -> None:
        pass

    def watch_current_room_num(self, old, new):
        """Watch for changes in current room number."""
        logger = logging.getLogger(__name__)
        self._rebuild_widgets()

    def _update_adjacent_by_depth(self, rooms_to_display, current_room, current_x, current_y, current_z, depth = 1):
        for direction, room_num in current_room["exits"].items():
            if direction not in self._get_mapper_coords_positions():
                continue

            new_x, new_y, new_z = self._get_mapper_coords(
                current_x,
                current_y,
                current_z,
                direction
            )
            if new_x == self.CENTER_COL and new_y == self.CENTER_ROW and new_z == self.CENTER_Z:
                # If center room, skip
                continue
            if new_x >= self.GRID_COLS or new_x < 0 or new_y >= self.GRID_ROWS or new_y < 0 or new_z < 0 or new_z > 2:
                continue
            try:
                new_room = Room.get(room_number=room_num).to_info()
            except Room.DoesNotExist:
                new_room = {
                    "num": room_num,
                    "exits": {}
                }
            rooms_to_display[(new_y, new_x, new_z)] = new_room
            if depth > 1:
                current_depth = depth - 1
                self._update_adjacent_by_depth(
                    rooms_to_display,
                    new_room,
                    new_x,
                    new_y,
                    new_z,
                    current_depth,
                )


    def _get_mapper_coords_positions(self):
        return {
            "n": (0, -1, 0),
            "s": (0, 1, 0),
            "e": (1, 0, 0),
            "w": (-1, 0, 0),
            "u": (0, 0, 1),
            "d": (0, 0, -1),
        }

    def _get_mapper_coords(self, x, y, z, direction):
        # Position mapping for exits (0-indexed, relative to center)
        positions = self._get_mapper_coords_positions()
        dx, dy, dz = positions[direction]
        return x + dx, y + dy, z + dz
