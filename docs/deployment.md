# 部署指南

本文档说明如何在本地或测试环境通过 Docker Compose 部署 Memory System 全栈。日常运维与 CI 细节见 [operations.md](operations.md)。

## 前置条件

- Linux 宿主机（推荐；Preflight 脚本针对 Linux）
- Docker Engine + Compose 插件
- [uv](https://github.com/astral-sh/uv)（本地开发与 quality gate）
- 可复制 `.env.example` → `.env` 并配置 LLM / API Key

**禁止**在脚本、CI 或文档示例中直接调用裸 `docker compose`；一律经 `./scripts/compose.sh`。

## Runtime

- Python **3.12.13**（见 `.python-version`）
- 依赖管理：**uv** + 已提交的 `uv.lock`
- 基础设施镜像标签：`versions.env` + TEI digest（`versions.lock.env`）

## 标准启动（§3.17）

```bash
# 1. Preflight（Linux 宿主机）
bash scripts/preflight/check_linux_host.sh --mode=auto

# 2. 锁定 TEI 镜像（首次或 tag 变更后）
./scripts/lock_tei_images.sh --update

# 3. 准备环境
cp .env.example .env

# 4. Pull / build（无 embedding override）
./scripts/compose.sh --embedding=none pull
./scripts/compose.sh --embedding=none build

# 5. 启动基础设施
./scripts/compose.sh --embedding=none \
  up -d redis mongodb kafka neo4j elasticsearch

# 6. 启动 Embedding（写入 .runtime/embedding.env）
./scripts/start_embedding.sh auto

# 7. 基础设施迁移（Migration Runner）
./scripts/compose.sh --embedding=current run --rm init-infra
# 等价本地入口：python -m scripts.migrate

# 8. 启动应用容器
./scripts/compose.sh --embedding=current up -d \
  memory-api memory-extraction-worker memory-consolidation-worker
```

### 常用命令

```bash
./scripts/compose.sh --embedding=current ps
./scripts/compose.sh --embedding=current logs -f memory-api
./scripts/compose.sh --embedding=current down          # 保留 volumes
./scripts/compose.sh --embedding=current down -v      # 销毁数据（显式）
./scripts/compose.sh --stack=test --embedding=cpu config
```

### Embedding 模式

| 脚本 / 标志 | 行为 |
| --- | --- |
| `start_embedding.sh cpu` | CPU TEI，token budget 4096 |
| `start_embedding.sh gpu` | GPU TEI（RTX A5000），budget 16384；无自动回退 |
| `start_embedding.sh auto` | GPU 优先，失败回退 CPU |
| `compose.sh --embedding=none` | 不注入 TEI override |
| `compose.sh --embedding=current` | 读取 `.runtime/embedding.env` |

## 本地开发（不跑全栈 Compose）

```bash
uv sync --locked
cp .env.example .env
```

基础设施需已运行且迁移已执行（`./scripts/compose.sh --stack=test run --rm init-infra`），`/health/ready` 返回 `200` 后再启动 API。

最小环境变量示例见 `tests/unit/test_settings_validation.py` 中的 `VALID_ENV`，或：

```bash
export APP_ENV=test
export REDIS__URI=redis://127.0.0.1:6379/0
export MONGODB__URI=mongodb://127.0.0.1:27017/memory_system
export KAFKA__BOOTSTRAP_SERVERS=127.0.0.1:9092
export NEO4J__URI=neo4j://127.0.0.1:7687
export ELASTICSEARCH__URL=http://127.0.0.1:9200
export LLM__BASE_URL=https://api.deepseek.com
export LLM__API_KEY=sk-example-replace-me
export LLM__COMPRESSION__MODEL=deepseek-v4-flash
export LLM__EXTRACTION__MODEL=deepseek-v4-flash
export EMBEDDING__MODEL_ID=BAAI/bge-m3
export EMBEDDING__BASE_URL=http://127.0.0.1:8080
export MEMORY_API_KEY=dev-memory-api-key-change-me
export MEMORY_ADMIN_API_KEY=dev-memory-admin-key-change-me
export PROXY__HTTP_URL=
export EMBEDDING_EFFECTIVE_RUNTIME_MODE=cpu
export EMBEDDING_CLIENT_TOTAL_TOKEN_BUDGET=4096

uv run python -m memory_system.entrypoints.api
```

单独启动 Worker：

```bash
uv run python -m memory_system.entrypoints.extraction_worker
uv run python -m memory_system.entrypoints.consolidation_worker
```

## Entrypoints（规格 §3.2）

| 进程 | 命令 |
| --- | --- |
| memory-api | `python -m memory_system.entrypoints.api` |
| memory-extraction-worker | `python -m memory_system.entrypoints.extraction_worker` |
| memory-consolidation-worker | `python -m memory_system.entrypoints.consolidation_worker` |

Extraction Worker 连接 MongoDB、Neo4j、Elasticsearch、Kafka，运行 production extraction pipeline。Consolidation Worker 含 APScheduler、batch/read/write service、进程内 mutex 与 graceful shutdown。

## 回滚（DEV-003 Task Plan §13）

1. `./scripts/compose.sh --embedding=current down`（不加 `-v`）
2. 删除 `.runtime/embedding.env`；重新 preflight + `start_embedding.sh`
3. 若 digest 更新有误，从 Git 恢复 `versions.lock.env`
4. `rm -rf .runtime/`
