# {TASK_ID} {TASK_NAME}

## 1. 任务信息

```yaml
task_id: {TASK_ID}
task_name: {TASK_NAME}
status: planned
spec_sections:
  - "{SECTION}"
prerequisites:
  - "{PREREQUISITE}"
branch: "feat/{TASK_ID}-{slug}"
created_at: "{YYYY-MM-DD HH:mm UTC}"
updated_at: "{YYYY-MM-DD HH:mm UTC}"
```

## 2. 任务目标

说明本任务完成后，系统新增的可验证能力。

## 3. 非目标

明确本任务不会实现的内容，避免范围膨胀。

## 4. 当前代码状态

- 已存在代码：
- 可复用组件：
- 当前缺失：
- 与技术规格不一致之处：
- 前置任务检查：

## 5. 实现方案

### Step 1

- 文件：
- 类/函数/Schema：
- 输入：
- 输出：
- 错误处理：
- 幂等/并发/事务要求：

### Step 2

同上。

## 6. 文件变更清单

| 文件路径 | 创建/修改 | 目的 |
|---|---|---|
|  |  |  |

## 7. 数据一致性分析

| 维度 | 结论 | 处理方式 |
|---|---|---|
| 原子性 |  |  |
| 幂等 |  |  |
| 并发 |  |  |
| 版本冲突 |  |  |
| 用户隔离 |  |  |
| 部分失败 |  |  |
| 进程异常恢复 |  |  |

不适用的维度必须写明“不适用”及原因。

## 8. 测试计划

### Unit Test

| 场景 | 预期 |
|---|---|
|  |  |

### Contract Test

| 场景 | 预期 |
|---|---|
|  |  |

### Integration Test

| 场景 | 预期 |
|---|---|
|  |  |

### E2E Test

| 场景 | 预期 |
|---|---|
|  |  |

### 失败注入与并发测试

| 场景 | 预期 |
|---|---|
|  |  |

## 9. 验收标准

- [ ] 可通过命令或断言验证的验收条件 1
- [ ] 可通过命令或断言验证的验收条件 2
- [ ] 对应测试全部通过
- [ ] Ruff 通过
- [ ] Mypy 通过
- [ ] Review 无 P0/P1

## 10. 风险与阻塞项

- 设计文档冲突：
- 当前代码冲突：
- 前置任务：
- 未批准依赖：
- API/Schema 变化：
- 其他风险：

## 11. Git 计划

```yaml
branch: "feat/{TASK_ID}-{slug}"
expected_commits:
  - "docs(plan): add {TASK_ID} implementation plan"
  - "{type}({scope}): {summary}"
out_of_scope_changes:
  - "列出不得混入的无关修改"
```

## 12. Plan Amendment

计划批准后如需修改，新增记录，禁止覆盖原计划。

### Amendment 001

- 日期：
- 原计划：
- 修改内容：
- 修改原因：
- 是否影响技术规格：
- 审批状态：

## 13. 执行记录

| 时间 | 步骤 | 实际修改 | 测试 | 风险/差异 |
|---|---|---|---|---|
|  |  |  |  |  |

## 14. 实际执行结果

### 实际修改文件

| 文件 | 结果 |
|---|---|
|  |  |

### 与原计划的差异

暂无。

### 测试结果

| 测试 | 命令 | 结果 |
|---|---|---|
| Unit |  |  |
| Contract |  |  |
| Integration |  |  |
| E2E |  |  |
| Ruff |  |  |
| Mypy |  |  |

### Review 结果

```yaml
p0: 0
p1: 0
p2: 0
p3: 0
review_report: null
```

### Git 记录

```yaml
branch: null
plan_commit: null
implementation_commit: null
implementation_commit_message: null
```

### 最终状态

`planned`
