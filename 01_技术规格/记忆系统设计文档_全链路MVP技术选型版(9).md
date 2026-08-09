# 记忆系统

> 当前版本：Memory System 全链路 MVP 技术选型版（9）。该版本在技术选型版（8）基础上，统一巩固任务的唯一调度配置源、HTTP 错误响应与 `session_closing` 语义、Extraction 管理接口的用户隔离、CLI 运维工具与 Admin HTTP API 的边界、YAML 配置加载方式、工程规范中的强制性表述以及 MVP 验收标准。Embedding 仍默认使用 CPU，在 RTX A5000 空闲时通过 Docker Compose Override 切换至 Ampere 8.6 GPU 镜像；启动模式支持 `cpu`、`gpu` 和 `auto`，MVP 不实现运行时热切换。模型固定为 `BAAI/bge-m3` 指定 Revision，仅使用 1024 维 Dense Embedding，单条向量输入上限固定为 1024 Token。短期记忆 Token 数量仍采用字符比例近似估算，不使用模型 tokenizer。

Memory System 通过统一 Memory API 接收外部 Agent 产生的交互数据，并统一管理用户会话级短期记忆（Short-term Memory）与长期记忆（Long-term Memory）。短期记忆负责维护当前会话上下文，长期记忆负责保存跨会话的用户事实、偏好、事件和画像信息；任务经验记忆在后续版本中实现。系统通过记忆萃取机制将短期交互中的高价值信息转化为长期记忆，并通过检索、巩固和遗忘机制实现长期记忆生命周期管理。

## 1. 短期记忆管理

### 1.1 整体架构

短期记忆 MVP 采用基于 Redis 和 MongoDB 的分层存储架构。Redis 作为当前会话 Working Memory，保存 Agent 推理所需的压缩上下文和近期消息；Context Archive 作为持久化上下文归档，保存从 Redis 中移出的完整原始历史消息。

当 Working Memory 的上下文长度超过预设 token 阈值时，系统从 Redis List 头部选择较早的历史消息，将其写入 Context Archive，并发布 `context.archive.created` Kafka 事件，供后续长期记忆萃取使用。随后调用 Compression Service，将 Redis 中已有的 `compressed_context` 与本次归档消息进行融合压缩，并将新的压缩结果写回 Redis。

压缩成功后，系统从 Redis List 中移除已经持久化并参与压缩的历史消息，仅保留近期上下文。压缩失败时，不更新 Redis 压缩结果，不移除 Redis 原始消息，并记录错误日志。MVP 阶段暂不实现独立任务状态表、自动重试、补偿事务和死信队列。

短期记忆整体处理流程如下：

```
Create Session

        |

Initialize Redis Working Memory

        |

Receive New Message

        |

Append Message to Redis

        |

Calculate Current Token Usage

        |

Check Compression Trigger

        |

  +-------------------------+
  |                         |
Below Threshold       Exceed Threshold
  |                         |
Continue Conversation       |
                            v
                  Select Historical Messages

                            |

                  Create Context Archive

                            |

                  Publish Kafka Event

                            |

                  Call Compression Service

                            |

                  Update compressed_context

                            |

                  Remove Archived Messages

                            |

                  Continue Conversation
```

### 1.2 设计细节

#### 1.2.1 Redis Working Memory 数据结构设计

Redis 保存当前活跃会话上下文，用于 Agent 推理时快速获取上下文并构建 Prompt。为避免将消息数组序列化后整体覆盖导致并发写入冲突，Working Memory 使用 Redis Hash 保存会话元数据，并使用 Redis List 保存近期消息。(hash 里面普通字段是原子操作, hash里list 不是原子操作, 所以使用redis list确保原子操作)

会话元数据 Key：

```
memory:working:{user_id}:{session_id}
```

示例：

```
memory:working:user_001:session_001
```

会话元数据采用 `Redis Hash` 存储：

```
{
    "user_id": "user_001",

    "session_id": "session_001",

    "compressed_context":
    "用户正在设计Agent Memory System，关注长期记忆管理和上下文优化",

    "estimated_tokens": 53,

    "compression_version": 2,

    "status": "active",

    "pending_archive_id": null,

    "pending_archive_batch_key": null,

    "pending_archive_message_count": 0,

    "pending_archive_estimated_tokens": 0,

    "created_time": 1720000000,

    "updated_time": 1720000010
}
```

消息列表 Key：

```
memory:working:{user_id}:{session_id}:messages
```

示例：

```
memory:working:user_001:session_001:messages
```

消息列表采用 `Redis List` 存储，每个元素为 JSON 字符串，并按照写入顺序使用 `RPUSH` 追加：

```
[
    {
        "message_id": "msg_000001",

        "role": "user",

        "content": "我最近想研究Agent系统",

        "estimated_tokens": 12,

        "timestamp": 1720000000
    },
    {
        "message_id": "msg_000002",

        "role": "assistant",

        "content": "可以关注Memory System设计",

        "estimated_tokens": 11,

        "timestamp": 1720000010
    }
]
```

消息 ID 集合 Key：

```
memory:working:{user_id}:{session_id}:message_ids
```

该 Key 使用 `Redis Set` 保存当前 Session 中已经写入的全部 `message_id`。消息完成归档后仍保留对应 ID，直到 Session 被关闭。外部 Agent 因网络超时或调用失败而重试消息写入接口时，必须复用首次请求中的 `message_id`。Memory API 根据该集合判断消息是否已经存在，从而避免重复追加。

字段说明：

| 字段                | 说明                                                         |
| ------------------- | ------------------------------------------------------------ |
| user_id             | 用户唯一标识，由外部 Agent 平台或用户中心生成，Memory System 仅负责关联 |
| session_id          | 当前会话唯一标识，由 Memory System 创建，采用 UUID v4        |
| compressed_context  | 历史上下文压缩摘要，用于补充当前 Agent 推理上下文；初始为空，每次压缩成功后由 LLM 更新 |
| estimated_tokens    | 当前 `compressed_context` 与近期消息的估算 token 总量。MVP 不使用 tokenizer，统一按照中文字符数 × 1.25 加其他字符数 × 0.25 后向上取整 |
| compression_version | 上下文压缩版本号，初始值为 0，每次压缩结果成功写入 Redis 后递增 |
| status              | Session 当前状态，MVP 取值为 `active` 或 `closing`；只有 `active` 状态允许写入新消息 |
| pending_archive_id  | 已创建但尚未从 Redis List 中完成裁剪的 Context Archive ID；不存在时为 `null` |
| pending_archive_batch_key | Pending Archive 的确定性批次标识；不存在时为 `null` |
| pending_archive_message_count | Pending Archive 覆盖的 Redis List 头部消息数量；不存在时为 `0` |
| pending_archive_estimated_tokens | Pending Archive 中消息 token 估算总量；不存在时为 `0` |
| message_id          | 消息唯一标识，由外部 Agent 使用 UUID v4 生成；同一条消息重复调用写入接口时必须复用相同值 |
| role                | 消息角色，可选值为 `user` 和 `assistant`                     |
| content             | 用户或 Assistant 的对话文本内容                              |
| timestamp           | 消息来源时间，采用 Unix timestamp；由 Agent 提供或由 Memory API 在首次成功写入时生成 |
| created_time        | Working Memory 创建时间，采用 Unix timestamp                 |
| updated_time        | 最近更新时间，在消息写入、上下文读取或压缩完成后更新         |

MVP Token 估算规则：

```
estimated_tokens = ceil(
    chinese_character_count * 1.25
    + other_character_count * 0.25
)
```

其中，`chinese_character_count` 统计中文汉字数量，MVP 可使用正则范围 `\u4e00-\u9fff` 判断；`other_character_count` 统计英文字符、数字、标点、空格及其他非中文字符数量。消息写入时对 `content` 单独计算并保存消息级 `estimated_tokens`；压缩完成后使用同一规则分别计算旧 `compressed_context` 和新 `compressed_context` 的估算 token 数量。

全链路大小与时间规则：

1. 单条消息的 `estimated_tokens` 不得超过 `context.max_message_estimated_tokens`；超过时写入接口返回 `message_too_large`，不得写入 Redis。
2. 单个 Working Memory 的 `estimated_tokens` 不得超过 `context.max_working_memory_estimated_tokens`。该值是 Compression 长期失败或 Pending Archive 无法完成时的最终背压上限，不是正常压缩触发阈值。
3. 单个 Context Archive 的消息 token 总量不得超过 `context.max_archive_estimated_tokens`。普通压缩和关闭 Session 均必须按消息边界拆分，不得截断单条消息。
4. 启动时必须校验：

```
context.max_message_estimated_tokens
<= context.max_archive_estimated_tokens
<= memory_extraction.max_archive_estimated_tokens
```

```
context.compression_target_tokens
< context.compression_trigger_tokens
< context.max_working_memory_estimated_tokens
```

```
context.max_message_estimated_tokens
< context.max_working_memory_estimated_tokens
```

5. 写入请求允许携带可选 `timestamp`。提供时必须是合法 Unix timestamp，且不得晚于 `server_time + context.allowed_future_timestamp_skew_seconds`；未提供时，由 Memory API 使用该消息首次成功写入 Redis 时的服务器时间生成。相同 `message_id` 重试时必须保留首次写入的原始 `timestamp`，不得重新生成。历史时间允许早于服务器时间，用于支持延迟上传。

数据管理规则：

1. Redis 中仅保存当前活跃上下文，不保存完整历史消息。
2. 同一 Session 的消息统一通过 `RPUSH` 追加至 Redis List，消息顺序由 Redis List 的元素顺序保证，不额外维护顺序编号。
3. Memory API 在调用 Lua Script 前，按照 MVP Token 估算规则计算当前消息的 `estimated_tokens`，并将消息 JSON、该整数值和 `context.max_working_memory_estimated_tokens` 一并传入脚本。消息写入 Lua Script 将以下操作作为一个原子操作执行：
   - 检查 Session `status` 是否为 `active`；若不是，则返回 `session_closing`；
   - 检查 `message_id` 是否已经存在于消息 ID 集合；
   - 若已存在，则立即结束脚本并返回 `duplicate`，不追加消息，也不更新 token；
   - 读取当前会话 `estimated_tokens`，计算 `new_total = current_estimated_tokens + message_estimated_tokens`；
   - 若 `new_total > context.max_working_memory_estimated_tokens`，返回内部结果 `capacity_exceeded`，不得执行 `RPUSH`、`SADD`、token 更新或 `updated_time` 更新；
   - 若未超过绝对上限，则使用 `RPUSH` 追加消息；
   - 使用 `SADD` 将 `message_id` 写入消息 ID 集合；
   - 将会话总 `estimated_tokens` 设置为 `new_total`，并更新 `updated_time`。

   当 Lua Script 返回 `capacity_exceeded` 时，Memory API 必须先尝试执行一次当前 Session 的压缩协调流程；该流程存在 Pending Archive 时必须复用 Pending Archive。压缩结束后，Memory API 使用相同 `message_id`、相同消息内容和相同来源时间重新执行一次写入 Lua Script：
   - 第二次写入成功时，按照正常流程继续检查压缩触发条件；
   - 第二次仍返回 `capacity_exceeded` 时，接口返回 HTTP 503 和 `working_memory_full`；
   - `working_memory_full` 不得写入消息、消息 ID、token 或更新时间，调用方可在 Compression 恢复后使用相同 `message_id` 重试；
   - Working Memory 达到绝对上限时仍允许调用关闭 Session 接口，以便完成持久化归档并释放会话数据。
4. 当上下文长度超过压缩阈值时，由 Memory API 中的压缩协调流程执行以下操作：
   - 获取当前 Session 的压缩锁；
   - 若 `pending_archive_id` 非空，则不得重新选择消息或创建新 Archive，必须复用该 Pending Archive；
   - 若不存在 Pending Archive，则从 Redis List 头部选择不超过 `context.max_archive_estimated_tokens` 的较早历史消息，创建或复用 Context Archive，并通过 Lua Script 写入全部 `pending_archive_*` 字段；
   - 使用 `user_id` 作为 Kafka Message Key 发布或重新发布 `context.archive.created` 事件；重复发布由萃取任务和 Evidence 幂等规则处理；
   - 在持有压缩锁的前提下调用 Compression Service 生成新的 `compressed_context`；Compression Service 不重复获取压缩锁；
   - 使用 Redis Lua Script 校验 `compression_version`、`pending_archive_id` 和 Redis List 头部消息范围，原子更新 `compressed_context`、`compression_version` 和 `estimated_tokens`；
   - 根据 `pending_archive_message_count` 使用 `LTRIM` 移除已归档消息，并清空全部 `pending_archive_*` 字段；
   - 释放压缩锁。
5. 压缩失败时，不得更新 `compressed_context` 和 `compression_version`，不得执行 `LTRIM`，不得清空 `pending_archive_*`。Redis List 中的原始消息和 Pending Archive 必须完整保留；下一次压缩触发直接复用该 Archive，避免产生消息范围重叠的新 Archive。
6. 同一 Session 同一时间仅允许执行一个压缩或关闭流程。压缩锁 Key 为：

```
memory:compression:lock:{user_id}:{session_id}
```

压缩锁使用 `SET key value NX EX` 创建，并保存唯一 owner token。TTL 使用 `context.compression_lock_ttl_seconds`，所有外部调用必须受超时限制，并满足 `compression_lock_ttl_seconds > max_compression_rounds_per_request * compression_llm_timeout_seconds + safety_margin_seconds`。释放锁时必须校验 owner token，避免误删其他请求持有的锁。MVP 不实现锁续期。

7. 获取当前上下文时，Memory API 必须通过单个 Redis Lua Script 读取 `compression_version`、`compressed_context` 和近期消息，并更新 `updated_time`。Lua Script 内部命令仍按顺序执行，但脚本执行期间不会插入其他客户端命令，因此可以保证返回的摘要和消息列表属于同一个一致状态。不得在应用层使用独立的 Hash 查询和 `LRANGE` 命令分别读取。

#### 1.2.2 Context Archive 文档数据库设计

Context Archive 用于保存从 Redis Working Memory 中归档的完整历史上下文，是短期记忆与长期记忆萃取之间的数据桥梁。Redis 保存当前活跃状态，而 Context Archive 保存不可变的原始历史交互记录，用于后续长期记忆萃取、问题追踪以及上下文恢复。

采用 MongoDB 作为文档存储。

Collection：

```
context_archive
```

Document Schema：

```
{
    "archive_id": "archive_000001",

    "user_id": "user_001",

    "session_id": "session_001",

    "archive_batch_key": "session_001:msg_000001:msg_000002",

    "base_compression_version": 2,

    "messages": [
        {
            "message_id": "msg_000001",

            "role": "user",

            "content": "...",

            "timestamp": 1720000000
        },
        {
            "message_id": "msg_000002",

            "role": "assistant",

            "content": "...",

            "timestamp": 1720000015
        }
    ],

    "created_time": 1720000020
}
```

字段说明：

| 字段                     | 说明                                                         |
| ------------------------ | ------------------------------------------------------------ |
| archive_id               | 归档记录唯一标识，使用 UUID v4 生成                          |
| user_id                  | 用户唯一标识，与 Redis Working Memory 保持一致，由外部系统提供 |
| session_id               | 来源会话 ID，用于关联对应会话上下文                          |
| archive_batch_key        | 归档消息批次的确定性标识，MVP 使用 `session_id:first_message_id:last_message_id` 生成，用于避免同一批消息重复创建 Archive |
| base_compression_version | 创建 Archive 时 Redis 中的压缩版本。普通压缩 Archive 用于写回压缩结果前的版本校验；Session Close 创建的 Archive 写入关闭开始时读取的版本，仅保持 Schema 一致，不参与关闭后的压缩校验 |
| messages                 | 从 Redis List 头部选出的完整历史消息列表，数组顺序与原 Redis List 顺序一致，保存后不得修改 |
| created_time             | Archive 创建时间，采用 Unix timestamp                        |

Context Archive 仅保存原始完整对话及必要来源信息。文档创建后保持不可变，不写入压缩结果、压缩状态、长期记忆萃取状态或 Kafka 发布状态。

MongoDB Index 设计：

Archive 唯一索引：

```
db.context_archive.createIndex(
{
    "archive_id": 1
},
{
    "unique": true
}
)
1 代表升序, -1 代表降序
unique表示建立唯一索引
```

用户会话归档查询：

```
db.context_archive.createIndex(
{
    "user_id": 1,
    "session_id": 1,
    "created_time": 1
}
)
```

归档消息批次唯一索引：

```
db.context_archive.createIndex(
{
    "archive_batch_key": 1
},
{
    "unique": true
}
)
```

该唯一索引用于避免同一批消息重复创建 Archive。创建 Archive 前，调用方根据 `session_id`、首条 `message_id` 和末条 `message_id` 生成 `archive_batch_key`。若插入时发生唯一键冲突，则查询并复用已有 Archive，不重新创建文档。`base_compression_version` 不参与 Archive 唯一索引。普通压缩 Archive 使用它校验压缩结果写回；Session Close Archive 仅记录关闭开始时的版本。

数据生命周期管理：

1. 当 Redis Working Memory 超过上下文阈值时，系统获取当前 Session 的压缩锁。
2. 若 Working Memory 已存在 `pending_archive_id`，直接查询并复用该 Archive，不重新选择消息，也不创建消息范围重叠的新 Archive。
3. 若不存在 Pending Archive，则从 Redis List 头部选择不超过 `context.max_archive_estimated_tokens` 的历史消息，生成 `archive_batch_key`，创建或复用 Context Archive，并将 Archive ID、批次标识、消息数量和消息 token 总量写入 Redis `pending_archive_*` 字段。
4. Archive 创建或复用完成后，发布 `context.archive.created` Kafka 事件。Kafka 重复发布同一 `archive_id` 属于允许行为。
5. Compression Service 根据 Pending `archive_id` 查询归档消息并执行压缩。只有压缩成功并完成 Redis 原子裁剪后，才能清空 Pending 字段。
6. Context Archive 创建后不再更新。普通压缩产生的 Archive 与关闭 Session 拆分产生的 Archive 均必须满足全链路 Archive 大小上限。

#### 1.2.3 Memory API 接口设计

Memory API 作为 Memory System 对外统一访问接口，用于接收外部 Agent 产生的交互数据、管理 Working Memory 生命周期，并为 Agent 推理提供当前上下文。Memory API 屏蔽底层 Redis、MongoDB 和 Kafka 实现，使上层 Agent 与 Memory System 解耦。

------

**1. 写入消息接口**

Endpoint：

```
POST /api/v1/memory/working/message
```

Request：

```
{
    "message_id": "550e8400-e29b-41d4-a716",

    "user_id": "user_001",

    "session_id": "session_001",

    "role": "user",

    "content": "我最近想研究Agent系统",

    "timestamp": 1720000000
}
```

字段说明：

| 字段       | 说明                                                         |
| ---------- | ------------------------------------------------------------ |
| message_id | 消息唯一标识，由外部 Agent 使用 UUID v4 生成；重试同一消息写入请求时必须复用相同值 |
| user_id    | 用户唯一标识，由外部 Agent 平台或用户中心提供                |
| session_id | 当前会话唯一标识，由 Memory System 创建                      |
| role       | 消息角色，可选值为 `user` 和 `assistant`                     |
| content    | 用户或 Assistant 的对话文本内容                              |
| timestamp  | 可选消息来源时间，Unix timestamp；缺省时由 Memory API 在首次成功写入时生成 |

请求校验规则：

1. `content` 不能为空。
2. 按统一字符比例规则计算出的消息 `estimated_tokens` 不得超过 `context.max_message_estimated_tokens`；超过时返回 HTTP 400 和 `message_too_large`。
3. `timestamp` 提供时必须为合法 Unix timestamp，且不得晚于 `server_time + context.allowed_future_timestamp_skew_seconds`；超过允许偏差时返回 HTTP 400 和 `invalid_message_timestamp`。未提供时在首次成功写入的 Lua Script 参数构建阶段使用服务器时间。
4. 同一 `message_id` 的重复请求不覆盖首次保存的 `content`、`role`、`timestamp` 或 `estimated_tokens`。
5. 写入后预计总量超过 `context.max_working_memory_estimated_tokens` 时，Memory API 先执行一次压缩协调流程并重试原子写入一次；仍无法写入时返回 HTTP 503 和：

```json
{
    "success": false,
    "error": {
        "code": "working_memory_full",
        "message": "Working Memory has reached the configured capacity limit",
        "details": {}
    },
    "request_id": "1f47e791-62b6-4b93-b31f-6c5811d78e13"
}
```

`working_memory_full` 表示本次消息尚未写入，不属于 `status` 的可选值。调用方必须复用相同 `message_id` 重试。

Response：

```
{
    "message_id": "550e8400-e29b-41d4-a716",

    "status": "success",

    "compression_status": "not_triggered"
}
```

`status` 表示成功响应中的消息写入结果，可选值仅为 `success` 和 `duplicate`。当 Session 已进入 `closing` 状态时，接口不返回成功 Response，而是返回 HTTP `409` 和统一错误码 `session_closing`；错误 Body 必须遵循第 `3.23` 节的统一结构。`compression_status` 表示消息已经成功写入后，本次压缩执行的结果，可选值为：

- `not_triggered`：未达到压缩阈值；
- `completed`：达到阈值并完成一轮或多轮压缩，压缩后总量已经低于触发阈值；
- `partial_completed`：至少完成一轮压缩，但达到单请求最大轮数，或只剩绝对最小近期消息窗口，压缩后总量仍高于触发阈值；
- `failed`：消息写入成功，但压缩失败；
- `skipped_lock`：达到阈值，但当前 Session 已有压缩流程；
- `insufficient_messages`：达到阈值，但 Redis List 消息数量不大于绝对最小近期消息数量，没有可继续归档的历史消息；
- `version_conflict`：压缩结果写回时发现版本已变化，本次旧结果未写入。

当相同 `message_id` 已经写入时，接口返回原 `message_id`，并将 `status` 设置为 `duplicate`，不得重复追加消息。重复消息不再次触发压缩检查，`compression_status` 返回 `not_triggered`。

写入接口在消息成功追加后检查压缩阈值。若达到阈值，MVP 同步执行压缩流程并等待压缩结果后再返回；压缩失败、未获取到压缩锁、没有可压缩历史消息或发生版本冲突，都不改变消息已经写入成功的事实，因此 `status` 仍为 `success`，仅通过 `compression_status` 返回对应的压缩执行结果。

处理流程：

```
Agent
  |
  v
Memory API
  |
  v
Validate Session and Request
  |
  v
Execute Redis Lua Script
  |
  +---- capacity_exceeded ---> Run Compression Once
  |                                  |
  |                                  v
  |                           Retry Same Atomic Write
  |                                  |
  |                         +--------+--------+
  |                         |                 |
  |                      Success      capacity_exceeded
  |                         |                 |
  |                         |          Return working_memory_full
  |                         |
  +-------------------------+
  |
  v
Append Message and Update Metadata
  |
  v
Check Compression Trigger
  |
  +---- Below Threshold ----> Return Result
  |
  +---- Exceed Threshold ---> Execute Compression Synchronously
                              |
                              v
                         Return Result
```

------

**2. 获取当前上下文接口**

用于 Agent 推理时获取当前会话上下文，并构建 LLM Prompt。返回结果按照 `compressed_context` 在前、近期消息在后的顺序组织。

Endpoint：

```
GET /api/v1/memory/working/{user_id}/{session_id}
```

Response：

```
{
    "compression_version": 2,

    "compressed_context":
    "用户正在设计Agent Memory System，关注长期记忆管理和上下文优化",

    "messages": [
        {
            "message_id": "msg_000081",

            "role": "user",

            "content": "我最近想研究Agent系统",

            "timestamp": 1720000000
        }
    ]
}
```

字段说明：

| 字段                | 说明                                                         |
| ------------------- | ------------------------------------------------------------ |
| compression_version | 当前压缩摘要版本号，用于请求追踪和压缩版本校验               |
| compressed_context  | 历史上下文压缩摘要                                           |
| messages            | 当前 Working Memory 中的近期未压缩消息，按照 Redis List 顺序返回 |

读取上下文时，必须使用单个 Redis Lua Script 原子获取一致性快照。脚本在同一次执行中完成以下操作：

- 检查 Session Working Memory 是否存在；
- 从 Redis Hash 读取 `compression_version` 和 `compressed_context`；
- 使用 `LRANGE` 读取 Redis List 中的全部近期消息；
- 更新 `updated_time`；
- 将上述结果一次性返回给 Memory API。

由于 Redis 在 Lua Script 执行期间不会插入其他命令，因此上下文读取不会跨越压缩结果更新和 `LTRIM` 操作，避免返回旧 `compressed_context` 与裁剪后消息列表的混合状态。

处理流程：

```
Agent
  |
  v
Memory API
  |
  v
Execute Redis Lua Script
  |
  +-- Read compression_version
  |
  +-- Read compressed_context
  |
  +-- LRANGE Recent Messages
  |
  +-- Update updated_time
  |
  v
Return Consistent Context Snapshot
```

------

**3. 创建 Session 接口**

用于初始化新的 Working Memory。

Endpoint：

```
POST /api/v1/memory/session
```

Request：

```
{
    "user_id": "user_001"
}
```

Response：

```
{
    "session_id": "550e8400-e29b-41d4-a716",

    "status": "created"
}
```

处理流程：

```
Receive user_id

      |

Generate session_id(UUID v4)

      |

Initialize Redis Working Memory Metadata
(status = active)

      |

Return session_id
```

Redis List 和 Set 在首次写入时由 Redis 自动创建，不需要预先写入空结构。

------

**4. 关闭 Session 接口**

用于在会话结束时将 Redis 中尚未持久化的近期消息按 Archive 上限拆分归档，并释放 Working Memory。

Endpoint：

```
POST /api/v1/memory/session/{user_id}/{session_id}/close
```

Response：

```
{
    "session_id": "550e8400-e29b-41d4-a716",

    "archive_ids": [
        "archive_000002",
        "archive_000003"
    ],

    "status": "closed"
}
```

没有剩余消息且不存在 Pending Archive 时，`archive_ids` 返回空数组。

处理流程：

```
Acquire Session Compression Lock

        |

Read Session State

        |

active -> Atomically Change to closing
closing -> Resume Previous Close Attempt

        |

Load Pending Archive Metadata and Remaining Redis Messages

        |

Reuse Pending Archive for Head Messages

        |

Split Remaining Suffix by max_archive_estimated_tokens

        |

Create or Reuse Context Archives

        |

Confirm All Archives Persisted

        |

Publish context.archive.created for Every archive_id

        |

Atomically Delete Redis Working Memory Keys

        |

Release Lock in finally and Return Closed Result
```

关闭规则：

1. 关闭 Session 复用当前 Session 的压缩锁，避免关闭与上下文压缩同时执行。锁必须保存 owner token，并在 `finally` 中通过 owner token 校验后释放。
2. 关闭入口通过 Redis Lua Script 读取当前状态：
   - `status=active` 时原子修改为 `closing`；
   - `status=closing` 时视为上一次关闭未完成，允许继续恢复执行，不得返回新的关闭冲突；
   - Session Key 不存在时返回 `session_not_found`。如果上一次请求在 Redis 删除成功后客户端未收到 Response，重复调用可能返回该错误；MVP 将此作为已知限制，调用方可按 `user_id + session_id` 查询 Context Archive 确认数据已归档。
3. 状态变为 `closing` 后，新消息写入返回 HTTP `409` 和统一错误码 `session_closing`，普通上下文压缩也不得再执行。只有在本次关闭尚未持久化任何“关闭新增 Archive”，并且尚未进入“全部 Archive 已确认持久化”阶段时，失败处理才允许将 Session 恢复为 `active`。关闭开始前已经存在的 Pending Archive 不视为本次关闭新增 Archive。
4. 若存在 `pending_archive_id`，该 Archive 已覆盖 Redis List 头部 `pending_archive_message_count` 条消息。关闭流程必须复用该 Archive，不得再次归档相同头部消息。
5. Pending Archive 之后新增的剩余消息按照 Redis List 顺序，以 `context.max_archive_estimated_tokens` 为上限按消息边界拆分为零个或多个 Archive；不得拆分单条消息。
6. 关闭开始时读取一次当前 `compression_version`。本次关闭创建或复用的后续 Archive 均将该值写入 `base_compression_version`，仅用于保持 Archive Schema 一致，不参与关闭后的压缩结果校验。
7. `archive_ids` 按 Redis 消息顺序返回，包含复用的 Pending Archive 和本次新建或复用的后续 Archive。
8. 如果失败发生时尚未成功持久化任何本次关闭新增 Archive，且尚未确认全部 Archive 已持久化：
   - 不得删除 Redis 数据；
   - 可以通过 Lua Script 将 `status` 从 `closing` 恢复为 `active`；
   - 保留关闭开始前已有的 Pending 字段和全部消息；
   - 后续普通压缩仍按 Pending Archive 规则继续执行。
9. 一旦至少一个本次关闭新增 Archive 已经成功持久化，或者关闭计划中的全部 Archive 已经确认持久化，Session 就必须保持 `closing`：
   - 不得恢复为 `active`，不得接受新消息，也不得执行普通压缩；
   - 下一次 close 请求重新读取仍保留的 Redis 消息，按相同 token 上限重建确定性拆分计划；
   - 已创建 Archive 必须通过 `archive_batch_key` 复用，未创建的 Archive 继续创建；
   - 不得创建覆盖相同消息范围的新 Archive。
10. 全部 Archive 均已确认持久化后，对每个 `archive_id` 发布 `context.archive.created` 事件；发布失败只记录日志，由人工事件补发工具恢复，不阻止后续 Redis 删除，也不得将 Session 恢复为 `active`。
11. Redis 元数据、消息 List 和消息 ID Set 必须通过一个 Lua Script 原子删除。若删除调用失败或结果无法确认：
    - 保持 `status=closing`；
    - 返回 `close_incomplete`；
    - 下一次 close 请求重新构建相同关闭计划，通过 `archive_batch_key` 复用已有 Archive，然后再次执行事件发布检查和 Redis 删除；
    - 不得创建覆盖相同消息的新 Archive。
12. Redis 删除成功后，Pending 字段随元数据删除，不再执行上下文压缩。

由于 Redis 按顺序执行脚本，并发消息写入与关闭状态切换只会出现两种结果：消息写入脚本先执行，则该消息进入待归档范围；关闭状态切换先执行，则该消息被拒绝，不会出现读取剩余消息后又写入新消息并被删除的情况。

#### 1.2.4 Kafka Event 设计

Kafka 用于解耦短期记忆归档和长期记忆萃取流程。当 Context Archive 创建完成后，Memory System 直接发布事件，由 Memory Extraction Worker 异步消费并执行长期记忆萃取。

Topic：

```
context.archive.created(Kafka Topic 名称)
```

Producer：

```
Memory API / Context Archive Service
```

触发条件：

```
Create Context Archive
        |
Publish Kafka Event
```

Message Schema：

```
{
    "event_id": "event_000001",

    "event_type": "context.archive.created",

    "archive_id": "550e8400-e29b-41d4-a716",

    "user_id": "user_001",

    "session_id": "session_001",

    "created_time": 1720000020
}
```

字段说明：

| 字段         | 说明                                       |
| ------------ | ------------------------------------------ |
| event_id     | 事件唯一标识，采用 UUID v4 生成            |
| event_type   | 事件类型                                   |
| archive_id   | Context Archive 唯一标识，用于查询归档数据 |
| user_id      | 用户唯一标识                               |
| session_id   | 来源会话 ID                                |
| created_time | 事件创建时间                               |

Consumer：

```
Memory Extraction Worker
```

Consumer Group：

```
memory-extraction-group
```

消费流程：

```
Consume context.archive.created Event (拉取消息)
        |
Query MongoDB Context Archive (查询归档文档)
        |
Execute Memory Extraction (执行记忆提取)
        |
Commit Kafka Offset (提交偏移量)
```

MVP 阶段由 Producer 直接发布事件。发布失败时记录错误日志，不实现独立 Event Publisher、Outbox、指数退避、Dead Letter Topic 和自动补偿。

为避免 Archive 已持久化但事件丢失后长期无法萃取，MVP 必须提供人工运维命令或脚本：扫描不存在对应 `memory_extraction_task` 的 Context Archive，并使用 Archive 的 `user_id` 作为 Kafka Message Key 重新发布 `context.archive.created`。该工具只执行人工补发，不作为自动后台任务运行。

