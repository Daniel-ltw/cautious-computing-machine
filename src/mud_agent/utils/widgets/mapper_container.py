import logging
from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Grid
from textual.reactive import reactive
from textual.widgets import TabbedContent, TabPane

from mud_agent.db.models import Room

from .room_map_widget import RoomMapWidget
from .state_listener import StateListener
import asyncio


class MapperContainer(StateListener, Container):
    """Container for arranging RoomMapWidget instances in a grid, centering the current room."""

    GRID_ROWS = 9
    GRID_COLS = 11
    CENTER_ROW = GRID_ROWS // 2
    CENTER_COL = GRID_COLS // 2
    CENTER_Z = 1
    LEVELS = (0, 1, 2)

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

        for z in self.LEVELS:
            try:
                grid = self.query_one(f"#map-grid-z{z}", Grid)
                grid.styles.grid_size_columns = self.GRID_COLS
                grid.styles.grid_size_rows = self.GRID_ROWS
                grid.styles.grid_gutter_vertical = 0
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

        try:
            content_width = self.GRID_COLS * 5
            self.styles.width = content_width
            self.styles.min_width = content_width
            self.styles.max_width = content_width
        except Exception:
            pass

        asyncio.create_task(self._rebuild_widgets())

    async def _rebuild_widgets(self):
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

        # Yield to event loop before starting expensive work
        await asyncio.sleep(0)

        current_room = await self._get_current_room_info()
        if not current_room:
            logger.warning(f"Current room {self.current_room_num} not found in rooms data.")
            return

        # A map of all rooms to display, with their grid coordinates
        rooms_to_display = {}  # (r, c) -> room_data

        # Add the current room at the center
        rooms_to_display[(self.CENTER_ROW, self.CENTER_COL, self.CENTER_Z)] = current_room

        # Call the adjacents method with reduced depth to prevent freezing
        center_pos = (self.CENTER_ROW, self.CENTER_COL, self.CENTER_Z)
        await self._update_adjacent_by_depth(
            rooms_to_display,
            current_room,
            center_pos,
            3,
        )

        # Yield after expensive recursive traversal
        await asyncio.sleep(0)

        # Ensure cardinal neighbors render on Level 0 even when targets are unresolved
        try:
            cx, cy, cz = center_pos
            for dir_key in ("n", "e", "s", "w"):
                if dir_key in (current_room.get("exits") or {}):
                    nr, nc, nz = self._get_mapper_coords(cx, cy, cz, dir_key)
                    k = (nr, nc, nz)
                    if k not in rooms_to_display:
                        rooms_to_display[k] = {"num": -1, "exits": {}, "placeholder": True}
        except Exception:
            pass

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
        try:
            if isinstance(new_room_num, str) and new_room_num.isdigit():
                new_room_num = int(new_room_num)
        except Exception:
            pass
        if new_room_num and new_room_num != self.current_room_num:
            logger.debug(f"Room update received: {new_room_num}")
            self.current_room_num = new_room_num
            pass

    def _on_state_update(self, data: Any) -> None:
        pass

    def watch_current_room_num(self, old, new):
        """Watch for changes in current room number."""
        asyncio.create_task(self._rebuild_widgets())

    async def _update_adjacent_by_depth(self, rooms_to_display, current_room, current_pos, depth = 1):
        current_r, current_c, current_z = current_pos

        # Batch fetch all adjacent rooms concurrently
        fetch_tasks = []
        exit_info = []  # Store (direction, room_num, new_r, new_c, new_z) tuples

        for direction, room_num in current_room.get("exits", {}).items():
            if direction not in self._get_mapper_coords_positions():
                continue
            # Skip exits without a resolvable target room number
            try:
                dest_room_num = room_num
                if isinstance(dest_room_num, str):
                    dest_room_num = int(dest_room_num) if dest_room_num.isdigit() else None
            except Exception:
                dest_room_num = None

            new_r, new_c, new_z = self._get_mapper_coords(
                current_r,
                current_c,
                current_z,
                direction,
            )
            if new_c == self.CENTER_COL and new_r == self.CENTER_ROW and new_z == self.CENTER_Z:
                # If center room, skip
                continue
            if new_c >= self.GRID_COLS or new_c < 0 or new_r >= self.GRID_ROWS or new_r < 0 or new_z not in self.LEVELS:
                continue

            # Store exit info for processing after fetch
            exit_info.append((direction, dest_room_num, new_r, new_c, new_z))

            # Create fetch task if room number is valid
            if isinstance(dest_room_num, int) and dest_room_num > 0:
                fetch_tasks.append(self.app.agent.knowledge_graph.get_room_info(dest_room_num))
            else:
                fetch_tasks.append(None)  # Placeholder for invalid room

        # Fetch all rooms concurrently
        if fetch_tasks:
            fetched_rooms = await asyncio.gather(*[task if task else asyncio.sleep(0, result=None) for task in fetch_tasks], return_exceptions=True)
        else:
            fetched_rooms = []

        # Process fetched rooms
        for idx, (direction, dest_room_num, new_r, new_c, new_z) in enumerate(exit_info):
            new_room = fetched_rooms[idx] if idx < len(fetched_rooms) else None

            # Handle exceptions or missing rooms
            if isinstance(new_room, Exception) or not new_room:
                new_room = {
                    "num": dest_room_num if dest_room_num else -1,
                    "exits": {},
                    "placeholder": True,
                }

            rooms_to_display[(new_r, new_c, new_z)] = new_room

            # Recursively fetch deeper levels
            if depth > 1:
                current_depth = depth - 1
                await self._update_adjacent_by_depth(
                    rooms_to_display,
                    new_room,
                    (new_r, new_c, new_z),
                    current_depth,
                )
                # Yield to event loop after each recursive call
                await asyncio.sleep(0)

    async def _get_current_room_info(self) -> dict[str, Any] | None:
        room = None
        try:
            if hasattr(self.app, 'agent') and hasattr(self.app.agent, 'knowledge_graph'):
                room = await self.app.agent.knowledge_graph.get_room_info(self.current_room_num)
        except Exception:
            room = None
        if room:
            return room
        fallback = {}
        try:
            if getattr(self, "state_manager", None) and hasattr(self.state_manager, "get_current_room_data"):
                fallback = self.state_manager.get_current_room_data() or {}
            elif hasattr(self.app, "agent") and hasattr(self.app.agent, "aardwolf_gmcp"):
                fallback = self.app.agent.aardwolf_gmcp.get_room_info() or {}
        except Exception:
            fallback = {}
        if fallback:
            if "num" not in fallback:
                fallback["num"] = self.current_room_num
            else:
                try:
                    num_val = fallback.get("num")
                    if isinstance(num_val, str) and num_val.isdigit():
                        fallback["num"] = int(num_val)
                except Exception:
                    pass
            if not fallback.get("num") or fallback.get("num") == 0:
                try:
                    if getattr(self, "state_manager", None) and getattr(self.state_manager, "room_num", 0):
                        fallback["num"] = int(self.state_manager.room_num)
                except Exception:
                    pass
            raw_exits = fallback.get("exits") or {}
            normalized_exits: dict[str, int | None] = {}
            try:
                if isinstance(raw_exits, dict):
                    for k, v in raw_exits.items():
                        key = str(k).lower()
                        if isinstance(v, dict):
                            num = v.get("num")
                            normalized_exits[key] = int(num) if isinstance(num, int) or (isinstance(num, str) and num.isdigit()) else None
                        elif isinstance(v, int):
                            normalized_exits[key] = v
                        elif isinstance(v, str) and v.isdigit():
                            normalized_exits[key] = int(v)
                        else:
                            # Keep the direction even if target is unresolved
                            normalized_exits[key] = None
                elif isinstance(raw_exits, list):
                    for item in raw_exits:
                        if isinstance(item, dict):
                            key = str(item.get("dir") or item.get("direction") or "").lower()
                            num = item.get("num")
                            if key:
                                normalized_exits[key] = int(num) if isinstance(num, int) or (isinstance(num, str) and num.isdigit()) else None
                        elif isinstance(item, str):
                            # GMCP often provides exits as a simple list of direction strings
                            normalized_exits[item.lower()] = None
            except Exception:
                normalized_exits = {}
            # Keep exits even when unresolved; adjacency will render placeholders for unknowns
            fallback["exits"] = normalized_exits
            return fallback
        return None


    def _get_mapper_coords_positions(self):
        return {
            "n": (-1, 0, 0),
            "s": (1, 0, 0),
            "e": (0, 1, 0),
            "w": (0, -1, 0),
            "u": (0, 0, 1),
            "d": (0, 0, -1),
        }

    def _get_mapper_coords(self, r, c, z, direction):
        # Position mapping for exits (0-indexed, relative to center)
        positions = self._get_mapper_coords_positions()
        dr, dc, dz = positions[direction]
        return r + dr, c + dc, z + dz
