"""Remote (Supabase) database models for sync.

These models mirror the local SQLite schema exactly but are bound
to a remote PostgreSQL database. They are used exclusively by
the SyncWorker for push/pull operations.
"""

import logging
from datetime import datetime

from peewee import (
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKeyField,
    IntegerField,
    Model,
    TextField,
)
from playhouse.db_url import connect

logger = logging.getLogger(__name__)

_remote_db = None


def create_remote_db(database_url: str, **kwargs):
    """Create and return a Peewee database connection to the remote DB."""
    global _remote_db
    connect_kwargs = kwargs.pop("connect_kwargs", {})
    connect_kwargs.setdefault("options", "-c statement_timeout=30000 -c lock_timeout=10000")
    _remote_db = connect(database_url, **connect_kwargs)

    for model in REMOTE_ALL_MODELS:
        model._meta.database = _remote_db

    return _remote_db


class RemoteBaseModel(Model):
    """Base model for remote database."""

    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    sync_status = CharField(max_length=10, default="synced")
    remote_updated_at = DateTimeField(null=True, default=None)

    class Meta:
        database = None

    def save(self, *args, **kwargs):
        self.updated_at = datetime.now()
        return super().save(*args, **kwargs)


class RemoteEntity(RemoteBaseModel):
    """Remote mirror of Entity."""
    name = CharField(max_length=200, index=True)
    entity_type = CharField(max_length=50, index=True)

    class Meta:
        table_name = "entity"


class RemoteRoom(RemoteBaseModel):
    """Remote mirror of Room."""
    entity = ForeignKeyField(RemoteEntity, backref="room_data", unique=True)
    room_number = IntegerField(unique=True, index=True)
    terrain = CharField(max_length=50, null=True, index=True)
    zone = CharField(max_length=100, null=True, index=True)
    full_name = CharField(max_length=200, null=True)
    outside = BooleanField(default=False, index=True)
    coord_x = IntegerField(null=True)
    coord_y = IntegerField(null=True)
    coord_z = IntegerField(null=True)
    details = TextField(null=True)

    class Meta:
        table_name = "room"
        indexes = (
            (("coord_x", "coord_y", "coord_z"), False),
            (("zone", "terrain"), False),
        )


class RemoteRoomExit(RemoteBaseModel):
    """Remote mirror of RoomExit."""
    from_room = ForeignKeyField(RemoteRoom, backref="exits")
    direction = CharField(max_length=20, index=True)
    to_room_number = IntegerField(index=True, null=True)
    is_door = BooleanField(default=False)
    door_is_closed = BooleanField(default=False)
    to_room = ForeignKeyField(RemoteRoom, backref="entrances", null=True)
    details = TextField(null=True)

    class Meta:
        table_name = "roomexit"
        indexes = (
            (("from_room", "direction"), True),
            (("to_room_number", "direction"), False),
        )


class RemoteNPC(RemoteBaseModel):
    """Remote mirror of NPC."""
    entity = ForeignKeyField(RemoteEntity, backref="npc_data")
    npc_type = CharField(max_length=50, null=True)
    current_room = ForeignKeyField(RemoteRoom, backref="npcs", null=True)

    class Meta:
        table_name = "npc"


class RemoteObservation(RemoteBaseModel):
    """Remote mirror of Observation."""
    entity = ForeignKeyField(RemoteEntity, backref="observations")
    observation_text = TextField()
    observation_type = CharField(max_length=50, default="general")

    class Meta:
        table_name = "observation"


class RemoteRelation(RemoteBaseModel):
    """Remote mirror of Relation."""
    from_entity = ForeignKeyField(RemoteEntity, backref="relations_from")
    to_entity = ForeignKeyField(RemoteEntity, backref="relations_to")
    relation_type = CharField(max_length=100)
    metadata = TextField(null=True)

    class Meta:
        table_name = "relation"


class RemoteSyncDelete(Model):
    """Remote mirror of SyncDelete — populated by Postgres triggers."""

    table_name_field = CharField(max_length=50)
    natural_key = TextField()
    deleted_at = DateTimeField(default=datetime.now)
    synced = BooleanField(default=False)

    class Meta:
        database = None
        table_name = "sync_deletes"


REMOTE_ALL_MODELS = [
    RemoteEntity,
    RemoteRoom,
    RemoteRoomExit,
    RemoteNPC,
    RemoteObservation,
    RemoteRelation,
    RemoteSyncDelete,
]