#### 1.2.5 Compression Service 设计

Compression Service 负责将 Context Archive 中的归档历史消息与 Redis 中已有 `compressed_context` 进行融合压缩，生成新的上下文摘要，并更新 Redis Working Memory。MVP 中该服务由已持有当前 Session 压缩锁的 Memory API 压缩协调流程调用，Compression Service 本身不重复获取或释放压缩锁。

**Application Service Contract**

MVP 中 Compression Service 是 `memory-api` 进程内的应用层服务，不暴露独立 HTTP Endpoint。Memory API 在持有 Session 压缩锁后，通过 Python 异步方法调用：

```python
await compression_service.compress(
    archive_id="archive_000001",
    user_id="user_001",
    session_id="session_001",
    lock_owner_token="opaque-owner-token",
)
```

输入 Contract：

```
{
    "archive_id": "archive_000001",

    "user_id": "user_001",

    "session_id": "session_001",

    "lock_owner_token": "opaque-owner-token"
}
```

字段说明：

| 字段       | 说明                                                        |
| ---------- | ----------------------------------------------------------- |
| archive_id | Context Archive 唯一标识，用于查询待压缩历史消息            |
| user_id    | 用户唯一标识，用于校验 Archive 与 Working Memory 的归属关系 |
| session_id | 当前会话 ID                                                 |
| lock_owner_token | 当前压缩协调流程持有的锁 owner token；仅用于 Redis Lua Script 校验，不持久化 |

返回 Contract：

```
{
    "archive_id": "archive_000001",

    "compressed_context":
    "用户正在开发Agent Memory System，关注Redis短期记忆管理、长期记忆萃取以及上下文压缩策略",

    "compression_version": 3,

    "status": "completed"
}
```

规则：

1. 不实现 `POST /api/v1/memory/compress` 公共或内部网络接口。
2. Compression Service 只能由 `memory-api` 的压缩协调流程调用。
3. Contract 使用 Pydantic Model 定义，便于单元测试和未来拆分服务，但 MVP 不产生网络序列化开销。

**LLM Compression Prompt**

Compression Service 使用 Structured Output 调用 LLM，要求模型严格输出 JSON 格式。

System Prompt：

```
You are a memory compression assistant.

Your task is to merge the previous compressed context with newly archived conversation messages and produce a concise context summary for future agent reasoning.

Requirements:

1. Preserve stable user preferences and important user facts.
2. Preserve current user goals and ongoing tasks.
3. Preserve important decisions and their reasons when explicitly stated.
4. Preserve unresolved questions, blockers and pending actions.
5. Preserve necessary conversation state and pending actions.
6. Preserve important temporal order and references.
7. Remove greetings, repeated statements and low-value conversational details.
8. Do not invent, infer or add information that is not present in the input.
9. Do not include hidden reasoning or internal chain-of-thought.
10. Keep the compressed context within the configured estimated-token limit: {max_compressed_context_estimated_tokens}.
11. If there is no information worth preserving, return an empty string for compressed_context.
12. Output valid JSON matching the required schema.
```

User Prompt：

```
Previous compressed context:

{compressed_context}


Archived conversation messages:

{messages}


Generate the updated compressed context.
```

Output Schema：

```
{
    "compressed_context":
    "用户正在开发Agent Memory System，关注上下文管理和长期记忆设计"
}
```

应用层必须校验 `compressed_context` 为字符串，允许为空字符串，但不允许为 `null` 或其他类型。当没有值得保留的上下文时，LLM 应返回空字符串，应用层将其 `new_compressed_context_tokens` 记为 `0`。非空字符串按照统一字符比例规则计算 `new_compressed_context_tokens`。若该值超过 `context.max_compressed_context_estimated_tokens`，返回 `compression_output_too_large`，不得更新 Redis、裁剪消息或清空 Pending 字段。空字符串属于合法压缩结果，后续仍按照正常成功流程更新 Redis、递增 `compression_version`、裁剪 Pending Archive 对应消息并清空 Pending 字段。MVP 不对超长压缩输出自动进行第二次 LLM 重写。

**Compression Update Flow**

```
Receive pending archive_id

        |

Query Context Archive

        |

Load Redis pending_archive_* and compressed_context

        |

Validate Pending Archive and base_compression_version

        |

Call LLM Compression with Timeout

        |

Calculate Token Deltas

        |

Atomically Update Summary, Trim Pending Head Messages and Clear Pending Fields
```

MVP 并发与一致性规则：

1. Compression Service 只能处理 Redis 当前 `pending_archive_id` 指向的 Archive。若 Request `archive_id` 与 Redis Pending 字段不一致，返回 `pending_archive_mismatch`，不得调用 LLM 或修改 Redis。
2. 更新 Redis 前，必须校验当前 `compression_version` 与 Archive 中的 `base_compression_version` 一致。若版本不一致，则终止本次更新，避免旧压缩结果覆盖新结果。
3. 调用 Lua Script 前，Compression Service 按照统一的 MVP Token 估算规则计算以下整数值：
   - `archived_message_tokens`：Archive 中全部消息的 token 估算总量；
   - `old_compressed_context_tokens`：旧 `compressed_context` 的估算 token 数；
   - `new_compressed_context_tokens`：新 `compressed_context` 的估算 token 数。
4. Redis 更新使用 Lua Script 原子执行以下操作：
   - 再次校验压缩锁 owner token；
   - 再次校验 `compression_version`；
   - 校验 `pending_archive_id`、`pending_archive_message_count` 和 `pending_archive_batch_key`；
   - 校验 Redis List 头部首尾 `message_id` 与 Archive 的首尾消息一致；
   - 读取 Redis 当前 `estimated_tokens`；
   - 按以下公式计算新的总量：

```
new_estimated_tokens = max(
    0,
    current_estimated_tokens
    - archived_message_tokens
    - old_compressed_context_tokens
    + new_compressed_context_tokens
)
```

   - 写入新的 `compressed_context`；
   - 递增 `compression_version`；
   - 根据 `pending_archive_message_count` 使用 `LTRIM` 裁剪 Redis List 头部消息；
   - 写入 `new_estimated_tokens`；
   - 清空 `pending_archive_id`、`pending_archive_batch_key`、`pending_archive_message_count` 和 `pending_archive_estimated_tokens`；
   - 更新 `updated_time`。
5. 新消息在 LLM 压缩期间仍可追加至 Redis List。Lua Script 使用执行时的 `current_estimated_tokens` 计算差值，且只裁剪 Pending Archive 对应的头部消息，因此不会删除压缩期间新增的消息。
6. 消息 ID 集合在压缩时不裁剪，用于保证整个 Session 生命周期内的消息写入幂等。
7. LLM 调用、MongoDB 查询或 Redis 更新失败时，不得更新压缩摘要，不得裁剪消息，不得清空 Pending 字段。下一次触发必须复用同一 Pending Archive。
8. Compression LLM 每轮调用必须使用 `context.compression_llm_timeout_seconds`。压缩锁 TTL 必须大于单请求最大压缩轮数乘以单轮 LLM 超时，再加数据库、Kafka 和 Redis 操作安全余量。MVP 不实现锁续期；旧 owner 在锁过期后返回时仍必须通过 owner token、Pending Archive 和版本校验，失败后不得写入。

#### 1.2.6 Context Compression Trigger Strategy

Context Compression 根据 Redis Working Memory 当前的 `estimated_tokens` 触发，用于防止发送给 LLM 的上下文超过模型限制。

MVP 配置如下：

```yaml
context:
    compression_trigger_tokens: 5000
    compression_target_tokens: 3000
    preferred_recent_messages: 10
    absolute_min_recent_messages: 2
    max_compressed_context_estimated_tokens: 1000
    max_compression_rounds_per_request: 3
    max_message_estimated_tokens: 2000
    max_working_memory_estimated_tokens: 12000
    max_archive_estimated_tokens: 7000
    allowed_future_timestamp_skew_seconds: 300
    compression_llm_timeout_seconds: 120
    compression_lock_ttl_seconds: 420
    safety_margin_seconds: 30
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| compression_trigger_tokens | 当 Working Memory `estimated_tokens` 达到该值时触发压缩 |
| compression_target_tokens | 一次压缩协调流程希望达到的 Working Memory 近似目标 token 数量 |
| preferred_recent_messages | 普通情况下优先保留的最近消息数量，不是不可突破的硬下限 |
| absolute_min_recent_messages | 普通压缩后绝对不能少于的最近消息数量 |
| max_compressed_context_estimated_tokens | 新 `compressed_context` 允许的最大估算 token 数 |
| max_compression_rounds_per_request | 单次写消息请求持锁连续执行的最大压缩轮数 |
| max_message_estimated_tokens | 单条消息允许写入的最大估算 token 数 |
| max_working_memory_estimated_tokens | 单个 Session Working Memory 的绝对估算 token 上限；超过时先尝试压缩，仍无法释放容量则拒绝新消息写入 |
| max_archive_estimated_tokens | 单个 Context Archive 允许包含的最大消息 token 总量 |
| allowed_future_timestamp_skew_seconds | Agent 提供消息时间允许晚于服务器时间的最大秒数 |
| compression_llm_timeout_seconds | Compression LLM 单次调用超时 |
| compression_lock_ttl_seconds | Session 压缩锁 TTL |
| safety_margin_seconds | MongoDB、Kafka 和 Redis 操作预留安全时间 |

启动校验：

```
0 < absolute_min_recent_messages
<= preferred_recent_messages
```

```
max_message_estimated_tokens
<= context.max_archive_estimated_tokens
<= memory_extraction.max_archive_estimated_tokens
```

```
max_compressed_context_estimated_tokens
< compression_trigger_tokens
```

```
compression_target_tokens
< compression_trigger_tokens
< max_working_memory_estimated_tokens
```

```
max_message_estimated_tokens
< max_working_memory_estimated_tokens
```

```
compression_lock_ttl_seconds
>
max_compression_rounds_per_request
* compression_llm_timeout_seconds
+ safety_margin_seconds
```

`estimated_tokens` 的计算范围包括：

```
estimated(compressed_context)
+
sum(estimated_tokens of recent messages)
```

所有估算均使用统一字符比例规则，MVP 不调用模型 tokenizer。

触发后先获取压缩锁，并在同一锁内最多执行 `max_compression_rounds_per_request` 轮：

1. 若未获取到锁，返回 `skipped_lock`。
2. 每轮开始时读取当前 `estimated_tokens`。若已经低于 `compression_trigger_tokens`，结束流程并返回 `completed`。
3. 若 `pending_archive_id` 非空，当前轮直接复用该 Archive，重新发布 Kafka 事件并重试压缩；不得重新选择消息。
4. 若不存在 Pending Archive，读取 Redis List 并选择头部消息：
   - 优先保留最近 `preferred_recent_messages` 条；
   - 如果保留该数量后 Working Memory 仍高于 `compression_trigger_tokens`，允许继续归档较早消息，将保留窗口逐步缩小；
   - 无论上下文多大，最终至少保留 `absolute_min_recent_messages` 条；
   - 已选消息总量不得超过 `max_archive_estimated_tokens`；
   - 在满足上述约束时，优先选择使当前总量接近或低于 `compression_target_tokens` 的最大连续头部消息范围；不得跳过中间消息或拆分单条消息。
5. 当 Redis List 消息数量不大于 `absolute_min_recent_messages`，或在绝对最小窗口约束下无法选择任何消息时：
   - 本次尚未完成任何压缩轮次时返回 `insufficient_messages`；
   - 本次已经成功完成至少一轮时返回 `partial_completed`。
6. 选择完成后创建或复用 Context Archive，使用 Lua Script 写入 Pending Archive 元数据，再发布 Kafka 事件并调用 Compression Service。
7. 压缩成功后原子更新摘要、裁剪 Pending 消息并清空 Pending 字段，然后进入下一轮重新检查 `estimated_tokens`。
8. 达到 `max_compression_rounds_per_request` 后仍高于触发阈值时，返回 `partial_completed`。后续新消息写入时会再次检查阈值并继续处理。
9. 任意轮次压缩失败时保留当前 Pending Archive 和原始消息。若此前已有成功轮次，接口仍返回 `failed`，并在日志中记录成功轮数和失败 Archive；下一次触发直接复用 Pending Archive。
10. Kafka 发布失败不阻塞压缩，但必须记录 `archive_id`，供人工补发工具处理。

压缩流程：

```
Check estimated_tokens

        |

Acquire Session Lock

        |

Set round = 0

        |

  +-----------------------------+
  |                             |
Pending Archive Exists      No Pending Archive
  |                             |
Reuse Pending Archive       Select Head Messages with
  |                         Preferred and Absolute Windows
  +-------------+---------------+
                |
       Create/Reuse Archive
                |
       Persist pending_archive_*
                |
       Publish Kafka Event
                |
       Call Compression Service
                |
       Atomic Update + LTRIM + Clear Pending
                |
       round = round + 1
                |
       Recheck estimated_tokens
                |
       Continue or Return completed / partial_completed
                |
       Release Lock in finally
```

#### 1.2.7 Session 生命周期

MVP 通过创建 Session、写入消息、获取上下文和显式关闭 Session 管理 Working Memory 生命周期。

数据管理规则：

1. 创建 Session 时初始化 Redis Working Memory 元数据，将 `status` 设置为 `active`，并将全部 `pending_archive_*` 字段初始化为空值或 `0`。MVP 不在 Session 中保存默认时区。
2. 写入消息和获取上下文时更新 `updated_time`。
3. 普通压缩创建 Archive 后，在完成 Redis 裁剪前始终保留 Pending Archive 元数据；压缩失败或进程异常退出时不得创建覆盖相同消息头部的新 Archive。
4. 普通压缩优先保留 `preferred_recent_messages`，但为保证 Working Memory 有界，允许缩小至 `absolute_min_recent_messages`。压缩成功后若仍达到阈值，应在单请求轮数限制内继续压缩。
5. `max_working_memory_estimated_tokens` 是最终背压上限。新消息预计使总量超过该值时，写入接口必须先尝试压缩并重试一次；仍超限则返回 `working_memory_full`，不得写入该消息。关闭 Session 不受该背压限制。
6. 会话结束时，由外部 Agent 显式调用关闭 Session 接口。
7. 关闭 Session 时获取当前 Session 的压缩锁。`active` 状态原子修改为 `closing`；已有 `closing` 状态允许恢复执行；后续消息写入请求返回 HTTP `409` 和统一错误码 `session_closing`。
8. 关闭流程复用已有 Pending Archive，并将其后的剩余消息按 `context.max_archive_estimated_tokens` 拆分为多个非重叠 Archive。
9. 只有在尚未持久化任何本次关闭新增 Archive、且尚未确认全部 Archive 已持久化时，失败后才允许恢复 `status=active`；一旦已有关闭新增 Archive 持久化或全部 Archive 已确认持久化，后续失败必须保持 `status=closing`，下一次 close 通过 `archive_batch_key` 复用已有 Archive 并继续完成关闭。
10. Kafka 事件发布失败不阻止关闭，但必须通过人工事件补发工具恢复长期记忆萃取。
11. Redis Working Memory 的全部 Key 仅在 Archive 全部持久化后通过 Lua Script 原子删除。关闭锁无论成功或失败都必须在 `finally` 中按 owner token 释放。
12. MVP 阶段不使用 Redis TTL 自动删除 Working Memory，也不实现闲置 Session 扫描、自动关闭和后台清理任务。

## 2. 长期记忆管理

### 2.1 记忆萃取

#### 2.1.1 整体架构

记忆萃取模块负责将 Context Archive 中已经归档的原始历史消息转换为结构化、可追溯、可合并的长期记忆。该模块由 `context.archive.created` Kafka 事件异步触发，Memory Extraction Worker 根据事件中的 `archive_id` 查询 MongoDB Context Archive，完成预处理、LLM 结构化抽取、实体对齐、记忆去重与冲突处理，并将最终结果写入 Neo4j 长期记忆图谱。该图谱统一保存知识型记忆（`fact`、`preference`、`profile`）和事件型记忆（`event`），不分别维护两套独立图谱。

Context Archive 是记忆萃取的唯一原始数据来源。记忆萃取不得直接读取 Redis Working Memory，也不得使用 `compressed_context` 代替原始消息，以避免压缩摘要丢失事件细节、时间信息和用户原始表述。

MVP 中，记忆萃取仅生成原子长期记忆，`abstraction_level` 固定为 `0`。跨多个 Archive 的高层摘要记忆和主题记忆由后续版本的记忆抽象模块生成；MVP 阶段的巩固与遗忘仅维护原子记忆的动态重要性和软遗忘状态。任务执行经验由后续经验记忆模块设计，避免在单批消息萃取阶段过早抽象。

整体处理流程如下：

```
Consume context.archive.created Event

        |

Create or Load Extraction Task

        |

Query MongoDB Context Archive

        |

Validate Archive Ownership and Messages

        |

Normalize Messages and Resolve Local References

        |

Call LLM Structured Extraction

        |

Validate and Persist Extraction Result

        |

Align Entities with Existing Graph

        |

Retrieve Related Existing Memories

        |

Reconcile Duplicate, Update and Conflict

        |

Write Entity, Memory and Evidence Graph

        |

Mark Extraction Task Completed

        |

