import logging
from peewee import fn
from mud_agent.db.models import Room, RoomExit, NPC, db
from mud_agent.utils.retrievers import get_retriever

def extract_rooms_from_db(limit: int = 10) -> list[Room]:
    """
    Extracts room entities from the SQLite database and transforms them into the format expected by MapperContainer.

    Returns:
        List of dicts with keys: num, name, area, terrain, symbol, exits, npcs
    """
    logger = logging.getLogger(__name__)
    rooms_data = []
    try:
        db.connect(reuse_if_open=True)
        for room in Room.select():
            exits = {exit.direction.lower(): exit.to_room_number for exit in room.exits}
            npcs = [npc.entity.name for npc in room.npcs]

            room_dict = {
                "num": room.room_number,
                "name": room.full_name or room.entity.name,
                "area": room.zone,
                "terrain": room.terrain,
                "symbol": "●",
                "exits": exits,
                "npcs": npcs,
            }

            rooms_data.append(room_dict)
    except Exception as e:
        logger.error(f"Error loading rooms from database: {e}")
    finally:
        if not db.is_closed():
            db.close()

    logger.info(f"Extracted {len(rooms_data)} rooms from the database")
    return rooms_data
