# 运维与工程规范

## CI / Quality Gate

GitHub Actions：`.github/workflows/ci.yml`

| Job | 内容 |
| --- | --- |
| `static` | Ruff · Mypy · `.env.example` 校验 |
| `unit-contract-coverage` | Unit + Contract；`memory_system.domain` + `memory_system.application` **≥ 80%** |
| `integration` | 集成测试（排除 `runtime_contract_gate` marker） |

本地等价命令：

```bash
bash scripts/ci/run_merge_gate.sh
```

或手动：

```bash
uv sync --locked
uv run ruff check src tests scripts
uv run mypy src
uv run python scripts/check_env_example.py
uv run pytest tests/unit tests/contract \
  -m "not runtime_contract_gate and not task_scope_boundary" \
  --cov=memory_system.domain \
  --cov=memory_system.application \
  --cov-report=term-missing \
  --cov-fail-under=80 \
  -q
cp .env.example .env
uv run pytest tests/integration -m "not runtime_contract_gate" -q
```

E2E 与 failure injection 见 `tests/e2e/`（非默认 merge gate，见 PR #59）。

## TEI CPU 内存契约（OI-011）

正式 CPU TEI `mem_limit` 为 **12g**（`BAAI/bge-m3` float32 ONNX CPU 固定契约）。低于 12g 为 `NON_SPEC_COMPLIANT`。

Preflight **Check 8** CPU MemAvailable：最低 **16** GiB / 推荐 **20** GiB。  
**Check 13a**：`MemTotal >= 14`（ES 2g + TEI 12g）。  
**Check 13b**：在 `mem_limit: 12g` 下真实 TEI CPU 探测（最长约 300s），适用于 `cpu` / `auto→cpu` 路径。

### Runtime contract gate（非默认 CI）

```bash
uv run pytest tests/runtime_contract_gate -m runtime_contract_gate -q
bash scripts/diagnostics/measure_tei_memory.sh --timeout=300
```

报告字段含 `runtime_contract_verdict`、RSS、`time_to_ready_sec`、`oom_killed` 等。OOM 或证据不完整时 fail-closed。**禁止**用 `docker update` 作为正式证据。

## 人类操作手册

会话历史不可用时的粘贴 / 恢复 / 失败处置：

[docs/ai-workflow/prompts/01_项目日常操作手册.md](ai-workflow/prompts/01_项目日常操作手册.md)

## 规格与验收

- 权威设计文档：`01_技术规格/记忆系统设计文档_全链路MVP技术选型版(9).md`
- 测试矩阵：`05_测试与验收/test_matrix.md`
- MVP 验收清单：`05_测试与验收/mvp_acceptance_checklist.md`

## LoCoMo 评测复现

```bash
# 报告目录
ls data/locomo/

# 评测脚本入口（需配置 LLM 与运行中服务）
ls scripts/locomo_eval/
```

冻结指标说明见根目录 [README.md](../README.md#locomo-评测结果conv-3081-题)。
