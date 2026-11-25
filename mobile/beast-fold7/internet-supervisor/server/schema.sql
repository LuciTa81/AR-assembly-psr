CREATE TABLE IF NOT EXISTS devices (
  id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, name TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE, expires_ms BIGINT NOT NULL,
  revoked BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS tickets (
  token_hash TEXT PRIMARY KEY, device_id TEXT NOT NULL REFERENCES devices(id),
  owner_id TEXT NOT NULL, expires_ms BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  device_id TEXT NOT NULL REFERENCES devices(id), stream_id TEXT NOT NULL,
  seq BIGINT NOT NULL, kind TEXT NOT NULL, received_ms BIGINT NOT NULL,
  state JSONB NOT NULL,
  UNIQUE(device_id, stream_id, seq, kind)
);
CREATE INDEX IF NOT EXISTS events_device_time ON events(device_id, id DESC);
CREATE TABLE IF NOT EXISTS viewer_sessions (
  id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, revoked BOOLEAN NOT NULL DEFAULT FALSE
);
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS viewer_session TEXT;
CREATE TABLE IF NOT EXISTS pairing_requests (
  id TEXT PRIMARY KEY, slot SMALLINT NOT NULL UNIQUE CHECK(slot >= 0 AND slot < 128),
  code_hash TEXT NOT NULL UNIQUE, poll_hash TEXT NOT NULL UNIQUE,
  device_name TEXT NOT NULL, expires_ms BIGINT NOT NULL, approved_device_id TEXT
);
CREATE TABLE IF NOT EXISTS recording_accounts (
  owner_id TEXT PRIMARY KEY, used_bytes BIGINT NOT NULL DEFAULT 0 CHECK(used_bytes>=0)
);
CREATE TABLE IF NOT EXISTS recordings (
  id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES recording_accounts(owner_id),
  device_id TEXT NOT NULL REFERENCES devices(id), session TEXT NOT NULL,
  object_key TEXT NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT 'capturing'
    CHECK(status IN ('capturing','ready','deleting','deleted')),
  created_ms BIGINT NOT NULL, completed_ms BIGINT, expires_ms BIGINT NOT NULL,
  bytes BIGINT NOT NULL CHECK(bytes>0), duration_ms BIGINT NOT NULL DEFAULT 0,
  reason TEXT NOT NULL DEFAULT 'capturing'
);
CREATE INDEX IF NOT EXISTS recordings_owner_time ON recordings(owner_id,device_id,created_ms DESC);
CREATE INDEX IF NOT EXISTS recordings_expiry ON recordings(status,expires_ms);
ALTER TABLE recordings ADD COLUMN IF NOT EXISTS segment INTEGER NOT NULL DEFAULT 1 CHECK(segment>0);
ALTER TABLE recordings ADD COLUMN IF NOT EXISTS gap_before_ms BIGINT NOT NULL DEFAULT 0 CHECK(gap_before_ms>=0);
ALTER TABLE recordings ADD COLUMN IF NOT EXISTS resume_blocked BOOLEAN NOT NULL DEFAULT FALSE;
CREATE UNIQUE INDEX IF NOT EXISTS recordings_device_session_segment ON recordings(device_id,session,segment);
DROP INDEX IF EXISTS recordings_device_session;
