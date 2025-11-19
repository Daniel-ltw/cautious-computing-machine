import pytest
from rich.text import Text

from mud_agent.utils.widgets.room_map_widget import RoomMapWidget


@pytest.fixture
def room_widget():
    """Provides a fresh RoomMapWidget for each test."""
    return RoomMapWidget()


def test_render_no_room_data(room_widget):
    """Tests that a widget with no room data renders a dot."""
    room_widget.room_data = {}
    assert room_widget.render() == Text("  .  ", justify="center")


def test_render_no_room_num(room_widget):
    """Tests that a widget with no room number renders a dot."""
    room_widget.room_data = {"exits": {"n": 1}}
    assert room_widget.render() == Text("  .  ", justify="center")


def test_render_current_room(room_widget):
    """Tests that the current room is always rendered as '[@]' in the center."""
    room_widget.is_current = True
    room_widget.room_data = {"num": 1, "exits": {"n": 2, "w": 3}}
    expected_grid = "  |  \n-[@] \n     "
    assert room_widget.render().plain == expected_grid.replace("\\n", "\n")


def test_render_no_exits(room_widget):
    """Tests that a room with no exits renders as '[#]' in the center."""
    room_widget.room_data = {"num": 1, "exits": {}}
    expected_grid = "     \n [#] \n     "
    assert room_widget.render().plain == expected_grid.replace("\\n", "\n")


@pytest.mark.parametrize(
    "exits, expected_grid",
    [
        # Cardinal
        ({"n": 2}, "  |  \n [#] \n     "),
        ({"s": 2}, "     \n [#] \n  |  "),
        ({"e": 2}, "     \n [#]-\n     "),
        ({"w": 2}, "     \n-[#] \n     "),
        ({"n": 2, "s": 3}, "  |  \n [#] \n  |  "),
        ({"e": 2, "w": 3}, "     \n-[#]-\n     "),
        ({"n": 2, "e": 3}, "  |  \n [#]-\n     "),
        ({"n": 2, "w": 3}, "  |  \n-[#] \n     "),
        ({"s": 2, "e": 3}, "     \n [#]-\n  |  "),
        ({"s": 2, "w": 3}, "     \n-[#] \n  |  "),
        ({"n": 2, "s": 3, "e": 4}, "  |  \n [#]-\n  |  "),
        ({"n": 2, "s": 3, "w": 4}, "  |  \n-[#] \n  |  "),
        ({"n": 2, "e": 3, "w": 4}, "  |  \n-[#]-\n     "),
        ({"s": 2, "e": 3, "w": 4}, "     \n-[#]-\n  |  "),
        ({"n": 2, "s": 3, "e": 4, "w": 5}, "  |  \n-[#]-\n  |  "),
        # Vertical
        ({"u": 2}, "    /\n [#] \n     "),
        ({"d": 2}, "     \n [#] \n/    "),
        ({"u": 2, "d": 3}, "    /\n [#] \n/    "),
        # Combined
        ({"n": 1, "u": 2}, "  | /\n [#] \n     "),
        ({"s": 1, "d": 2}, "     \n [#] \n/ |  "),
        ({"n": 1, "s": 2, "e": 3, "w": 4, "u": 5, "d": 6}, "  | /\n-[#]-\n/ |  "),
    ],
)
def test_render_exits(room_widget, exits, expected_grid):
    """Tests rendering of all combinations of exits."""
    room_widget.room_data = {"num": 1, "exits": exits}
    assert room_widget.render().plain == expected_grid.replace("\\n", "\n")


def test_current_room_precedence(room_widget):
    """Tests that the current room '[@]' symbol has the highest precedence."""
    room_widget.is_current = True
    exits = {"u": 1, "n": 2, "w": 3}
    room_widget.room_data = {"num": 1, "exits": exits}
    expected_grid = "  | /\n-[@] \n     "
    assert room_widget.render().plain == expected_grid.replace("\\n", "\n")
