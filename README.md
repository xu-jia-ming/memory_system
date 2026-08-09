# Memory System MVP

Python monorepo for the Memory System MVP (API + extraction worker + consolidation worker).

## Status

**Phase 0 infrastructure** delivers Docker Compose topology, TEI Embedding deployment, Linux host Preflight, and the versioned Migration Runner.

- **Available**: `scripts/compose.sh` (唯一 Compose 入口), `scripts/start_embedding.sh`, `scripts/lock_tei_images.sh`, `scripts/preflight/check_linux_host.sh`, `versions.env` / `versions.lock.env`, multi-stage `Dockerfile`, full §3.3 Compose stack.
- **Migration Runner (DEV-004)**: `python -m scripts.migrate`（亦为 `init-infra` 唯一入口）幂等初始化 Mongo / Neo4j / Elasticsearch Mapping+Alias / Kafka Topic；记录写入 `infra_schema_migrations`。
- **Configuration**: `.env.example` + `configs/` (DEV-002).
- **memory-api shell (DEV-005)**: FastAPI app with auth, health, metrics, structlog JSON logging.
- **Not yet available**: TEI Embedding Client (DEV-006).

**禁止**在脚本、CI 或文档示例中直接调用裸 `docker compose`；一律经 `./scripts/compose.sh`。

## Runtime

- Python **3.12.13** (see `.python-version`)
- Dependency management: **uv** with committed `uv.lock`
- Infrastructure image tags: `versions.env` + TEI digests in `versions.lock.env`

## Entrypoints (spec §3.2)

| Process | Command |
| --- | --- |
| memory-api | `python -m memory_system.entrypoints.api` |
| memory-extraction-worker | `python -m memory_system.entrypoints.extraction_worker` |
| memory-consolidation-worker | `python -m memory_system.entrypoints.consolidation_worker` |

Until DEV-006 wires the TEI Embedding Client, extraction and consolidation workers are safe to import but exit non-zero when executed. `memory-api` starts via Uvicorn when configuration is valid.

## Local setup

```bash
uv sync --locked
cp .env.example .env   # edit secrets as needed
```

### Run memory-api locally (test env)

Use the same required environment variables as unit tests (see `tests/unit/test_settings_validation.py` `VALID_ENV`). Example:

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

Infrastructure must be running and migrations applied (`./scripts/compose.sh --stack=test run --rm init-infra`) before `/health/ready` returns `200`. **Do not** start the API with bare `docker compose`; use `./scripts/compose.sh` per §3.17.

Quality gates:

```bash
uv run pytest tests/unit tests/contract tests/integration
uv run ruff check .
uv run mypy src tests scripts
```

## Standard startup (§3.17)

All Compose operations go through `./scripts/compose.sh`.

```bash
# 1. Preflight (Linux host)
bash scripts/preflight/check_linux_host.sh --mode=auto

# 2. Lock TEI images (first time or after tag change)
./scripts/lock_tei_images.sh --update

# 3. Prepare environment
cp .env.example .env

# 4. Pull/build without embedding override
./scripts/compose.sh --embedding=none pull
./scripts/compose.sh --embedding=none build

# 5. Start infrastructure
./scripts/compose.sh --embedding=none \
  up -d redis mongodb kafka neo4j elasticsearch

# 6. Start embedding only (writes .runtime/embedding.env)
./scripts/start_embedding.sh auto

# 7. Initialize infrastructure (Migration Runner)
./scripts/compose.sh --embedding=current run --rm init-infra
# Equivalent local entrypoint (same implementation): python -m scripts.migrate

# 8. Start application containers
./scripts/compose.sh --embedding=current up -d \
  memory-api memory-extraction-worker memory-consolidation-worker
```

### Useful commands

```bash
./scripts/compose.sh --embedding=current ps
./scripts/compose.sh --embedding=current logs -f memory-api
./scripts/compose.sh --embedding=current down          # keep volumes
./scripts/compose.sh --embedding=current down -v      # destroy data (explicit)
./scripts/compose.sh --stack=test --embedding=cpu config  # test stack
```

### Embedding modes

| Script / flag | Behavior |
| --- | --- |
| `start_embedding.sh cpu` | CPU TEI, budget 4096 |
| `start_embedding.sh gpu` | GPU TEI (RTX A5000), budget 16384; no auto-fallback |
| `start_embedding.sh auto` | GPU-first; falls back to CPU |
| `compose.sh --embedding=none` | No TEI override |
| `compose.sh --embedding=current` | Read `.runtime/embedding.env` |

### TEI CPU memory contract (OI-011)

Formal CPU TEI `mem_limit` is **12g** (model-runtime-profile-specific fixed contract for `BAAI/bge-m3` float32 ONNX CPU). Overrides below 12g are `NON_SPEC_COMPLIANT`.

Preflight **Check 8** CPU MemAvailable: min **16** GiB / rec **20** GiB (`12/16 + (D-8)`, D=12). **Check 13a** verifies host `MemTotal >= 14` (ES 2g + TEI 12g). **Check 13b** runs a real TEI CPU runtime probe under formal `mem_limit: 12g` (up to ~300s) for `cpu` / `auto→cpu` paths. GPU / `auto→gpu` skip Check 13b.

**Default merge-gate tests** (exclude `tests/runtime_contract_gate/`):

```bash
uv run pytest tests/unit tests/contract tests/integration -q
```

**Explicit reference runtime contract gate** (not default CI; dual fixtures: historical CONFLICT@8g + approved PASS@12g):

```bash
uv run pytest tests/runtime_contract_gate -m runtime_contract_gate -q
bash scripts/diagnostics/measure_tei_memory.sh --timeout=300
# Optional characterization (not loaded by compose.sh):
# bash scripts/diagnostics/measure_tei_memory.sh --mem-limit=10g|16g --timeout=300
```

Report fields include `runtime_contract_verdict`, model/revision/dtype, `image_digest`, warm-up peak RSS, steady-state RSS (only after healthy), `time_to_ready_sec` / `time_to_failure_sec`, `health_ready`, `oom_killed`, `exit_code`, plus audit `run_id` / `requested_limit` / `invalidation_reason`. OOM or incomplete evidence is fail-closed on operational commands (no skip/degraded pass on CPU path). Never use `docker update` as formal evidence.

### Rollback (DEV-003 Task Plan §13)

1. `./scripts/compose.sh --embedding=current down` (no `-v`)
2. Remove `.runtime/embedding.env`; re-run preflight + `start_embedding.sh`
3. Restore `versions.lock.env` from Git if digest update was bad
4. `rm -rf .runtime/`

## Human operations playbook

会话历史不可用时，人类日常粘贴 / 恢复 / 失败处置入口：

`03_AI_Prompts/01_项目日常操作手册.md`

（六模板与规则 A–E；勿在本 README 复制全文。）

## Specification

Authoritative design document:

`01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md`
