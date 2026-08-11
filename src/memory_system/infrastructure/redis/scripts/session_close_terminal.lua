-- Atomic terminal delete of Working Memory keys (STM-010 §5.0 #16).
-- KEYS[1] meta Hash, KEYS[2] messages List, KEYS[3] message_ids Set
-- ARGV[1] expected_user_id, ARGV[2] expected_session_id

local meta_key = KEYS[1]
local messages_key = KEYS[2]
local message_ids_key = KEYS[3]

if redis.call('EXISTS', meta_key) == 0 then
  return 'session_not_found'
end

local stored_user_id = redis.call('HGET', meta_key, 'user_id')
local stored_session_id = redis.call('HGET', meta_key, 'session_id')
if stored_user_id ~= ARGV[1] or stored_session_id ~= ARGV[2] then
  return 'session_not_found'
end

local status = redis.call('HGET', meta_key, 'status')
if status ~= 'closing' then
  return 'invalid_session_state'
end

redis.call('DEL', meta_key, messages_key, message_ids_key)
return 'success'
