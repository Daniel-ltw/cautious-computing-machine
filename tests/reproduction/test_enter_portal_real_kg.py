
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from mud_agent.agent.room_manager import RoomManager
from mud_agent.mcp.game_knowledge_graph import GameKnowledgeGraph
from mud_agent.db.models import db, Room, RoomExit, Entity

@pytest.mark.asyncio
class TestEnterPortalRealKG:
    async def test_enter_portal_full_stack(self):
        """Test 'enter rubble' with real GameKnowledgeGraph and in-memory DB."""

        # 1. Setup In-Memory DB
        db.init(":memory:")
        db.connect()
        db.create_tables([Room, RoomExit, Entity])

        # 2. Setup GameKnowledgeGraph
        kg = GameKnowledgeGraph()
        await kg.initialize()

        # 3. Setup Agent and RoomManager
        mock_agent = MagicMock()
        mock_agent.events = MagicMock()
        mock_agent.events.emit = AsyncMock()
        mock_agent.events.on = MagicMock()
        mock_agent.knowledge_graph = kg

        # Mock state manager
        mock_agent.state_manager = MagicMock()
        mock_agent.state_manager.room_num = 1

        manager = RoomManager(mock_agent)
        await manager.setup()

        # 4. Create Initial Rooms in DB
        # Room 1: The starting room
        await kg.add_entity({
            "entityType": "Room",
            "name": "Start Room",
            "num": 1,
            "description": "A pile of rubble is here.",
            "exits": {}
        })

        # Room 2: The destination
        await kg.add_entity({
            "entityType": "Room",
            "name": "Inside Rubble",
            "num": 2,
            "description": "Dark and cramped.",
            "exits": {}
        })

        # Room 99: Another destination
        await kg.add_entity({
            "entityType": "Room",
            "name": "Hut Interior",
            "num": 99,
            "description": "A small hut.",
            "exits": {}
        })

        # Pre-create a conflicting exit: "enter hut" -> Room 99
        print("Pre-creating conflicting exit 'enter hut' -> Room 99")
        room1 = Room.get(Room.room_number == 1)
        room99 = Room.get(Room.room_number == 99)
        RoomExit.create(from_room=room1, direction="enter hut", to_room=room99, to_room_number=99)

        manager.current_room = {"num": 1, "name": "Start Room"}

        # 5. Execute "enter rubble" -> Room 99 (Collision with 'enter hut')
        print("\nSending command 'enter rubble'...")
        # We need to simulate the room alias scenario.
        # Room update says we are in Room 99.
        await manager._handle_command_sent(command="enter rubble", from_room_num=1)

        assert manager.pending_exit_command == "enter rubble"

        # 6. Simulate Room Update (Move successful to 99)
        print("Simulating room update to Room 99...")
        await manager._on_room_update(room_data={"num": 99, "name": "Hut Interior"})

        # 7. Verify DB State
        # Check if exit was created in Room 1
        room1 = Room.get(Room.room_number == 1)
        exits = list(room1.exits)
        print(f"Room 1 exits: {[e.direction for e in exits]}")

        found_rubble = False
        found_hut = False
        for ex in exits:
            if ex.direction == "enter rubble" and ex.to_room_number == 99:
                found_rubble = True
            if ex.direction == "enter hut" and ex.to_room_number == 99:
                found_hut = True
                print(f"Existing 'enter hut' details: {ex.details}")

        if found_rubble:
             print("SUCCESS: New exit 'enter rubble' created!")
        else:
             print("FAILURE: New exit 'enter rubble' NOT created.")

        assert found_rubble, "Expected 'enter rubble' to be a separate exit, but it was not created!"

        # Teardown
        db.close()
