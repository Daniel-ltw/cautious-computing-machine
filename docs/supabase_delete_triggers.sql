-- Supabase Delete Triggers for Bidirectional Sync
-- Run this SQL in the Supabase SQL editor to enable delete tracking.
--
-- When you delete a record in Supabase (via the dashboard or any tool),
-- these triggers automatically log the deletion to the sync_deletes table.
-- The SyncWorker will then pull these delete records and apply them locally.

-- 1. Create the sync_deletes table (if not already created by SyncWorker)
CREATE TABLE IF NOT EXISTS sync_deletes (
    id SERIAL PRIMARY KEY,
    table_name_field VARCHAR(50) NOT NULL,
    natural_key TEXT NOT NULL,
    deleted_at TIMESTAMP NOT NULL DEFAULT NOW(),
    synced BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_sync_deletes_synced ON sync_deletes (synced);

-- 2. Trigger function for entity table
CREATE OR REPLACE FUNCTION log_entity_delete() RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO sync_deletes (table_name_field, natural_key)
    VALUES ('entity', json_build_object('name', OLD.name, 'entity_type', OLD.entity_type)::text);
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_entity_delete ON entity;
CREATE TRIGGER trg_entity_delete
    BEFORE DELETE ON entity
    FOR EACH ROW EXECUTE FUNCTION log_entity_delete();

-- 3. Trigger function for room table
CREATE OR REPLACE FUNCTION log_room_delete() RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO sync_deletes (table_name_field, natural_key)
    VALUES ('room', json_build_object('room_number', OLD.room_number)::text);
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_room_delete ON room;
CREATE TRIGGER trg_room_delete
    BEFORE DELETE ON room
    FOR EACH ROW EXECUTE FUNCTION log_room_delete();

-- 4. Trigger function for roomexit table
CREATE OR REPLACE FUNCTION log_roomexit_delete() RETURNS TRIGGER AS $$
DECLARE
    from_room_num INTEGER;
BEGIN
    SELECT room_number INTO from_room_num FROM room WHERE id = OLD.from_room_id;
    INSERT INTO sync_deletes (table_name_field, natural_key)
    VALUES ('roomexit', json_build_object('from_room_number', from_room_num, 'direction', OLD.direction)::text);
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_roomexit_delete ON roomexit;
CREATE TRIGGER trg_roomexit_delete
    BEFORE DELETE ON roomexit
    FOR EACH ROW EXECUTE FUNCTION log_roomexit_delete();

-- 5. Trigger function for npc table
CREATE OR REPLACE FUNCTION log_npc_delete() RETURNS TRIGGER AS $$
DECLARE
    ent_name VARCHAR;
    ent_type VARCHAR;
BEGIN
    SELECT name, entity_type INTO ent_name, ent_type FROM entity WHERE id = OLD.entity_id;
    INSERT INTO sync_deletes (table_name_field, natural_key)
    VALUES ('npc', json_build_object('entity_name', ent_name, 'entity_type', ent_type)::text);
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_npc_delete ON npc;
CREATE TRIGGER trg_npc_delete
    BEFORE DELETE ON npc
    FOR EACH ROW EXECUTE FUNCTION log_npc_delete();

-- 6. Trigger function for observation table
CREATE OR REPLACE FUNCTION log_observation_delete() RETURNS TRIGGER AS $$
DECLARE
    ent_name VARCHAR;
    ent_type VARCHAR;
BEGIN
    SELECT name, entity_type INTO ent_name, ent_type FROM entity WHERE id = OLD.entity_id;
    INSERT INTO sync_deletes (table_name_field, natural_key)
    VALUES ('observation', json_build_object(
        'entity_name', ent_name,
        'entity_type', ent_type,
        'observation_type', OLD.observation_type
    )::text);
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_observation_delete ON observation;
CREATE TRIGGER trg_observation_delete
    BEFORE DELETE ON observation
    FOR EACH ROW EXECUTE FUNCTION log_observation_delete();

-- 7. Trigger function for relation table
CREATE OR REPLACE FUNCTION log_relation_delete() RETURNS TRIGGER AS $$
DECLARE
    from_name VARCHAR;
    from_type VARCHAR;
    to_name VARCHAR;
    to_type VARCHAR;
BEGIN
    SELECT name, entity_type INTO from_name, from_type FROM entity WHERE id = OLD.from_entity_id;
    SELECT name, entity_type INTO to_name, to_type FROM entity WHERE id = OLD.to_entity_id;
    INSERT INTO sync_deletes (table_name_field, natural_key)
    VALUES ('relation', json_build_object(
        'from_entity_name', from_name,
        'from_entity_type', from_type,
        'to_entity_name', to_name,
        'to_entity_type', to_type,
        'relation_type', OLD.relation_type
    )::text);
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_relation_delete ON relation;
CREATE TRIGGER trg_relation_delete
    BEFORE DELETE ON relation
    FOR EACH ROW EXECUTE FUNCTION log_relation_delete();
