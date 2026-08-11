-- Revert closing→active on early close failure (STM-010 §5.0 #13).
-- KEYS[1] meta Hash
-- ARGV[1] expected_user_id, ARGV[2] expected_session_id, ARGV[3] updated_time

local meta_key = KEYS[1]

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

redis.call('HSET', meta_key, 'status', 'active', 'updated_time', ARGV[3])
return 'success'