Commit Kafka Offset
```

模块职责划分如下：

| 组件 | 职责 |
| --- | --- |
| Context Archive | 保存不可变的原始归档消息，作为记忆萃取的数据来源 |
| Kafka | 异步传递 `context.archive.created` 事件 |
| Memory Extraction Worker | 消费事件、管理任务状态并协调完整萃取流程 |
| LLM Extraction Service | 根据原始消息输出符合固定 Schema 的候选实体和候选记忆 |
| MongoDB `memory_extraction_task` | 保存萃取任务状态、重试次数、结构化抽取结果和错误信息 |
| Neo4j | 保存实体节点、长期记忆节点、证据节点及其关系 |

MVP 中 Memory Extraction Worker 与 LLM Extraction Service 可以部署在同一个服务进程中，通过内部方法调用完成，不要求拆分为独立微服务。

#### 2.1.2 记忆萃取范围与类型定义

长期记忆仅保存能够跨当前对话继续使用的信息。LLM 必须将候选记忆分类为以下四类：

| memory_type | 定义 | 示例 |
| --- | --- | --- |
| `fact` | 描述当前成立的客观状态、属性或关系，不强调具体发生过程 | 用户当前使用 Java 进行后端开发 |
| `preference` | 用户明确表达的偏好、厌恶、风格或选择倾向 | 用户偏好使用中文回复 |
| `event` | 描述在特定时间已发生、正在进行或计划发生的动作、变化或经历 | 用户计划下周提交论文 |
| `profile` | 描述用户相对长期的身份、角色、职业、能力或长期目标 | 用户是一名后端开发者 |

分类时按照以下顺序判断：

1. 明确表达偏好、厌恶或风格时，归类为 `preference`。
2. 描述特定时间发生、正在发生或计划发生的动作、变化或经历时，归类为 `event`。
3. 描述用户相对长期的身份、职业、能力或长期目标时，归类为 `profile`。
4. 其余描述当前客观状态、属性或关系的内容，归类为 `fact`。

同一段消息可以同时产生事件记忆和事件导致的当前状态记忆。例如“用户上个月搬到槟城”可以生成一条 `event`，并在语义明确时生成“用户当前居住在槟城”的 `fact`。两条记忆必须分别表达变化过程和当前状态，不得生成语义完全重复的候选。

以下内容默认不写入长期记忆：

1. 问候语、寒暄、确认词和无独立语义的短句。
2. 仅在当前轮次有效的临时指令，例如“把上一句缩短一点”。
3. Assistant 单方面提出但用户未确认的建议、推测和结论。
4. 无法从原始消息直接支持的推断内容。
5. 密码、验证码、访问令牌、API Key、银行卡完整号码、CVV 和私钥等敏感凭证。
6. 与用户长期任务、事实、偏好、画像或事件无关的低价值对话细节。
7. 任务执行策略、成功率和可复用操作经验。MVP 暂不抽取独立“经验记忆”，相关内容在后续经验记忆设计中实现。

记忆必须至少包含一条 `role=user` 的来源消息。Assistant 消息可以用于补充上下文和解析指代，但不得作为一条长期记忆的唯一证据。

对于用户明确纠正历史信息的消息，例如“我不是 Java 开发者，我现在主要使用 Python”，必须保留纠正语义，并在后续冲突处理阶段将新记忆标记为对旧记忆的更新或冲突。

#### 2.1.3 Memory Extraction Task 数据库设计

记忆萃取任务采用 MongoDB 保存，用于处理 Kafka 重复投递、记录任务执行状态、支持失败重试和问题追踪。任务表不保存原始消息和最终长期记忆；原始消息保存在 Context Archive，最终记忆保存在 Neo4j。

Collection：

```
memory_extraction_task
```

Document Schema：

```
{
    "task_id": "550e8400-e29b-41d4-a716-446655440000",

    "archive_id": "archive_000001",

    "user_id": "user_001",

    "status": "processing",

    "attempt_count": 1,

    "extraction_result": null,

    "last_error": null,

    "created_time": 1720000020,

    "updated_time": 1720000020,

    "completed_time": null
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| task_id | 萃取任务唯一标识，采用 UUID v4 |
| archive_id | 来源 Context Archive ID，同一 Archive 只允许存在一个任务 |
| user_id | 记忆所属用户，用于数据隔离和归属校验 |
| status | 任务状态，可选值为 `pending`、`processing`、`completed`、`failed` |
| attempt_count | 任务执行次数，每次开始执行时递增 |
| extraction_result | 已通过校验的 LLM 结构化抽取结果；LLM 成功后立即持久化，后续图谱写入失败时可以复用 |
| last_error | 最近一次失败信息，包含 `error_code`、`failed_stage` 和 `message` |
| created_time | 任务创建时间，采用 Unix timestamp |
| updated_time | 最近更新时间，采用 Unix timestamp |
| completed_time | 任务成功完成时间，未完成时为 `null` |

`last_error` 示例：

```
{
    "error_code": "graph_write_failed",

    "failed_stage": "graph_write",

    "message": "Neo4j connection timeout"
}
```

任务状态转换：

```
pending
   |
   v
processing
   |
   +---- 执行成功 ----> completed
   |
   +---- 执行失败 ----> failed
                            |
                            +---- 人工重试 ----> pending
```

MongoDB Index 设计：

任务唯一索引：

```
db.memory_extraction_task.createIndex(
{
    "archive_id": 1
},
{
    "unique": true
}
)
```

该索引用于保证同一份 Context Archive 只创建一个萃取任务。Kafka 重复投递同一 `archive_id` 时，Worker 查询并复用已有任务，不重复创建任务。

任务状态查询索引：

```
db.memory_extraction_task.createIndex(
{
    "status": 1,
    "updated_time": 1
}
)
```

该索引用于查询失败任务、处理中任务以及按照更新时间进行任务排查。

MVP 不实现 Worker 租约、任务抢占、自动定时重试和阶段级状态机。Worker 异常退出时，Kafka Offset 不会提交，事件重新投递后复用原任务和已有 `extraction_result` 继续执行。

#### 2.1.4 Kafka 消费与任务幂等

Memory Extraction Worker 消费短期记忆模块发布的 `context.archive.created` 事件。

Topic：

```
context.archive.created
```

Consumer Group：

```
memory-extraction-group
```

事件发布时必须使用 `user_id` 作为 Kafka Message Key，使同一用户的 Archive 事件进入同一 Partition。Consumer 必须按 Partition 顺序串行处理，不得在同一 Partition 内并发执行多个 Archive，从而保持同一用户长期记忆的处理顺序。人工重试或历史事件延迟到达时，更新和冲突判断仍必须比较来源消息时间，不能仅根据 Worker 的处理时间判断新旧。

事件处理规则：

1. Worker 收到事件后，根据 `archive_id` 对 `memory_extraction_task` 执行 Upsert。插入时使用 `$setOnInsert` 创建 `pending` 任务，避免重复事件覆盖已有任务状态。
2. 若任务状态为 `completed`，说明该 Archive 已完成萃取，Worker 直接提交当前 Kafka Offset，不重复调用 LLM 或写入 Neo4j。
3. 若任务状态为 `failed`，说明该任务已经记录失败并等待人工处理。普通重复事件不得自动重试该任务，Worker 直接提交当前 Kafka Offset；只有人工重试接口将任务重新修改为 `pending` 后，才允许再次执行。
4. 若任务状态为 `pending`，Worker 将其更新为 `processing`，递增 `attempt_count`，清空 `last_error` 并开始执行。
5. 若任务状态为 `processing`，说明上一次执行可能在提交 Kafka Offset 前异常中断。Worker 递增 `attempt_count` 并恢复执行；若 `extraction_result` 不为空，则不得再次调用 LLM，应直接复用该结果继续实体对齐、记忆协调和图谱写入。
6. Neo4j 写入成功并将任务状态更新为 `completed` 后，才允许提交 Kafka Offset。
7. 任意执行阶段失败时，必须先将任务状态更新为 `failed` 并成功保存 `last_error`，随后才允许提交当前 Kafka Offset，避免单个失败事件持续阻塞 Partition。
8. 若失败状态或 `last_error` 写入 MongoDB 失败，则不得提交 Kafka Offset，使 Kafka 后续重新投递当前事件。
9. 失败任务通过人工重试接口重新发布同一 `archive_id` 的事件。MVP 不实现自动重试、Retry Topic 和 Dead Letter Topic。

MVP 配置：

```yaml
memory_extraction:
    prompt_version: "memory_extraction_v1"
    llm_timeout_seconds: 120
    max_archive_estimated_tokens: 8000
    max_memory_candidates_per_archive: 50
    max_entity_candidates_per_archive: 100
```

`max_archive_estimated_tokens` 使用短期记忆相同的字符比例规则估算 Archive 中全部消息 `content` 的 token 总量。该值必须小于所用模型的最大输入长度，并为 System Prompt、输出和安全余量预留空间。短期模块的 `context.max_archive_estimated_tokens` 必须小于等于该值；合法写入链路生成的 Archive 不应触发 `archive_too_large`。超过该上限时仍返回 `archive_too_large`，用于拦截旧数据、配置错误或外部写入的异常 Archive。MVP 不在记忆萃取阶段执行分块抽取。

`prompt_version` 同时写入每个 Evidence，用于追踪生成候选时使用的 Structured Extraction Prompt 版本。

Worker 异常退出时，由于 Offset 尚未提交，Kafka 会重新投递当前事件。若异常发生在 LLM 结果持久化之后，重试复用 `extraction_result`；若异常发生在 Neo4j Transaction 提交之后，重试通过 Evidence 唯一约束和图谱幂等规则避免重复写入。

短期记忆模块当前采用直接发布 Kafka 事件的方式。如果 Archive 创建成功但事件发布失败，长期记忆萃取不会被自动触发。MVP 通过人工事件补发工具扫描不存在对应 `memory_extraction_task` 的 Archive 并重新发布事件；自动 Outbox Event Publisher 在后续版本实现。

#### 2.1.5 Context Archive 读取与预处理

Worker 根据事件中的 `archive_id` 查询 `context_archive` Collection，并执行以下校验：

1. Archive 必须存在，否则返回 `archive_not_found`。
2. Archive 中的 `user_id` 必须与 Kafka 事件和任务文档一致，`session_id` 必须与 Kafka 事件一致，否则返回 `archive_ownership_mismatch`。
3. `messages` 必须为数组，允许为空。若数组为空，则不调用 LLM、不写入 Neo4j，直接将任务标记为 `completed` 并提交 Kafka Offset。
4. 当 `messages` 非空时，每条消息必须包含 `message_id`、`role`、`content` 和 `timestamp`。
5. `role` 仅允许为 `user` 或 `assistant`。
6. 使用短期记忆相同的字符比例规则估算全部消息 `content` 的 token 总量；若超过 `max_archive_estimated_tokens`，返回 `archive_too_large`。
7. 消息按照 Archive 中的数组顺序处理；若 timestamp 相同，不额外重新排序。

预处理仅进行格式标准化和引用辅助，不对原始消息进行语义压缩。具体规则如下：

- 对文本执行 Unicode NFKC 标准化。
- 将连续空格和连续空行压缩为单个空格或单个换行。
- 去除文本首尾空白字符。
- 保留原始 `content`，标准化结果写入临时字段 `normalized_content`。
- 保留消息角色、消息 ID 和时间戳，使 LLM 可以追溯每条候选记忆的来源。
- 将“我”“本人”“我的”等第一人称引用绑定到当前 `user_id` 对应的用户实体。
- 相对时间必须结合来源消息的 `timestamp` 和明确时区解析，不使用 Worker 当前执行时间。当前 Archive 未提供时区时，不将“明天”“下周”等表达强制转换为绝对时间。
- 无法确定的实体、关系或时间保持未知，不允许通过规则或 LLM 猜测。
- 敏感凭证在发送给 LLM 前替换为 `[REDACTED_SECRET]`，原始 Archive 不修改。

传给 LLM 的标准化输入格式：

```
{
    "archive_id": "archive_000001",

    "user_id": "user_001",

    "session_id": "session_001",

    "messages": [
        {
            "message_id": "msg_000001",

            "role": "user",

            "content": "我正在开发一个 Agent Memory System。",

            "timestamp": 1720000000
        }
    ]
}
```

#### 2.1.6 LLM Structured Extraction 设计

LLM Extraction Service 使用 Structured Output，一次调用完成实体识别、记忆分类、原子记忆抽取和事件时间识别。LLM 只负责生成候选实体和候选记忆，不直接决定数据库中的实体 ID、最终记忆 ID 或新旧记忆合并操作。实体之间的长期关系统一通过 Memory 的 `SUBJECT` 和 `OBJECT` 表达，MVP 不额外输出或保存独立 `entity_relations`。

为降低 LLM 输出难度和应用层校验复杂度，MVP Structured Output 仅保留图谱写入、记忆协调和来源追溯真正需要的字段。

System Prompt：

```
You are a long-term memory extraction engine.

Your task is to extract only durable and reusable memories from archived conversation messages.

Requirements:

1. Extract only memories supported by the provided messages.
2. Every memory must include at least one source message whose role is user.
3. Assistant messages may provide context, but must never be the only evidence.
4. Classify each memory as fact, preference, event, or profile.
5. Each memory must express one atomic meaning. Split unrelated information into separate memories.
6. Resolve first-person references such as "I" and "my" to the current user entity.
7. Preserve explicit corrections, negations, temporal order, event status and unresolved conflicts.
8. Preserve the original time expression. Resolve relative time only when the source timestamp and timezone are both available.
9. For non-event memories, set all event-related fields to null.
10. Do not infer hidden attributes, intentions, diagnoses or relationships.
11. Do not extract greetings, temporary formatting requests, unsupported assistant suggestions, secrets or authentication credentials.
12. Use lower_snake_case for predicate.
13. Return only valid JSON matching the required schema.
```

User Prompt：

```
Current user ID:
{user_id}

Archived conversation messages:
{messages}

Extract durable long-term memory candidates.
```

Output Schema：

```
{
    "entities": [
        {
            "local_entity_id": "entity_1",

            "name": "Agent Memory System",

            "type": "project",

            "aliases": [
                "记忆系统项目"
            ]
        }
    ],

    "memories": [
        {
            "memory_type": "event",

            "content": "用户正在开发 Agent Memory System",

            "subject_entity_id": "user",

            "predicate": "works_on",

            "object_entity_id": "entity_1",

            "object_value": null,

            "event_status": "ongoing",

            "start_time": null,

            "end_time": null,

            "original_time_text": "正在",

            "confidence": 0.95,

            "source_message_ids": [
                "msg_000001"
            ]
        }
    ]
}
```

字段约束：

| 字段 | 约束 |
| --- | --- |
| local_entity_id | 当前 LLM 输出内部唯一标识，不作为数据库 ID；`user` 为当前用户实体的保留值 |
| name | 实体标准名称，不能为空 |
| type | 可选值为 `person`、`organization`、`product`、`project`、`location`、`concept`、`other` |
| aliases | 实体别名数组，没有别名时返回空数组 |
| memory_type | 可选值为 `fact`、`preference`、`event`、`profile` |
| content | 一条可独立理解的原子记忆，不能为空 |
| subject_entity_id | 必须引用 `entities` 中的 `local_entity_id` 或保留值 `user` |
| predicate | 使用 lower_snake_case，不得为空 |
| object_entity_id | 宾语是实体时填写 `entities` 中的 `local_entity_id` 或保留值 `user`；否则为 `null` |
| object_value | 宾语是普通值时填写字符串；否则为 `null` |
| event_status | `memory_type=event` 时必填，可选值为 `occurred`、`ongoing`、`planned`、`cancelled`、`unknown`；其他类型必须为 `null` |
| start_time | 事件开始时间；无法可靠确定时为 `null` |
| end_time | 事件结束时间；无法可靠确定时为 `null` |
| original_time_text | 用户原始时间表达；没有时间表达时为 `null` |
| confidence | 范围为 `0.0` 至 `1.0`，表示 LLM 对抽取正确性的置信度 |
| source_message_ids | 必须是当前 Archive 中实际存在的 message_id，且至少包含一条用户消息 |

`object_entity_id` 和 `object_value` 必须且只能有一个非 `null`。`memory_type` 不是 `event` 时，`event_status`、`start_time`、`end_time` 和 `original_time_text` 必须全部为 `null`。

为保证后续 `search_text` 能稳定进入 BGE-M3 的 1024 Token 输入上限，Structured Output 还必须满足以下字符边界：

```yaml
memory_extraction:
  max_memory_content_characters: 512
  max_entity_name_characters: 128
  max_entity_alias_count_per_candidate: 32
  max_entity_alias_characters: 128
  max_predicate_characters: 64
  max_object_value_characters: 256
  max_original_time_text_characters: 128
  max_stored_entity_alias_count: 50
  max_search_text_tokens: 1024
```

字符数按 Unicode Code Point 计算。超过任一字段限制属于 Structured Output 校验失败，第一次失败时使用相同 Archive 和更严格的纠错 Prompt 重试一次；第二次仍失败返回 `llm_invalid_output`。应用不得静默截断 LLM 字段。

Entity 对齐时，候选 aliases 先执行 NFKC、去空白、去重并排序。已有 Entity 的 aliases 与新 aliases 合并后最多保存 `50` 条：优先保留已有合法 aliases，再按排序顺序追加新 aliases，达到上限后忽略剩余新 aliases并记录指标 `memory_entity_alias_omitted_total`。不得因 Alias 超限删除已有 Alias。

`abstraction_level` 不由 LLM 输出。MVP 写入长期记忆节点时统一设置为 `0`。

Structured Output 校验失败时，允许使用相同输入重新调用 LLM 一次。第二次仍失败则返回 `llm_invalid_output`，不得使用不完整 JSON 写入图数据库。

#### 2.1.7 抽取结果校验与标准化

LLM 返回后，Memory Extraction Service 必须在应用层执行以下校验：

1. JSON 必须符合固定 Schema，未知字段可以忽略，但必填字段不得缺失。
2. 所有 `local_entity_id` 在当前结果中必须唯一。
3. `subject_entity_id` 和 `object_entity_id` 中的实体引用必须指向已存在的 local ID 或保留值 `user`。
4. `object_entity_id` 和 `object_value` 必须且只能有一个非 `null`。
5. 所有 `source_message_ids` 必须属于当前 Archive。
6. 每条 Memory 的来源中必须至少包含一条 `role=user` 的消息。
7. `confidence` 必须位于 `0.0` 至 `1.0`，超出范围时判定输出无效，不进行静默截断。
8. `content`、实体名称和 `predicate` 不得为空。
9. `memory_type=event` 时 `event_status` 必须存在；其他记忆类型的全部事件字段必须为 `null`。
10. 候选记忆数量不得超过 `max_memory_candidates_per_archive`；候选实体数量不得超过 `max_entity_candidates_per_archive`。
11. `content`、Entity `name`、单个 Alias、Alias 数量、`predicate`、`object_value` 和 `original_time_text` 必须满足本节固定字符边界；超限属于输出无效，不得截断后继续。
12. 完全相同的候选 Memory 在同一次输出中只保留一条，并合并其 `source_message_ids`。
13. 包含 `[REDACTED_SECRET]` 的内容不得作为长期记忆 `content` 或 `object_value` 保存。

校验通过后，应用层必须为每条候选 Memory 计算确定性的来源时间中间字段：

```
candidate_source_time = max(
    source_message_ids 中 role=user 消息的 timestamp
)
```

`candidate_source_time` 由应用层根据当前 Archive 原始消息计算，不由 LLM 输出。每条候选至少包含一条用户消息，因此该字段必须存在；若对应用户消息缺失或 `timestamp` 非法，则判定当前 Archive 无效并返回 `invalid_archive`。应用层应在写入 `memory_extraction_task.extraction_result` 前，将 `candidate_source_time` 附加到对应候选 Memory。该字段不参与 `candidate_fingerprint` 计算，因为 `source_message_ids` 已参与指纹且 Archive 消息时间不可变；后续重试必须复用已保存的 `candidate_source_time`，不得重新采用服务器当前时间。

校验通过后，应用层先对候选 Memory 生成规范化指纹：

```
candidate_fingerprint = SHA256(
    canonical_json({
        memory_type,
        content,
        subject_entity_id,
        predicate,
        object_entity_id,
        object_value,
        event_status,
        start_time,
        end_time,
        original_time_text,
        sorted(source_message_ids)
    })
)
```

再生成 Evidence 唯一标识：

```
evidence_id = SHA256(
    archive_id
    + ":"
    + candidate_fingerprint
)
```

`canonical_json` 必须使用固定字段顺序、UTF-8 编码、无多余空白，并对 `source_message_ids` 排序。完整结构化结果写入 `memory_extraction_task.extraction_result` 后，才进入实体对齐和图谱写入阶段。后续重试必须复用该结果，从而保证候选指纹和 `evidence_id` 不发生变化。

如果 Archive 包含有效消息，但 LLM 返回合法的空结果：

```
{
    "entities": [],
    "memories": []
}
```

说明本批消息中没有值得跨会话保存的长期记忆。服务应保存该空 `extraction_result`，不写入 Neo4j，将任务标记为 `completed`，然后提交 Kafka Offset；空结果属于正常完成，不属于失败。

#### 2.1.8 时间标准化

时间处理规则：

1. LLM 必须将用户原始时间表达保存至 `original_time_text`。
2. 输入中包含明确时区或 UTC Offset 的完整时间时，统一转换为 ISO 8601 UTC 字符串后写入 `start_time` 或 `end_time`。
3. 只能确定到年份、月份或日期时，允许分别使用 `YYYY`、`YYYY-MM` 或 `YYYY-MM-DD` 格式保存，不填充虚假的小时、分钟和秒。
4. 只有同时具备来源消息 `timestamp` 和明确时区时，才将“明天”“下周”“上个月”等相对时间转换为绝对时间。
5. MVP 不在 Session 或 Context Archive 中保存默认时区。只有用户文本本身明确包含时区、UTC Offset 或可无歧义确定的绝对时区信息时，才允许解析相对时间；否则保留 `original_time_text`，并将 `start_time` 和 `end_time` 设为 `null`。
6. 完全无法识别时间表达时，`start_time`、`end_time` 和 `original_time_text` 均可为 `null`。
7. 不同时间发生的同类事件默认视为不同事件，不因文本相似而直接合并。

#### 2.1.9 Neo4j 记忆图谱数据模型

MVP 使用 Neo4j 保存实体、长期记忆和来源证据。每个用户的记忆通过 `user_id` 隔离，实体对齐和记忆合并不得跨用户执行。

**Entity 节点**

```
(:Entity {
    entity_id: "entity_uuid",
    user_id: "user_001",
    entity_key: "sha256_value",
    canonical_name: "Agent Memory System",
    normalized_name: "agent memory system",
    entity_type: "project",
    aliases: ["记忆系统项目"],
    created_time: 1720000020,
    updated_time: 1720000020
})
```

LLM 输出中的 `name` 和 `type` 在写入图谱时分别映射为 `canonical_name` 和 `entity_type`。

当前用户实体采用确定性 ID：

```
entity_id = "user:" + user_id
```

**Memory 节点**

```
(:Memory {
    memory_id: "memory_uuid",
    user_id: "user_001",
    memory_type: "event",
    content: "用户正在开发 Agent Memory System",
    subject_entity_id: "user:user_001",
    predicate: "works_on",
    object_entity_id: "entity_uuid",
    object_value: null,
    status: "active",
    abstraction_level: 0,
    event_status: "ongoing",
    start_time: null,
    end_time: null,
    original_time_text: "正在",
    confidence: 0.95,
    importance: 0.55,
    latest_source_time: 1720000000,
    first_seen_time: 1720000020,
    last_seen_time: 1720000020,
    retrieval_count: 0,
    last_retrieved_time: null,
    last_consolidated_time: null,
    memory_version: 1,
    created_time: 1720000020,
    updated_time: 1720000020
})
```

`status` 可选值：

```
active
superseded
conflicted
```

`subject_entity_id`、`object_entity_id` 和 `object_value` 是为了支持高效去重和候选召回而保存的结构化字段。`object_entity_id` 非 `null` 时，应用层必须建立 `OBJECT` 图关系并将 `object_value` 设为 `null`；`object_value` 非 `null` 时，不建立 `OBJECT` 图关系，并将 `object_entity_id` 设为 `null`。仅 `memory_type=event` 的 Memory 写入 `event_status`、`start_time`、`end_time` 和 `original_time_text`；其他类型将这些字段统一写为 `null`。

时间字段定义：

- `first_seen_time`：Memory 第一次创建成功时的服务器 Unix timestamp，后续不得修改。
- `last_seen_time`：最近一次成功建立新的 `Evidence-[:SUPPORTS]->Memory` 关系时的服务器 Unix timestamp；同一 Evidence 幂等重试不得更新。
- `latest_source_time`：当前 Memory 所有 Evidence 中，用户来源消息 `timestamp` 的最大值。新增 Evidence 时更新为 `max(old_latest_source_time, current_user_source_max_timestamp)`。
- `created_time`：Memory 节点创建服务器时间。
- `updated_time`：记忆萃取最近一次修改已有 Memory 的内容、状态、事件时间或置信度字段的服务器时间；检索统计和巩固更新不修改它。Memory 的结构字段创建后不可修改。

`retrieval_count` 和 `last_retrieved_time` 由 `2.2 记忆检索` 模块维护，分别表示该 Memory 被检索接口返回的累计次数和最近返回时间。记忆萃取创建新 Memory 时分别初始化为 `0` 和 `null`；记忆萃取不得根据原始对话修改这两个检索统计字段。MVP 尚未实现 Agent 使用反馈，因此不得将这两个字段解释为真实使用次数和真实使用时间。

`last_consolidated_time` 由 `2.3 巩固与遗忘` 模块维护，表示该 Memory 最近一次完成重要性重算的评估时间。记忆萃取创建新 Memory 时初始化为 `null`，记忆检索不得修改该字段。

`memory_version` 是 Memory 内容状态及巩固输入的乐观并发版本号。新 Memory 创建时初始化为 `1`。记忆萃取每次修改已有 Memory 的 `content`、`confidence`、`status`、事件时间、`latest_source_time`、`last_seen_time`，或者将新的 `Evidence-[:SUPPORTS]->Memory` 关系连接到已有 Memory 时，必须执行 `memory_version = memory_version + 1`。同一事务中即使同时发生多个字段变化并新增 Evidence，也只递增一次。已有 Memory 的结构字段不得修改。记忆检索更新 `retrieval_count`、`last_retrieved_time` 时不得修改该字段；巩固与遗忘更新 `importance`、`last_consolidated_time` 时也不得修改该字段。

Memory 字段所有权：

| 模块 | 允许创建或修改的字段 |
| --- | --- |
| Memory Extraction Worker | 创建新 Memory 时写入全部初始字段；对已有 Memory 只允许修改 `content`、`status`、`event_status`、`start_time`、`end_time`、`original_time_text`、`confidence`、`latest_source_time`、`last_seen_time`、`memory_version` 和 `updated_time` |
| Memory Retrieval Service | 只允许修改 `retrieval_count` 和 `last_retrieved_time` |
| Consolidation Worker | 只允许修改 `importance` 和 `last_consolidated_time` |

以下字段构成 Memory 的结构身份，创建后不可修改：

```
memory_type
subject_entity_id
predicate
object_entity_id
object_value
```

候选的任一结构字段与已有 Memory 不一致时，不得通过 `MERGE` 修改旧节点。明确的新值或纠正语义使用 `CREATE + SUPERSEDE`；无法判断新旧有效性时使用 `CREATE + CONFLICT`；时间不同的独立事件使用 `CREATE`。因此已有 Memory 的 `SUBJECT` 和 `OBJECT` 关系也不需要被替换或删除。

`memory_id`、`user_id`、`first_seen_time` 和 `created_time` 创建后不得修改。`abstraction_level` 在 MVP 创建时固定为 `0`，后续模块不得修改。Memory Extraction Worker 只在创建新 Memory 时写入初始 `importance`、`retrieval_count`、`last_retrieved_time` 和 `last_consolidated_time`，不得在更新已有 Memory 时覆盖这些字段。

所有模块必须使用字段级 `SET` 更新，只发送本模块拥有的字段。禁止使用 `SET m = row`、整节点 Map 替换，或把其他模块维护的字段包含在更新 Map 中；否则可能覆盖检索统计、巩固结果或最新 `memory_version`。

**Evidence 节点**

```
(:Evidence {
    evidence_id: "sha256_value",
    user_id: "user_001",
    archive_id: "archive_000001",
    session_id: "session_001",
    source_message_ids: ["msg_000001"],
    source_time_start: 1720000000,
    source_time_end: 1720000000,
    extracted_content: "用户正在开发 Agent Memory System",
    prompt_version: "memory_extraction_v1",
    created_time: 1720000020
})
```

Evidence 节点用于保存 Archive 与最终长期记忆之间的来源关系。同一条 Memory 可以由多个 Evidence 支持，同一 Archive 的重试通过唯一 `evidence_id` 保证不会重复写入证据。

Evidence 字段生成规则：

- `source_time_start`：`source_message_ids` 对应全部来源消息 `timestamp` 的最小值。
- `source_time_end`：`source_message_ids` 对应全部来源消息 `timestamp` 的最大值。
- `extracted_content`：当前候选 Memory 通过 Structured Output 校验后、进入 Reconciliation 前的原子 `content`；即使最终执行 `MERGE`，仍保留候选原始抽取文本。
- `prompt_version`：使用 `memory_extraction.prompt_version` 配置值。
- `created_time`：Evidence 第一次创建成功的服务器 Unix timestamp；幂等重试不得修改。

关系类型：

| 关系 | 含义 |
| --- | --- |
| `(Memory)-[:SUBJECT]->(Entity)` | Memory 的主体实体 |
| `(Memory)-[:OBJECT]->(Entity)` | `object_entity_id` 非空时连接对象实体 |
| `(Evidence)-[:SUPPORTS]->(Memory)` | 原始 Archive 证据支持某条长期记忆 |
| `(Memory)-[:SUPERSEDES]->(Memory)` | 新记忆取代旧记忆 |
| `(Memory)-[:CONFLICTS_WITH]->(Memory)` | 两条记忆存在未解决冲突 |

Neo4j Constraint 与 Index：

```
CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
FOR (e:Entity)
REQUIRE e.entity_id IS UNIQUE;
```

```
CREATE CONSTRAINT entity_key_unique IF NOT EXISTS
FOR (e:Entity)
REQUIRE e.entity_key IS UNIQUE;
```

```
CREATE CONSTRAINT memory_id_unique IF NOT EXISTS
FOR (m:Memory)
REQUIRE m.memory_id IS UNIQUE;
```

```
CREATE CONSTRAINT evidence_id_unique IF NOT EXISTS
FOR (e:Evidence)
REQUIRE e.evidence_id IS UNIQUE;
```

```
CREATE INDEX memory_user_type_status IF NOT EXISTS
FOR (m:Memory)
ON (m.user_id, m.memory_type, m.status);
```

```
CREATE INDEX memory_subject_predicate IF NOT EXISTS
FOR (m:Memory)
ON (m.user_id, m.subject_entity_id, m.predicate, m.status);
```

`entity_key` 计算方式：

```
entity_key = SHA256(
    user_id
    + ":"
    + entity_type
    + ":"
    + normalized_name
)
```

#### 2.1.10 实体对齐与别名合并

实体对齐用于判断 LLM 输出的候选实体是否已经存在于当前用户的记忆图谱中。MVP 仅实现确定性匹配，按以下顺序执行：

1. 当 `local_entity_id=user` 时，直接映射至 `entity_id=user:{user_id}`。用户实体不参与普通名称和别名对齐；不存在时按固定字段创建：

```
{
    "entity_id": "user:user_001",
    "user_id": "user_001",
    "entity_key": "SHA256(user_001:person:current_user)",
    "entity_type": "person",
    "canonical_name": "current_user",
    "normalized_name": "current_user",
    "aliases": [],
    "created_time": 1720000020,
    "updated_time": 1720000020
}
```

2. 将候选实体的 `name` 执行 Unicode NFKC、转小写、去除首尾空格和连续空白标准化，生成 `normalized_name`。
3. 根据 `user_id + type + normalized_name` 计算 `entity_key`，其中 LLM 的 `type` 映射为图谱字段 `entity_type`，优先执行精确匹配。
4. 若未匹配，查询当前用户、相同 `entity_type` 下 `canonical_name` 或 `aliases` 完全相同的实体。
5. 若仍未匹配，则创建新实体，不使用模糊相似度强制合并。
6. 实体对齐仅在同一 `user_id` 范围内执行，MVP 不做跨用户全局实体合并。

别名更新时必须去重，并保留原 `canonical_name`。除非新名称是用户明确给出的正式名称，否则不得自动替换已有 `canonical_name`。实体对齐阶段可以查询全部候选实体，但 Neo4j 写事务只允许创建或更新被最终非 `SKIP` Memory 写入计划引用的 Entity；未被任何有效 Memory 引用的候选 Entity 不得单独写入或更新别名，避免产生孤立节点。全文检索、向量相似度和模糊实体合并在后续版本中实现。

MVP 不直接创建 `Entity-[:RELATED_TO]->Entity` 关系。实体之间的事实、偏好、画像和事件关系统一通过 Memory 节点及其 `SUBJECT`、`OBJECT` 关系表达；复杂多实体语义拆分为多条原子 Memory，避免同一知识在图谱中重复保存。

#### 2.1.11 记忆候选召回与新旧记忆处理

每条候选 Memory 在写入前，必须检索当前用户图谱中的相关已有记忆。候选召回条件：

1. `user_id` 相同。
2. `memory_type` 相同。
3. `subject_entity_id` 相同。
4. `predicate` 完全相同。
5. `status` 为 `active` 或 `conflicted`。
6. 查询结果必须使用以下确定性顺序排序后最多返回 20 条：

```
status_priority ASC,
coalesce(latest_source_time, 0) DESC,
memory_id ASC
```

其中 `status_priority` 固定为：

```
active = 0
conflicted = 1
```

对应 Cypher 排序逻辑：

```cypher
ORDER BY CASE m.status
             WHEN 'active' THEN 0
             WHEN 'conflicted' THEN 1
             ELSE 2
         END ASC,
         coalesce(m.latest_source_time, 0) DESC,
         m.memory_id ASC
LIMIT 20
```

MVP 仅使用上述确定性条件召回候选，不在此阶段执行谓词语义相似匹配。不同谓词的同义归一，例如 `lives_in` 与 `resides_in`，在后续版本中实现。应用层在召回到一个或多个候选时调用一次 LLM Reconciliation，最终操作类型固定为：

```
CREATE
MERGE
SUPERSEDE
CONFLICT
SKIP
```

操作含义：

| action | 处理方式 |
| --- | --- |
| CREATE | 创建新的 Memory 节点，并连接 Evidence 和实体 |
| MERGE | 不创建重复 Memory；将 Evidence 连接至结构字段完全一致的已有 Memory，必要时补充 `content` 和被有效 Memory 引用实体的别名，并更新置信度、事件字段与 `last_seen_time`；不得修改已有 Memory 的结构字段 |
| SUPERSEDE | 创建新的 active Memory，将旧 Memory 标记为 superseded，并建立 `(new)-[:SUPERSEDES]->(old)` |
| CONFLICT | 保留新旧两条 Memory，将双方状态标记为 conflicted，并固定建立 `(new_memory)-[:CONFLICTS_WITH]->(old_memory)`；查询时使用无方向匹配，不创建重复的反向关系 |
| SKIP | 候选不满足长期记忆条件或已经由当前 Evidence 处理，不写入 |

`memory_version` 更新规则：

1. `CREATE` 创建的新 Memory 将 `memory_version` 初始化为 `1`。
2. `MERGE` 只要更新已有 Memory 的 `content`、`confidence`、`latest_source_time`、`last_seen_time` 或事件字段，就必须将目标 Memory 的 `memory_version` 加 `1`。`MERGE` 不得修改结构字段。
3. `SUPERSEDE` 将旧 Memory 的 `status` 改为 `superseded` 时，旧 Memory 的 `memory_version` 加 `1`；新 Memory 初始化为 `1`。
4. `CONFLICT` 将新旧 Memory 标记为 `conflicted` 时，所有被修改的已有 Memory 分别将 `memory_version` 加 `1`；新 Memory 初始化为 `1`。
5. 将新的 `Evidence-[:SUPPORTS]->Memory` 关系连接至已有 Memory 时，目标 Memory 的 `memory_version` 必须加 `1`。即使没有修改 `content`、`confidence`、`latest_source_time`、`last_seen_time` 或其他内容状态字段，也必须递增，因为独立 Archive Evidence 数量是巩固计算的输入。若新增 Evidence 同时引起其他字段变化，同一事务内仍然只增加一次，不得因多个变化重复递增。

Archive 内候选聚合规则：

**A. 指向已有 Memory 的候选聚合**

1. 每条候选先独立完成校验、指纹生成、Evidence ID 计算、实体对齐和 Reconciliation。
2. 在生成最终图谱写入计划前，按照 `archive_id + target_memory_id` 对所有指向已有 Memory 的非 `SKIP` 候选分组。
3. 同一组全部为 `MERGE` 时：
   - 每个合法候选仍创建或复用自己的 Evidence，并分别建立 `SUPPORTS`；
   - 目标 Memory 只更新一次，`memory_version` 只递增一次；
   - `last_seen_time` 使用本次 Neo4j Transaction 的服务器时间；
   - `latest_source_time` 取该组全部新 Evidence 用户来源消息时间的最大值；
   - 置信度每个 Archive 最多强化一次，使用该组候选中的最大 `new_confidence` 代入合并公式；
   - 多个非空 `merged_content` 必须规范化后完全一致，否则返回 `reconciliation_plan_conflict`，不得按候选数组顺序选择。
4. 同一 `target_memory_id` 在当前 Archive 中同时出现不同操作类型，或者出现两个及以上 `SUPERSEDE` / `CONFLICT` 操作时，返回 `reconciliation_plan_conflict`，不得执行部分写入。

**B. 实体对齐后的新 Memory 候选聚合**

1. 对所有最终操作为 `CREATE` 的候选，先将 `subject_entity_id` 和 `object_entity_id` 替换为实体对齐后的最终数据库 `entity_id`，再计算临时字段：

```
aligned_memory_key = SHA256(
    canonical_json({
        memory_type,
        final_subject_entity_id,
        predicate,
        final_object_entity_id,
        object_value,
        event_status,
        start_time,
        end_time
    })
)
```

2. `aligned_memory_key` 只用于当前 Archive 的事务前写入计划聚合，不写入 Neo4j，也不代替跨 Archive 的 Memory Reconciliation。`object_entity_id` 和 `object_value` 仍必须且只能有一个非 `null`。
3. 同一 Archive 中 `aligned_memory_key` 相同的多个 `CREATE` 候选视为同一条原子新 Memory，避免不同 `local_entity_id` 在对齐到同一数据库 Entity 后创建重复节点。
4. 同组候选只创建一条新 Memory：
   - 为该组预先生成一个 `memory_id`，全部候选 Evidence 均连接至该 Memory；
   - 每个原候选继续使用自己的 `candidate_fingerprint` 和 `evidence_id`，保留各自 `Evidence.extracted_content` 与来源消息；
   - `confidence` 使用组内最大值；
   - `latest_source_time` 使用组内最大 `candidate_source_time`；
   - `last_seen_time` 和 `first_seen_time` 使用本次 Neo4j Transaction 的服务器时间；
   - `memory_version` 初始化为 `1`，不得因组内候选数量重复递增。
5. 新 Memory 的 `content` 按以下确定性规则选择：
   - 先对候选 `content` 执行 Unicode NFKC、连续空白压缩和首尾空白去除；
   - 若规范化结果一致，使用该规范化内容；
   - 若规范化结果不同，按 `confidence DESC`、`candidate_source_time DESC`、`candidate_fingerprint ASC` 排序，使用第一条候选的原子 `content`；其他候选原文仍保存在各自 Evidence 中；
   - 若应用层检测到同组候选存在显式否定、互斥事件状态或无法由相同结构字段表达的冲突，返回 `reconciliation_plan_conflict`，不得强制聚合。
6. `aligned_memory_key` 不同的 `CREATE` 候选分别创建 Memory。完成已有 Memory 聚合和新 Memory 聚合后，生成不可变写入计划；后续 Neo4j Transaction 不得依赖候选原始数组顺序。

不同记忆类型的处理规则：

**Fact**

- 内容和对象一致时执行 `MERGE`。
- 对同一主体和谓词出现不同对象时，如果用户明确表示“之前说错了”“现在是”等纠正语义，且新候选 `candidate_source_time` 不早于旧 Memory 的 `latest_source_time`，则执行 `SUPERSEDE`。
- 无法确定新旧信息哪一条有效时执行 `CONFLICT`。

**Preference**

- 相同偏好重复出现时执行 `MERGE` 并提高置信度。
- 同一偏好维度出现明确变化，且新候选 `candidate_source_time` 不早于旧 Memory 的 `latest_source_time` 时，新偏好 `SUPERSEDE` 旧偏好；延迟到达的旧偏好不得覆盖较新的偏好。
- 同时喜欢多个对象不属于冲突，分别创建或合并对应记忆。

**Profile**

- 同一画像属性和值一致时执行 `MERGE`。
- 职业、角色、所在地等可变化属性出现明确新值，且新候选 `candidate_source_time` 不早于旧 Memory 的 `latest_source_time` 时执行 `SUPERSEDE`。
- 出生日期等相对稳定属性出现矛盾但没有明确纠正时执行 `CONFLICT`。

**Event**

- 参与者、事件类型和时间范围一致或高度重叠时执行 `MERGE`。
- 相似文本但时间不同的事件执行 `CREATE`，不得覆盖旧事件。
- 计划事件后来被取消时，必须创建一条 `event_status=cancelled` 的新 Event Memory，并建立 `(cancelled_event)-[:SUPERSEDES]->(planned_event)`；不得直接把原计划事件节点修改为 cancelled。

LLM Reconciliation 输入仅包含当前候选 Memory、应用层生成的 `candidate_source_time`，以及按照上述确定性顺序返回的最多 20 条已有候选记忆。已有候选至少提供 `memory_id`、`content`、结构字段、事件字段、`status`、`confidence` 和 `latest_source_time`。示例输入：

```
{
    "candidate": {
        "memory_type": "preference",
        "content": "用户现在偏好中文回复",
        "subject_entity_id": "user:user_001",
        "predicate": "prefers_language",
        "object_entity_id": null,
        "object_value": "中文",
        "candidate_source_time": 1720000100
    },
    "existing_memories": [
        {
            "memory_id": "memory_000001",
            "memory_type": "preference",
            "content": "用户偏好英文回复",
            "subject_entity_id": "user:user_001",
            "predicate": "prefers_language",
            "object_entity_id": null,
            "object_value": "英文",
            "status": "active",
            "confidence": 0.92,
            "latest_source_time": 1720000000
        }
    ]
}
```

Reconciliation 必须使用 `candidate_source_time` 与已有 Memory 的 `latest_source_time` 判断延迟到达和新旧顺序，不得使用 Archive 创建时间、任务执行时间或服务器当前时间替代。输出 Schema：

```
{
    "action": "MERGE",

    "target_memory_id": "memory_000001",

    "reason_code": "same_semantic_memory",

    "merged_content": null
}
```

`reason_code` 可选值：

```
new_memory
same_semantic_memory
additional_evidence
explicit_correction
newer_value
unresolved_contradiction
different_event_time
not_durable
invalid_candidate
```

LLM 不得输出自由形式的推理过程。`target_memory_id` 只能引用输入候选列表中的 ID；`CREATE` 和 `SKIP` 时允许为 `null`。当 `reason_code=additional_evidence` 且新候选包含已有 Memory 未保存的重要信息时，`merged_content` 必须给出融合后的内容；完全重复时为 `null`，应用层保留原 `content`。应用层必须再次校验融合内容只能来自新旧两条输入记忆。

#### 2.1.12 置信度与重要性初始化

每条 Memory 的最终置信度直接使用经过应用层校验的 LLM `confidence`：

```
final_confidence = round(
    llm_confidence,
    4
)
```

由于每条候选 Memory 都必须至少包含一条用户消息作为来源，MVP 不再额外输出或计算 `evidence_strength` 和 `source_reliability`。

MVP 的重要性使用记忆类型固定初始值，不要求 LLM 输出额外重要性信号：

| memory_type | importance |
| --- | ---: |
| profile | 0.75 |
| fact | 0.70 |
| preference | 0.65 |
| event | 0.55 |

当新 Evidence 合并至已有 Memory 时，置信度按以下方式保守增加：

```
merged_confidence = min(
    1.0,
    old_confidence
    + (1 - old_confidence) * new_confidence * 0.25
)
```

新 Memory 创建时使用上述固定初始值。新 Evidence 合并至已有 Memory 时，记忆萃取不直接增减 `importance`，保留当前值；`2.3 巩固与遗忘` 模块根据记忆类型、置信度、独立 Archive Evidence 数量和用户来源时间因素定期重新计算动态 `importance`。

#### 2.1.13 图谱写入事务与幂等

实体候选查询、已有 Memory 候选查询和必要的 LLM Reconciliation 必须在开启 Neo4j 写事务之前完成，避免在数据库事务中等待 LLM。处理分为事务前准备和事务内写入两个阶段。

事务前准备：

1. 根据每条候选记忆计算确定性的 `candidate_fingerprint` 和 `evidence_id`，查询 Evidence 是否已经存在并已连接 Memory；已处理的候选直接标记为跳过。
2. 查询或计算候选实体的精确匹配结果，先建立 `local_entity_id -> entity_id` 对齐映射；此阶段不得立即创建新 Entity。
3. 根据 `user_id`、`memory_type`、`subject_entity_id`、`predicate` 和 `status` 召回已有 Memory。
4. 必要时调用 LLM Reconciliation，确定每条候选的 `CREATE`、`MERGE`、`SUPERSEDE`、`CONFLICT` 或 `SKIP` 操作。
5. 按照 `2.1.11` 的 Archive 内候选聚合规则，先对指向同一已有 Memory 的操作生成单一更新计划，再基于实体对齐后的 `aligned_memory_key` 对 `CREATE` 候选生成单一新 Memory 创建计划；若发现操作、融合内容或同组候选存在无法确定处理的冲突，返回 `reconciliation_plan_conflict`，不得开启 Neo4j 写事务。
6. 对每条已有 Memory 计算布尔字段 `increment_memory_version`。只要聚合后的操作会修改内容状态字段，或者会将一个或多个新的 `Evidence-[:SUPPORTS]->Memory` 关系连接到该 Memory，该字段就设为 `true`；同一 Archive、同一事务内只能递增一次。
7. 为每个聚合后的新 Memory 组生成唯一 `memory_id`，并将组内全部 Evidence 写入计划指向同一 `memory_id`。新 Memory 的字段值必须按照 `2.1.11` 的确定性规则生成。
8. 从最终非 `SKIP` Memory 操作中收集实际引用的主体和客体 Entity，生成 `referenced_entity_write_set`。只有该集合中的 Entity 才能进入创建、复用或别名更新计划；没有被有效 Memory 引用的候选 Entity 必须丢弃。
9. 根据最终写入计划和当前图谱构建 `planned_index_sync_memory_set`，为每条计划写入或受 Entity 更新影响的 Memory 生成不含 aliases 的 `core_search_text`，并通过 TEI `/tokenize` 精确校验 Token 数。任一 `core_search_text` 超过 `1024` Token 时返回 `memory_search_text_too_long`，不得开启 Neo4j 写事务。该检查必须发生在图谱提交前，防止产生永久无法同步的 Memory。
10. 生成不可变的最终图谱写入计划，写事务内不得再次调用 LLM、重新执行候选召回、重新计算长度策略或按照原始候选顺序重新决策。

事务内写入：

1. 仅对事务前生成的 `referenced_entity_write_set` 使用 `MERGE` 创建、复用或更新 Entity 节点；禁止写入未被最终非 `SKIP` Memory 引用的候选 Entity。
2. 根据最终写入计划创建或更新 Memory 节点；新 Memory 将 `memory_version` 初始化为 `1`。对于已有 Memory，仅当 `increment_memory_version=true` 时执行一次 `memory_version = memory_version + 1`，不得在内容更新和 Evidence 写入步骤中分别重复递增。更新必须使用字段级 `SET`，只包含 Memory Extraction Worker 拥有的字段，禁止整节点 Map 覆盖。
3. 写入固定方向的 `SUPERSEDES`、`CONFLICTS_WITH` 等记忆间关系。
4. 使用 `MERGE` 创建 Evidence 节点，并建立 `SUPPORTS` 关系。写入计划已负责决定是否递增版本号，本步骤不得再次单独修改 `memory_version`。
5. 写入 Memory 与主体 Entity 之间的 `SUBJECT` 关系；仅当 `object_entity_id` 非空时写入 `OBJECT` 关系。
6. 提交 Neo4j Transaction。

跨 MongoDB 和 Neo4j 不使用分布式事务，依靠以下幂等机制保证重试安全：

- `memory_extraction_task.archive_id` 唯一，防止同一 Archive 创建多个任务。
- 已校验的 `extraction_result` 持久化后不再重新生成。
- `Evidence.evidence_id` 唯一，防止同一候选重复写入。
- Entity 使用唯一 `entity_key` 精确去重。
- Neo4j 写入使用 `MERGE` 和唯一约束。

如果 Neo4j Transaction 已提交，但 Retrieval Index 同步或 MongoDB 任务状态更新失败，Kafka 可能重新投递事件。重试时，Worker 按当前 Archive 的 `extraction_result` 重新计算全部 `candidate_fingerprint` 和 `evidence_id`；若这些 Evidence 均已存在并已通过 `SUPPORTS` 关联到 Memory，则跳过重复图谱写入，按照 `2.2.3 Retrieval Index 同步设计` 重新构建 `index_sync_memory_set` 并同步 Elasticsearch。只有索引同步成功后，才允许将任务更新为 `completed`。任务表不保存 Memory、Entity 结果 ID 数组。

完成顺序必须为：

```
Commit Neo4j Transaction

        |

Upsert index_sync_memory_set to Elasticsearch Retrieval Index

        |

Update memory_extraction_task = completed

        |

Commit Kafka Offset
```

不得在 Neo4j Transaction 和 Retrieval Index 同步完成前将任务标记为 `completed`。若 Neo4j 已提交但索引同步失败，重试时通过 Evidence 幂等规则跳过重复图谱写入，并重新执行索引同步。

#### 2.1.14 Memory Extraction 管理接口

记忆萃取主要由 Kafka 异步触发，不向外部 Agent 暴露同步萃取接口。MVP 提供以下内部管理接口，用于状态查询和人工重试。

**1. 查询萃取状态**

Endpoint：

```
GET /api/v1/memory/extraction/{user_id}/{archive_id}
```

Response：

```
{
    "user_id": "user_001",

    "archive_id": "archive_000001",

    "status": "completed",

    "attempt_count": 1,

    "last_error": null,

    "completed_time": 1720001000
}
```

**2. 人工重试萃取任务**

Endpoint：

```
POST /api/v1/memory/extraction/{user_id}/{archive_id}/retry
```

处理规则：

1. `user_id` 必须与 Extraction Task 和 Context Archive 的所属用户一致。查询或重试时必须同时使用 `user_id + archive_id` 过滤；不匹配时统一返回 HTTP `404` 和 `extraction_task_not_found`，不得泄露其他用户的资源是否存在。
2. 仅允许对 `status=failed` 且 `last_error.error_code` 属于失败处理表中“是否可人工重试=是”的任务执行。
3. `archive_not_found`、`archive_ownership_mismatch`、`invalid_archive`、`archive_too_large` 和 `reconciliation_plan_conflict` 等永久错误不得使用原 `extraction_result` 直接重试；接口返回 HTTP 409 和 `retry_not_allowed`。`reconciliation_plan_conflict` 只有在代码、Prompt 或人工数据修复后，才能通过专门管理操作清理或重建任务。
4. 将 `status` 修改为 `pending`，清空 `last_error`，`attempt_count` 不清零。
5. 已存在的 `extraction_result` 保留；若其不为空，Worker 重试时跳过 LLM 调用。
6. 接口生成新的 `event_id`，使用 `user_id` 作为 Kafka Message Key，将同一 `archive_id` 重新发布到 `context.archive.created` Topic，不重新创建 Context Archive。
7. Kafka 发布成功后返回 `pending`；发布失败时任务恢复或保持 `failed`，并使用 `last_error.error_code=kafka_publish_failed` 记录错误，允许再次调用重试接口。

Response：

```
{
    "user_id": "user_001",

    "archive_id": "archive_000001",

    "status": "pending"
}
```

#### 2.1.15 失败处理

标准错误码：

| 错误码 | 含义 | 是否可人工重试 |
| --- | --- | --- |
| archive_not_found | 根据 archive_id 未找到 Context Archive | 否 |
| archive_ownership_mismatch | Archive、事件和任务的用户或会话不一致 | 否 |
| invalid_archive | Archive 消息结构不合法 | 否 |
| archive_too_large | Archive 估算 token 总量超过 `max_archive_estimated_tokens` | 否 |
| llm_timeout | LLM 调用超时 | 是 |
| llm_request_failed | LLM 请求失败 | 是 |
| llm_invalid_output | Structured Output 两次校验均失败 | 是 |
| entity_alignment_failed | 实体对齐执行失败 | 是 |
| graph_query_failed | 查询已有记忆失败 | 是 |
| reconciliation_plan_conflict | 同一 Archive 对同一已有 Memory 或同一 `aligned_memory_key` 新 Memory 组无法形成确定性写入计划 | 否 |
| memory_search_text_too_long | 事务前构建的核心检索文本超过 1024 Token，禁止提交图谱写入计划 | 否 |
| graph_write_failed | Neo4j Transaction 写入失败 | 是 |
| retrieval_index_write_failed | Elasticsearch Retrieval Index 或 Memory Embedding 同步失败 | 是 |
| kafka_publish_failed | 人工重试事件发布失败 | 是 |

失败处理规则：

1. 任意阶段失败时，将任务 `status` 修改为 `failed`，并将错误码、失败阶段和错误描述写入 `last_error`。
2. Neo4j 写入必须使用事务，事务失败时不得保留本批次的部分图谱修改。
3. 已经持久化的 `extraction_result` 不因后续失败而删除。
4. 只有任务 `status=failed` 和 `last_error` 已成功写入 MongoDB 后，Worker 才允许提交当前 Kafka Offset；若失败状态写入失败，则不得提交 Offset。
5. 可恢复错误通过人工重试接口重新发布事件；永久错误不得重试，除非原始 Archive 数据已被修复。
6. 所有日志必须包含 `task_id`、`archive_id`、`user_id`、`failed_stage` 和 `attempt_count`；`session_id` 可从 Context Archive 获取并在可用时记录。

#### 2.1.16 MVP 实现边界

本阶段必须实现：

- 消费 `context.archive.created` Kafka 事件。
- Extraction Task 状态和 `archive_id` 幂等。
- Context Archive 查询、校验和预处理。
- Archive 输入 token 上限校验。
- LLM Structured Output、空结果处理及应用层 Schema 校验。
- 四类原子记忆抽取，知识型记忆与事件型记忆统一写入长期记忆图谱。
- Entity、Memory、Evidence 图谱模型。
- 用户范围内实体对齐和别名合并。
- 新旧记忆去重、更新和冲突关系。
- 同一 Archive 中指向同一已有 Memory 的候选聚合，以及实体对齐后具有相同 `aligned_memory_key` 的新 Memory 候选聚合与 `reconciliation_plan_conflict` 校验。
- 置信度与重要性初始化。
- Memory 字段所有权、字段级更新和禁止整节点覆盖。
- Neo4j 事务写入和重复任务幂等。
- 创建或修改 Memory 后同步 Elasticsearch Retrieval Index。
- 状态查询和人工重试接口。

MVP 暂不实现：

- 跨用户的全局实体对齐。
- 全文检索、向量相似度和模糊实体合并。
- 情感字段抽取与情绪分析。
- 自动生成跨多个 Archive 的高层摘要记忆。
- 独立经验记忆抽取和任务执行经验归纳。
- 人工审核工作流。
- MongoDB 与 Neo4j 分布式事务。
- 自动重试、Retry Topic、Dead Letter Topic 和 Outbox。
- 基于独立 Archive Evidence、置信度和时间衰减的动态重要性调整与软遗忘；这些内容在 `2.3 巩固与遗忘` 中设计。
- 基于 Agent 真实使用反馈、成功率或显式反馈的长期强化。

### 2.2 记忆检索

#### 2.2.1 整体架构

记忆检索模块负责根据当前用户问题或 Agent 子任务，从长期记忆中召回与当前任务相关、可信且仍然有效的 Memory，并以结构化结果返回给外部 Agent。直接候选来自 Elasticsearch；图谱扩展候选先从 Neo4j 权威图谱中发现，再通过 Elasticsearch Multi Get 校验索引文档存在。只有已经完成 Retrieval Index 同步的 Memory 才允许进入最终候选集合。检索模块不直接读取 Context Archive，不在检索阶段创建、修改或推断新的长期记忆。

最小 MVP 使用 Elasticsearch 与 Neo4j：

- Elasticsearch 保存 Memory 的关键词索引和向量索引，执行 BM25 关键词召回和 Vector 语义召回。
- Neo4j 是长期记忆的权威数据源，保存 Memory、Entity 和 Evidence，并提供完整 Memory 加载、一跳图谱扩展以及召回统计更新。
- Memory Retrieval API 负责请求校验、Query 标准化、Embedding 调用、多路召回、RRF 融合、图谱扩展、基础 ACT-R 评分和 Top-K 返回。

MVP 不使用 LLM 改写 Query，不建立独立检索任务表，不保存 Retrieval Log，也不实现 Agent 使用反馈接口。外部 Agent 必须传入能够独立表达当前任务的 `query`。

整体流程：

```
Receive Retrieval Request

        |

Validate and Normalize Query

        |

        +-----------------------------+
        |                             |
        v                             v
BM25 Retrieval              Generate Query Embedding
                                      |
                                      v
                             Vector Retrieval
        |                             |
        +---------- RRF Fusion -------+

                     |

             Load Memory from Neo4j

                     |

             One-Hop Graph Expansion

                     |

       Filter Graph Candidates by Elasticsearch MGET

                     |

          Basic ACT-R Approximation

                     |

              Select Final Top-K

                     |

       Batch Load Evidence for Top-K

                     |

       Update Retrieval Statistics

                     |

            Return Memory Context
```

模块职责：

| 组件 | 职责 |
| --- | --- |
| Memory Retrieval API | 校验请求并协调完整检索流程 |
| Embedding Service | 为 Memory 检索文本和 Query 生成固定维度向量 |
| Elasticsearch | 保存检索索引，执行 BM25 和 Vector 召回 |
| Neo4j | 保存权威图谱，加载完整 Memory、执行一跳扩展、批量加载 Evidence 和更新召回统计 |
| 外部 Agent | 生成 Query，并将返回的长期记忆作为参考上下文加入后续推理 |

Memory Retrieval API、Embedding Service 适配器和检索协调逻辑可以部署在同一服务进程中，不要求拆分为独立微服务。

#### 2.2.2 检索范围与基本规则

记忆检索必须遵循以下规则：

1. 所有 Elasticsearch 和 Neo4j 查询必须包含 `user_id`，不得跨用户召回、扩展或更新记忆。
2. 默认只召回 `status=active` 的 Memory。
3. `status=conflicted` 的 Memory 默认不参与召回；请求显式设置 `include_conflicted=true` 时才允许返回。
4. `status=superseded` 的 Memory 默认不参与召回；请求显式设置 `include_history=true` 时才允许返回。
5. Elasticsearch 只负责候选召回，最终返回内容必须从 Neo4j 读取。
6. 检索服务不得修改 Memory 的 `content`、`memory_type`、事实状态、事件时间或图谱关系。
7. 空结果属于正常完成，返回空数组，不视为失败。
8. MVP 不执行跨用户检索、LLM Query 改写、多跳图推理、自动事实推断和结果摘要生成。

#### 2.2.3 Retrieval Index 同步设计

记忆萃取完成 Neo4j Transaction 后，必须将受本次萃取影响的 Memory 同步到 Elasticsearch。Elasticsearch 同步成功并完成 Refresh 后，才允许将 `memory_extraction_task.status` 更新为 `completed`。

需要同步的 Memory 集合 `index_sync_memory_set` 包括：

1. 本次 Archive 对应的 Evidence 直接支持的 Memory。
2. 与上述 Memory 存在 `SUPERSEDES` 或 `CONFLICTS_WITH` 关系的 Memory，用于同步新旧状态。
3. 与本次 LLM 输出中已经完成对齐的**非用户 Entity**通过 `SUBJECT` 或 `OBJECT` 相连的 Memory，用于保证 Entity 新增别名后，已有 Memory 的 `search_text` 也能更新。

当前用户保留实体：

```
entity_id = "user:" + user_id
```

不得触发关联 Memory 的批量重建索引，否则几乎所有以当前用户为主体的 Memory 都会被加入同步集合。MVP 为保证失败重试能够确定性恢复，不额外保存 Entity 变化清单，而是保守地重新索引本次输出中全部已对齐非用户 Entity 的关联 Memory。集合按照 `memory_id` 去重。

同步流程：

```
Commit Neo4j Transaction

        |

Build index_sync_memory_set

        |

Load Memory and Related Entity Names

        |

Build search_text

        |

Generate Memory Embedding

        |

Bulk Upsert Elasticsearch
with refresh=wait_for

        |

Check Every Bulk Item

        |

Update Extraction Task = completed

        |

Commit Kafka Offset
```

`search_text` 分为不可省略的核心文本和可选 Alias 扩展：

```text
core_search_text = join_non_empty_with_single_space(
    content,
    subject entity canonical_name,
    predicate,
    object entity canonical_name or object_value
)

search_text = core_search_text + aliases_that_fit_budget
```

处理规则：

1. 忽略 `null`、空字符串和重复值，所有片段执行 NFKC、首尾去空白和连续空格压缩。
2. 当主体或客体为当前用户保留实体 `user:{user_id}` 时，不将其 `canonical_name=current_user` 和 aliases 拼接到检索文本；用户隔离已经由 `user_id` Filter 保证。
3. `content`、主体名称、`predicate` 和客体名称或普通值属于核心字段，不能为了满足长度限制被省略、截断或重新排序。
4. 在 Neo4j 写事务前，Worker 必须为 `planned_index_sync_memory_set` 构建 `core_search_text`，通过同一 TEI 实例的 `/tokenize` 精确计数。核心文本超过 `1024` Token 时返回 `memory_search_text_too_long`，不得提交图谱事务。
5. Entity aliases 分别执行去重和 Unicode Code Point 升序排序，主体 aliases 先于客体 aliases。按该稳定顺序逐条尝试追加；只有追加后的完整 `search_text` 仍不超过 `1024` Token 时才保留该 Alias，否则跳过该 Alias并继续检查后续 Alias。
6. Alias 被跳过只影响 Elasticsearch 检索文本，不删除 Neo4j 中保存的 Alias。每个 Document 记录内部构建结果 `omitted_alias_count` 供日志和指标使用，但 MVP 不要求将该字段写入 Elasticsearch Mapping；累计指标为 `memory_search_text_omitted_alias_total`。
7. 最终 `search_text` 必须再次通过 `/tokenize` 校验 `1 <= token_count <= 1024`，相同 Neo4j 数据必须生成逐字节一致的文本。
8. Embedding 统一基于最终 `search_text` 生成；不得对索引文本静默截断。
9. Elasticsearch Document ID 固定使用 `memory_id`，重复 Upsert 不创建重复文档。
10. Bulk API 必须检查 HTTP 状态和每一个 Item 的执行结果；任意 Item 失败都视为本次同步失败。Elasticsearch Bulk 不提供跨 Item 原子性，部分成功的 Document 可能已经写入。
11. 使用 `refresh=wait_for`。只有全部 Item 成功后任务才允许进入 `completed`；Bulk 部分失败时，已成功写入的单个 Memory 可能暂时可被直接召回，最终返回仍必须经过 Neo4j 权威数据校验。人工重试通过相同 Document ID Upsert 使全部受影响文档最终收敛。

若 Neo4j 已提交但 Embedding 或 Elasticsearch 同步失败：

- 将 `memory_extraction_task.status` 更新为 `failed`；
- `last_error.error_code` 使用 `retrieval_index_write_failed`；
- 先将失败状态和 `last_error` 成功写入 MongoDB，再提交当前 Kafka Offset，避免失败事件持续阻塞 Partition；若失败状态写入失败，则不得提交 Offset；
- 人工重试时复用已保存的 `extraction_result`，重新执行实体对齐和幂等图谱协调，并按照上述确定性规则重新构建 `index_sync_memory_set`；
- Neo4j 幂等规则负责避免重复节点和重复 Evidence，Elasticsearch Upsert 负责避免重复索引文档。

MVP 采用同步索引写入，不增加 Index Topic、Outbox、后台补偿任务和定时全量校验。该方案保证单个 Document 幂等和任务级最终一致，不保证一次 Bulk 中所有 Memory 的原子可见。

#### 2.2.4 Elasticsearch Retrieval Index 数据结构

物理 Index 与应用 Alias：

```
Physical Index: memory_retrieval_v1
Application Alias: memory_retrieval_current
```

初始化 Migration 创建物理 Index 和 Alias。应用侧的写入、BM25、Vector Search 和 MGET 一律使用 `memory_retrieval_current`，不得在业务代码中直接写死物理 Index 名称。每个 Neo4j Memory 对应一个 Elasticsearch Document，Document ID 使用 `memory_id`。

Document Schema：

```
{
    "memory_id": "memory_000001",

    "user_id": "user_001",

    "memory_type": "event",

    "status": "active",

    "content": "用户正在开发 Agent Memory System",

    "search_text":
    "用户正在开发 Agent Memory System works_on Agent Memory System 记忆系统项目",

    "predicate": "works_on",

    "event_status": "ongoing",

    "latest_source_time": 1720000000,

    "updated_time": 1720000020,

    "embedding": [0.012, -0.031, 0.084]
}
```

以上 Document Schema 为展示性示例，代码块仅展示向量前三个元素；真实 Elasticsearch Document 中的 `embedding` 必须严格包含 `1024` 个浮点数。

字段说明：

| 字段 | 说明 |
| --- | --- |
| memory_id | Neo4j Memory 唯一 ID，同时作为 Elasticsearch Document ID |
| user_id | 用户 ID，所有召回必须过滤该字段 |
| memory_type | `fact`、`preference`、`event`、`profile` |
| status | 与 Neo4j Memory 状态保持一致 |
| content | Memory 可读内容 |
| search_text | 用于 BM25 和 Embedding 的统一检索文本 |
| predicate | 规范化关系词 |
| event_status | Event 状态，非 Event 时为 `null` |
| latest_source_time | 最新用户证据时间 |
| updated_time | Memory 最近更新时间 |
| embedding | `search_text` 对应向量 |

MVP 固定使用 Elasticsearch `9.4.4`、`dense_vector`、HNSW 近似检索和 `cosine` similarity。开发、测试和生产环境必须使用同一完整 Patch 版本，不得只声明为不确定的 `9.x`，也不得使用 `latest` Tag。

Elasticsearch `9.4.4` 对 `float` 类型的 `dense_vector` 使用 `int8_hnsw` 量化索引。索引中同时保留原始浮点向量与量化向量；量化索引用于 HNSW 候选召回。MVP 接受该量化带来的轻微召回精度损失，并通过 `num_candidates` 扩大候选集。BM25 和 Vector 仍由应用层使用 RRF 按排名融合，不直接相加 Elasticsearch 原始分数。

Mapping：

```
PUT memory_retrieval_v1
{
  "mappings": {
    "properties": {
      "memory_id": {
        "type": "keyword"
      },
      "user_id": {
        "type": "keyword"
      },
      "memory_type": {
        "type": "keyword"
      },
      "status": {
        "type": "keyword"
      },
      "content": {
        "type": "text",
        "analyzer": "cjk"
      },
      "search_text": {
        "type": "text",
        "analyzer": "cjk"
      },
      "predicate": {
        "type": "keyword"
      },
      "event_status": {
        "type": "keyword"
      },
      "latest_source_time": {
        "type": "long"
      },
      "updated_time": {
        "type": "long"
      },
      "embedding": {
        "type": "dense_vector",
        "dims": 1024,
        "element_type": "float",
        "index": true,
        "similarity": "cosine",
        "index_options": {
          "type": "int8_hnsw",
          "m": 16,
          "ef_construction": 128
        }
      }
    }
  }
}
```

MVP 使用开源多语言模型 `BAAI/bge-m3` 的 Dense Embedding，向量维度固定为 `1024`。更换 Embedding Model、向量维度或距离度量时必须创建新版本 Index 并重新构建全部 Memory 向量。

Elasticsearch Index 由部署初始化脚本或数据库迁移命令创建。Memory Retrieval Service 启动时只校验 Elasticsearch 版本、Index 是否存在以及 Mapping 是否匹配，不负责自动创建或修改 Index。

Elasticsearch 不保存 `confidence`、`importance`、`retrieval_count` 和 `last_retrieved_time`。这些最终评分字段统一从 Neo4j 读取，避免多个存储重复维护动态状态。

初始化脚本完成 Mapping 创建后，必须原子创建或切换 Alias：

```
POST _aliases
{
  "actions": [
    {
      "add": {
        "index": "memory_retrieval_v1",
        "alias": "memory_retrieval_current"
      }
    }
  ]
}
```

业务代码只读取配置中的 `index_name=memory_retrieval_current`。

#### 2.2.5 Memory Retrieval API 设计

Endpoint：

```
POST /api/v1/memory/retrieval
```

Request：

```
{
    "user_id": "user_001",

    "query": "用户之前设计的 Agent 记忆系统使用了哪些技术",

    "memory_types": [
        "fact",
        "event"
    ],

    "top_k": 10,

    "include_conflicted": false,

    "include_history": false,

    "graph_expand": true
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| user_id | 当前用户 ID，必填 |
| query | 当前任务的长期记忆检索文本，必填 |
| memory_types | 可选类型过滤；缺省或空数组表示全部类型 |
| top_k | 最终返回数量，默认 `10`，允许 `1` 至 `20` |
| include_conflicted | 是否允许返回 `conflicted`，默认 `false` |
| include_history | 是否允许返回 `superseded`，默认 `false` |
| graph_expand | 是否执行一跳扩展，默认 `true` |

请求校验：

1. `user_id` 和 `query` 不能为空。
2. Query 标准化后字符长度必须在 `1` 至 `2000` 之间；超过 `2000` 字符返回 `query_too_long`。
3. 字符长度合法后，Vector 通道使用 TEI `/tokenize` 计算精确 Token 数。`1` 至 `1024` Token 正常生成 Query Embedding；超过 `1024` Token 时不调用 `/v1/embeddings`，跳过 Vector 通道并继续 BM25，返回 Warning `vector_skipped_query_too_long`。
4. `memory_types` 只能包含 `fact`、`preference`、`event`、`profile`，并进行去重；缺省或去重后为空数组时表示不限制 Memory 类型。
5. 当 `memory_types` 缺省或为空数组时，BM25 Query 和 Vector Query 中不得生成 `memory_type` 的 `terms` Filter。
6. `top_k` 超出范围时返回 `invalid_top_k`，不得静默截断。
7. 请求必须通过第 `3.21` 节定义的 Memory API Key 鉴权。
8. MVP 的静态 API Key 只验证受信任的上游 Agent 服务，不携带最终用户身份；Request `user_id` 由已鉴权的上游 Agent 负责提供，Memory API 不允许直接暴露给终端用户。
9. 单次请求只能包含一个 `user_id`，所有 Elasticsearch 和 Neo4j 查询必须强制附加该 `user_id` 过滤条件，不提供跨用户批量检索接口。

#### 2.2.6 Query 标准化与 Embedding

Query 标准化规则：

- Unicode NFKC 标准化。
- 去除首尾空白。
- 连续空格压缩为单个空格。
- 保留中英文、数字和标点。
- 不删除停用词，不做同义词扩展，不调用 LLM 改写。
- 不自动拼接当前短期上下文；需要上下文时由外部 Agent 在 Query 中明确表达。

Embedding 在应用层通过统一的 `EmbeddingClient` Protocol 调用：

```python
class EmbeddingClient(Protocol):
    async def embed(self, texts: list[str]) -> EmbeddingResult:
        ...
```

逻辑输入：

```json
{
    "texts": [
        "用户正在开发 Agent Memory System"
    ]
}
```

逻辑输出：

```json
{
    "model": "BAAI/bge-m3",
    "dimension": 1024,
    "vectors": [
        [0.012, -0.031, 0.084]
    ]
}
```

以上输出为应用内部 Contract，向量示例仅展示前三个元素；真实向量必须包含且只能包含 `1024` 个浮点数。MVP 不额外开发自定义 Embedding HTTP Wrapper。业务层仅依赖 `EmbeddingClient` Protocol，不得直接依赖 SiliconFlow SDK 或 TEI SDK；MVP 默认经 `SiliconFlowEmbeddingClient`（SiliconFlow Hosted API，`httpx`，无 SDK）实现，由 `create_embedding_client` 按 `memory_retrieval.embedding_provider` 分发。SiliconFlow 托管路径的向量 L2 归一化语义：**UNKNOWN / DEV-007 规划决策**（不得猜测实现行为）。`embedding_provider=local_tei` 时保留 `TEIEmbeddingClient`，使用 TEI 原生接口：

```text
POST http://embedding-service:80/tokenize
POST http://embedding-service:80/v1/embeddings
```

OpenAI-compatible Embedding Request：

```json
{
    "model": "BAAI/bge-m3",
    "input": [
        "用户正在开发 Agent Memory System"
    ],
    "encoding_format": "float"
}
```

规则：

1. `texts` 和返回向量的数组顺序必须一致。
2. 单次最多处理 `64` 条文本，索引同步超过该数量时分批调用。
3. `TEIEmbeddingClient` 在调用 `/v1/embeddings` 前，必须使用同一 TEI 实例的 `/tokenize` 对每条文本进行精确 Token 计数；单条超过 `1024` Token 时返回 `embedding_input_too_long`，不得静默截断。
4. Client 必须验证配置模型为 `BAAI/bge-m3`、返回记录数与输入数一致，并验证每个向量的实际元素数量严格等于 `1024`。
5. `BAAI/bge-m3` 模型配置包含 CLS Pooling 和 Normalize 模块；CPU 与 GPU 模式均使用 TEI 的同一模型流水线输出。应用层不得再次执行 L2 Normalization。
6. Elasticsearch Mapping 使用 `similarity=cosine`。索引与查询必须使用相同模型 Revision、Pooling、Normalize、Token 上限和输入预处理规则。零向量、NaN 或 Inf 属于非法结果，必须拒绝。
7. 空字符串不得发送给 TEI。
8. Query 标准化文本超过 `1024` Token 时属于预期降级，不是 `embedding_failed`：Client 不调用 `/v1/embeddings`，Vector 通道状态记为 `skipped_query_too_long`，BM25 正常继续。
9. Query Embedding 仅在当前请求内使用，不持久化。
10. TEI HTTP 返回必须由适配器转换为 `EmbeddingResult`，Domain 和 Application 层不得依赖 TEI 原生 Response Schema。

Embedding 服务异常时跳过 Vector 通道并返回 Warning `embedding_failed`；Query 超过 1024 Token 时跳过 Vector 通道并返回 Warning `vector_skipped_query_too_long`。两种情况都继续执行 BM25。若 BM25 也失败，返回 `retrieval_unavailable`。

#### 2.2.7 BM25 关键词召回

BM25 用于召回关键词、实体名称、项目名、产品名、技术名和明确事实高度匹配的 Memory。

Elasticsearch Filter：

- `user_id` 等于当前用户。
- `memory_type` 在请求允许范围内。
- 默认只允许 `status=active`。
- `include_conflicted=true` 时允许 `active`、`conflicted`。
- `include_history=true` 时在上述范围中增加 `superseded`。

查询字段和权重：

```
search_text^2.0
content^1.0
predicate^0.5
```

当 `memory_types` 缺省或为空数组时，应从 `filter` 中省略 `memory_type` 的 `terms` 条件，不得生成空数组 Filter。

BM25 Query 示例（默认仅检索 active，memory_types 为 fact 和 event）：

```
POST memory_retrieval_current/_search
{
  "size": 30,
  "_source": false,
  "query": {
    "bool": {
      "filter": [
        {"term": {"user_id": "user_001"}},
        {"terms": {"memory_type": ["fact", "event"]}},
        {"term": {"status": "active"}}
      ],
      "must": {
        "multi_match": {
          "query": "用户之前设计的 Agent 记忆系统使用了哪些技术",
          "fields": ["search_text^2.0", "content^1.0", "predicate^0.5"]
        }
      }
    }
  }
}
```

BM25 最多返回 `bm25_top_n` 条结果，默认 `30`。应用层只保存 `memory_id`、排名和 Elasticsearch 原始分数；原始分数不与向量相似度直接相加。

#### 2.2.8 Vector 语义召回

Vector Retrieval 用于召回语义相关但文字表达不同的 Memory。

向量检索使用 Query Embedding 搜索 `embedding` 字段，并应用与 BM25 完全相同的 `user_id`、`memory_type` 和 `status` Filter。最多返回 `vector_top_n` 条结果，默认 `30`。当 `memory_types` 缺省或为空数组时，应省略 Vector Query 中的 `memory_type` `terms` Filter。

Vector Query 示例（`query_vector` 实际长度必须为 1024）：

```
POST memory_retrieval_current/_search
{
  "size": 30,
  "_source": false,
  "knn": {
    "field": "embedding",
    "query_vector": [0.012, -0.031, 0.084],
    "k": 30,
    "num_candidates": 100,
    "filter": {
      "bool": {
        "filter": [
          {"term": {"user_id": "user_001"}},
          {"terms": {"memory_type": ["fact", "event"]}},
          {"term": {"status": "active"}}
        ]
      }
    }
  }
}
```

以上 Query 示例仅展示向量前三个元素；真实请求必须传入 `1024` 个浮点数。`k` 固定等于 `vector_top_n`，`num_candidates` 使用配置项 `vector_num_candidates`，并且必须大于或等于 `k`。MVP 默认 `k=30`、`num_candidates=100`。

向量通道只用于候选召回。应用层保存 `memory_id`、排名和 Elasticsearch `_score`，后续仅通过 RRF 与 BM25 结果融合，不将 `_score` 与 BM25 分数直接相加。

#### 2.2.9 RRF 多路结果融合

BM25 分数和向量相似度不在同一数值空间，MVP 使用 Reciprocal Rank Fusion（RRF）按照排名融合。

```
rrf_score(memory) =
sum(
    1 / (rrf_k + rank_i(memory))
)
```

其中排名从 `1` 开始，`rrf_k` 默认 `60`。

处理规则：

1. BM25 通道与“Query Embedding + Vector Retrieval”通道并行启动；Vector Retrieval 必须等待 Query Embedding 完成，但 BM25 不等待 Embedding。
2. 以 `memory_id` 为 Key 合并结果。
3. 保存 `bm25_rank`、`vector_rank`、召回来源和 `rrf_score`。
4. 单个通道失败时，仅使用成功通道计算。
5. 两个通道都成功但均为空时，直接返回空结果。
6. `min_available_rank` 定义为当前 Memory 在所有成功召回通道中的最小非空排名：

```
min_available_rank =
min(
    non_null(bm25_rank, vector_rank)
)
```

7. 按以下顺序稳定排序：

```
rrf_score DESC
min_available_rank ASC
memory_id ASC
```

8. 保留前 `fused_top_n` 条直接候选，默认 `30`。

RRF 使用固定理论最大值归一化，避免弱结果在当前集合中被强制归一化为 `1.0`。归一化时不按“请求是否成功”统计通道，而是按“成功执行且召回结果非空”的有效通道数量统计：

```
effective_channel_count =
count(
    retrieval_channel.status == success
    and retrieval_channel.result_count > 0
)
```

处理规则：

1. BM25 和 Vector 均成功且结果非空时，`effective_channel_count=2`。
2. 只有一个通道成功且结果非空时，`effective_channel_count=1`。
3. 一个通道成功但结果为空，另一个通道成功且结果非空时，`effective_channel_count=1`。
4. 两个通道都成功但结果均为空时，直接返回空结果，不计算归一化分数。
5. 两个通道都失败时，按照 `retrieval_unavailable` 返回失败。

```
rrf_max =
effective_channel_count
/
(rrf_k + 1)
```

```
normalized_retrieval_score =
min(
    1.0,
    rrf_score / rrf_max
)
```

只有 `effective_channel_count > 0` 时才允许计算 `rrf_max` 和 `normalized_retrieval_score`。

`retrieval_mode` 也必须按照有效非空通道计算，而不是仅按照请求是否成功计算：两个有效通道为 `hybrid`，仅 BM25 有效为 `bm25_only`，仅 Vector 有效为 `vector_only`，没有有效通道但至少一个通道成功为空时为 `none`。

#### 2.2.10 Neo4j Memory 加载与一跳图谱扩展

RRF 得到候选 `memory_id` 后，应用层从 Neo4j 批量读取完整 Memory，以及主体和客体 Entity。Elasticsearch 中存在但 Neo4j 中不存在的 ID 视为脏索引，跳过并记录 `dirty_index_document` Warning，不得直接返回 Elasticsearch 文档内容。

Neo4j 是权威数据源。直接候选加载完成后，应用层必须按照当前请求重新校验：

1. `Memory.user_id` 必须等于请求中的 `user_id`。
2. 当 `memory_types` 非空时，`Memory.memory_type` 必须属于请求允许范围。
3. `Memory.status` 必须符合 `include_conflicted` 和 `include_history` 规则。
4. 不满足任一条件的候选必须丢弃，不得参与图谱扩展、最终评分或 Response 构建。
5. Elasticsearch Document 存在但 Neo4j 权威字段与当前请求过滤条件不一致时，记录 `stale_index_document` Warning。

这一步用于防止 Neo4j 已更新而 Elasticsearch 尚未同步时，旧索引状态影响最终结果。

当 `graph_expand=true` 时，先从 Neo4j 执行一跳扩展，再通过 Elasticsearch Multi Get 校验候选索引可见性。图谱候选必须同时通过当前请求的 `user_id`、`memory_type`、`status` 校验，并且存在对应的 Elasticsearch Document，才允许进入最终评分。允许的路径：

```
(seed:Memory)-[:SUBJECT|OBJECT]->(entity:Entity)
             <-[:SUBJECT|OBJECT]-(related:Memory)
```

```
(seed:Memory)-[:SUPERSEDES|CONFLICTS_WITH]-(related:Memory)
```

通过共享 Entity 扩展时，必须排除当前用户实体：

```
entity.entity_id != "user:" + user_id
```

否则所有以当前用户为主体的 Memory 都可能互相扩展，导致候选污染。

扩展规则：

1. `related.user_id` 必须等于当前用户。
2. 状态范围与直接召回相同。
3. 不返回 Seed 自身，不递归扩展。
4. 每条 Seed 最多保留 `graph_expand_per_seed` 条扩展候选，默认 `2`。
5. 全部扩展候选最多 `max_graph_candidates` 条，默认 `20`。
6. 扩展候选按以下优先级确定性排序：

```
SUPERSEDES / CONFLICTS_WITH 关系优先
共享 OBJECT Entity 次之
共享非用户 SUBJECT Entity 再次
importance DESC
latest_source_time DESC
memory_id ASC
```

7. 扩展候选去重，同一 Memory 被多个 Seed 扩展时只保留一次。
8. 若扩展候选已经存在于直接候选集合中，不重复添加 Memory；保留直接候选的 `normalized_retrieval_score`，不得使用较低的 `graph_retrieval_score` 覆盖直接召回分数，并在原有 `retrieval_source` 中追加 `graph`。
9. 扩展候选的初始检索分数为：

```
graph_retrieval_score =
seed.normalized_retrieval_score
* graph_decay
```

10. 一个扩展候选来自多个 Seed 时，取最大的 `graph_retrieval_score`。
11. Neo4j 扩展和去重完成后，对全部扩展候选 `memory_id` 执行一次 Elasticsearch Multi Get。不存在索引文档的候选必须丢弃，不得进入评分；这用于阻止 Neo4j 已提交但 Retrieval Index 同步失败的 Memory 提前可见。
12. Multi Get 或 Neo4j 图谱扩展失败时，跳过全部扩展候选，继续返回直接候选，并在 Response `warnings` 中加入 `graph_expansion_failed`。
13. Multi Get 只校验索引文档存在，不使用 Elasticsearch 文档覆盖 Neo4j 权威内容；候选的完整字段和状态仍以 Neo4j 为准。

图谱扩展只补充和直接候选关联的上下文，不代表扩展 Memory 一定进入最终结果。直接候选和通过索引可见性校验的扩展候选统一进入最终评分。

#### 2.2.11 基础 ACT-R 近似评分

MVP 保留 ACT-R 的两个基础思想：

- 被检索接口返回次数越多的 Memory，具有更高的基础激活倾向。
- 最近被检索返回或最近获得新 Evidence 的 Memory，具有更高的新鲜度。

为避免首版过度复杂，不保存每次访问时间序列，不实现成功/失败反馈，不建立 Feedback 节点。Neo4j Memory 仅维护：

```
retrieval_count: 0
last_retrieved_time: null
```

评分分量：

**1. Retrieval Score**

直接候选使用 RRF 归一化分数；图谱扩展候选使用 `graph_retrieval_score`。

```
retrieval_score =
normalized_retrieval_score
```

**2. Importance Score**

```
importance_score = importance
```

**3. Confidence Score**

```
confidence_score = confidence
```

**4. Frequency Score**

```
frequency_score =
min(
    1.0,
    ln(1 + retrieval_count) / ln(21)
)
```

当 `retrieval_count >= 20` 时达到 `1.0`，避免召回次数无限放大。该字段表示 Memory 被接口返回的次数，不表示 Agent 实际使用次数。

**5. Recency Score**

同时考虑最近检索返回时间和最新 Evidence 时间：

```
reference_time =
max(
    last_retrieved_time or 0,
    latest_source_time
)
```

因此，Memory 新增 Evidence 后，即使上一次被检索的时间较早，也会按照较新的 `latest_source_time` 计算新鲜度。

```
age_days =
max(
    0,
    current_time - reference_time
) / 86400
```

```
recency_score =
exp(
    -ln(2) * age_days / recency_half_life_days
)
```

默认 `recency_half_life_days=30`。

最终得分：

```
final_score =
0.55 * retrieval_score
+ 0.15 * importance_score
+ 0.10 * confidence_score
+ 0.10 * frequency_score
+ 0.10 * recency_score
```

处理规则：

1. 所有分量限制在 `0.0` 至 `1.0`。
2. 最终分数保留 6 位小数。
3. `conflicted` Memory 在允许返回时乘以 `0.85`。
4. `superseded` Memory 在允许返回时乘以 `0.60`。
5. 按以下顺序稳定排序：

```
final_score DESC
latest_source_time DESC
importance DESC
memory_id ASC
```

6. 最终取前 `top_k` 条。
7. 权重和半衰期必须读取配置，不得散落硬编码。

这属于基础 ACT-R 工程近似，只用于检索排序。完整访问时间序列、任务成功率和强化学习式权重更新留到后续版本。

#### 2.2.12 Evidence 加载与 Retrieval Response 设计

最终 Top-K 确定后，应用层只针对最终返回的 Memory 批量查询：

```
(Evidence)-[:SUPPORTS]->(Memory)
```

Evidence 加载规则：

1. 仅为最终 Top-K Memory 查询 Evidence，不为全部直接候选和图谱扩展候选提前加载 Evidence。
2. 查询必须同时限制 `Memory.user_id` 和 `Evidence.user_id` 等于当前用户。
3. 一次 Neo4j 查询批量加载全部 Top-K Memory 的 Evidence，不得为每条 Memory 单独发起查询。
4. 根据查询结果计算每条 Memory 的 `evidence_count`，并按照下述确定性规则生成 `source_message_ids`。
5. Evidence 加载失败时，视为 Response 所需权威数据加载失败，返回 `graph_load_failed`，不得伪造空来源数据。

Response：

```
{
    "retrieval_mode": "hybrid",

    "warnings": [],

    "memories": [
        {
            "memory_id": "memory_000001",

            "memory_type": "event",

            "content": "用户正在开发 Agent Memory System",

            "subject": {
                "entity_id": "user:user_001",

                "name": "current_user"
            },

            "predicate": "works_on",

            "object": {
                "entity_id": "entity_uuid",

                "name": "Agent Memory System",

                "value": null
            },

            "status": "active",

            "event_status": "ongoing",

            "start_time": null,

            "end_time": null,

            "confidence": 0.95,

            "importance": 0.55,

            "latest_source_time": 1720000000,

            "score": 0.873412,

            "retrieval_source": [
                "bm25",
                "vector"
            ],

            "source_message_ids": [
                "msg_000001"
            ],

            "evidence_count": 1
        }
    ]
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| retrieval_mode | 按成功且结果非空的有效召回通道计算：`hybrid`、`bm25_only`、`vector_only` 或 `none` |
| warnings | 非致命降级信息，没有时为空数组 |
| memories | 按最终分数降序返回的 Memory |
| subject | 主体 Entity ID 和标准名称 |
| object | 客体为实体时返回 Entity；客体为普通值时仅 `value` 有值 |
| score | 最终激活分数 |
| retrieval_source | `bm25`、`vector`、`graph` 中一个或多个来源 |
| source_message_ids | 从 Evidence 聚合的来源消息 ID，按照下述确定性规则排序并去重，最多返回 `20` 条 |
| evidence_count | 支持该 Memory 的 Evidence 总数 |

`source_message_ids` 聚合规则：

1. Evidence 按 `source_time_end DESC`、`evidence_id ASC` 稳定排序。
2. 每个 Evidence 内保持 `source_message_ids` 原始数组顺序。
3. 按上述顺序依次合并，并对重复 `message_id` 保留第一次出现。
4. 最多返回 `max_source_message_ids` 条；`evidence_count` 仍返回全部 Evidence 数量。

空结果：

```
{
    "retrieval_mode": "none",

    "warnings": [],

    "memories": []
}
```

若 Embedding 或某个召回通道失败但已经降级返回，必须将对应 Warning 写入 `warnings`。

外部 Agent 应按照返回顺序将 Memory 加入 Prompt。长期记忆仅作为参考上下文，不得覆盖当前用户消息中的明确新信息。返回 `conflicted` Memory 时，Agent 必须保留不确定性。

#### 2.2.13 召回统计更新

最终 Top-K 确定后，对返回的 Memory 执行一次 Neo4j 批量更新：

```cypher
SET m.retrieval_count = coalesce(m.retrieval_count, 0) + 1,
    m.last_retrieved_time =
        CASE
            WHEN m.last_retrieved_time IS NULL
              OR m.last_retrieved_time < $current_time
            THEN $current_time
            ELSE m.last_retrieved_time
        END
```

`last_retrieved_time` 必须单调不减，避免并发请求以不同提交顺序导致时间回退。

规则：

1. 只更新最终返回的 Memory，不更新未返回候选。
2. 单次请求内 Memory ID 必须去重，每条 Memory 最多加一。
3. 更新条件必须包含 `user_id`，不得更新其他用户 Memory。
4. 召回统计更新失败不影响本次检索结果返回。
5. 更新失败时在 `warnings` 中加入 `retrieval_stat_update_failed` 并记录错误日志。
6. MVP 接受客户端超时重试可能使 `retrieval_count` 重复增加；该字段只作为弱排序信号，不作为计费或强一致业务数据，因此首版不增加请求幂等表。

#### 2.2.14 MVP 配置

```
memory_retrieval:
    elasticsearch_version: "9.4.4"

    physical_index_name: "memory_retrieval_v1"

    index_name: "memory_retrieval_current"

    embedding_provider: "siliconflow"

    # 合法枚举：siliconflow（默认）、local_tei（可选自托管；非 MVP 阻塞）

    embedding_model: "BAAI/bge-m3"

    embedding_model_revision: "57aacf8560157b7c1d4f771ce1a199877aeeec74"

    embedding_dimension: 1024

    embedding_max_input_tokens: 1024

    embedding_timeout_seconds: 10

    elasticsearch_timeout_seconds: 5

    neo4j_timeout_seconds: 5

    retrieval_total_timeout_seconds: 15

    bm25_top_n: 30

    vector_top_n: 30

    vector_num_candidates: 100

    fused_top_n: 30

    rrf_k: 60

    graph_expand_per_seed: 2

    max_graph_candidates: 20

    graph_decay: 0.60

    default_top_k: 10

    max_top_k: 20

    max_source_message_ids: 20

    recency_half_life_days: 30

    retrieval_score_weight: 0.55

    importance_weight: 0.15

    confidence_weight: 0.10

    frequency_weight: 0.10

    recency_weight: 0.10

    conflicted_penalty: 0.85

    superseded_penalty: 0.60
```

配置校验：

1. Top-N、Top-K 和 `vector_num_candidates` 必须为正整数。
2. `vector_num_candidates` 必须大于或等于 `vector_top_n`，且不得超过 Elasticsearch 单次 kNN 查询允许的上限。
3. `fused_top_n` 必须不小于 `max_top_k`。
4. 五个评分权重之和必须等于 `1.0`，允许误差不超过 `0.000001`。
5. `graph_decay`、惩罚系数和权重必须在 `0.0` 至 `1.0`。
6. `embedding_dimension` 必须与 Embedding Model 和 Elasticsearch Mapping 一致。
7. 实际 Elasticsearch 服务版本必须与 `elasticsearch_version` 完全一致。
8. `embedding_timeout_seconds`、`elasticsearch_timeout_seconds`、`neo4j_timeout_seconds` 和 `retrieval_total_timeout_seconds` 必须为正数，且单阶段超时不得大于总超时。
9. 应用启动时校验服务版本、Index 是否存在以及 Mapping 是否匹配；不一致时启动失败，不自动创建或修改现有 Index。

#### 2.2.15 失败处理与降级策略

致命错误码：

| 错误码 | 含义 |
| --- | --- |
| invalid_request | 请求结构或必填字段不合法 |
| invalid_memory_type | `memory_types` 包含非法类型 |
| invalid_top_k | `top_k` 不在允许范围 |
| query_too_long | Query 超过 2000 字符 |
| retrieval_unavailable | BM25 和 Vector 两个召回通道都不可用 |
| graph_load_failed | 无法从 Neo4j 加载检索所需的权威 Memory、Entity 或 Evidence |
| retrieval_timeout | 总检索超时，且 Response 所需数据尚未完整构建 |

非致命 Warning：

| Warning | 含义 |
| --- | --- |
| embedding_failed | Embedding 服务或向量生成异常，已跳过 Vector 通道 |
| vector_skipped_query_too_long | Query 超过 1024 Token，按设计跳过 Vector 通道并继续 BM25 |
| bm25_retrieval_failed | BM25 通道失败，已使用 Vector 通道 |
| vector_retrieval_failed | Vector 通道失败，已使用 BM25 通道 |
| graph_expansion_failed | 图谱扩展失败，已仅使用直接候选 |
| dirty_index_document | Elasticsearch 候选在 Neo4j 中不存在，已跳过 |
| stale_index_document | Elasticsearch 索引字段与 Neo4j 权威 Memory 不一致，候选已按 Neo4j 数据重新过滤 |
| retrieval_stat_update_failed | 召回统计更新失败，但检索结果仍正常返回 |
| retrieval_timeout_degraded | Response 数据已完整构建后发生总超时，已跳过召回统计更新并返回现有结果 |

降级规则：

1. BM25 和 Vector 都成功且结果非空时返回 `retrieval_mode=hybrid`。
2. 只有 BM25 成功且结果非空时返回 `retrieval_mode=bm25_only`，无论 Vector 是失败还是成功但为空。
3. 只有 Vector 成功且结果非空时返回 `retrieval_mode=vector_only`，无论 BM25 是失败还是成功但为空。
4. 所有成功通道结果均为空时返回 `retrieval_mode=none` 和空 `memories`；失败通道仍按规则加入 Warning。
5. 两个通道都失败时返回 `retrieval_unavailable`。
5. Neo4j 权威 Memory、Entity 或最终 Top-K Evidence 加载失败时，不得使用 Elasticsearch 内容或伪造空来源字段替代，返回 `graph_load_failed`。
6. 图谱扩展失败时跳过扩展，继续处理直接候选。
7. 单条脏索引或过期索引候选按 Neo4j 权威数据跳过或重新过滤；全部候选均无效时返回空数组。
8. 单阶段调用超过对应超时时间时，按该阶段失败处理。整个请求超过 `retrieval_total_timeout_seconds` 时：
   - 若尚未完成最终 Top-K 的 Evidence 加载和 Response 数据构建，则终止请求并返回 `retrieval_timeout`；
   - 若 Response 数据已经完整构建，仅召回统计尚未更新，则跳过召回统计更新，返回现有结果，并在 `warnings` 中加入 `retrieval_timeout_degraded`；
   - 不得直接使用尚未从 Neo4j 加载的 Elasticsearch 文档内容返回，也不得在 Evidence 尚未完成聚合时返回伪造的空来源字段。
10. 所有错误日志至少包含 `user_id`、Query Hash、失败阶段和错误码；日志不得打印 Query Embedding。

#### 2.2.16 完整处理流程

```
Receive Retrieval Request

        |

Validate user_id, query, filters and top_k

        |

Normalize Query

        |

        +-----------------------------+
        |                             |
        v                             v
Execute BM25 Retrieval       Generate Query Embedding
                                      |
                                      v
                             Execute Vector Retrieval
        |                             |
        +---------- RRF Fusion -------+

        |

Load Authoritative Memory from Neo4j

        |

Revalidate user_id, memory_type and status
using Neo4j Authoritative Data

        |

Execute Optional One-Hop Graph Expansion
excluding Current User Entity

        |

Calculate Retrieval, Importance, Confidence,
Frequency and Recency Scores

        |

Apply Status Penalty and Stable Sort

        |

Select Final Top-K

        |

Batch Load Evidence for Final Top-K
and Aggregate Source Message IDs

        |

Update retrieval_count and last_retrieved_time

        |

Return Structured Memory Context
```

#### 2.2.17 MVP 实现边界

本阶段必须实现：

- Memory 从 Neo4j 到 Elasticsearch 的同步 Upsert。
- `refresh=wait_for` 和 Bulk Item 级失败检查。
- Elasticsearch BM25 关键词召回。
- 基于 `BAAI/bge-m3` Dense Embedding 的 Memory 和 Query 向量。
- Elasticsearch Vector 召回。
- 用户、Memory 类型和状态过滤。
- RRF 多路结果融合和固定理论最大值归一化。
- Neo4j 权威 Memory 加载，并按照当前请求重新校验 `user_id`、`memory_type` 和 `status`。
- 排除当前用户实体的一跳图谱扩展。
- 基于检索相关性、重要性、置信度、召回频率和时间新鲜度的基础 ACT-R 评分。
- 最终 Top-K Evidence 批量加载，以及 `source_message_ids` 和 `evidence_count` 聚合。
- Top-K 结构化结果返回。
- `retrieval_count` 和 `last_retrieved_time` 更新。
- 单路召回失败和图谱扩展失败时的降级处理。
- Embedding、Elasticsearch、Neo4j 和检索总流程的基础超时控制。

MVP 暂不实现：

- MongoDB Retrieval Log。
- Agent 使用反馈接口。
- `success_count`、`failure_count` 和 RetrievalFeedback 节点。
- 使用 LLM 进行 Query 改写、意图识别或检索计划生成。
- 多跳图谱遍历和复杂图推理。
- Cross-Encoder Reranker。
- 跨用户检索和公共知识图谱。
- 自动选择检索通道。
- 查询结果摘要或重新生成。
- 个性化动态权重学习。
- 完整 ACT-R 访问时间序列建模。
- Elasticsearch Outbox、后台自动补偿和定时全量索引校验。

### 2.3 巩固与遗忘

长期记忆巩固与遗忘模块负责定期评估 Neo4j 中的 Memory，根据记忆类型、置信度、独立 Archive 数量以及距离最近用户来源证据的时间，重新计算动态 `importance`。

MVP 采用**软遗忘**策略：只调整 Memory 的重要性，不自动删除 Memory、Evidence 或 Entity，不修改 `content`、`status`、事件时间和图谱关系。每条 Memory 的首个 Archive 提供基础 Evidence 分；后续不同 Archive 的独立支持会继续提高 Evidence 强化分。高置信度且具有更多独立 Archive 支持的 Memory 会得到更强强化；长期没有新 Evidence 的 Memory，其重要性会随时间衰减。

MVP 不将 `retrieval_count` 或 `last_retrieved_time` 用于长期巩固。它们仅由记忆检索模块用于请求级 ACT-R 近似排序，避免“被返回得越多，长期重要性越高，之后又更容易被返回”的自我强化循环。

MVP 不调用 LLM 生成高层摘要，不执行语义重复合并，不自动解决冲突，也不进行物理删除。内容级记忆压缩、分层抽象、硬删除和图谱重构在后续版本中实现。

#### 2.3.1 整体架构

巩固与遗忘采用定时批处理，不依赖用户请求，也不消费 Kafka 事件。MVP 只部署一个 Consolidation Worker 实例，由内部 Scheduler 每天触发一次。

整体流程：

```
Daily Scheduler

        |

Try Acquire Local Consolidation Lock

        |

Create Fixed Evaluation Time

        |

Scan Memory in Batches from Neo4j

        |

Load Distinct Archive Evidence Count

        |

Calculate Reinforcement Signals

        |

Calculate Time Decay

        |

Recompute Dynamic Importance

        |

Batch Update Neo4j

        |

Write Run Metrics and Logs

        |

Release Local Consolidation Lock
```

模块职责：

| 组件 | 职责 |
| --- | --- |
| Consolidation Scheduler | 按固定周期触发巩固任务，并生成本次统一的 `evaluation_time` |
| Consolidation Worker | 获取本地互斥锁，分批扫描 Memory、计算重要性并批量更新 Neo4j |
| Neo4j | 保存权威 Memory 和 Evidence，提供候选数据并接收重要性更新 |
| Elasticsearch | 不参与重要性计算；MVP 不保存 `importance`，因此巩固后不需要同步索引 |

Scheduler 和 Consolidation Worker 可以与 Memory Retrieval Service 部署在同一进程中，也可以作为独立 Worker 运行。MVP 必须保证 Consolidation Worker 只部署一个实例，并在进程内使用互斥锁或原子 Running Flag，防止上一轮未完成时下一轮重复进入。MVP 不实现 Redis 分布式锁或跨实例选主。

#### 2.3.2 MVP 范围与基本规则

巩固与遗忘必须遵循以下规则：

1. Neo4j 是巩固与遗忘的唯一权威数据源。
2. 所有 Memory 独立计算，任何查询和更新不得跨用户合并记忆。
3. MVP 处理 `status=active`、`conflicted` 和 `superseded` 的 Memory。
4. 巩固模块只允许修改 `importance` 和 `last_consolidated_time`。
5. 巩固模块不得修改 `content`、`memory_type`、`confidence`、`status`、`event_status`、时间字段、主体客体字段和图谱关系。
6. `retrieval_count` 和 `last_retrieved_time` 只由记忆检索模块维护。巩固模块不得修改，也不将其用于长期重要性计算。
7. 同一轮任务的所有 Memory 必须使用相同的 `evaluation_time`，避免不同批次因执行时间不同产生不一致结果。
8. 空候选集合属于正常完成，不视为失败。
9. MVP 不使用任务成功率、Agent 反馈、人工评分或用户行为数据，因为当前系统尚未实现这些可信强化信号。
10. MVP 不物理删除长期记忆。所谓遗忘仅表示重要性衰减，旧记忆仍可在高度相关或显式历史检索时被召回。
11. 同一进程同一时间只允许执行一个巩固任务。未获取本地互斥锁的调度触发必须直接跳过，不得并行执行第二轮任务。
12. 每轮任务一旦开始，应持续扫描至本轮候选全部处理完成。MVP 不设置单轮最长执行时间，也不保存持久化 Cursor。

#### 2.3.3 Memory 字段补充

Memory 节点用于巩固的字段：

```
last_consolidated_time: null
memory_version: 1
```

字段含义：

| 字段 | 说明 |
| --- | --- |
| importance | 当前动态重要性，范围为 `0.0` 至 `1.0` |
| last_consolidated_time | 最近一次完成重要性计算的统一评估时间；从未处理时为 `null` |
| memory_version | Memory 内容状态版本号；由记忆萃取维护，巩固任务只读取并用于乐观并发校验 |

新 Memory 创建时：

```
importance = memory_type 对应的固定初始值
last_consolidated_time = null
memory_version = 1
```

巩固任务更新 `importance` 时不得修改 Memory 的通用 `updated_time`。`updated_time` 表示记忆内容或事实状态发生变化；仅重要性重算不属于内容变化。这样可以避免将定时评分误判为新的用户证据或触发不必要的 Elasticsearch 重建。

MVP 不额外创建 `memory_consolidation_scan` 索引。批量分页先依赖已有的 `memory_id` 唯一约束及其索引。数据规模扩大后，再根据 Neo4j `PROFILE` 结果决定是否增加专用扫描索引。

#### 2.3.4 调度、互斥与批量扫描

默认每天执行一次：

```
0 3 * * *
```

时区固定为 UTC。每次调度首先尝试获取进程内本地互斥锁：

```
Try Acquire Local Consolidation Lock

    获取成功：继续执行

    获取失败：记录 consolidation_already_running，并跳过本次触发
```

本地互斥锁规则：

1. 可以使用语言运行时提供的 Mutex、Semaphore 或原子 Running Flag。
2. 获取锁后才允许生成 `run_id` 和开始扫描。
3. 无论任务成功、失败还是抛出异常，都必须在 `finally` 中释放锁。
4. MVP 只允许部署一个 Consolidation Worker 实例；本地锁不用于多实例分布式互斥。

获取锁成功后生成：

```
run_id = UUID

evaluation_time = 本次计划触发时间的 Unix timestamp
```

同一轮运行中不得使用每个批次的实际开始时间替代 `evaluation_time`。

MVP 使用 `memory_id` 游标分页，每批默认处理 `500` 条。候选扫描条件：

1. `created_time <= evaluation_time`。
2. `last_consolidated_time` 为 `null`，或者小于本次 `evaluation_time`。
3. `memory_id` 大于上一批最后一个游标。
4. 状态为 `active`、`conflicted` 或 `superseded`。

Neo4j 查询示意：

```
MATCH (m:Memory)
WHERE m.created_time <= $evaluation_time
  AND (m.last_consolidated_time IS NULL
       OR m.last_consolidated_time < $evaluation_time)
  AND ($cursor IS NULL OR m.memory_id > $cursor)
  AND m.status IN ["active", "conflicted", "superseded"]
OPTIONAL MATCH (e:Evidence)-[:SUPPORTS]->(m)
RETURN m, count(DISTINCT e.archive_id) AS independent_archive_count
ORDER BY m.memory_id ASC
LIMIT $batch_size
```

`independent_archive_count` 的含义：

> 支持当前 Memory 的不同 `archive_id` 数量。同一 Archive 即使因为重试、候选拆分或其他原因存在多个 Evidence，也最多贡献一次强化计数。

该字段仅是巩固任务运行时的查询结果，不写入 Memory 节点。它与 `2.2 记忆检索` Response 中表示 Evidence 节点总数的 `evidence_count` 含义不同，二者不得复用同一统计结果。

规则：

1. `memory_id` 在全局唯一约束下可以作为稳定游标。
2. 每个批次必须一次性返回计算所需的 Memory 字段和 `independent_archive_count`，避免逐条查询 Evidence。
3. 只要当前批次读取成功，且没有发生致命的批量写入失败，无论有效更新数量是否为 `0`，都必须将 Cursor 推进到当前批次最后一个 `memory_id`。
4. 当当前批次全部 Memory 都因字段非法、缺少 Evidence 或版本冲突而没有可写入的更新记录时，跳过 Neo4j 写 Transaction，记录指标后直接推进 Cursor，避免反复读取同一批次形成死循环。
5. MVP 不设置 `max_run_seconds`，任务必须持续运行至本轮候选全部处理完成，避免每次从头扫描导致后半部分 Memory 长期得不到处理。
6. MVP 不保存持久化 Cursor。进程崩溃后下一次任务从头扫描；已完成节点会根据新的 `evaluation_time` 再次计算，但公式是确定性的，不会产生累积强化或重复衰减。

#### 2.3.5 巩固信号计算

每条 Memory 使用以下信号。

**1. Base Importance**

基础重要性根据 `memory_type` 固定生成，与 `2.1.12` 的初始值一致：

| memory_type | base_importance |
| --- | ---: |
| profile | 0.75 |
| fact | 0.70 |
| preference | 0.65 |
| event | 0.55 |

巩固时根据 `memory_type` 重新查表，不额外保存 `base_importance` 字段。

**2. Confidence Score**

```
confidence_score = clamp(
    confidence,
    0.0,
    1.0
)
```

**3. Evidence Score**

每条 Memory 的首个 Archive 提供基础 Evidence 分；后续不同 Archive 对同一 Memory 的独立支持会继续提高长期强化分：

```
evidence_score = min(
    1.0,
    ln(1 + independent_archive_count)
    /
    ln(1 + evidence_saturation_count)
)
```

默认：

```
evidence_saturation_count = 5
```

当 `independent_archive_count=1` 时，首个 Archive 已提供基础 Evidence 分；随着独立 Archive 数量增加，Evidence 强化分继续上升。当 `independent_archive_count >= 5` 时达到上限。`independent_archive_count=0` 表示图谱数据异常，该 Memory 不更新重要性，并记录 `missing_evidence`。

**4. Reference Time**

长期时间衰减只使用用户来源证据时间，不使用检索返回时间：

```
reference_time = max(
    latest_source_time or 0,
    created_time
)
```

```
inactive_days = max(
    0,
    (evaluation_time - reference_time) / 86400
)
```

如果来源时间晚于 `evaluation_time`，按 `inactive_days=0` 处理，不产生负衰减。

#### 2.3.6 时间衰减设计

MVP 使用半衰期形式的指数衰减近似艾宾浩斯遗忘曲线：

```
recency_score =
2 ^ (-inactive_days / half_life_days)
```

不同记忆类型采用不同半衰期：

| memory_type | half_life_days |
| --- | ---: |
| profile | 365 |
| fact | 180 |
| preference | 120 |
| event | 60 |

`superseded` Memory 已经被新记忆取代，使用更短的半衰期：

```
half_life_days = min(
    memory_type_half_life_days,
    superseded_half_life_days
)
```

默认：

```
superseded_half_life_days = 30
```

`conflicted` Memory 仍处于未解决状态，不能因为时间衰减而完全失去可见性。其最终重要性使用单独的最低值保护，具体规则见下一节。

#### 2.3.7 动态重要性计算

强化分：

```
reinforcement_score =
    confidence_weight * confidence_score
    + evidence_weight * evidence_score
```

默认权重：

```
confidence_weight = 0.55

evidence_weight = 0.45
```

两个强化权重之和必须等于 `1.0`。

动态重要性：

```
raw_importance =
    base_importance * recency_score
    + reinforcement_bonus_weight * reinforcement_score
```

```
new_importance = round(
    clamp(
        raw_importance,
        effective_min_importance,
        max_importance
    ),
    4
)
```

默认：

```
reinforcement_bonus_weight = 0.35

min_importance = 0.05

conflicted_min_importance = 0.30

max_importance = 1.00
```

最低值：

```
if status == "conflicted":
    effective_min_importance = conflicted_min_importance
else:
    effective_min_importance = min_importance
```

计算规则：

1. 不使用旧 `importance` 参与本次公式，避免重复运行产生累积强化或重复衰减。
2. 相同 `evaluation_time` 和相同输入字段必须得到完全相同的 `new_importance`。
3. 新的独立 Archive 支持和较高置信度可以提高强化分。
4. 长期没有新的用户来源 Evidence 时，`recency_score` 持续降低。
5. `superseded` Memory 衰减更快，但不会被自动删除。
6. `conflicted` Memory 的重要性不得低于 `conflicted_min_importance`，避免未解决冲突完全消失。
7. `retrieval_count` 和 `last_retrieved_time` 不参与本公式，避免与检索阶段的 ACT-R 频率、Recency 信号重复计分。

#### 2.3.8 强化与软遗忘规则

**记忆强化**

以下情况会提高或维持重要性：

- Memory 至少具有一个 Archive Evidence，首个 Archive 提供基础 Evidence 分；更多不同 Archive 的独立支持会进一步强化。
- Memory 的置信度较高。
- Memory 最近获得了新的用户来源 Evidence。
- Memory 类型本身较稳定，例如 Profile 或 Fact。

**软遗忘**

以下情况会降低重要性：

- 长期没有新的用户来源 Evidence。
- Memory 类型本身偏短期，例如 Event。
- Memory 已被新信息标记为 `superseded`。

MVP 的软遗忘只降低排序权重，不执行以下操作：

- 不将 Memory 自动改为其他 `status`。
- 不从 Elasticsearch 删除索引文档。
- 不删除 Neo4j Memory、Evidence、Entity 或图关系。
- 不清空 `content` 或来源信息。
- 不阻止高度相关的低重要性 Memory 被 BM25 或 Vector 召回。

这种策略优先保证可追溯性，避免首版因为错误衰减而永久丢失用户信息。

#### 2.3.9 Neo4j 批量更新与并发控制

Worker 为每条 Memory 生成更新记录：

```
{
    "memory_id": "memory_000001",

    "user_id": "user_001",

    "expected_memory_version": 3,

    "importance": 0.6842
}
```

每批在一个 Neo4j Transaction 中更新：

```
UNWIND $rows AS row
MATCH (m:Memory {memory_id: row.memory_id})
WHERE m.user_id = row.user_id
  AND m.memory_version = row.expected_memory_version
SET m.importance = row.importance,
    m.last_consolidated_time = $evaluation_time
RETURN count(m) AS updated_count
```

规则：

1. 更新条件必须包含 `memory_id`、`user_id` 和读取时的 `memory_version`。
2. 如果记忆萃取在扫描后修改了 Memory 内容、置信度、状态、来源时间或主体客体字段，`memory_version` 会增加，本次巩固更新必须跳过该 Memory，避免使用旧数据计算的重要性覆盖最新状态。
3. 被版本冲突跳过的 Memory 不更新 `last_consolidated_time`，后续任务重新读取并计算。
4. 巩固只更新 `importance` 和 `last_consolidated_time`，不得修改 `memory_version`，也不得使用整节点覆盖写入。
5. 单批 Transaction 失败时，该批次不得部分提交。
6. `updated_count` 小于输入更新记录数量时，差值记录为 `version_conflict_count`，不视为整个任务失败。
7. 当更新记录数组为空时，不执行该写 Transaction，直接记录指标并推进 Cursor。
8. 本地互斥锁负责防止两个巩固任务同时执行；`memory_version` 乐观校验只负责处理巩固任务与记忆萃取之间的并发修改，不能替代任务互斥锁。

记忆检索可能在巩固期间更新 `retrieval_count` 和 `last_retrieved_time`。检索统计更新不得修改 `memory_version`，且巩固公式不读取这些字段，因此二者互不影响，不需要额外锁或分布式事务。

#### 2.3.10 与萃取和检索模块的协作

**与记忆萃取协作**

- 新 Memory 初始化固定 `importance` 和 `last_consolidated_time=null`。
- `MERGE` 新 Evidence 时，无论是否同时更新 `confidence`、`latest_source_time`、`last_seen_time` 或其他内容状态字段，都必须将目标 Memory 的 `memory_version` 加 `1`，且同一事务只增加一次；萃取模块不直接重新计算 `importance`。
- `CREATE`、`SUPERSEDE` 和 `CONFLICT` 产生的新 Memory 在下一次定时任务中进入巩固。
- Memory 内容或状态在巩固扫描后发生变化时，通过 `memory_version` 乐观校验跳过旧计算。

**与记忆检索协作**

- 检索模块从 Neo4j 读取最新 `importance` 并参与基础 ACT-R 排序。
- 检索模块独立维护 `retrieval_count` 和 `last_retrieved_time`，用于请求级频率和新鲜度评分。
- 巩固模块不读取 `retrieval_count` 和 `last_retrieved_time`，避免检索结果对长期重要性形成自我强化。
- Elasticsearch 不保存 `importance`、`retrieval_count` 和 `last_retrieved_time`，因此巩固任务完成后不需要更新 Elasticsearch。
- 重要性变化只影响最终排序，不影响 BM25 和 Vector 的直接候选召回。

#### 2.3.11 完整处理流程

```
Scheduler Trigger

        |

Try Acquire Local Consolidation Lock

   +---------+---------+
   |                   |
Failed              Acquired
   |                   |
Skip Trigger             v
                 Create run_id and
                 Fixed evaluation_time

                         |

                 Set cursor = null

                         |

                 Load Memory Batch and
                 Independent Archive Count

                         |

                 Validate Memory Fields

                         |

                 Calculate Base Importance

                         |

                 Calculate Confidence and
                 Evidence Scores

                         |

                 Calculate Reference Time
                 and Recency Score

                         |

                 Calculate New Dynamic Importance

                         |

                 Batch Update Neo4j with
                 memory_version Check

                         |

                 Record Metrics

                         |

                 Advance memory_id Cursor

                         |

                 More Candidates?

                 +---------+---------+
                 |                   |
                Yes                  No
                 |                   |
                 +---- Next Batch    v
                              Complete Run

                                     |

                              Release Local Lock
```

无论在哪个步骤退出，都必须在 `finally` 中释放本地互斥锁。

#### 2.3.12 MVP 配置

```
memory_consolidation:
    enabled: true

    schedule_cron: "0 3 * * *"

    timezone: "UTC"

    scheduler_max_instances: 1

    scheduler_coalesce: true

    scheduler_misfire_grace_time_seconds: 3600

    batch_size: 500

    evidence_saturation_count: 5

    profile_half_life_days: 365

    fact_half_life_days: 180

    preference_half_life_days: 120

    event_half_life_days: 60

    superseded_half_life_days: 30

    confidence_weight: 0.55

    evidence_weight: 0.45

    reinforcement_bonus_weight: 0.35

    min_importance: 0.05

    conflicted_min_importance: 0.30

    max_importance: 1.00
```

配置校验：

1. `batch_size` 和 `evidence_saturation_count` 必须为正整数。
2. 所有半衰期必须大于 `0`。
3. `confidence_weight + evidence_weight` 必须等于 `1.0`，允许误差不超过 `0.000001`。
4. 强化权重、Bonus 权重和重要性边界必须位于 `0.0` 至 `1.0`。
5. `min_importance <= conflicted_min_importance <= max_importance`。
6. `schedule_cron` 和 `timezone` 必须可以被 Scheduler 正确解析。
7. `scheduler_max_instances` 必须为正整数，`scheduler_misfire_grace_time_seconds` 必须大于 `0`，`scheduler_coalesce` 必须为布尔值。
8. `memory_consolidation` 是巩固调度参数的唯一配置命名空间；不得再定义 `scheduler.consolidation_cron_hour`、`scheduler.consolidation_cron_minute` 或其他重复时间配置。
9. MVP 启动时发现配置非法，应阻止巩固任务启动，但不得影响 Memory Retrieval API 提供查询服务。

#### 2.3.13 失败处理与恢复

错误或状态码：

| 错误码 | 含义 |
| --- | --- |
| consolidation_invalid_config | 巩固配置不合法，任务不启动 |
| consolidation_already_running | 已存在正在执行的巩固任务，本次调度触发被跳过 |
| consolidation_read_failed | 无法从 Neo4j 读取 Memory 或独立 Archive 数量 |
| consolidation_write_failed | Neo4j 批量更新失败 |
| invalid_memory_state | Memory 缺少计算必需字段或字段值非法 |
| missing_evidence | Memory 的 `independent_archive_count` 为 `0`，已跳过重要性更新 |

处理规则：

1. 未获取本地互斥锁时，记录 `consolidation_already_running` 并结束本次触发，不视为系统故障。
2. 读取失败时终止本轮任务；下一次定时任务重新从头扫描。
3. 批量写入失败时当前 Transaction 回滚并终止本轮任务，已完成批次不回滚。
4. 单条 Memory 字段非法或缺少 Evidence 时跳过该 Memory，继续处理同批其他数据，并记录错误日志。
5. 进程崩溃后不需要补偿事务。下一次任务从头扫描并使用新的 `evaluation_time` 重新计算；公式不依赖旧 `importance`，不会发生累积强化或重复衰减。
6. MVP 不建立 `memory_consolidation_task` 状态表，不发布 Kafka 事件，不配置自动重试队列和死信队列。
7. 所有日志至少包含 `run_id`、`evaluation_time`、Cursor、批次大小、错误码和处理数量；不得记录完整 Memory `content`。
8. 本地互斥锁必须在 `finally` 中释放，避免异常后进程内任务永久无法再次运行。

运行指标至少包括：

```
scanned_count
updated_count
version_conflict_count
invalid_memory_count
missing_evidence_count
batch_count
skipped_trigger_count
run_duration_ms
```

#### 2.3.14 MVP 实现边界

本阶段必须实现：

- 单实例定时 Scheduler。
- 进程内本地互斥锁或原子 Running Flag。
- 固定 `evaluation_time` 的每日批处理。
- 持续运行至本轮候选全部完成，不设置单轮任务超时。
- 基于 `memory_id` 的游标分页。
- Memory 与独立 Archive 数量的批量读取。
- 基于记忆类型的基础重要性和半衰期。
- Confidence、独立 Archive 数量和来源时间 Recency 信号计算。
- 动态 `importance` 重算。
- `superseded` 加速衰减和 `conflicted` 最低重要性保护。
- 基于 `memory_version` 的乐观并发校验。
- Neo4j 批量更新 `importance` 和 `last_consolidated_time`。
- 批次失败、字段非法和缺少 Evidence 的处理。
- 基础运行日志和指标。

MVP 暂不实现：

- 自动物理删除 Memory、Evidence、Entity 或图关系。
- 将低重要性 Memory 从 Elasticsearch 删除或标记为不可检索。
- MongoDB 巩固任务状态表和持久化 Cursor。
- 单轮任务最大执行时间和超时中断。
- Redis 分布式锁、多实例选主或分布式调度。
- Kafka 触发、自动重试队列和死信队列。
- 基于 `retrieval_count`、`last_retrieved_time`、Agent 成功率、失败率或显式反馈的长期强化。
- 完整 ACT-R 访问时间序列和个性化参数学习。
- LLM 生成高层摘要或 `abstraction_level > 0` 的分层记忆。
- 语义重复 Memory 的周期性合并。
- 自动解决 `CONFLICTS_WITH` 冲突。
- Entity 合并、孤立节点清理和图谱结构重写。
- 跨用户巩固和公共记忆池。

## 3. 技术选型与工程架构

本章用于固定 Memory System MVP 的第一轮工程技术选型，并将前述业务设计映射为可部署、可测试和可维护的工程结构。业务规则仍以前两章为准；本章负责规定运行环境、应用形态、进程边界、异步客户端、容器拓扑、配置方式和代理使用规则。

### 3.1 已确定的核心选型

| 决策项 | 已确定方案 |
| --- | --- |
| 操作系统 | Linux |
| 容器化 | Docker Engine |
| 本地编排 | Docker Compose v2 |
| 开发语言 | Python 3.12.13 |
| Web 框架 | FastAPI |
| 数据模型与校验 | Pydantic v2 |
| 并发模型 | 基于 `asyncio` 的全异步模型 |
| 依赖与虚拟环境管理 | `uv` + `pyproject.toml` + `uv.lock` |
| 仓库形态 | 单 Git 仓库 |
| 部署形态 | 单仓库、单应用镜像、多个独立容器入口 |
| LLM Provider | DeepSeek 官方 API，OpenAI ChatCompletions 兼容接口 |
| LLM Model | Compression 与 Structured Extraction 均使用 `deepseek-v4-flash` |
| LLM Structured Output | 非思考模式 + `response_format={"type":"json_object"}` + Pydantic Schema 校验 |
| Embedding | **默认** SiliconFlow 托管 API；本地 TEI 为**可选**自托管（非 MVP 阻塞） |
| Embedding Model | 开源模型 `BAAI/bge-m3`，仅使用 Dense Embedding，输出维度固定为 `1024` |
| Embedding Engine | **默认** SiliconFlow Hosted API；**可选** Hugging Face Text Embeddings Inference（TEI）`1.9.3` 自托管，镜像使用 Digest 锁定 |
| Embedding Runtime | SiliconFlow 托管为默认路径；TEI 自托管时默认 CPU，RTX A5000 空闲时使用 Ampere 8.6 GPU；通过 Compose Override 在启动前选择 |
| Embedding Input Limit | 单条文本最多 `1024` Token；TEI 路径使用 `/tokenize` 精确校验；SiliconFlow 路径见 §3.10.0 与 DEV-007 Contract |
| 消息队列 | Apache Kafka，单节点 KRaft Combined Mode |
| MongoDB 部署 | 单节点 Standalone；MVP 不使用跨文档事务和 Change Stream |
| Elasticsearch | `9.4.4`，单节点，开发与测试环境设置 `xpack.security.enabled=false` |
| API 鉴权 | 内部静态 API Key；普通 Key 与 Admin Key 分离 |
| Scheduler | APScheduler `3.11.3` 的 `AsyncIOScheduler` |
| 日志与指标 | `structlog` JSON Log + `prometheus-client` |
| 测试容器策略 | `compose.test.yaml` 启动独立集成与 E2E 环境 |
| 基础设施 | Redis、MongoDB、Kafka、Neo4j、Elasticsearch 全部由 Docker Compose 启动 |
| 宿主机网络代理 | 宿主机端口 `7890` |

MVP 不采用多仓库微服务，不为每个业务模块单独维护应用镜像，也不使用 Kubernetes、服务网格、Celery 或第二套任务队列。

### 3.2 应用容器与进程边界

MVP 使用一份应用代码和一份应用镜像，通过不同启动命令运行三个应用容器：

| 容器 | 启动入口 | 主要职责 |
| --- | --- | --- |
| `memory-api` | `python -m memory_system.entrypoints.api` | Session、消息、Working Memory、Session Close、Compression 协调和 Memory Retrieval API |
| `memory-extraction-worker` | `python -m memory_system.entrypoints.extraction_worker` | 消费 Kafka、管理 Extraction Task、调用外部 LLM、写入 Neo4j 并同步 Elasticsearch |
| `memory-consolidation-worker` | `python -m memory_system.entrypoints.consolidation_worker` | 运行单实例 Scheduler，执行巩固与软遗忘批处理 |

`Compression Service` 和 `Memory Retrieval Service` 与 `memory-api` 部署在同一个进程中，通过应用层内部 Service 调用完成，不额外拆成独立网络服务。

`LLM Extraction Service` 与 `memory-extraction-worker` 部署在同一个进程中。Worker 通过内部 DeepSeek LLM Client 调用 DeepSeek 官方 API，不为 Structured Extraction 单独部署 HTTP 服务。

本地 Embedding 使用独立容器：

| 容器 | 主要职责 |
| --- | --- |
| `embedding-service` | 运行 Digest 锁定的 TEI `1.9.3`，加载固定 Revision 的 `BAAI/bge-m3`，通过 `/tokenize` 和 `/v1/embeddings` 提供 1024 维 Dense Embedding |

应用侧只依赖 `EmbeddingClient` Protocol，不直接依赖 TEI Python SDK。具体适配器使用共享 `httpx.AsyncClient` 调用 TEI 原生 HTTP API，并满足：

1. 模型标识固定为 `BAAI/bge-m3`，Revision 固定为 `57aacf8560157b7c1d4f771ce1a199877aeeec74`。
2. 输出维度严格为 `1024`，只返回 Dense Embedding。
3. 支持批量文本输入，单次最多 `64` 条。
4. 容器只监听 Compose 内部网络，默认不对宿主机开放。
5. 返回顺序与输入顺序一致。
6. 单条输入通过 `/tokenize` 精确校验为不超过 `1024` Token。
7. CPU 与 GPU 模式使用相同模型 Revision、Pooling、Normalize 和输入规则。

### 3.3 Docker Compose 服务拓扑

MVP Compose 至少包含以下服务：

```
memory-api
memory-extraction-worker
memory-consolidation-worker
embedding-service
redis
mongodb
kafka
neo4j
elasticsearch
init-infra
```

其中：

- `memory-api`、`memory-extraction-worker` 和 `memory-consolidation-worker` 使用同一个应用镜像。
- `embedding-service` 使用 TEI 独立推理镜像；基础 Compose 不固定 CPU 或 GPU 镜像，由 `compose.embedding.cpu.yaml` 或 `compose.embedding.gpu.yaml` 覆盖定义。
- CPU 与 GPU Override 使用相同 Service Name `embedding-service`，不能同时启用。
- `init-infra` 是一次性初始化容器或初始化命令，不常驻运行。
- Redis、MongoDB、Kafka、Neo4j 和 Elasticsearch 使用独立持久化 Volume。
- 应用容器通过 Compose Service Name 访问基础设施，禁止在容器配置中使用 `localhost` 访问其他服务。

内部连接地址示例：

```
redis://redis:6379
mongodb://mongodb:27017
kafka:9092
neo4j://neo4j:7687
http://elasticsearch:9200
http://embedding-service:80
```

Compose 使用一个内部网络：

```
memory-system-network
```

MVP 不需要为不同基础设施划分多个 Docker Network。后续需要更严格网络隔离时，再拆分应用网络和数据网络。

### 3.4 单仓库目录结构

MVP 固定项目目录：

```
memory-system/
├── pyproject.toml
├── uv.lock
├── .python-version
├── .env.example
├── versions.env
├── .gitignore
├── .dockerignore
├── Dockerfile
├── compose.yaml
├── compose.override.yaml
├── compose.embedding.cpu.yaml
├── compose.embedding.gpu.yaml
├── compose.test.yaml
├── README.md
│
├── configs/
│   ├── base.yaml
│   ├── development.yaml
│   └── test.yaml
│
├── src/
│   └── memory_system/
│       ├── __init__.py
│       │
│       ├── entrypoints/
│       │   ├── api.py
│       │   ├── extraction_worker.py
│       │   └── consolidation_worker.py
│       │
│       ├── api/
│       │   ├── routes/
│       │   ├── dependencies.py
│       │   ├── middleware.py
│       │   └── error_handlers.py
│       │
│       ├── domain/
│       │   ├── models/
│       │   ├── enums/
│       │   ├── errors/
│       │   └── services/
│       │
│       ├── application/
│       │   ├── short_term_memory/
│       │   ├── compression/
│       │   ├── extraction/
│       │   ├── retrieval/
│       │   └── consolidation/
│       │
│       ├── infrastructure/
│       │   ├── redis/
│       │   ├── mongodb/
│       │   ├── kafka/
│       │   ├── neo4j/
│       │   ├── elasticsearch/
│       │   ├── llm/
│       │   ├── embedding/
│       │   └── security/
│       │
│       ├── settings/
│       ├── observability/
│       └── utils/
│
├── scripts/
│   ├── __init__.py
│   ├── preflight/
│   │   └── check_linux_host.sh
│   ├── migrations/
│   │   ├── __init__.py
│   │   ├── 001_initial_mongodb.py
│   │   ├── 002_initial_neo4j.py
│   │   ├── 003_elasticsearch_memory_v1.py
│   │   └── 004_initial_kafka_topics.py
│   ├── migrate.py
│   ├── compose.sh
│   ├── start_embedding.sh
│   ├── check_env_example.py
│   └── republish_archive_event.py
│
└── tests/
    ├── unit/
    ├── integration/
    ├── contract/
    └── e2e/
```

规则：

1. `domain` 不直接依赖 Redis、MongoDB、Kafka、Neo4j 或 Elasticsearch Client。
2. `application` 编排业务流程，通过 Repository 或 Client Protocol 访问基础设施。
3. `infrastructure` 实现具体数据库、外部服务、安全与可观测性适配器。
4. API Route 不直接编写数据库查询和跨存储事务流程。
5. 三个 Entrypoint 共享 Domain、Application 和 Infrastructure 代码。
6. MVP 不引入复杂插件系统或动态依赖注入框架，使用显式 Factory 和 FastAPI Dependency 即可。
7. `versions.env` 保存 Compose 基础设施镜像 Tag；不得在多个 Compose 文件中重复硬编码版本。
8. `compose.test.yaml` 使用独立容器名、Volume 和测试数据库，禁止复用开发环境持久化数据。
9. `compose.embedding.cpu.yaml` 与 `compose.embedding.gpu.yaml` 必须使用相同的 `embedding-service` 名称并保持互斥；Embedding 模式选择由 `scripts/start_embedding.sh` 管理。
10. 所有 Docker Compose 操作必须通过 `scripts/compose.sh` 执行。文档、开发脚本、CI 和运维命令不得直接调用裸 `docker compose`，避免遗漏环境文件或 CPU/GPU Override。

### 3.5 Python 与依赖管理

Python 运行时版本固定为：

```text
Python 3.12.13
```

`pyproject.toml` 的兼容范围声明为：

```
requires-python = ">=3.12,<3.13"
```

依赖管理使用 `uv`：

- `pyproject.toml` 声明直接依赖和允许的版本范围。
- `uv.lock` 保存完整解析后的精确版本。
- `uv.lock` 必须提交到 Git。
- 本地开发使用 `uv sync`。
- CI 和 Docker Build 使用 `uv sync --locked`。
- 禁止直接手工修改 `uv.lock`。
- MVP 不同时维护 Poetry、Pipenv 和 Conda 环境文件。

依赖按运行时、质量和测试三个 Dependency Group 管理。`pyproject.toml` 必须使用以下兼容范围，首次执行 `uv lock` 后由 `uv.lock` 固定实际 Patch 版本：

```toml
[project]
requires-python = ">=3.12,<3.13"
dependencies = [
    "fastapi>=0.139,<0.140",
    "pydantic>=2.13,<2.14",
    "pydantic-settings>=2.14,<2.15",
    "pyyaml>=6.0,<7",
    "uvicorn[standard]>=0.47,<0.48",
    "httpx>=0.28,<0.29",
    "openai>=2.46,<3",
    "redis>=8.0,<8.1",
    "pymongo>=4.17,<4.18",
    "aiokafka>=0.13,<0.14",
    "neo4j>=5.28,<6",
    "elasticsearch[async]>=9.4,<9.5",
    "apscheduler>=3.11,<4",
    "structlog>=26.1,<27",
    "prometheus-client>=0.25,<0.26",
]

[dependency-groups]
quality = [
    "ruff>=0.15,<0.16",
    "mypy>=2.1,<2.2",
]
test = [
    "pytest>=9.1,<9.2",
    "pytest-asyncio>=1.4,<1.5",
    "pytest-cov>=7.1,<7.2",
]
```

Build System 固定如下。`uv_build` 仅为 Build System Requirement，不属于 `project.dependencies`、`quality` 或 `test` 组，不得写入上述三组依赖列表：

```toml
[build-system]
requires = ["uv_build>=0.11.32,<0.13"]
build-backend = "uv_build"
```

禁止将 Build Backend 自行替换为 Hatchling、Setuptools、Poetry Backend 或其他构建后端；禁止放宽或抬高 `uv_build` 的版本上界。

规则：

1. `pyproject.toml` 固定允许升级的 Minor 范围，`uv.lock` 固定实际精确版本；二者缺一不可。
2. AI Coding Agent 首次初始化项目时必须严格使用上述范围生成 `uv.lock`，不得自行替换为更高 Minor / Major 版本。
3. `uv sync --locked` 是 Docker Build 和 CI 的唯一安装方式；Lockfile 与 `pyproject.toml` 不一致时必须失败，不得自动重新解析。
4. 依赖升级必须作为独立提交，更新允许范围和 Lockfile，并执行 Unit、Contract、Integration 与 E2E 测试。
5. 禁止使用无上界依赖，例如 `fastapi>=0.139`、`redis>=8` 或 `elasticsearch>=9`。
6. YAML 解析固定使用 `PyYAML` 的 `yaml.safe_load`；禁止使用 `yaml.load` 的不安全默认 Loader，也不得由 AI 替换为第二套 YAML 库。
7. 禁止使用 `opensearch-py`、旧 `elasticsearch-async` 包、Motor、APScheduler 4 预发布版本或未经兼容性测试的其他替代包。
8. Elasticsearch Server 固定为 `9.4.4`，Python Client 只允许 `9.4.x`。未来升级 Server Minor 时，必须同步调整 Client 允许范围并执行完整检索回归。
9. 如果上游依赖发布安全补丁但仍位于允许范围内，只能通过显式 `uv lock --upgrade-package <package>` 升级；不得在普通 Build 中隐式漂移。
10. `pyproject.toml` 必须包含上文固定的 `[build-system]`；`uv_build` 仅作为 Build System Requirement，不得加入 `project.dependencies`、`quality` 或 `test` 组，也不得替换为其他 Build Backend。

### 3.6 全异步客户端选型

应用层统一使用 `asyncio`。所有网络 I/O 必须使用异步接口，禁止在 Event Loop 中直接执行长时间同步网络调用。

| 依赖 | 客户端选择 | 使用规则 |
| --- | --- | --- |
| DeepSeek LLM | `openai.AsyncOpenAI` | 使用 `base_url=https://api.deepseek.com`；每个调用 DeepSeek 的进程创建一个长期存活 Client，关闭时显式 `close()` |
| Embedding / 其他内部 HTTP | `httpx.AsyncClient` | 每个进程创建共享 Client，应用关闭时显式关闭 |
| Redis | `redis.asyncio` | 使用连接池；进程关闭时显式关闭 Client 和 Pool |
| MongoDB | `pymongo.AsyncMongoClient` | 不使用 Motor；每个 Event Loop 使用独立 Client |
| Kafka | `aiokafka.AIOKafkaProducer`、`AIOKafkaConsumer` | Producer 和 Consumer 在 Entrypoint 生命周期中启动和关闭；Consumer 必须关闭自动提交 |
| Neo4j | `neo4j.AsyncGraphDatabase` | 每个进程创建一个长期存活的 Async Driver；每次操作使用短生命周期 Session |
| Elasticsearch | `elasticsearch.AsyncElasticsearch` | 安装 `elasticsearch[async]>=9.4,<9.5`；使用官方异步 Client 与异步 Bulk Helper；实际 Patch 版本由 `uv.lock` 固定 |

Kafka Consumer 必须设置：

```
enable_auto_commit = false
```

Offset 提交严格遵守前文 `2.1` 定义的状态机。不得因为使用 `aiokafka` 而改变任务完成、失败记录和 Offset Commit 顺序。

PyMongo Async Client 不得跨 Event Loop 或线程共享。每个应用进程只在自己的主 Event Loop 中创建和使用 Client。

对于暂时没有可靠异步接口的 CPU 密集型本地操作，应使用独立进程或受控线程池，禁止直接阻塞 FastAPI Event Loop。当前 MVP 的字符 Token 估算、Fingerprint 和评分公式可以直接在 Event Loop 中执行。

### 3.7 Web 服务与应用生命周期

`memory-api` 使用：

```
FastAPI
Uvicorn
Pydantic v2
Pydantic Settings
```

MVP 每个 `memory-api` 容器运行一个 Uvicorn 进程。后续需要提高吞吐量时，优先增加容器副本，不在 MVP 中引入 Gunicorn 多 Worker 和进程内共享状态问题。

FastAPI Lifespan 负责：

1. 加载和校验配置。
2. 创建 Redis、MongoDB、Neo4j、Elasticsearch 和 HTTP Client。
3. 创建 Kafka Producer。
4. 执行依赖连接检查。
5. 在应用关闭时按照与创建相反的顺序释放资源。

`memory-extraction-worker` 和 `memory-consolidation-worker` 使用独立 `asyncio.run(main())` Entrypoint，不依赖 FastAPI 启动。

### 3.8 配置管理

配置采用：

```
.env
+
YAML
+
Pydantic Settings
```

职责划分：

| 配置来源 | 保存内容 |
| --- | --- |
| `.env` / 环境变量 | 密码、API Key、连接地址、代理地址、部署环境和容器级覆盖参数 |
| YAML | 前文定义的业务阈值、超时、权重、半衰期和批量大小 |
| Pydantic Settings | 读取、类型转换、跨字段校验和默认值 |

优先级：

```
环境变量
    > 环境专用 YAML
    > base.yaml
    > 代码默认值
```

加载实现固定如下：

1. `settings/loader.py` 使用 `yaml.safe_load` 读取 `configs/base.yaml`；空文件按空字典处理。
2. 根据 `APP_ENV` 读取对应的 `configs/{environment}.yaml`，并对基础配置执行递归字典覆盖。
3. 合并后的 YAML 字典作为自定义 Pydantic Settings Source；`settings_customise_sources` 必须保证环境变量 Source 的优先级高于 YAML Source，YAML Source 高于 Model 默认值。
4. 应用代码只能通过统一 Settings Model 读取配置，不得在业务模块中散落调用 `os.getenv()` 或再次读取 YAML。

规则：

1. `.env` 不得提交 Git，只提交 `.env.example`。
2. `.env.example` 只能包含字段名和非敏感示例值。
3. 密码、Token 和 LLM API Key 不得写入 YAML、代码或 Dockerfile。
4. YAML 只允许使用 `PyYAML` 的 `yaml.safe_load`；解析结果根节点必须为 Object/Mapping，否则服务启动失败并返回配置错误。
5. 服务启动时必须执行配置校验；配置非法时对应服务启动失败。
6. 配置字段命名使用大写环境变量和双下划线层级映射，例如：

```
APP_ENV
MONGODB__URI
REDIS__URI
KAFKA__BOOTSTRAP_SERVERS
LLM__BASE_URL
LLM__API_KEY
LLM__COMPRESSION__MODEL
LLM__EXTRACTION__MODEL
EMBEDDING__MODEL_ID
EMBEDDING__BASE_URL
SILICONFLOW_API_KEY
PROXY__HTTP_URL
```

`SILICONFLOW_API_KEY` 通过环境变量注入，类型为 `SecretStr`；**仅当** `memory_retrieval.embedding_provider=siliconflow` 时必填。不得将 API Key 写入 YAML、代码、Dockerfile、日志或测试 Fixture。

### 3.9 DeepSeek LLM 接入方式

Compression 和 Structured Extraction 统一使用 DeepSeek 官方 API：

```yaml
llm:
    provider: "deepseek"
    base_url: "https://api.deepseek.com"
    api_mode: "openai_chat_completions"

    compression:
        model: "deepseek-v4-flash"
        thinking: "disabled"
        response_format: "json_object"
        temperature: 0
        max_output_tokens: 2048

    extraction:
        model: "deepseek-v4-flash"
        thinking: "disabled"
        response_format: "json_object"
        temperature: 0
        max_output_tokens: 8192
```

API Key 通过环境变量注入：

```text
LLM__API_KEY
```

不得将 API Key 写入 YAML、代码、Dockerfile、日志或测试 Fixture。

应用使用 `openai.AsyncOpenAI` 访问 DeepSeek 的 OpenAI ChatCompletions 兼容接口：

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=settings.llm.api_key.get_secret_value(),
    base_url="https://api.deepseek.com",
)
```

MVP 不使用 Anthropic 兼容接口，也不使用已经废弃的 `deepseek-chat` 或 `deepseek-reasoner` 模型别名。模型名称必须显式使用：

```text
deepseek-v4-flash
```

DeepSeek V4 默认启用思考模式。Compression 和 Structured Extraction 都属于受 Schema 约束的单轮数据处理任务，为降低延迟、输出成本和响应结构复杂度，必须显式关闭思考模式：

```python
extra_body={"thinking": {"type": "disabled"}}
```

不得依赖服务端默认值。MVP 不读取、不存储也不转发 `reasoning_content`。

单次结构化调用的核心参数如下：

```python
response = await client.chat.completions.create(
    model=model_name,
    messages=messages,
    stream=False,
    temperature=0,
    max_tokens=max_output_tokens,
    response_format={"type": "json_object"},
    extra_body={"thinking": {"type": "disabled"}},
)
```

DeepSeek 当前提供的是 JSON Object 模式，而不是由服务端严格执行的原生 JSON Schema。应用必须继续使用 Pydantic v2 对返回内容进行完整 Schema 校验，禁止仅因为结果能够被 `json.loads()` 解析就认为调用成功。

JSON Output 规则：

1. System Prompt 或 User Prompt 中必须明确包含 `JSON` 字样。
2. Prompt 必须提供目标 JSON 结构或示例。
3. Compression 和 Extraction 使用不同的 `prompt_version`、Schema 和 `max_output_tokens`。
4. `response_format` 固定为 `{"type":"json_object"}`，不得改为 Tool Calling。
5. `stream` 固定为 `false`，不得对结构化结果使用流式拼接。
6. Assistant `content` 为 `null`、空字符串或仅空白字符时，属于 `llm_empty_output`，不是合法的空业务结果。
7. Compression 的合法空结果必须是可解析 JSON，例如 `{"compressed_context":""}`。
8. JSON 解析失败、字段缺失、类型错误、枚举非法或 Pydantic 校验失败，按照前文规则最多使用相同输入重新调用一次。
9. 第二次仍失败时，Compression 返回对应压缩错误，Extraction 返回 `llm_invalid_output`。
10. LLM HTTP Read Timeout 不在传输层自动重试，避免重复计费；只允许业务流程明确规定的 Schema 失败重试。

统一 `LLMClient` Contract：

```python
async generate_structured(
    model: str,
    system_prompt: str,
    user_prompt: str,
    response_schema: type[BaseModel],
    timeout_seconds: float,
    max_output_tokens: int,
) -> BaseModel
```

实现要求：

1. Compression 和 Extraction 共用 DeepSeek Client 与底层连接池，但使用独立配置对象。
2. `memory-api` 和 `memory-extraction-worker` 分别在自己的 Event Loop 中创建 Client，不跨进程或 Event Loop 共享。
3. 超时、连接错误、HTTP 错误、限流错误、空输出和 Schema 错误必须映射为文档定义的业务错误码。
4. 对 HTTP `429` 和 `5xx` 不做无限自动重试；是否人工重试由对应业务状态机决定。
5. 日志不得记录完整 Prompt、完整原始消息、完整模型 Response 或 API Key。
6. 日志可以记录模型名、Prompt Version、输入与输出 Token Usage、请求耗时、HTTP Status 和错误码。
7. MVP 不实现多 Provider、模型路由、自动故障切换或 V4-Pro 降级/升级策略。
8. `openai` Python SDK 在 `pyproject.toml` 中限制为 `>=2.46,<3`，实际 Patch 版本由 `uv.lock` 固定。

### 3.10 本地 Embedding 部署方式

#### 3.10.0 MVP 默认 Embedding Provider Pivot（OI-012）

MVP 默认 Embedding Provider 为 **SiliconFlow 托管 API**，模型 `BAAI/bge-m3`，输出维度 **1024**。Integration 门禁：实际输出 `dim≠1024` 时 **HALT**（报告；**不改** ES mapping）。本地 TEI 自托管为**可选**、**非 MVP 阻塞**；保留 OI-011 既有 TEI contract，本 OI 不修改。

Provider-specific batch limits（各自 Client Contract 内分片）：

- **SiliconFlow**：每 HTTP 请求 `input` 最多 **32** 条
- **TEI**：每 HTTP 请求最多 **64** 条

`SiliconFlowEmbeddingClient` 实现 Contract（**DEV-007**）摘要 **M1–M11**：保留 `EmbeddingClient` Protocol；`POST https://api.siliconflow.cn/v1/embeddings`；`httpx`（无 SDK）；`SILICONFLOW_API_KEY`（`SecretStr`）；默认 `embedding_provider=siliconflow`；429/5xx/timeout **有界重试**：**1 次初始 + 最多 2 次重试 = 最多 3 次 HTTP attempt**；400/401/403 fail-fast；空字符串零 HTTP；observability 最小集（provider、status_code、trace_id、bounded sanitized error；禁止 key/auth/全文/vectors）。SiliconFlow 向量 L2 归一化：**UNKNOWN / DEV-007 规划决策**（不得猜测）。本地 HF tokenizer 体系：**DEFERRED**（MVP 不建）。

#### 3.10.1 固定选型

Embedding Service 固定采用 Hugging Face Text Embeddings Inference（TEI）`1.9.3`：

```text
Engine: Hugging Face Text Embeddings Inference 1.9.3
Model ID: BAAI/bge-m3
Model Revision: 57aacf8560157b7c1d4f771ce1a199877aeeec74
Embedding Mode: dense only
Dimension: 1024
Pooling: 使用模型自身 CLS Pooling 配置
Normalize: 使用模型自身 Normalize 模块，应用层不再次归一化
Model Maximum Sequence Length: 8192
MVP Per-Input Limit: 1024 Token
Default Runtime: CPU
Optional GPU: NVIDIA RTX A5000, Ampere Compute Capability 8.6
Runtime Hot Switch: disabled
```

TEI 官方提供的 `cpu-1.9` 与 `86-1.9` 属于 `1.9.x` 发布线标签，不能单独作为最终可复现锁。项目使用“来源标签 + 精确 Digest”两层锁定：

```dotenv
# versions.env：可读的来源标签与预期版本
TEI_EXPECTED_VERSION=1.9.3
TEI_CPU_IMAGE_SOURCE=ghcr.io/huggingface/text-embeddings-inference:cpu-1.9
TEI_GPU_IMAGE_SOURCE=ghcr.io/huggingface/text-embeddings-inference:86-1.9
```

```dotenv
# versions.lock.env：由锁定脚本生成并提交 Git
TEI_CPU_IMAGE=ghcr.io/huggingface/text-embeddings-inference:cpu-1.9@sha256:<cpu_image_digest>
TEI_GPU_IMAGE=ghcr.io/huggingface/text-embeddings-inference:86-1.9@sha256:<gpu_image_digest>
```

Compose 只允许读取 `versions.lock.env` 中包含 `@sha256:` 的 `TEI_CPU_IMAGE` 和 `TEI_GPU_IMAGE`。缺失 Digest、Digest 格式非法或镜像元数据版本不等于 `TEI_EXPECTED_VERSION` 时，Preflight 和启动脚本都必须硬失败。Digest 的解析与更新规则见第 `3.10.9` 节。

RTX A5000 使用 Ampere 8.6 镜像。GPU 模式要求 Linux 宿主机安装可用的 NVIDIA Driver 与 NVIDIA Container Toolkit，驱动需兼容 TEI 镜像要求的 CUDA 运行时。

#### 3.10.2 Compose 文件结构

Embedding 使用以下 Compose 文件：

```text
compose.yaml
compose.embedding.cpu.yaml
compose.embedding.gpu.yaml
```

两个 Override 都定义相同 Service Name：

```text
embedding-service
```

应用内部始终访问：

```text
http://embedding-service:80
```

TEI 原生接口：

```text
POST /tokenize
POST /v1/embeddings
GET  /docs
```

不得同时加载 CPU 与 GPU Override。标准启动命令：

```bash
# CPU
./scripts/start_embedding.sh cpu

# GPU
./scripts/start_embedding.sh gpu

# 启动前自动选择
./scripts/start_embedding.sh auto
```

脚本必须按以下顺序加载配置：

```text
.env
versions.env
versions.lock.env
.runtime/embedding.env
```

后加载文件覆盖前面的同名非 Secret 变量。`.env` 保存本地 Secret，不提交 Git；`versions.env` 和 `versions.lock.env` 必须提交 Git；`.runtime/embedding.env` 由启动脚本生成，不提交 Git。

`scripts/start_embedding.sh` 只负责模式检测、生成 `.runtime/embedding.env`，并通过统一 Compose Wrapper 启动 `embedding-service`，不得顺带启动应用或其他基础设施。其内部等价于：

```bash
# CPU
./scripts/compose.sh --embedding=cpu up -d embedding-service

# GPU
./scripts/compose.sh --embedding=gpu up -d embedding-service
```

项目必须提供统一入口：

```text
scripts/compose.sh
```

Wrapper 语义：

```text
--embedding=none
    仅加载 compose.yaml，不加载 Embedding Override。

--embedding=cpu
    加载 compose.yaml + compose.embedding.cpu.yaml。

--embedding=gpu
    加载 compose.yaml + compose.embedding.gpu.yaml。

--embedding=current
    从 .runtime/embedding.env 读取 EMBEDDING_EFFECTIVE_RUNTIME_MODE，
    只允许解析为 cpu 或 gpu，并加载对应 Override。
```

`scripts/compose.sh` 每次调用必须按固定顺序加载：

```text
.env
versions.env
versions.lock.env
.runtime/embedding.env（存在时）
```

规则：

1. 默认模式为 `--embedding=current`；若 `.runtime/embedding.env` 尚不存在，只有显式 `--embedding=none`、`cpu` 或 `gpu` 才允许执行。
2. `current` 模式遇到缺失文件、非法模式或 Token Budget 与模式不匹配时必须硬失败。
3. Wrapper 必须使用 `exec docker compose ... "$@"` 传递原始子命令和参数，不得重新解释 `run`、`up`、`logs`、`down` 等命令。
4. `start_embedding.sh` 调用 Wrapper 时必须在命令末尾指定 `embedding-service`，防止 `up -d` 启动 Compose 中全部服务。
5. `init-infra`、三个应用容器、日志、停止和测试命令都必须复用同一个 Wrapper，从而读取完全相同的镜像、运行模式和 Token Budget。
6. CI 增加静态检查：除 `scripts/compose.sh` 自身和说明文档外，Shell Script 与 Makefile 中不得出现裸 `docker compose`。

#### 3.10.3 CPU 默认模式

CPU 是默认和可靠兜底模式。CPU Override 至少包含：

```yaml
services:
  embedding-service:
    image: ${TEI_CPU_IMAGE}
    environment:
      AUTO_TRUNCATE: "false"
    command:
      - --model-id
      - ${EMBEDDING_MODEL_ID}
      - --revision
      - ${EMBEDDING_MODEL_REVISION}
      - --served-model-name
      - ${EMBEDDING_MODEL_ID}
      - --dtype
      - float32
      - --max-client-batch-size
      - "64"
      - --max-batch-tokens
      - "8192"
      - --max-batch-requests
      - "4"
      - --max-concurrent-requests
      - "8"
      - --json-output
    volumes:
      - embedding-model-cache:/data
    mem_limit: 12g
    cpus: 4.0
```

CPU TEI `mem_limit: 12g` 是 **model-runtime-profile-specific fixed contract**，仅适用于当前 MVP CPU profile（`BAAI/bge-m3` @ 规格冻结 Revision、`dtype=float32`、ONNX CPU、pinned TEI digest）。模型、Revision、Pooling、Normalize、维度与单条输入上限不得改变。任何低于该正式 contract 的 override（含环境变量、临时 compose overlay、手工 `docker update` 等）均为 **`NON_SPEC_COMPLIANT`**（unsupported），不得视为规格合规。

#### 3.10.4 RTX A5000 GPU 模式

GPU Override 使用 Ampere 8.6 TEI 镜像：

```yaml
services:
  embedding-service:
    image: ${TEI_GPU_IMAGE}
    environment:
      AUTO_TRUNCATE: "false"
    command:
      - --model-id
      - ${EMBEDDING_MODEL_ID}
      - --revision
      - ${EMBEDDING_MODEL_REVISION}
      - --served-model-name
      - ${EMBEDDING_MODEL_ID}
      - --dtype
      - float16
      - --max-client-batch-size
      - "64"
      - --max-batch-tokens
      - "16384"
      - --max-batch-requests
      - "16"
      - --max-concurrent-requests
      - "32"
      - --json-output
    volumes:
      - embedding-model-cache:/data
    mem_limit: 8g
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities:
                - gpu
```

GPU 模式只表示容器获得一张 GPU 的访问权限，不代表独占 GPU。启动脚本必须在启动前检查空闲显存，默认阈值：

```yaml
embedding:
  gpu:
    minimum_free_memory_mb: 8192
```

#### 3.10.5 `cpu`、`gpu` 与 `auto` 启动语义

`scripts/start_embedding.sh` 必须支持：

```text
cpu：无条件使用 CPU Override。
gpu：要求 NVIDIA Driver、Container Toolkit、A5000 可见且空闲显存满足阈值；不满足则失败，不自动改为 CPU。
auto：启动前检测 GPU；满足条件时尝试 GPU，否则使用 CPU。
```

`auto` 模式流程：

```text
检查 nvidia-smi
    ↓
检查 Docker NVIDIA Runtime
    ↓
查找可见 RTX A5000
    ↓
检查空闲显存 >= 8192 MiB
    ↓
满足：启动 GPU Override 并等待 Health Check
不满足：启动 CPU Override
    ↓
GPU 启动或 Health Check 失败：清理失败容器并回退 CPU
```

自动选择只发生在服务启动前。MVP 不实现请求级 GPU/CPU 路由，不监控其他用户任务后自动迁移，不在运行中热切换容器。

启动脚本在确定最终模式后必须生成仅供本次 Compose 启动使用的：

```text
.runtime/embedding.env
```

内容至少包括：

```dotenv
EMBEDDING_EFFECTIVE_RUNTIME_MODE=cpu|gpu
EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET=4096|16384
```

`auto` 不是应用运行时可见的有效模式。`memory-api` 和 `memory-extraction-worker` 必须读取脚本解析后的 `EMBEDDING_EFFECTIVE_RUNTIME_MODE`，不得自行再次探测 GPU 或根据延迟猜测运行模式。

`compose.yaml` 必须在 `memory-api` 和 `memory-extraction-worker` 的 `environment` 中显式映射：

```yaml
EMBEDDING_EFFECTIVE_RUNTIME_MODE: ${EMBEDDING_EFFECTIVE_RUNTIME_MODE}
EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET: ${EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET}
```

`--env-file` 只作为 Compose 变量来源，不等于自动将全部变量注入容器；禁止依赖隐式环境继承。

#### 3.10.6 输入、批量和一致性规则

Embedding 输入处理分为“单条长度校验”“业务请求拆分”“TEI 动态批处理”三层，三者不得混为同一个限制。

固定配置：

```yaml
embedding:
  max_client_batch_size: 64
  per_input_token_limit: 1024

  cpu:
    client_total_token_budget: 4096
    tei_max_batch_tokens: 8192

  gpu:
    client_total_token_budget: 16384
    tei_max_batch_tokens: 16384
```

规则：

1. `TEIEmbeddingClient` 必须先调用 `/tokenize` 获得每条输入的精确 `token_count`；任何单条输入超过 `1024` Token 时，立即返回 `embedding_input_too_long`，不得调用 `/v1/embeddings`。
2. CPU 和 GPU Override 都必须显式设置 `AUTO_TRUNCATE=false`。业务层的 1024 Token 限制是主要保护，TEI 禁止自动截断是服务端兜底；任何路径都不得返回被静默截断后的向量。
3. BGE-M3 的模型最大长度为 `8192`。关闭自动截断后，CPU 的 TEI `max_batch_tokens` 固定为 `8192`，不得继续设置为 `4096`，否则服务可能因批次上限低于模型最大长度而拒绝启动。客户端仍可使用更保守的 `4096` Token 子批次预算。
4. 单次业务调用最多接受 `64` 条文本。这里的 `64` 只限制输入条数，不代表这 64 条可以一次提交给 TEI。
5. 客户端按原始输入顺序进行稳定分批。每个子批次必须同时满足：

```text
len(sub_batch) <= 64

CPU：
sum(token_count) <= 4096

GPU：
sum(token_count) <= 16384
```

6. 分批算法必须是确定性的 First-Fit-In-Order：从第一条输入开始累加，加入下一条将超过条数或 Token 预算时结束当前子批次，再创建下一个子批次。不得为了提高装箱率而重排文本。
7. 每个子批次调用 `/v1/embeddings` 后，客户端按原始输入下标合并向量，最终返回顺序必须与请求顺序完全一致。任一子批次失败时，整个业务调用失败，不返回部分向量。
8. `EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET` 由启动脚本根据最终有效模式写入 `.runtime/embedding.env`：CPU 为 `4096`，GPU 为 `16384`。应用不得从用户请求、GPU 当前利用率或 TEI 响应时间动态修改预算。
9. CPU 使用 `float32`，GPU 使用 `float16`；两种模式必须使用相同模型 Revision 和模型自带的 CLS Pooling、Normalize 模块。
10. CPU/GPU 切换不要求立即重建索引，但切换后必须先通过向量一致性 Contract Test。
11. 固定 Fixture 至少包含 `20` 条中英文文本。CPU 与 GPU 对应向量必须满足：维度为 `1024`、无 NaN/Inf、L2 Norm 接近 `1`、对应向量 Cosine Similarity 不低于配置项 `embedding.consistency.minimum_cosine_similarity`；初始值为 `0.999`。
12. `0.999` 是初始验收值，必须通过实际 RTX A5000 Fixture 测试确认。若不能稳定通过，只能由人工基于测试报告调整配置并记录原因，AI Coding Agent 不得自行降低阈值。
13. 一致性测试失败时禁止继续向同一 Elasticsearch Index 混写向量；必须统一运行模式并重建 Index。
14. Query 不添加额外检索指令；Memory 与 Query 使用相同预处理规则。
15. Contract Test 必须覆盖两类超长输入：应用层超过 `1024` Token 时不调用 TEI；绕过应用 Client 直接向 TEI 提交超过模型支持长度的输入时，TEI 必须返回错误而不是截断后成功。

#### 3.10.7 模型缓存与代理

模型文件使用独立 Volume：

```text
embedding-model-cache
```

规则：

1. 模型权重不得写入应用镜像。
2. `EMBEDDING_MODEL_REVISION` 必须固定为完整 Commit Hash，禁止部署时使用 `main`。
3. 首次下载通过宿主机 `7890` 代理；下载完成后重启应复用 Volume。
4. CPU 与 GPU Override 共享同一个只用于模型缓存的 Volume。
5. 可选离线模式必须先将固定 Revision 下载到 Volume，再禁止外网访问。
6. Embedding Service 不访问 Redis、MongoDB、Neo4j、Elasticsearch 或 Kafka。

#### 3.10.8 Health、Readiness 与降级

1. Health Check 必须确认 TEI HTTP 服务可访问。
2. Readiness Probe 必须使用固定短文本调用 `/v1/embeddings`，确认返回一条 1024 维有限浮点向量。
3. 启动前必须对最终 Digest 锁定镜像执行 `text-embeddings-router --version`，实际输出必须等于 `TEI_EXPECTED_VERSION=1.9.3`；版本不一致时不得启动。
4. `scripts/compose.sh --embedding=current config` 与 `docker inspect` 必须共同验证实际容器镜像 Digest、Command、`AUTO_TRUNCATE=false`、模型 ID、完整 Revision、Dtype、`max-client-batch-size` 和 `max-batch-tokens` 与当前模式配置一致。
5. Readiness 必须记录实际镜像 Digest、TEI 版本、有效运行模式、模型 ID、模型 Revision 和 Dtype。若当前 TEI 版本提供 `/info`，可以将其作为附加诊断信息，但不得把未在官方 Contract 中保证存在的字段作为唯一校验来源。
6. 自动截断行为由 Contract Test 通过超长输入验证：输入超过模型允许长度时 TEI 必须返回错误，不得返回截断后的向量。
7. `memory-api` 不将 Embedding 作为阻塞启动条件；Embedding 不可用时 Retrieval 跳过 Vector 通道并使用 BM25。
8. `memory-extraction-worker` 在索引同步阶段依赖 Embedding；不可用时按 `retrieval_index_write_failed` 保存失败状态，等待人工重试。
9. TEI 日志使用 JSON；不得记录完整待嵌入文本或向量。

#### 3.10.9 TEI 镜像 Digest 锁定

项目必须提供：

```text
scripts/lock_tei_images.sh
versions.env
versions.lock.env
```

锁定流程：

```text
读取 versions.env 中的 TEI_CPU_IMAGE_SOURCE、TEI_GPU_IMAGE_SOURCE
    ↓
拉取两个来源标签
    ↓
分别执行镜像 CLI 的 --version，确认输出等于 TEI_EXPECTED_VERSION=1.9.3
    ↓
解析 Linux x86_64 实际镜像 RepoDigest
    ↓
使用 Digest 引用再次执行 --version，确认版本仍一致
    ↓
生成临时 versions.lock.env
    ↓
验证两个值均包含 @sha256: 且能够重新拉取
    ↓
原子替换 versions.lock.env
```

版本命令等价于：

```bash
docker run --rm \
  --entrypoint text-embeddings-router \
  "$TEI_CPU_IMAGE_SOURCE" \
  --version

docker run --rm \
  --entrypoint text-embeddings-router \
  "$TEI_GPU_IMAGE_SOURCE" \
  --version
```

如果实际镜像 Entrypoint 已经是 `text-embeddings-router`，脚本仍应显式指定 `--entrypoint`，避免上游 Entrypoint Wrapper 改变导致版本解析失效。版本输出必须通过严格语义版本解析获得 `1.9.3`，不得使用模糊字符串包含判断。

规则：

1. `versions.lock.env` 必须提交 Git，它属于可复现构建输入，不得加入 `.gitignore`。
2. 日常 Pull、启动、CI 和 E2E 测试必须通过 `scripts/compose.sh` 使用 Digest 锁定后的 `TEI_CPU_IMAGE`、`TEI_GPU_IMAGE`，不得直接使用 `*_IMAGE_SOURCE`。
3. `scripts/start_embedding.sh` 在启动前必须检查镜像引用包含 `@sha256:`；缺失时提示先执行锁定脚本并退出非零。
4. 锁定脚本默认只校验现有 Digest，不得静默更新。只有显式传入 `--update` 才允许重新解析来源标签并修改 Lock 文件。
5. 更新 Digest 必须作为独立提交，记录旧 Digest、新 Digest、预期 TEI 版本，并运行 CPU Contract Test；GPU 可用时还必须运行 GPU 与 CPU 一致性 Contract Test。
6. 如果来源标签移动到其他 Patch 版本，而 `TEI_EXPECTED_VERSION` 未修改，锁定脚本必须失败，禁止自动接受新版本。
7. 版本校验不得依赖某个未明确约定名称的 OCI Label。OCI Label 可以记录到诊断日志，但 CLI `--version` 才是镜像版本的规范校验方式。
8. Compose 解析完成后，Preflight 必须输出最终 CPU/GPU 镜像 Digest；容器启动后还必须通过 `docker inspect` 确认运行容器实际使用同一 Digest。
9. `/info` 端点如存在只能作为附加信息；若字段缺失，不得推断配置正确，必须继续使用 Compose Config、Container Inspect 和功能 Contract Test 验证。
10. 文档示例中的 `<cpu_image_digest>` 与 `<gpu_image_digest>` 只是格式占位，不得出现在真实 `versions.lock.env` 中。

### 3.11 Apache Kafka KRaft 部署

Kafka 使用 Apache Kafka 官方镜像，单节点 KRaft Combined Mode：

```
Broker + Controller
```

MVP 不部署 ZooKeeper。

Kafka 容器要求：

- 一个 Broker。
- 一个 Controller，与 Broker 位于同一进程。
- 持久化 Kafka Data Volume。
- 内部 Listener 供 Compose 服务访问。
- 可选宿主机 Listener 供本地调试工具访问。
- `context.archive.created` Topic 由 Migration 幂等创建。
- Topic 使用 `3` 个 Partition、`replication.factor=1`、`cleanup.policy=delete`、`compression.type=producer`、保留时间 `7` 天。
- Producer 使用 LZ4 压缩；Event Payload 最大值限制为 `1 MiB`，正常 Archive Event 应远小于该上限。

应用使用 `aiokafka`。Producer 和 Consumer 的序列化格式统一为 UTF-8 JSON。Kafka Event Schema 以前文 `1.2.4` 为准，详细客户端参数见第 `3.19` 节。

### 3.12 基础设施初始化

`init-infra` 通过版本化 Migration 负责幂等初始化：

```
MongoDB Collection / Index
Neo4j Constraint / Index
Elasticsearch Index / Mapping / Alias
Kafka Topic
Migration Version Record
```

统一调用方式：

```bash
./scripts/compose.sh --embedding=current run --rm init-infra
```

该容器执行 `python -m scripts.migrate`，不得维护另一套初始化实现。

初始化脚本规则：

1. Migration 按编号顺序执行并可重复运行。
2. 已执行的 Migration 通过 `infra_schema_migrations` 记录 `migration_id`、`checksum` 和 `applied_at`。
3. 同一 `migration_id` 的脚本 Checksum 发生变化时必须失败，禁止修改已执行 Migration。
4. 已存在且兼容时不报错；已存在但 Schema 或 Mapping 不兼容时必须失败，不得静默覆盖。
5. Elasticsearch Mapping 变化时创建新版本 Index，并通过 Alias 切换，不在原 Index 上直接修改向量维度。
6. Kafka Topic 已存在时校验关键配置。
7. 初始化失败时不得启动应用服务进入对外可用状态。

### 3.13 Docker Image 构建规范

应用镜像基础版本固定为：

```text
python:3.12.13-slim-bookworm
```

`versions.env` 中必须声明：

```dotenv
PYTHON_IMAGE=python:3.12.13-slim-bookworm
```

Dockerfile 通过 Build Arg 使用该值：

```dockerfile
ARG PYTHON_IMAGE=python:3.12.13-slim-bookworm
FROM ${PYTHON_IMAGE} AS builder
# 安装并构建依赖

FROM ${PYTHON_IMAGE} AS runtime
# 复制虚拟环境与应用代码
```

Builder 与 Runtime 必须继续使用同一个 `PYTHON_IMAGE`，禁止使用不同 Python Patch 版本。应用基础镜像与基础设施镜像 Tag 均统一从 `versions.env` 读取，当前固定值见第 `3.18` 节。

构建要求：

1. 使用多阶段 Docker Build。
2. 使用 `uv sync --locked` 安装依赖。
3. 将依赖安装层与源代码层分离，利用构建缓存。
4. `.venv`、测试缓存、Git 目录和本地模型文件必须加入 `.dockerignore`。
5. 最终运行阶段使用非 Root 用户。
6. 应用镜像不包含数据库、Kafka、Elasticsearch 或 Embedding 模型。
7. 同一镜像通过不同 `command` 运行三个应用容器。
8. 禁止使用 `python:3.12-slim-bookworm`、`python:3.12` 或 `latest` 等浮动应用基础镜像；当前必须使用 `python:3.12.13-slim-bookworm`，首次正式发布时可进一步固定镜像 Digest。
9. 代理地址不得通过 Dockerfile `ENV` 永久写入镜像。
10. Build Secret、API Key 和数据库密码不得进入镜像 Layer。

### 3.14 Docker Compose 持久化与端口

持久化 Volume 至少包括：

```
redis-data
mongodb-data
kafka-data
neo4j-data
neo4j-logs
elasticsearch-data
embedding-model-cache
```

开发环境可以将以下端口绑定至宿主机 `127.0.0.1`：

| 服务 | 默认端口 |
| --- | --- |
| Memory API | `8000` |
| Redis | `6379` |
| MongoDB | `27017` |
| Kafka | 由 Listener 配置确定 |
| Neo4j HTTP | `7474` |
| Neo4j Bolt | `7687` |
| Elasticsearch | `9200` |
| Embedding Service | `8080`，默认不对宿主机开放 |

MVP 默认只必须暴露 `memory-api:8000`。其他端口仅在开发调试 Profile 中绑定宿主机 `127.0.0.1`，常规运行应只通过 Compose 内部网络访问。Elasticsearch 开发与测试环境设置 `xpack.security.enabled=false` 时，`9200` 禁止绑定 `0.0.0.0`。

所有持久化服务必须配置 Health Check。应用服务使用 `depends_on.condition=service_healthy` 或启动时连接重试，但不得只依赖容器启动顺序判断服务可用。

### 3.15 宿主机代理端口 7890

MVP 假设 Linux 宿主机代理软件提供 `7890` HTTP 或 Mixed Proxy 端口。

代理分为三个独立层次。

#### 3.15.1 Docker Daemon 代理

Docker Daemon 拉取镜像时不能使用容器内部环境变量。Linux 宿主机需要单独配置：

```
HTTP Proxy:  http://127.0.0.1:7890
HTTPS Proxy: http://127.0.0.1:7890
```

配置完成后重启 Docker Daemon，再执行：

```bash
./scripts/compose.sh --embedding=none pull
```

若宿主机代理不是 HTTP/Mixed 端口，而是 SOCKS-only，不能直接使用上述 HTTP Proxy URL，必须改用代理软件提供的 HTTP/Mixed Port。

#### 3.15.2 Docker Build 代理

Build 阶段下载 Python 依赖时，通过 Build Args 或 Docker Client Proxy 配置传入：

```
HTTP_PROXY
HTTPS_PROXY
ALL_PROXY
NO_PROXY
```

禁止在 Dockerfile 中将代理地址写成永久 `ENV`。

#### 3.15.3 容器运行时代理

Linux 容器中的 `127.0.0.1` 指向容器自身，不能写成：

```
http://127.0.0.1:7890
```

Compose 中需要为访问外部 LLM 的应用容器配置：

```
extra_hosts:
  - "host.docker.internal:host-gateway"
```

运行时代理地址使用：

```
HTTP_PROXY=http://host.docker.internal:7890
HTTPS_PROXY=http://host.docker.internal:7890
```

建议 Compose 公共环境变量：

```
NO_PROXY=localhost,127.0.0.1,redis,mongodb,kafka,neo4j,elasticsearch,embedding-service,memory-api,memory-extraction-worker,memory-consolidation-worker
```

代理环境变量至少注入：

- `memory-api`：调用 DeepSeek 官方 API 执行 Compression。
- `memory-extraction-worker`：调用 DeepSeek 官方 API 执行 Structured Extraction。
- `embedding-service`：仅首次下载模型或检查远程模型仓库时需要。
- Docker Build：下载 Python 依赖时需要。

Redis、MongoDB、Kafka、Neo4j 和 Elasticsearch 的内部连接不得经过代理。

如果代理软件只监听宿主机 `127.0.0.1` 且不允许 Docker Bridge 访问，`host.docker.internal:7890` 仍可能连接失败。宿主机代理必须允许局域网或 Docker Bridge 连接，或者另外暴露一个仅 Docker 网桥可访问的监听地址。

### 3.16 健康检查与就绪规则

每个服务需要区分进程存活和依赖就绪。

`memory-api` Readiness 至少检查：

- Redis 可连接。
- MongoDB 可连接。
- Neo4j 可连接。
- Elasticsearch 版本和 Index Mapping 合法。
- Kafka Producer 已启动。

Embedding Service 不作为 `memory-api` 的阻塞型 Readiness 条件。Embedding 不可用时服务进入降级状态，Memory Retrieval 按前文规则跳过 Vector 通道并继续执行 BM25；健康接口应单独暴露该依赖异常。

DeepSeek 官方 API 不纳入启动阻塞型 Readiness，避免外部网络短暂故障导致应用无法启动；实际调用失败按照业务状态机和错误规则处理。

`memory-extraction-worker` 启动前至少检查：

- MongoDB。
- Kafka。
- Neo4j。
- Elasticsearch。
- Embedding Service。

`memory-consolidation-worker` 启动前至少检查 Neo4j。

Health Check 不得记录密码、连接字符串中的认证信息或 API Key。

### 3.17 MVP 部署与开发命令

MVP 标准初始化流程：

```bash
cp .env.example .env

# 尚未选择 Embedding 模式时，只处理基础镜像与应用构建
./scripts/compose.sh --embedding=none pull
./scripts/compose.sh --embedding=none build

./scripts/compose.sh --embedding=none \
  up -d redis mongodb kafka neo4j elasticsearch

# 生成 .runtime/embedding.env，并只启动 embedding-service
./scripts/start_embedding.sh auto

# 从此处开始统一使用已解析的 current 模式
./scripts/compose.sh --embedding=current run --rm init-infra

./scripts/compose.sh --embedding=current up -d \
  memory-api \
  memory-extraction-worker \
  memory-consolidation-worker
```

查看状态：

```bash
./scripts/compose.sh --embedding=current ps
```

查看日志：

```bash
./scripts/compose.sh --embedding=current logs -f memory-api
./scripts/compose.sh --embedding=current logs -f memory-extraction-worker
./scripts/compose.sh --embedding=current logs -f memory-consolidation-worker
./scripts/compose.sh --embedding=current logs -f embedding-service
```

停止但保留数据：

```bash
./scripts/compose.sh --embedding=current down
```

删除开发环境及持久化数据：

```bash
./scripts/compose.sh --embedding=current down -v
```

执行 `down -v` 会永久删除开发环境数据库和模型缓存，必须显式人工执行，脚本不得默认调用。

如果 Embedding 容器启动失败但 `.runtime/embedding.env` 已生成，`start_embedding.sh` 必须先清理失败容器并原子更新为实际回退模式；其他进程只能读取最终成功模式。任何文档或脚本中出现未通过 `scripts/compose.sh` 的 Compose 命令都视为工程规范检查失败。

### 3.18 基础设施版本与部署模式

MVP 固定以下镜像版本。Compose 禁止使用 `latest`，版本统一保存在 `versions.env`：

```dotenv
PYTHON_IMAGE=python:3.12.13-slim-bookworm
REDIS_IMAGE=redis:8.6.5
MONGODB_IMAGE=mongo:8.0.28
KAFKA_IMAGE=apache/kafka:4.3.1
NEO4J_IMAGE=neo4j:5.26.28-community
ELASTICSEARCH_IMAGE=docker.elastic.co/elasticsearch/elasticsearch:9.4.4
TEI_EXPECTED_VERSION=1.9.3
TEI_CPU_IMAGE_SOURCE=ghcr.io/huggingface/text-embeddings-inference:cpu-1.9
TEI_GPU_IMAGE_SOURCE=ghcr.io/huggingface/text-embeddings-inference:86-1.9

# 精确值由 scripts/lock_tei_images.sh 写入 versions.lock.env
TEI_CPU_IMAGE=ghcr.io/huggingface/text-embeddings-inference:cpu-1.9@sha256:<cpu_image_digest>
TEI_GPU_IMAGE=ghcr.io/huggingface/text-embeddings-inference:86-1.9@sha256:<gpu_image_digest>
```

| 组件 | 部署模式 | MVP 规则 |
| --- | --- | --- |
| Python 应用镜像 | 3.12.13 slim-bookworm | API、Extraction Worker 与 Consolidation Worker 使用同一镜像和同一 Python Patch 版本 |
| Redis | 单节点 | 使用 AOF；只承担 Working Memory、锁和弱统计，不作为长期事实源 |
| MongoDB | 单节点 Standalone | 不启用 Replica Set，不使用跨文档事务和 Change Stream |
| Kafka | 单节点 KRaft Combined Mode | `replication.factor=1`，仅用于开发、测试和 MVP 演示 |
| Neo4j | Community 5.26 LTS 单节点 | 只使用一个默认数据库；不依赖 Enterprise 集群能力 |
| Elasticsearch | 9.4.4 单节点 | `discovery.type=single-node`，Index 与 Mapping 按前文固定 |
| TEI CPU | 1.9.3，CPU x86_64，Digest 锁定 | 默认 Embedding Runtime，`float32` |
| TEI GPU | 1.9.3，Ampere 8.6，Digest 锁定 | RTX A5000 可用时启用，`float16`，容器内存上限 `8g` |

规则：

1. `versions.env` 必须提交 Git；其中不得包含密码或 API Key。
2. 升级镜像版本必须单独提交，运行 Migration、集成测试和 E2E 测试后才能合并。
3. Python 与基础设施使用固定 Patch Tag；TEI 因官方公开使用 `1.9` 发布线标签，必须额外通过 `versions.lock.env` 固定精确镜像 Digest，禁止仅依赖移动标签。
4. Elasticsearch `9.4.4` 与前文 Memory Retrieval Mapping 保持一致；禁止使用 `latest`，禁止未经 Migration、集成测试和 E2E 测试直接升级到其他 Minor 或 Major 版本。
5. MongoDB Standalone 已满足当前单文档原子更新和唯一索引需求；业务代码不得暗中依赖 Transaction 或 Change Stream。
6. Python Patch 版本升级必须同时修改 `PYTHON_IMAGE`、重新生成 `uv.lock`，并运行 Unit、Contract、Integration 与 E2E 测试；不得只更新 Docker Tag。
7. TEI 镜像升级必须显式修改 `TEI_EXPECTED_VERSION` 或执行 Digest `--update`，并同时验证 CPU/GPU Contract Test、固定模型 Revision、1024 维输出和 Elasticsearch 检索回归；禁止只升级其中一个 Override。

### 3.19 Kafka Topic 与客户端参数

Topic 固定配置：

```yaml
kafka:
  topic: context.archive.created
  partitions: 3
  replication_factor: 1
  retention_ms: 604800000
  cleanup_policy: delete
  compression_type: producer
  max_message_bytes: 1048576
```

Producer 固定配置：

```yaml
kafka_producer:
  acks: all
  enable_idempotence: true
  compression_type: lz4
  request_timeout_ms: 30000
  max_batch_size: 16384
  linger_ms: 10
```

Consumer 固定配置：

```yaml
kafka_consumer:
  enable_auto_commit: false
  auto_offset_reset: earliest
  session_timeout_ms: 30000
  heartbeat_interval_ms: 10000
  max_poll_interval_ms: 900000
  max_poll_records: 1
```

规则：

1. Kafka Message Key 固定使用 `user_id`，保证同一用户事件进入同一 Partition。
2. Extraction Worker 每次最多拉取一条 Event，完成前文任务状态持久化后再提交 Offset。
3. `max_poll_interval_ms` 必须覆盖单次 LLM 萃取、Neo4j 写入和 Elasticsearch 同步的最坏正常时长。
4. Producer Idempotence 只降低网络重试产生的重复事件；业务层仍必须依赖 `archive_id` 和 Extraction Task 唯一索引实现幂等。
5. 单节点 Kafka 不具备高可用能力，Broker Volume 丢失属于 MVP 可接受的开发环境风险。

### 3.20 MongoDB 与 Elasticsearch 本地运行规则

MongoDB 使用 Standalone：

```text
mongodb://mongodb:27017/memory_system
```

规则：

1. 每个需要原子性的状态变化必须落在同一 MongoDB Document 内。
2. 不允许 AI 为实现方便新增跨 Collection Transaction。
3. Context Archive、Extraction Task 和 Migration Collection 都必须创建前文规定的唯一索引。

Elasticsearch 开发与测试环境固定：

```yaml
elasticsearch:
  image: ${ELASTICSEARCH_IMAGE}
  environment:
    discovery.type: single-node
    xpack.security.enabled: "false"
  mem_limit: 2g
  ulimits:
    nofile:
      soft: 65535
      hard: 65535
  volumes:
    - elasticsearch-data:/usr/share/elasticsearch/data
```

MVP 默认不显式设置 `ES_JAVA_OPTS`，让 Elasticsearch 根据 `2g` 容器内存限制自动确定 JVM Heap。若后续需要显式 Heap，必须在性能测试后统一设置 `-Xms` 与 `-Xmx` 为相同值，并删除与自动 Heap 相冲突的配置。

Linux 宿主机在启动 Elasticsearch 前必须满足：

```bash
sudo sysctl -w vm.max_map_count=1048576
```

持久化配置写入：

```text
/etc/sysctl.d/99-elasticsearch.conf
```

文件内容：

```text
vm.max_map_count=1048576
```

应用后执行：

```bash
sudo sysctl --system
```

项目必须提供：

```text
scripts/preflight/check_linux_host.sh
```

Preflight 至少检查：

1. 操作系统为 Linux。
2. Docker Engine 可用。
3. `docker compose version` 可用且为 Compose v2。
4. `vm.max_map_count >= 1048576`，不满足时硬失败。
5. 当前用户具有访问 Docker Daemon 的权限。
6. 当代理配置启用时，宿主机 `7890` 端口可连接；未启用代理时跳过。
7. Elasticsearch 数据 Volume 所在文件系统可用空间低于 `20 GiB` 时输出 Warning，但不阻止开发环境启动。
8. 内存检查使用 Linux `/proc/meminfo` 的 `MemAvailable`，不得只检查物理总内存。不同有效模式采用不同门槛：

```yaml
preflight:
  cpu_mode:
    # D = TEI CPU mem_limit GiB（当前 formal contract D=12）
    # CPU_MIN = 12 + (D - 8); CPU_REC = 16 + (D - 8)
    minimum_available_memory_gib: 16
    recommended_available_memory_gib: 20

  gpu_mode:
    minimum_available_memory_gib: 8
    recommended_available_memory_gib: 12
```

9. 低于当前模式的 `minimum_available_memory_gib` 时硬失败；达到 Minimum 但低于 Recommended 时输出 Warning；达到 Recommended 时通过。该门槛覆盖 TEI、Elasticsearch、MongoDB、Kafka、Neo4j、Redis 和应用容器的开发环境共同开销。
10. `cpu` 模式不要求 NVIDIA 环境，并使用 CPU 内存门槛。`gpu` 模式必须检查 NVIDIA Driver、Container Toolkit、RTX A5000 可见性和空闲显存，并使用 GPU 内存门槛。
11. `auto` 模式必须先评估 GPU 可用性：GPU 条件满足且宿主机满足 GPU Minimum 时选择 GPU；否则再检查 CPU 门槛并选择 CPU。GPU 与 CPU 门槛都不满足时硬失败，不得启动部分基础设施。
12. Preflight 必须确认 Docker 能为 Elasticsearch 提供 `2g` Memory Limit、为所选 TEI CPU 模式提供 `12g` Memory Limit（GPU TEI 仍为 `8g`，见 §3.10.4）；无法满足时硬失败。Check 13a 使用 `required_host_mem_gib = 2 + TEI_LIMIT_GIB`（当前 CPU = 14）；Check 13b 在正式 CPU `mem_limit` 下做真实 warm-up 探针。
13. Preflight 必须校验 `versions.lock.env` 存在、TEI 镜像包含 `@sha256:`、最终有效运行模式和客户端 Token 预算一致。
14. 所有检查必须输出机器可读的退出码：硬失败返回非零；仅存在 Warning 时返回 `0`。

MVP 标准启动顺序：

```bash
bash scripts/preflight/check_linux_host.sh
./scripts/compose.sh --embedding=current config
./scripts/compose.sh --embedding=current up -d
```

规则：

1. Elasticsearch 仅监听 Compose 内部网络；开发调试时最多绑定 `127.0.0.1:9200`。
2. 设置 `xpack.security.enabled=false` 时禁止绑定公网地址或部署到不受信任网络。
3. 生产环境的 TLS、用户认证与安全配置属于首次发布前 P2 工作，不得复用开发环境的无认证配置。
4. 应用启动必须校验服务版本严格等于 `9.4.4`。
5. MVP 只使用免费 Basic 能力，包括 BM25、`dense_vector`、kNN、Bulk、MGET 和 Alias；RRF 继续由 Python 应用层实现，不依赖 Elasticsearch 原生付费功能。
6. 团队使用官方 Elasticsearch Distribution，必须接受并遵守对应发行版许可证；不得将其误标为 Apache 2.0 组件。
7. Compose 中 `nofile` 软硬限制固定为 `65535`；不得依赖宿主机默认值。
8. `vm.max_map_count` 属于 Linux 宿主机内核参数，不能只在容器环境变量中声明。
9. `mem_limit: 2g` 是开发、测试与 MVP 演示的默认值；若真实数据规模或并发测试证明不足，必须通过配置变更和回归测试调整，不得由 AI 随意增减。

### 3.21 Memory API 鉴权与接口暴露

MVP 将 Memory System 部署为上游 Agent 调用的内部服务，使用静态 API Key，不实现用户登录、JWT 签发或 OAuth。

请求头：

```http
X-API-Key: <secret>
```

环境变量：

```dotenv
MEMORY_API_KEY=...
MEMORY_ADMIN_API_KEY=...
```

接口分级：

| 接口类别 | 鉴权规则 |
| --- | --- |
| Session、Message、Working Context、Session Close、Memory Retrieval | 接受普通 Key 或 Admin Key |
| Extraction Task 查询与人工重试 | 只接受 Admin Key，并要求路径中的 `user_id` 与资源归属一致 |
| Archive Event 人工补发、Migration 执行 | 不暴露 HTTP Endpoint；仅通过受信任运行环境中的 CLI 脚本执行 |
| Health Liveness | 不要求 Key，但只返回进程状态 |
| Health Readiness | 不要求 Key，只返回依赖名称与 `ready/not_ready`，不得返回连接地址和异常堆栈 |
| Metrics | 必须使用 Admin Key，并仅允许内部网络访问 |

规则：

1. Key 比较必须使用 Constant-time Compare。
2. 缺失或错误 Key 返回 HTTP `401` 和 `invalid_api_key`，不得区分“缺失”和“错误”以泄露信息。
3. API Key 不写入日志、Trace、错误详情或响应。
4. 静态 Key 只验证受信任的 Agent 服务，不携带最终用户身份；`user_id` 由上游 Agent 负责传入。
5. Memory API 不得直接暴露给浏览器或终端用户；需要终端用户鉴权时由后续 API Gateway 或 JWT 方案承担。
6. 所有面向业务资源的 HTTP 数据访问仍必须强制以 Request 或 Path 中的 `user_id` 过滤，禁止由于调用方受信任而省略用户隔离条件。
7. Admin Key 只用于本节列出的 HTTP 管理接口，不用于 CLI 身份认证。
8. `scripts/republish_archive_event.py` 和 `python -m scripts.migrate` 只能在受信任的内部运行环境执行，通过环境变量获取基础设施凭证，不得被包装成未在本文定义的 HTTP Endpoint。

### 3.22 Consolidation Scheduler

Scheduler 固定使用：

```text
APScheduler 3.11.3
AsyncIOScheduler
CronTrigger
```

调度参数的唯一来源是第 `2.3.12` 节的 `memory_consolidation` 配置。应用必须直接使用以下字段创建 Job，不得在 `scheduler` 命名空间或代码常量中重复定义执行时间：

```python
CronTrigger.from_crontab(
    settings.memory_consolidation.schedule_cron,
    timezone=settings.memory_consolidation.timezone,
)
```

Job 的 `max_instances`、`coalesce` 和 `misfire_grace_time` 分别读取 `scheduler_max_instances`、`scheduler_coalesce` 和 `scheduler_misfire_grace_time_seconds`。当前默认计划为每天 `03:00 UTC`，修改计划时只允许修改第 `2.3.12` 节对应配置及其环境覆盖值。

规则：

1. Scheduler 只运行于 `memory-consolidation-worker`。
2. MVP 只启动一个 Consolidation Worker 容器，并继续使用前文定义的本地单实例锁。
3. 不配置持久化 Job Store；Scheduler 重启后重新注册固定 Job。
4. 漏执行一次不会丢失业务数据，下一次扫描仍会根据 `last_consolidated_time` 处理未巩固 Memory。
5. Scheduler Job 内不得创建第二层无限循环；每次触发只执行一次有界扫描。

### 3.23 统一 API 响应与 Request ID

成功响应继续使用各业务接口已定义的 Response Schema。前文各业务章节出现的所有 HTTP 错误码和错误示例均必须转换为本节结构；不得返回 `{error_code, message}` 等第二套错误 Body。所有错误统一返回：

```json
{
  "success": false,
  "error": {
    "code": "working_memory_full",
    "message": "Working Memory has reached the configured capacity limit",
    "details": {}
  },
  "request_id": "1f47e791-62b6-4b93-b31f-6c5811d78e13"
}
```

Request ID 规则：

1. 客户端可通过 `X-Request-ID` 传入合法值；缺省时由 API 生成 UUID4。
2. Response Header 和错误 Body 都返回同一个 Request ID。
3. Worker 从 Kafka Event 生成新的 `task_run_id`，并同时记录 `archive_id` 和 `task_id`；不复用历史 HTTP Request ID 作为任务唯一标识。

基础 HTTP 映射：

| HTTP Status | 使用场景 |
| --- | --- |
| `400` | 业务参数格式正确但语义非法 |
| `401` | API Key 缺失或无效 |
| `404` | Session、Task 或 Archive 不存在 |
| `409` | Session Closing、版本冲突或幂等资源冲突 |
| `422` | Pydantic Request Schema 校验失败 |
| `429` | 明确的调用频率或并发限制 |
| `503` | Working Memory 背压、基础设施不可用或外部依赖暂时失败 |

Pydantic Validation Error 必须转换为统一错误结构，错误码固定为 `validation_error`，不得直接返回 FastAPI 默认错误格式。`session_closing` 必须映射为 HTTP `409`，不得作为写消息接口的成功 `status` 返回。写消息已经成功后发生的 Compression `version_conflict` 仍返回 HTTP `200`，并通过 `compression_status=version_conflict` 表达；只有独立资源更新请求的版本冲突才使用 HTTP `409`。

### 3.24 连接池、超时与重试

MVP 固定工程默认值：

```yaml
http_client:
  connect_timeout_seconds: 5
  read_timeout_seconds: 120
  write_timeout_seconds: 30
  pool_timeout_seconds: 5
  max_connections: 100
  max_keepalive_connections: 20

embedding_http_client:
  connect_timeout_seconds: 5
  read_timeout_seconds: 30

redis:
  socket_connect_timeout_seconds: 3
  socket_timeout_seconds: 5
  max_connections: 50

mongodb:
  server_selection_timeout_ms: 5000
  connect_timeout_ms: 5000
  max_pool_size: 50

neo4j:
  connection_timeout_seconds: 5
  connection_acquisition_timeout_seconds: 10
  max_connection_pool_size: 50

elasticsearch:
  request_timeout_seconds: 10
  max_retries: 2
  retry_on_timeout: true
```

重试规则：

1. 禁止使用一个通用 Retry Decorator 重试所有数据库和外部调用。
2. Elasticsearch Search、MGET 和使用确定性 Document ID 的 Index 写入可以进行最多 `2` 次短重试。
3. Redis Lua Script、MongoDB 状态迁移和 Neo4j Transaction 只有在操作本身满足前文幂等条件时才能重试。
4. 外部 LLM 在发生 Read Timeout 后不得在同一次业务调用中自动重试，避免重复计费和不确定结果；按照前文 Compression 或 Extraction 失败流程处理。
5. Embedding 请求可以在连接失败时短重试 `1` 次；Schema、维度或输入错误不得重试。
6. Kafka 客户端传输重试与业务 Task 重试分离；禁止因 Kafka 内部重试而跳过 Extraction Task 幂等检查。

### 3.25 优雅关闭

所有 Entrypoint 必须监听 `SIGTERM` 和 `SIGINT`。

`memory-api`：

```text
停止接收新请求
    → 等待正在处理的请求进入完成或可恢复状态
    → Flush / Close Kafka Producer
    → 关闭 HTTP、Redis、MongoDB、Neo4j、Elasticsearch Client
    → 退出
```

`memory-extraction-worker`：

```text
停止拉取新 Kafka Event
    → 等待当前 Archive 完成或持久化 failed 状态
    → 按前文规则决定是否提交 Offset
    → 关闭 Consumer、Producer 和数据库 Client
    → 退出
```

`memory-consolidation-worker`：

```text
停止 Scheduler 接收新 Job
    → 等待当前批次结束或完成当前 Memory 的原子更新
    → 释放本地锁和 Neo4j Driver
    → 退出
```

Docker Compose 分别设置：

```yaml
memory-api:
  stop_grace_period: 480s

memory-extraction-worker:
  stop_grace_period: 300s

memory-consolidation-worker:
  stop_grace_period: 300s
```

应用内部关闭 Deadline 固定为：

```yaml
shutdown:
  memory_api_timeout_seconds: 450
  extraction_worker_timeout_seconds: 270
  consolidation_worker_timeout_seconds: 270
```

`memory-api` 启动 Uvicorn 时必须设置等价的 Graceful Shutdown Timeout：

```text
--timeout-graceful-shutdown 450
```

应用内部 Deadline 必须小于对应 Compose `stop_grace_period`，为 Client Close、日志 Flush 和进程退出预留至少 `30s`。

规则：

1. `memory-api.stop_grace_period` 必须大于 `compression_lock_ttl_seconds`。当前压缩锁 TTL 为 `420s`，因此固定为 `480s`。
2. `memory-api` 收到 Shutdown Event 后不得开始新的压缩轮次；已经进入 LLM 调用或 Redis Finalize 的当前轮允许完成，随后结束本次压缩请求。这样可避免关停阶段继续启动最多三轮压缩。
3. Extraction Worker 的 `300s` 应覆盖单个 Archive 在正常情况下完成当前 LLM 调用后的任务状态持久化、Neo4j 事务和 Elasticsearch 同步收尾；收到 Shutdown Event 后不得 Poll 新 Event。
4. Consolidation Worker 的 `300s` 用于完成当前批次或当前 Memory 原子更新；收到 Shutdown Event 后 Scheduler 不得启动新 Job。
5. 超出 Grace Period 被强制终止时，系统必须依赖前文幂等和状态恢复规则重新处理。
6. 不得在 Signal Handler 中直接执行复杂异步数据库逻辑；Handler 只设置 Shutdown Event，由主协程完成清理。
7. 修改 Compression LLM Timeout、最大压缩轮数或锁 TTL 时，必须重新校验 `memory-api.stop_grace_period` 与 `memory_api_timeout_seconds`，禁止出现应用内部 Deadline 小于锁 TTL，或 Compose Grace Period 小于应用内部 Deadline 的配置。
8. Worker 达到内部关闭 Deadline 但当前任务尚未结束时，应取消当前协程并依赖前文任务状态、确定性 ID 和幂等规则恢复；不得继续无限等待。

### 3.26 Schema Migration

MVP 不使用 Alembic，因为主要存储不是关系数据库。使用项目自带的版本化 Migration Runner：

```text
python -m scripts.migrate
```

Migration Record 保存在 MongoDB：

```json
{
  "migration_id": "003_elasticsearch_memory_v1",
  "checksum": "sha256:...",
  "applied_at": 1720000000,
  "app_version": "0.1.0"
}
```

规则：

1. Migration 文件只允许新增，不允许修改已执行文件。
2. Migration 必须幂等，并在执行前校验依赖服务版本。
3. Elasticsearch 使用版本化 Index，例如 `memory_retrieval_v1`，稳定 Alias 为 `memory_retrieval_current`。
4. Mapping 不兼容升级时创建新 Index、执行数据迁移和 Alias 原子切换。
5. 应用 Readiness 校验必须确认全部必需 Migration 已应用。
6. `init-infra` 实际执行同一个 Migration Runner，不维护第二套初始化逻辑。

### 3.27 日志、指标与敏感信息保护

日志固定使用：

```text
Python standard logging
+ structlog
+ JSON Renderer
```

每条结构化日志至少包含：

```text
timestamp（UTC）
level
service_name
environment
request_id 或 task_run_id
user_id（允许）
session_id（存在时）
archive_id（存在时）
task_id（存在时）
error_code（错误时）
duration_ms（完成时）
```

禁止记录：

- 完整用户消息、完整 `compressed_context` 或完整 Memory Content。
- 完整 LLM Prompt、完整 LLM Response。
- API Key、Authorization Header、数据库密码和连接串凭证。
- 原始 Token、私钥、验证码和其他认证信息。

指标使用 `prometheus-client`，由内部 `/internal/metrics` 暴露。MVP 至少提供：

```text
http_requests_total
http_request_duration_seconds
compression_total{status}
extraction_tasks_total{status}
extraction_task_duration_seconds
retrieval_requests_total{mode,status}
retrieval_duration_seconds
kafka_consumer_lag（可获取时）
consolidation_runs_total{status}
```

OpenTelemetry Trace 在 MVP 中后置，不作为首轮开发依赖。

### 3.28 测试策略

测试分四层：

| 层级 | 运行方式 | 覆盖范围 |
| --- | --- | --- |
| Unit | 不启动 Docker | Token 估算、选择算法、Fingerprint、Reconciliation、RRF、ACT-R 和巩固公式 |
| Contract | Fake Server / 固定 Fixture | LLM Structured Output、Embedding Contract、Kafka Event Schema |
| Integration | `compose.test.yaml` 启动真实基础设施 | Redis Lua、Mongo Index、Kafka Offset、Neo4j Transaction、Elasticsearch Mapping |
| E2E | 完整测试 Compose | Session → Archive → Extraction → Retrieval → Consolidation |

规则：

1. 测试环境使用独立数据库名、Index、Topic 和 Docker Volume。
2. Integration 和 E2E 测试结束后自动删除测试 Volume，不得删除开发 Volume。
3. DeepSeek Adapter 的 Contract Test 默认使用 Fake LLM Server，固定返回合法 JSON、空 content、非法 JSON、Schema 非法和 HTTP 错误 Fixture；CI 不调用真实计费 API。
4. Embedding Contract 测试可使用 Fake Service；至少一组可选本地测试使用真实 `BAAI/bge-m3` 验证向量维度、Pooling、截断和归一化约定。
5. 必须覆盖失败注入：Archive 已写入但 Kafka 发布失败、LLM 超时、Elasticsearch Bulk 部分失败、Worker 在 Neo4j Commit 后退出、Session Close 部分归档成功。
6. 合并代码前至少运行 Unit、Contract 和 Integration；发布前运行完整 E2E。
7. CI 对 `src/memory_system/domain` 和 `src/memory_system/application` 统计行覆盖率，最低阈值固定为 `80%`；其他目录输出覆盖率报告但不单独设置阻塞阈值。

### 3.29 P0 技术选型完成状态

LLM 和 Embedding 的 P0 技术选型均已完成：

- LLM：DeepSeek 官方 API，Compression 与 Extraction 均使用 `deepseek-v4-flash`。
- Embedding Engine：TEI `1.9.3`，CPU/GPU 镜像使用 Digest 锁定。
- Embedding Model：`BAAI/bge-m3`，Revision `57aacf8560157b7c1d4f771ce1a199877aeeec74`。
- 默认运行模式：CPU `float32`。
- 可选加速模式：RTX A5000 + Ampere 8.6 TEI GPU 镜像 + `float16`。
- 启动方式：Compose Override，支持 `cpu`、`gpu`、`auto`。
- 单条输入上限：`1024` Token；客户端按 CPU `4096` / GPU `16384` 总 Token 预算稳定分批。
- 运行时热切换：不实现。

AI Coding Agent 不得替换 LLM Provider、LLM Model、Embedding Engine、Embedding Model、模型 Revision、向量维度、Pooling、Normalize 或启动模式语义。资源参数可以基于本机压力测试在配置允许范围内调整，但必须保持 Contract Test 通过。

### 3.30 P1 与 P2 后续工程项

P1，主流程完成前完成：

- AI 实现 Pydantic Settings Model 时必须同步生成完整 `.env.example`；至少包含 `APP_ENV`、全部基础设施连接字段以及 `LLM__BASE_URL`、`LLM__API_KEY`、`LLM__COMPRESSION__MODEL` 和 `LLM__EXTRACTION__MODEL`。项目提供 `scripts/check_env_example.py`，CI 校验所有必需环境变量均出现在 `.env.example`，且示例文件不包含真实 Secret。
- 基于本机压力测试微调应用容器、CPU Embedding 和 GPU Embedding 的资源限制；不得改变第 `3.10` 节的默认值，除非保留基准结果和配置变更记录。
- 离线模型缓存打包、备份和恢复流程。
- GitHub Actions 或其他 CI 平台，并强制执行第 `3.28` 节定义的测试门禁和 `80%` 核心代码覆盖率阈值。

P2，首次对外发布前确定：

- 镜像仓库和镜像签名。
- 生产 Secrets Manager。
- TLS、Elasticsearch 与数据库认证。
- 数据备份、恢复演练和保留周期。
- 生产 API Gateway、JWT 或租户级授权。
- 多节点高可用和灾难恢复。

### 3.31 当前技术选型的 MVP 边界

本阶段已经确定并必须实现：

- Linux + Docker Engine + Docker Compose v2。
- Python 3.12.13、FastAPI、Pydantic v2、Pydantic Settings、PyYAML 和 `uv`。
- 单仓库、单应用镜像、三个应用容器入口。
- 基于 `asyncio` 的全异步应用层。
- Compression 作为 `memory-api` 进程内 Application Service，不暴露独立 HTTP Endpoint。
- 基于 `openai.AsyncOpenAI` 的 DeepSeek `LLMClient` 实现，Compression 与 Extraction 均使用 `deepseek-v4-flash` 非思考 JSON Output。
- TEI `1.9.3` + Digest 锁定镜像 + 固定 Revision `BAAI/bge-m3` 的本地 Dense Embedding Service；默认 CPU、可选 RTX A5000 GPU，并支持 `cpu/gpu/auto` Compose Override。
- TEI `AUTO_TRUNCATE=false`，应用层 1024 Token 硬限制，以及 CPU/GPU 按总 Token 预算进行的确定性子批次拆分。
- 统一 `scripts/compose.sh` 入口、环境文件加载顺序和 CPU/GPU Override 选择；禁止裸 `docker compose` 命令。
- `search_text` 核心文本事务前长度校验、Alias 按 Token Budget 稳定追加，以及超长 Retrieval Query 的 BM25-only 降级。
- TEI CLI `--version`、Digest、Compose Config、Container Inspect 和功能 Contract Test 组成的运行版本与配置校验。
- 全部核心 Python 运行时、质量和测试依赖的 Minor 兼容范围，以及 `uv.lock` 精确锁定。
- 固定版本的 Python 应用基础镜像，以及 Redis、MongoDB、Kafka、Neo4j 和 Elasticsearch 镜像。
- Apache Kafka 单节点 KRaft 与固定 Topic 参数。
- MongoDB Standalone 和 Elasticsearch 单节点开发安全规则。
- Elasticsearch Linux Preflight、`vm.max_map_count`、`nofile` 与 `2g` 开发资源限制，以及 CPU/GPU Embedding 模式分别对应的宿主机内存门槛。
- 静态 API Key 与 Admin API Key。
- APScheduler `AsyncIOScheduler`，并以 `memory_consolidation.schedule_cron` 作为唯一调度时间源。
- 统一错误响应、Request ID、连接池、超时和有限重试。
- 按进程设置的优雅关闭宽限期、版本化 Migration、JSON Log、Prometheus Metrics。
- Unit、Contract、Integration 和 E2E 四层测试。
- Docker Daemon、Build 和 Runtime 三层代理配置。
- 宿主机 `7890` 代理访问规则和 `NO_PROXY`。

本阶段暂不实现：

- Kubernetes、Helm 和云原生 Operator。
- 多节点 Kafka、MongoDB、Neo4j 或 Elasticsearch 高可用集群。
- 多仓库和每服务独立发布版本。
- 服务网格、完整 API Gateway 和复杂流量治理。
- 自动水平扩缩容。
- 分布式配置中心和生产 Secret Manager。
- 多 LLM Provider 自动路由与 `deepseek-v4-pro` 自动升级策略。
- 多 Embedding Model 路由。
- GPU 集群调度。
- OpenTelemetry 全链路追踪。
- 蓝绿发布和跨区域容灾。

### 3.32 MVP 开发完成验收标准

MVP 只有同时满足以下条件，才可判定为“开发完成”，不能仅以主流程能够启动作为完成标准：

1. 在空白环境中，按照第 `3.17` 节标准命令可以完成镜像准备、基础设施启动、Embedding 模式解析、Migration 和三个应用容器启动。
2. `python -m scripts.migrate` 首次执行成功，重复执行保持幂等；已执行 Migration 的 Checksum 被修改时必须失败。
3. Unit、Contract、Integration 全部通过，核心 `domain` 与 `application` 行覆盖率不低于 `80%`。
4. 完整 E2E 跑通 `Session → Message → Archive → Compression → Extraction → Elasticsearch Sync → Retrieval → Consolidation → Session Close`。
5. 重复 `message_id`、重复 Kafka Event、Worker 重启和 Extraction 重试不得产生重复 Message、Archive、Memory、Evidence 或 Elasticsearch Document。
6. 必须通过第 `3.28` 节定义的失败注入；任何失败场景均不得丢失已经成功写入的原始消息，且必须能够按本文定义的人工恢复路径继续处理。
7. CPU Embedding 模式是必测和发布阻塞项；GPU 模式在具备 RTX A5000 环境时执行 Contract 与 E2E 回归，但没有 GPU 不阻塞 CPU MVP 验收。
8. 所有 HTTP 错误均使用第 `3.23` 节统一结构；所有业务资源查询均执行 `user_id` 隔离；日志和指标中不得出现本文禁止记录的敏感内容。
9. `.env.example`、`versions.env`、`versions.lock.env`、基础 YAML、Compose 文件、Migration、运维脚本和 README 启动命令必须与实际代码一致，不得保留影响主流程的 TODO、占位实现或未决技术选型。
