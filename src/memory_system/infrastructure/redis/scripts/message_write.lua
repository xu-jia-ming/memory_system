-- Atomic Working Memory message write (§1.2.1 rule 3; STM-003).
-- KEYS[1] meta Hash, KEYS[2] messages List, KEYS[3] message_ids Set
-- ARGV[1] message_json, ARGV[2] message_estimated_tokens, ARGV[3] max_wm_tokens
-- ARGV[4] updated_time, ARGV[5] expected_user_id, ARGV[6] expected_session_id
-- ARGV[7] message_id (SISMEMBER/SADD; must match JSON message_id from Python)

local meta_key = KEYS[1]
local messages_key = KEYS[2]
local message_ids_key = KEYS[3]

if redis.call('EXISTS', meta_key) == 0 then
  return 'session_not_found'
end

local stored_user_id = redis.call('HGET', meta_key, 'user_id')
local stored_session_id = redis.call('HGET', meta_key, 'session_id')
if stored_user_id ~= ARGV[5] or stored_session_id ~= ARGV[6] then
  return 'session_not_found'
end

local status = redis.call('HGET', meta_key, 'status')
if status ~= 'active' then
  return 'session_closing'
end

if redis.call('SISMEMBER', message_ids_key, ARGV[7]) == 1 then
  return 'duplicate'
end

local current_raw = redis.call('HGET', meta_key, 'estimated_tokens')
if current_raw == nil or current_raw == false then
  return 'invalid_session_state'
end
local current = tonumber(current_raw)
if current == nil then
  return 'invalid_session_state'
end

local message_tokens = tonumber(ARGV[2])
local max_wm = tonumber(ARGV[3])
local new_total = current + message_tokens
if new_total > max_wm then
  return 'capacity_exceeded'
end

redis.call('RPUSH', messages_key, ARGV[1])
redis.call('SADD', message_ids_key, ARGV[7])
redis.call('HSET', meta_key, 'estimated_tokens', tostring(new_total), 'updated_time', ARGV[4])
return 'success'
