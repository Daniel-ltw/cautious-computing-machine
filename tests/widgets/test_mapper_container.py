import pytest
from textual.app import App

from mud_agent.utils.widgets.mapper_container import MapperContainer


class MapperContainerApp(App):
    def compose(self):
        yield MapperContainer()


@pytest.mark.asyncio
async def test_initial_state():
    """Test that MapperContainer can be mounted and queried."""
    app = MapperContainerApp()
    async with app.run_test() as pilot:
        assert pilot.app.query_one(MapperContainer)
