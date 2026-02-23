"""SyncWorker: Background bidirectional sync between local SQLite and remote Supabase.

Push: Finds all local records modified since last push (by updated_at), upserts them to remote.
      No local writes during push — avoids SQLite write lock contention.
Pull: Finds all remote records newer than last_pull_timestamp, merges locally.
"""

import asyncio
import json
import logging
import time
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
        self._last_push_at: Optional[datetime] = None
        self._stopping = False
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
        self._stopping = True
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
        """Main sync loop.

        First cycle: pull first (deletes then updates) so we don't push
        stale data over newer remote state.
        Subsequent cycles: push first so local changes propagate quickly,
        then pull.
        """
        first_cycle = True
        try:
            while True:
                try:
                    if first_cycle:
                        self.logger.info("First sync cycle — pulling remote state first")
                        await asyncio.to_thread(self._pull_with_connection)
                        await asyncio.to_thread(self._push_with_connection)
                        first_cycle = False
                    else:
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
        """Push with a dedicated local DB connection for thread safety.

        Only reads from local DB (to find modified records and resolve FKs),
        then writes to remote. No local writes happen during push.
        """
        with local_db.connection_context():
            self._push_to_remote()
            self._push_deletes_to_remote()

    def _pull_with_connection(self) -> None:
        """Pull with short per-record local DB connections for thread safety.

        Each local write (delete or upsert) uses its own connection_context()
        so the write lock is held only briefly, letting the main thread
        interleave its own writes.
        """
        # Pull deletes — each local delete in its own connection
        query = RemoteSyncDelete.select().where(RemoteSyncDelete.synced == False)
        remote_deletes = list(query)
        if remote_deletes:
            self.logger.debug(f"Pulling {len(remote_deletes)} delete records from remote")

        for record in remote_deletes:
            if self._stopping:
                return
            try:
                natural_key = json.loads(record.natural_key)
                table_name = record.table_name_field
                local_model = TABLE_NAME_TO_LOCAL.get(table_name)
                if not local_model:
                    self.logger.warning(f"Unknown table for delete sync: {table_name}")
                    continue

                with local_db.connection_context():
                    local_record = self._find_local_by_natural_key_dict(
                        table_name, natural_key, local_model
                    )
                    if local_record:
                        local_model.delete_by_id(local_record.id)
                        self.logger.debug(
                            f"Deleted local {table_name} with key {natural_key}"
                        )

                # Mark remote delete as synced (remote DB, no local lock)
                with self._remote_db.atomic():
                    RemoteSyncDelete.update(synced=True).where(
                        RemoteSyncDelete.id == record.id
                    ).execute()

            except Exception as e:
                self.logger.error(
                    f"Failed to pull delete {record.table_name_field}: {e}"
                )
            time.sleep(0.01)

        # Pull updates — each local upsert in its own connection
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
                if self._stopping:
                    return
                try:
                    with local_db.connection_context():
                        self._pull_record(remote_record, local_model, remote_model)
                except Exception as e:
                    self.logger.error(
                        f"Failed to pull {remote_model.__name__} id={remote_record.id}: {e}"
                    )
                time.sleep(0.01)

        self._last_pull_at = datetime.now(timezone.utc)

    # Maximum number of IDs to mark as synced in a single UPDATE statement
    PUSH_BATCH_SIZE = 50

    def push(self) -> None:
        """Push all locally-modified records to remote.

        No local writes — uses updated_at timestamps to detect changes.
        """
        self._push_to_remote()

    def push_deletes(self) -> None:
        """Push local delete records to remote and mark them synced."""
        synced_ids = self._push_deletes_to_remote()
        for i in range(0, len(synced_ids), self.PUSH_BATCH_SIZE):
            batch = synced_ids[i : i + self.PUSH_BATCH_SIZE]
            SyncDelete.update(synced=True).where(
                SyncDelete.id.in_(batch)
            ).execute()

    def _push_to_remote(self) -> None:
        """Read locally-modified records and push to remote.

        Uses updated_at > _last_push_at to detect changes instead of
        sync_status, so no local writes are needed during push.
        """
        for local_model in PUSH_ORDER:
            remote_model = LOCAL_TO_REMOTE[local_model]
            if self._last_push_at:
                dirty_records = list(local_model.select().where(
                    local_model.updated_at > self._last_push_at
                ))
            else:
                # First push — push everything
                dirty_records = list(local_model.select())

            if not dirty_records:
                continue

            self.logger.debug(
                f"Pushing {len(dirty_records)} modified {local_model.__name__} records"
            )

            for record in dirty_records:
                if self._stopping:
                    return
                try:
                    self._push_record(record, local_model, remote_model)
                except Exception as e:
                    self.logger.error(
                        f"Failed to push {local_model.__name__} id={record.id}: {e}"
                    )

        self._last_push_at = datetime.now()

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

    def _resolve_fk_for_push(self, record, local_model, data: dict) -> dict:
        """Resolve local FK IDs to remote FK IDs for push.

        Raises DoesNotExist if a required FK target is missing locally
        (the caller treats this as a push failure for this record).
        """
        if local_model == Room:
            local_entity = record.entity  # raises DoesNotExist if orphaned
            remote_entity = RemoteEntity.get_or_none(
                (RemoteEntity.name == local_entity.name)
                & (RemoteEntity.entity_type == local_entity.entity_type)
            )
            if remote_entity:
                data["entity"] = remote_entity.id

        elif local_model == RoomExit:
            # from_room FK — required; skip record if local Room is gone
            try:
                from_room = record.from_room
            except DoesNotExist:
                self.logger.warning(
                    f"Skipping RoomExit id={record.id}: from_room_id={record.from_room_id} missing locally"
                )
                raise
            remote_from = RemoteRoom.get_or_none(
                RemoteRoom.room_number == from_room.room_number
            )
            if remote_from:
                data["from_room"] = remote_from.id

            # to_room FK (nullable)
            if record.to_room_id:
                try:
                    to_room = record.to_room
                    remote_to = RemoteRoom.get_or_none(
                        RemoteRoom.room_number == to_room.room_number
                    )
                    data["to_room"] = remote_to.id if remote_to else None
                except DoesNotExist:
                    data["to_room"] = None

        elif local_model == NPC:
            local_entity = record.entity
            remote_entity = RemoteEntity.get_or_none(
                (RemoteEntity.name == local_entity.name)
                & (RemoteEntity.entity_type == local_entity.entity_type)
            )
            if remote_entity:
                data["entity"] = remote_entity.id
            if record.current_room_id:
                try:
                    local_room = record.current_room
                    remote_room = RemoteRoom.get_or_none(
                        RemoteRoom.room_number == local_room.room_number
                    )
                    data["current_room"] = remote_room.id if remote_room else None
                except DoesNotExist:
                    data["current_room"] = None

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
                    # Match by entity + current_room (compound unique)
                    if record.current_room_id:
                        local_room = record.current_room
                        remote_room = RemoteRoom.get_or_none(
                            RemoteRoom.room_number == local_room.room_number
                        )
                        return remote_model.get_or_none(
                            (remote_model.entity == remote_entity)
                            & (remote_model.current_room == remote_room)
                        )
                    else:
                        return remote_model.get_or_none(
                            (remote_model.entity == remote_entity)
                            & (remote_model.current_room.is_null())
                        )
                return None
            elif local_model == Observation:
                entity = record.entity
                remote_entity = RemoteEntity.get_or_none(
                    (RemoteEntity.name == entity.name)
                    & (RemoteEntity.entity_type == entity.entity_type)
                )
                if remote_entity:
                    return remote_model.get_or_none(
                        (remote_model.entity == remote_entity)
                        & (remote_model.observation_type == record.observation_type)
                    )
                return None
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
                if remote_from and remote_to:
                    return remote_model.get_or_none(
                        (remote_model.from_entity == remote_from)
                        & (remote_model.to_entity == remote_to)
                        & (remote_model.relation_type == record.relation_type)
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
                if self._stopping:
                    return
                try:
                    self._pull_record(remote_record, local_model, remote_model)
                except Exception as e:
                    self.logger.error(
                        f"Failed to pull {remote_model.__name__} id={remote_record.id}: {e}"
                    )
                # Yield the SQLite write lock briefly so the main thread can write
                time.sleep(0.01)

        self._last_pull_at = datetime.now(timezone.utc)

    def _pull_record(self, remote_record, local_model, remote_model) -> None:
        """Pull a single remote record and merge it locally."""
        local_record = self._find_local_by_natural_key(
            remote_record, local_model, remote_model
        )

        if local_record is None:
            self._insert_local_from_remote(remote_record, local_model, remote_model)
            return

        # If local hasn't been modified since last pull/insert, safe to overwrite.
        # If local was modified after that, merge instead.
        # Compare as naive datetimes to avoid tz-aware vs naive mismatch.
        # SQLite may return DateTimeField values as strings, so parse if needed.
        locally_modified = False
        if local_record.remote_updated_at is not None and local_record.updated_at is not None:
            local_ts = local_record.updated_at
            remote_ts = local_record.remote_updated_at
            if isinstance(local_ts, str):
                local_ts = datetime.fromisoformat(local_ts)
            if isinstance(remote_ts, str):
                remote_ts = datetime.fromisoformat(remote_ts)
            # Strip tzinfo for safe comparison
            local_ts = local_ts.replace(tzinfo=None)
            remote_ts = remote_ts.replace(tzinfo=None)
            locally_modified = local_ts > remote_ts

        if not locally_modified:
            self._overwrite_local_from_remote(
                local_record, remote_record, local_model, remote_model
            )
        else:
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
            local_model.create(**data)

    def _overwrite_local_from_remote(
        self, local_record, remote_record, local_model, remote_model
    ) -> None:
        """Overwrite a locally-unmodified record with remote data."""
        update_data = {}
        for field in remote_model._meta.sorted_fields:
            if field.name in ("id", "sync_status", "remote_updated_at"):
                continue
            if hasattr(field, "rel_model"):
                continue  # Skip FK resolution — handled by natural keys
            update_data[field.name] = getattr(remote_record, field.name)

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

    def _push_deletes_to_remote(self) -> list[int]:
        """Push local delete records to remote. Returns list of synced SyncDelete IDs.

        Does NOT write to local DB — caller handles marking as synced.
        """
        unsynced = list(SyncDelete.select().where(SyncDelete.synced == False))
        if not unsynced:
            return []

        self.logger.debug(f"Pushing {len(unsynced)} delete records to remote")

        synced_ids = []
        for record in unsynced:
            if self._stopping:
                break
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

                synced_ids.append(record.id)

            except Exception as e:
                self.logger.error(
                    f"Failed to push delete {record.table_name_field}: {e}"
                )

        return synced_ids

    def pull_deletes(self) -> None:
        """Pull delete records from remote and apply locally."""
        query = RemoteSyncDelete.select().where(RemoteSyncDelete.synced == False)
        remote_deletes = list(query)
        if not remote_deletes:
            return

        self.logger.debug(f"Pulling {len(remote_deletes)} delete records from remote")

        for record in remote_deletes:
            if self._stopping:
                return
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
