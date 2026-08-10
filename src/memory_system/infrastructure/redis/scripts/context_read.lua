-- Read-only atomic Working Memory context snapshot (§1.2.1 rule 7; STM-004).
-- KEYS[1] meta Hash, KEYS[2] messages List
-- ARGV[1] expected_user_id, ARGV[2] expected_session_id
-- Strictly read-only: no HSET/SET/RPUSH/LPUSH/SADD/DEL/EXPIRE/INCR/LTRIM.

local meta_key = KEYS[1]
local messages_key = KEYS[2]

if redis.call('EXISTS', meta_key) == 0 then
  return 'session_not_found'
end

local stored_user_id = redis.call('HGET', meta_key, 'user_id')
local stored_session_id = redis.call('HGET', meta_key, 'session_id')
if stored_user_id ~= ARGV[1] or stored_session_id ~= ARGV[2] then
  return 'session_not_found'
end

local compression_version_raw = redis.call('HGET', meta_key, 'compression_version')
if compression_version_raw == nil or compression_version_raw == false then
  return 'invalid_session_state'
end
local compression_version = tonumber(compression_version_raw)
if compression_version == nil then
  return 'invalid_session_state'
end

local compressed_context_raw = redis.call('HGET', meta_key, 'compressed_context')
if compressed_context_raw == false then
  return 'invalid_session_state'
end
local compressed_context = compressed_context_raw

local messages = redis.call('LRANGE', messages_key, 0, -1)

local result = { 'success', tostring(compression_version), compressed_context }
for i = 1, #messages do
  result[#result + 1] = messages[i]
end
return result
