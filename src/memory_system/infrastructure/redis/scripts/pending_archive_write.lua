-- Atomic pending_archive_* write with lock ownership verification (STM-006 / Amendment 001).
-- KEYS[1] meta Hash, KEYS[2] compression lock key
-- ARGV[1] expected_user_id
-- ARGV[2] expected_session_id
-- ARGV[3] archive_id
-- ARGV[4] archive_batch_key
-- ARGV[5] message_count
-- ARGV[6] estimated_tokens
-- ARGV[7] expected_lock_owner_token
--
-- Precondition order (fixed):
-- 1 meta EXISTS → session_not_found
-- 2 user_id/session_id match → session_not_found
-- 3 status == active → session_closing
-- 4 GET lock == expected_lock_owner_token → lock_not_acquired
-- 5 pending four-field state (malformed → invalid_session_state)
-- 6 archive identity + accounting consistency (conflict → pending_conflict)
-- 7 mutation when empty → success
--
-- Human SF: same archive_id+batch_key but different count/tokens → pending_conflict
-- (fail-closed; do not overwrite). Same identity + same accounting → idempotent success.

local meta_key = KEYS[1]
local lock_key = KEYS[2]

if redis.call('EXISTS', meta_key) == 0 then
  return 'session_not_found'
end

local stored_user_id = redis.call('HGET', meta_key, 'user_id')
local stored_session_id = redis.call('HGET', meta_key, 'session_id')
if stored_user_id ~= ARGV[1] or stored_session_id ~= ARGV[2] then
  return 'session_not_found'
end

local status = redis.call('HGET', meta_key, 'status')
if status ~= 'active' then
  return 'session_closing'
end

local lock_value = redis.call('GET', lock_key)
if lock_value == false or lock_value == nil or lock_value ~= ARGV[7] then
  return 'lock_not_acquired'
end

local pending_id = redis.call('HGET', meta_key, 'pending_archive_id')
local pending_batch = redis.call('HGET', meta_key, 'pending_archive_batch_key')
local pending_count_raw = redis.call('HGET', meta_key, 'pending_archive_message_count')
local pending_tokens_raw = redis.call('HGET', meta_key, 'pending_archive_estimated_tokens')

if pending_id == false or pending_id == nil then
  pending_id = ''
end
if pending_batch == false or pending_batch == nil then
  pending_batch = ''
end
if pending_count_raw == false or pending_count_raw == nil then
  return 'invalid_session_state'
end
if pending_tokens_raw == false or pending_tokens_raw == nil then
  return 'invalid_session_state'
end

-- Exact integer literals only (reject "", "1.5", "abc")
if not string.match(pending_count_raw, '^-?%d+$') then
  return 'invalid_session_state'
end
if not string.match(pending_tokens_raw, '^-?%d+$') then
  return 'invalid_session_state'
end

local pending_count = tonumber(pending_count_raw)
local pending_tokens = tonumber(pending_tokens_raw)
if pending_count == nil or pending_tokens == nil then
  return 'invalid_session_state'
end

-- Half-filled / inconsistent empty encoding (codec: id/batch "" = null; count/tokens 0 = empty)
local id_empty = (pending_id == '')
local batch_empty = (pending_batch == '')
local count_empty = (pending_count == 0)
local tokens_empty = (pending_tokens == 0)

if id_empty ~= batch_empty then
  return 'invalid_session_state'
end
if id_empty and (not count_empty or not tokens_empty) then
  return 'invalid_session_state'
end
if (not id_empty) and count_empty then
  -- non-empty pending must have message_count > 0
  return 'invalid_session_state'
end

if not id_empty then
  -- Occupied pending: identity must match; accounting must match (fail-closed)
  if pending_id ~= ARGV[3] or pending_batch ~= ARGV[4] then
    return 'pending_conflict'
  end
  local req_count = tonumber(ARGV[5])
  local req_tokens = tonumber(ARGV[6])
  if req_count == nil or req_tokens == nil then
    return 'invalid_session_state'
  end
  if pending_count ~= req_count or pending_tokens ~= req_tokens then
    return 'pending_conflict'
  end
  return 'success'
end

-- Empty pending: write all four fields
redis.call(
  'HSET',
  meta_key,
  'pending_archive_id', ARGV[3],
  'pending_archive_batch_key', ARGV[4],
  'pending_archive_message_count', ARGV[5],
  'pending_archive_estimated_tokens', ARGV[6]
)
return 'success'
