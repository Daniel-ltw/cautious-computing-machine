"""SyncWorker: Background bidirectional sync between local SQLite and remote Supabase.

Push: Finds all local records with sync_status='dirty', upserts them to remote.
Pull: Finds all remote records newer than last_pull_timestamp, merges locally.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from peewee import DoesNotExist

from mud_agent.db.models import (
    ALL_MODELS,
    Entity,
    NPC,
    Observation,
    Relation,
    Room,
    RoomExit,
    SyncDelete,
    db as local_db,
)
from mud_agent.db.sync_models import (
    REMOTE_ALL_MODELS,
    RemoteEntity,
    RemoteNPC,
    RemoteObservation,
    RemoteRelation,
    RemoteRoom,
    RemoteRoomExit,
    RemoteSyncDelete,
    create_remote_db,
)

logger = logging.getLogger(__name__)

# Mapping from local models to remote models
LOCAL_TO_REMOTE = {
    Entity: RemoteEntity,
    Room: RemoteRoom,
    RoomExit: RemoteRoomExit,
    NPC: RemoteNPC,
    Observation: RemoteObservation,
    Relation: RemoteRelation,
}

# Push order: entities first, then rooms, then everything else
PUSH_ORDER = [Entity, Room, RoomExit, NPC, Observation, Relation]

# Mappings from table_name strings to model classes (for delete sync)
TABLE_NAME_TO_REMOTE = {
    "entity": RemoteEntity,
    "room": RemoteRoom,
    "roomexit": RemoteRoomExit,
    "npc": RemoteNPC,
    "observation": RemoteObservation,
    "relation": RemoteRelation,
}
TABLE_NAME_TO_LOCAL = {
    "entity": Entity,
    "room": Room,
    "roomexit": RoomExit,
    "npc": NPC,
    "observation": Observation,
    "relation": Relation,
}


class SyncWorker:
    """Background worker that syncs local SQLite with remote Supabase."""

    def __init__(self, sync_interval: float = 30.0):
        self.sync_interval = sync_interval
        self._task: Optional[asyncio.Task] = None
        self._remote_db = None
        self._last_pull_at: Optional[datetime] = None
        self.logger = logging.getLogger(__name__)

    async def start(self, database_url: str) -> None:
        """Start the background sync loop."""
        try:
            self._remote_db = create_remote_db(database_url)
            if self._remote_db.is_closed():
                self._remote_db.connect()
            self._remote_db.create_tables(REMOTE_ALL_MODELS, safe=True)
            self.logger.info("SyncWorker connected to remote database.")
        except Exception as e:
            self.logger.error(f"SyncWorker failed to connect to remote DB: {e}")
            return

        self._task = asyncio.create_task(self._sync_loop())
        self.logger.info(f"SyncWorker started with interval={self.sync_interval}s")

    async def stop(self) -> None:
        """Stop the sync loop gracefully."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._remote_db and not self._remote_db.is_closed():
            self._remote_db.close()
        self.logger.info("SyncWorker stopped.")

    async def _sync_loop(self) -> None:
        """Main sync loop: push then pull on each cycle."""
        try:
            while True:
                try:
                    await asyncio.to_thread(self._push_with_connection)
                    await asyncio.to_thread(self._pull_with_connection)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.logger.error(f"Sync cycle error: {e}", exc_info=True)
                await asyncio.sleep(self.sync_interval)
        except asyncio.CancelledError:
            self.logger.info("SyncWorker loop cancelled.")

    def _push_with_connection(self) -> None:
        """Push with a dedicated local DB connection for thread safety."""
        with local_db.connection_context():
            self.push()
            self.push_deletes()

    def _pull_with_connection(self) -> None:
        """Pull with a dedicated local DB connection for thread safety."""
        with local_db.connection_context():
            self.pull()
            self.pull_deletes()

    def push(self) -> None:
        """Push all dirty local records to the remote database."""
        for local_model in PUSH_ORDER:
            remote_model = LOCAL_TO_REMOTE[local_model]
            dirty_records = list(local_model.select().where(
                local_model.sync_status == "dirty"
            ))

            if not dirty_records:
                continue

            self.logger.debug(
                f"Pushing {len(dirty_records)} dirty {local_model.__name__} records"
            )

            for record in dirty_records:
                try:
                    self._push_record(record, local_model, remote_model)
                except Exception as e:
                    self.logger.error(
                        f"Failed to push {local_model.__name__} id={record.id}: {e}"
                    )

    def _push_record(self, record, local_model, remote_model) -> None:
        """Push a single local record to the remote database."""
        data = {}
        for field in local_model._meta.sorted_fields:
            if field.name == "id":
                continue
            # Handle foreign keys: store the ID, not the object
            if hasattr(field, "rel_model"):
                fk_value = getattr(record, field.name + "_id", None)
                data[field.name] = fk_value
            else:
                data[field.name] = getattr(record, field.name)

        data["sync_status"] = "synced"
        data["remote_updated_at"] = datetime.now(timezone.utc)

        # Resolve foreign key IDs from local to remote
        data = self._resolve_fk_for_push(record, local_model, data)

        # Upsert to remote
        with self._remote_db.atomic():
            existing = self._find_remote_by_natural_key(record, local_model, remote_model)
            if existing:
                for key, value in data.items():
                    setattr(existing, key, value)
                existing.save()
            else:
                remote_model.create(**data)

        # Mark local as synced (bypass the save() override that sets dirty)
        local_model.update(
            sync_status="synced",
            remote_updated_at=datetime.now(timezone.utc),
        ).where(local_model.id == record.id).execute()

    def _resolve_fk_for_push(self, record, local_model, data: dict) -> dict:
        """Resolve local FK IDs to remote FK IDs for push."""
        if local_model == Room:
            # entity FK: find remote entity by natural key
            local_entity = record.entity
            remote_entity = RemoteEntity.get_or_none(
                (RemoteEntity.name == local_entity.name)
                & (RemoteEntity.entity_type == local_entity.entity_type)
            )
            if remote_entity:
                data["entity"] = remote_entity.id

        elif local_model == RoomExit:
            # from_room FK
            from_room = record.from_room
            remote_from = RemoteRoom.get_or_none(
                RemoteRoom.room_number == from_room.room_number
            )
            if remote_from:
                data["from_room"] = remote_from.id

            # to_room FK (nullable)
            if record.to_room_id:
                to_room = record.to_room
                remote_to = RemoteRoom.get_or_none(
                    RemoteRoom.room_number == to_room.room_number
                )
                data["to_room"] = remote_to.id if remote_to else None

        elif local_model == NPC:
            local_entity = record.entity
            remote_entity = RemoteEntity.get_or_none(
                (RemoteEntity.name == local_entity.name)
                & (RemoteEntity.entity_type == local_entity.entity_type)
            )
            if remote_entity:
                data["entity"] = remote_entity.id
            # current_room FK (nullable)
            if record.current_room_id:
                local_room = record.current_room
                remote_room = RemoteRoom.get_or_none(
                    RemoteRoom.room_number == local_room.room_number
                )
                data["current_room"] = remote_room.id if remote_room else None

        elif local_model == Observation:
            local_entity = record.entity
            remote_entity = RemoteEntity.get_or_none(
                (RemoteEntity.name == local_entity.name)
                & (RemoteEntity.entity_type == local_entity.entity_type)
            )
            if remote_entity:
                data["entity"] = remote_entity.id

        elif local_model == Relation:
            from_entity = record.from_entity
            to_entity = record.to_entity
            remote_from = RemoteEntity.get_or_none(
                (RemoteEntity.name == from_entity.name)
                & (RemoteEntity.entity_type == from_entity.entity_type)
            )
            remote_to = RemoteEntity.get_or_none(
                (RemoteEntity.name == to_entity.name)
                & (RemoteEntity.entity_type == to_entity.entity_type)
            )
            if remote_from:
                data["from_entity"] = remote_from.id
            if remote_to:
                data["to_entity"] = remote_to.id

        return data

    def _find_remote_by_natural_key(self, record, local_model, remote_model):
        """Find the remote counterpart of a local record by natural key."""
        try:
            if local_model == Entity:
                return remote_model.get_or_none(
                    (remote_model.name == record.name)
                    & (remote_model.entity_type == record.entity_type)
                )
            elif local_model == Room:
                return remote_model.get_or_none(
                    remote_model.room_number == record.room_number
                )
            elif local_model == RoomExit:
                from_room = record.from_room
                remote_from = RemoteRoom.get_or_none(
                    RemoteRoom.room_number == from_room.room_number
                )
                if remote_from:
                    return remote_model.get_or_none(
                        (remote_model.from_room == remote_from)
                        & (remote_model.direction == record.direction)
                    )
                return None
            elif local_model == NPC:
                entity = record.entity
                remote_entity = RemoteEntity.get_or_none(
                    (RemoteEntity.name == entity.name)
                    & (RemoteEntity.entity_type == entity.entity_type)
                )
                if remote_entity:
                    return remote_model.get_or_none(
                        remote_model.entity == remote_entity
                    )
                return None
            else:
                return remote_model.get_or_none(remote_model.id == record.id)
        except Exception:
            return None

    def pull(self) -> None:
        """Pull new/updated records from remote and merge locally."""
        for local_model in PUSH_ORDER:
            remote_model = LOCAL_TO_REMOTE[local_model]

            query = remote_model.select()
            if self._last_pull_at:
                query = query.where(remote_model.updated_at > self._last_pull_at)

            remote_records = list(query)
            if not remote_records:
                continue

            self.logger.debug(
                f"Pulling {len(remote_records)} {remote_model.__name__} records"
            )

            for remote_record in remote_records:
                try:
                    self._pull_record(remote_record, local_model, remote_model)
                except Exception as e:
                    self.logger.error(
                        f"Failed to pull {remote_model.__name__} id={remote_record.id}: {e}"
                    )

        self._last_pull_at = datetime.now(timezone.utc)

    def _pull_record(self, remote_record, local_model, remote_model) -> None:
        """Pull a single remote record and merge it locally."""
        local_record = self._find_local_by_natural_key(
            remote_record, local_model, remote_model
        )

        if local_record is None:
            self._insert_local_from_remote(remote_record, local_model, remote_model)
            return

        if local_record.sync_status == "synced":
            self._overwrite_local_from_remote(
                local_record, remote_record, local_model, remote_model
            )
        elif local_record.sync_status == "dirty":
            self._merge_local_with_remote(
                local_record, remote_record, local_model, remote_model
            )

    def _find_local_by_natural_key(self, remote_record, local_model, remote_model):
        """Find the local counterpart of a remote record."""
        try:
            if local_model == Entity:
                return local_model.get_or_none(
                    (local_model.name == remote_record.name)
                    & (local_model.entity_type == remote_record.entity_type)
                )
            elif local_model == Room:
                return local_model.get_or_none(
                    local_model.room_number == remote_record.room_number
                )
            elif local_model == RoomExit:
                remote_from = remote_record.from_room
                local_from = Room.get_or_none(
                    Room.room_number == remote_from.room_number
                )
                if local_from:
                    return local_model.get_or_none(
                        (local_model.from_room == local_from)
                        & (local_model.direction == remote_record.direction)
                    )
                return None
            elif local_model == NPC:
                remote_entity = remote_record.entity
                local_entity = Entity.get_or_none(
                    (Entity.name == remote_entity.name)
                    & (Entity.entity_type == remote_entity.entity_type)
                )
                if local_entity:
                    return local_model.get_or_none(local_model.entity == local_entity)
                return None
            else:
                return local_model.get_or_none(local_model.id == remote_record.id)
        except Exception:
            return None

    def _insert_local_from_remote(self, remote_record, local_model, remote_model) -> None:
        """Insert a new local record from a remote record."""
        data = {}
        for field in remote_model._meta.sorted_fields:
            if field.name == "id":
                continue
            if hasattr(field, "rel_model"):
                data[field.name] = getattr(remote_record, field.name + "_id", None)
            else:
                data[field.name] = getattr(remote_record, field.name)

        data["sync_status"] = "synced"
        data["remote_updated_at"] = remote_record.updated_at

        # Resolve foreign keys from remote IDs to local IDs
        if local_model == Room:
            remote_entity = remote_record.entity
            local_entity = Entity.get_or_none(
                (Entity.name == remote_entity.name)
                & (Entity.entity_type == remote_entity.entity_type)
            )
            if local_entity:
                data["entity"] = local_entity.id
            else:
                return  # Can't create room without entity

        elif local_model == RoomExit:
            remote_from = remote_record.from_room
            local_from = Room.get_or_none(Room.room_number == remote_from.room_number)
            if local_from:
                data["from_room"] = local_from.id
            else:
                return  # Can't create exit without from_room

            if remote_record.to_room_id:
                remote_to = remote_record.to_room
                local_to = Room.get_or_none(
                    Room.room_number == remote_to.room_number
                )
                data["to_room"] = local_to.id if local_to else None

        elif local_model == NPC:
            remote_entity = remote_record.entity
            local_entity = Entity.get_or_none(
                (Entity.name == remote_entity.name)
                & (Entity.entity_type == remote_entity.entity_type)
            )
            if local_entity:
                data["entity"] = local_entity.id
            else:
                return

            if remote_record.current_room_id:
                remote_room = remote_record.current_room
                local_room = Room.get_or_none(
                    Room.room_number == remote_room.room_number
                )
                data["current_room"] = local_room.id if local_room else None

        elif local_model == Observation:
            remote_entity = remote_record.entity
            local_entity = Entity.get_or_none(
                (Entity.name == remote_entity.name)
                & (Entity.entity_type == remote_entity.entity_type)
            )
            if local_entity:
                data["entity"] = local_entity.id
            else:
                return

        elif local_model == Relation:
            remote_from = remote_record.from_entity
            remote_to = remote_record.to_entity
            local_from = Entity.get_or_none(
                (Entity.name == remote_from.name)
                & (Entity.entity_type == remote_from.entity_type)
            )
            local_to = Entity.get_or_none(
                (Entity.name == remote_to.name)
                & (Entity.entity_type == remote_to.entity_type)
            )
            if local_from and local_to:
                data["from_entity"] = local_from.id
                data["to_entity"] = local_to.id
            else:
                return

        with local_db.atomic():
            # Use update().execute() after create to avoid save() setting dirty
            new_record = local_model.create(**data)
            local_model.update(sync_status="synced").where(
                local_model.id == new_record.id
            ).execute()

    def _overwrite_local_from_remote(
        self, local_record, remote_record, local_model, remote_model
    ) -> None:
        """Overwrite a clean local record with remote data."""
        update_data = {}
        for field in remote_model._meta.sorted_fields:
            if field.name in ("id", "sync_status", "remote_updated_at"):
                continue
            if hasattr(field, "rel_model"):
                continue  # Skip FK resolution — handled by natural keys
            update_data[field.name] = getattr(remote_record, field.name)

        update_data["sync_status"] = "synced"
        update_data["remote_updated_at"] = remote_record.updated_at
        update_data["updated_at"] = remote_record.updated_at

        # Bypass save() override
        local_model.update(**update_data).where(
            local_model.id == local_record.id
        ).execute()

    def _merge_local_with_remote(
        self, local_record, remote_record, local_model, remote_model
    ) -> None:
        """Merge a dirty local record with remote data (union strategy)."""
        if local_model == Room:
            # Scalar fields: latest updated_at wins
            if remote_record.updated_at and (
                not local_record.updated_at
                or remote_record.updated_at > local_record.updated_at
            ):
                for field_name in (
                    "terrain", "zone", "full_name",
                    "coord_x", "coord_y", "coord_z", "details",
                ):
                    remote_val = getattr(remote_record, field_name)
                    if remote_val is not None:
                        setattr(local_record, field_name, remote_val)

        elif local_model == RoomExit:
            import json
            local_details = json.loads(local_record.details) if local_record.details else {}
            remote_details = json.loads(remote_record.details) if remote_record.details else {}

            local_ts = local_details.get("last_success_at", "")
            remote_ts = remote_details.get("last_success_at", "")
            if remote_ts > local_ts:
                local_record.details = remote_record.details

        # Keep as dirty so next push cycle sends merged data
        local_record.save()

    def push_deletes(self) -> None:
        """Push local delete records to remote, then delete remote records."""
        unsynced = list(SyncDelete.select().where(SyncDelete.synced == False))
        if not unsynced:
            return

        self.logger.debug(f"Pushing {len(unsynced)} delete records to remote")

        for record in unsynced:
            try:
                natural_key = json.loads(record.natural_key)
                table_name = record.table_name_field
                remote_model = TABLE_NAME_TO_REMOTE.get(table_name)
                if not remote_model:
                    self.logger.warning(f"Unknown table for delete sync: {table_name}")
                    continue

                # Find and delete the remote record
                remote_record = self._find_remote_by_natural_key_dict(
                    table_name, natural_key, remote_model
                )
                if remote_record:
                    with self._remote_db.atomic():
                        remote_record.delete_instance()
                    self.logger.debug(
                        f"Deleted remote {table_name} with key {natural_key}"
                    )

                # Mark as synced
                SyncDelete.update(synced=True).where(
                    SyncDelete.id == record.id
                ).execute()

            except Exception as e:
                self.logger.error(
                    f"Failed to push delete {record.table_name_field}: {e}"
                )

    def pull_deletes(self) -> None:
        """Pull delete records from remote and apply locally."""
        query = RemoteSyncDelete.select().where(RemoteSyncDelete.synced == False)
        remote_deletes = list(query)
        if not remote_deletes:
            return

        self.logger.debug(f"Pulling {len(remote_deletes)} delete records from remote")

        for record in remote_deletes:
            try:
                natural_key = json.loads(record.natural_key)
                table_name = record.table_name_field
                local_model = TABLE_NAME_TO_LOCAL.get(table_name)
                if not local_model:
                    self.logger.warning(f"Unknown table for delete sync: {table_name}")
                    continue

                # Find and delete the local record
                local_record = self._find_local_by_natural_key_dict(
                    table_name, natural_key, local_model
                )
                if local_record:
                    # Use Model.delete_by_id to avoid re-logging the delete
                    local_model.delete_by_id(local_record.id)
                    self.logger.debug(
                        f"Deleted local {table_name} with key {natural_key}"
                    )

                # Mark remote delete as synced
                with self._remote_db.atomic():
                    RemoteSyncDelete.update(synced=True).where(
                        RemoteSyncDelete.id == record.id
                    ).execute()

            except Exception as e:
                self.logger.error(
                    f"Failed to pull delete {record.table_name_field}: {e}"
                )

    def _find_remote_by_natural_key_dict(
        self, table_name: str, natural_key: dict, remote_model
    ):
        """Find a remote record by its natural key dictionary."""
        try:
            if table_name == "entity":
                return remote_model.get_or_none(
                    (remote_model.name == natural_key["name"])
                    & (remote_model.entity_type == natural_key["entity_type"])
                )
            elif table_name == "room":
                return remote_model.get_or_none(
                    remote_model.room_number == natural_key["room_number"]
                )
            elif table_name == "roomexit":
                remote_from = RemoteRoom.get_or_none(
                    RemoteRoom.room_number == natural_key["from_room_number"]
                )
                if remote_from:
                    return remote_model.get_or_none(
                        (remote_model.from_room == remote_from)
                        & (remote_model.direction == natural_key["direction"])
                    )
                return None
            elif table_name == "npc":
                remote_entity = RemoteEntity.get_or_none(
                    (RemoteEntity.name == natural_key["entity_name"])
                    & (RemoteEntity.entity_type == natural_key["entity_type"])
                )
                if remote_entity:
                    return remote_model.get_or_none(
                        remote_model.entity == remote_entity
                    )
                return None
            elif table_name == "observation":
                remote_entity = RemoteEntity.get_or_none(
                    (RemoteEntity.name == natural_key["entity_name"])
                    & (RemoteEntity.entity_type == natural_key["entity_type"])
                )
                if remote_entity:
                    return remote_model.get_or_none(
                        (remote_model.entity == remote_entity)
                        & (remote_model.observation_type == natural_key["observation_type"])
                    )
                return None
            elif table_name == "relation":
                remote_from = RemoteEntity.get_or_none(
                    (RemoteEntity.name == natural_key["from_entity_name"])
                    & (RemoteEntity.entity_type == natural_key["from_entity_type"])
                )
                remote_to = RemoteEntity.get_or_none(
                    (RemoteEntity.name == natural_key["to_entity_name"])
                    & (RemoteEntity.entity_type == natural_key["to_entity_type"])
                )
                if remote_from and remote_to:
                    return remote_model.get_or_none(
                        (remote_model.from_entity == remote_from)
                        & (remote_model.to_entity == remote_to)
                        & (remote_model.relation_type == natural_key["relation_type"])
                    )
                return None
        except Exception:
            return None

    def _find_local_by_natural_key_dict(
        self, table_name: str, natural_key: dict, local_model
    ):
        """Find a local record by its natural key dictionary."""
        try:
            if table_name == "entity":
                return local_model.get_or_none(
                    (local_model.name == natural_key["name"])
                    & (local_model.entity_type == natural_key["entity_type"])
                )
            elif table_name == "room":
                return local_model.get_or_none(
                    local_model.room_number == natural_key["room_number"]
                )
            elif table_name == "roomexit":
                local_from = Room.get_or_none(
                    Room.room_number == natural_key["from_room_number"]
                )
                if local_from:
                    return local_model.get_or_none(
                        (local_model.from_room == local_from)
                        & (local_model.direction == natural_key["direction"])
                    )
                return None
            elif table_name == "npc":
                local_entity = Entity.get_or_none(
                    (Entity.name == natural_key["entity_name"])
                    & (Entity.entity_type == natural_key["entity_type"])
                )
                if local_entity:
                    return local_model.get_or_none(
                        local_model.entity == local_entity
                    )
                return None
            elif table_name == "observation":
                local_entity = Entity.get_or_none(
                    (Entity.name == natural_key["entity_name"])
                    & (Entity.entity_type == natural_key["entity_type"])
                )
                if local_entity:
                    return local_model.get_or_none(
                        (local_model.entity == local_entity)
                        & (local_model.observation_type == natural_key["observation_type"])
                    )
                return None
            elif table_name == "relation":
                local_from = Entity.get_or_none(
                    (Entity.name == natural_key["from_entity_name"])
                    & (Entity.entity_type == natural_key["from_entity_type"])
                )
                local_to = Entity.get_or_none(
                    (Entity.name == natural_key["to_entity_name"])
                    & (Entity.entity_type == natural_key["to_entity_type"])
                )
                if local_from and local_to:
                    return local_model.get_or_none(
                        (local_model.from_entity == local_from)
                        & (local_model.to_entity == local_to)
                        & (local_model.relation_type == natural_key["relation_type"])
                    )
                return None
        except Exception:
            return None
