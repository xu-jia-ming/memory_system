-- Atomic compression finalize: validate → mutate → release lock (STM-008 / §1.2.5).
-- KEYS[1] meta Hash, KEYS[2] messages List, KEYS[3] compression lock key
-- ARGV[1] expected_user_id
-- ARGV[2] expected_session_id
-- ARGV[3] expected_compression_version
-- ARGV[4] pending_archive_id
-- ARGV[5] pending_archive_batch_key
-- ARGV[6] pending_archive_message_count
-- ARGV[7] pending_archive_estimated_tokens
-- ARGV[8] lock_owner_token
-- ARGV[9] expected_first_message_id
-- ARGV[10] expected_last_message_id
-- ARGV[11] archived_message_tokens (must == ARGV[7])
-- ARGV[12] old_compressed_context_tokens
-- ARGV[13] new_compressed_context_tokens
-- ARGV[14] compressed_context
-- ARGV[15] updated_time
--
-- Precondition order (fixed 12 steps; see Task Plan §5.0 C8):
-- 1 meta EXISTS → session_not_found
-- 2 user_id/session_id → session_not_found
-- 3 status rules → session_closing / invalid_session_state
-- 4 lock ownership → lock_not_acquired
-- 5 compression_version → invalid_session_state / version_conflict
-- 6 pending four fields → invalid_session_state / pending_conflict
-- 7 ARGV[11] == ARGV[7] → pending_conflict
-- 8 token ARGV integers → invalid_session_state
-- 9 estimated_tokens Redis → invalid_session_state
-- 10 LLEN >= pending_count → message_boundary_mismatch
-- 11 message boundary JSON → message_boundary_mismatch
-- 12 (implicit) enter mutation
--
-- Success returns: { 'success', new_compression_version, new_estimated_tokens }

local meta_key = KEYS[1]
local messages_key = KEYS[2]
local lock_key = KEYS[3]

local function parse_nonneg_int_literal(raw)
  if raw == false or raw == nil then
    return nil
  end
  if not string.match(raw, '^-?%d+$') then
    return nil
  end
  local n = tonumber(raw)
  if n == nil or n < 0 then
    return nil
  end
  return n
end

local function parse_positive_int_literal(raw)
  local n = parse_nonneg_int_literal(raw)
  if n == nil or n <= 0 then
    return nil
  end
  return n
end

local function extract_message_id(json_str)
  if json_str == false or json_str == nil then
    return nil
  end
  local ok, decoded = pcall(cjson.decode, json_str)
  if not ok or type(decoded) ~= 'table' then
    return nil
  end
  local msg_id = decoded['message_id']
  if msg_id == nil or type(msg_id) ~= 'string' or msg_id == '' then
    return nil
  end
  return msg_id
end

-- 1. meta EXISTS
if redis.call('EXISTS', meta_key) == 0 then
  return 'session_not_found'
end

-- 2. identity
local stored_user_id = redis.call('HGET', meta_key, 'user_id')
local stored_session_id = redis.call('HGET', meta_key, 'session_id')
if stored_user_id ~= ARGV[1] or stored_session_id ~= ARGV[2] then
  return 'session_not_found'
end

-- 3. status rules (active OK; closing + non-empty pending OK; closing + empty → session_closing)
local status = redis.call('HGET', meta_key, 'status')
if status == false or status == nil then
  return 'invalid_session_state'
end
if status == 'closing' then
  local closing_pending_id = redis.call('HGET', meta_key, 'pending_archive_id')
  if closing_pending_id == false or closing_pending_id == nil or closing_pending_id == '' then
    return 'session_closing'
  end
elseif status ~= 'active' then
  return 'invalid_session_state'
end

-- 4. lock ownership
local lock_value = redis.call('GET', lock_key)
if lock_value == false or lock_value == nil or lock_value ~= ARGV[8] then
  return 'lock_not_acquired'
end

-- 5. compression_version
local version_raw = redis.call('HGET', meta_key, 'compression_version')
local current_version = parse_nonneg_int_literal(version_raw)
if current_version == nil then
  return 'invalid_session_state'
end
local expected_version = parse_nonneg_int_literal(ARGV[3])
if expected_version == nil then
  return 'invalid_session_state'
end
if current_version ~= expected_version then
  return 'version_conflict'
end

-- 6. pending four fields
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
  return 'invalid_session_state'
end

if pending_id ~= ARGV[4]
    or pending_batch ~= ARGV[5]
    or tostring(pending_count) ~= ARGV[6]
    or tostring(pending_tokens) ~= ARGV[7] then
  return 'pending_conflict'
end

-- 7. defense-in-depth: archived_message_tokens == pending_archive_estimated_tokens
if ARGV[11] ~= ARGV[7] then
  return 'pending_conflict'
end

-- 8. token ARGV integers
local archived_tokens = parse_nonneg_int_literal(ARGV[11])
local old_compressed_tokens = parse_nonneg_int_literal(ARGV[12])
local new_compressed_tokens = parse_nonneg_int_literal(ARGV[13])
if archived_tokens == nil or old_compressed_tokens == nil or new_compressed_tokens == nil then
  return 'invalid_session_state'
end

-- 9. estimated_tokens from Redis
local current_estimated_raw = redis.call('HGET', meta_key, 'estimated_tokens')
local current_estimated = parse_nonneg_int_literal(current_estimated_raw)
if current_estimated == nil then
  return 'invalid_session_state'
end

-- 10. list length
local list_len = redis.call('LLEN', messages_key)
if list_len < pending_count then
  return 'message_boundary_mismatch'
end

-- 11. message boundary
local first_json = redis.call('LRANGE', messages_key, 0, 0)[1]
local last_json = redis.call('LRANGE', messages_key, pending_count - 1, pending_count - 1)[1]

local first_id = extract_message_id(first_json)
local last_id = extract_message_id(last_json)
if first_id == nil or last_id == nil then
  return 'message_boundary_mismatch'
end
if first_id ~= ARGV[9] or last_id ~= ARGV[10] then
  return 'message_boundary_mismatch'
end

-- Mutations (strict order)
local raw_new = current_estimated - archived_tokens - old_compressed_tokens + new_compressed_tokens
local new_estimated = raw_new
if new_estimated < 0 then
  new_estimated = 0
end

local new_version = expected_version + 1

redis.call('HSET', meta_key, 'compressed_context', ARGV[14])
redis.call('HSET', meta_key, 'compression_version', tostring(new_version))
redis.call('LTRIM', messages_key, pending_count, -1)
redis.call('HSET', meta_key, 'estimated_tokens', tostring(new_estimated))
redis.call(
  'HSET',
  meta_key,
  'pending_archive_id', '',
  'pending_archive_batch_key', '',
  'pending_archive_message_count', '0',
  'pending_archive_estimated_tokens', '0'
)
redis.call('HSET', meta_key, 'updated_time', ARGV[15])

-- compare-and-delete lock
if redis.call('GET', lock_key) == ARGV[8] then
  redis.call('DEL', lock_key)
end

return { 'success', tostring(new_version), tostring(new_estimated) }
