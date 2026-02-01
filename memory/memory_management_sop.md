L1: global_mem_insight.txt (极简索引层 - 严格控制 ≤50 行)
    ↓ 导航指向
L2: global_mem.txt (事实库层 - 现短但会膨胀)
    ↓ 详细引用
L3: ../memory/ (记录库层 - 包含 .md/.py 等各类文件)
```

---

## 各层职责与原则

### L1：全局内存索引 (global_mem_insight.txt)

**职责**：为 L2 和 L3 提供极简导航索引。

**特征**：
- 体积限制：≤ 50 行（硬约束）
- 内容：CONSTITUTION、STORES、ACCESS、TOPICS、LESSONS_LEARNED
- 更新：L2 有新增/删除事实时同步；发现通用规律时追加 LESSONS

**禁止**：详细说明、过程记录、单次修复日志

---

### L2：全局事实库 (global_mem.txt)

**职责**：存储全局环保性事实（路径、凭证、配置等）。

**特征**：
- 现状：约 20 行（精简）
- 趋势：随环境扩展而膨胀（可接受）
- 内容：按 `## [SECTION]` 组织的事实条目
- 同步：变化时更新 L1 的相应 TOPIC 导航行

---

### L3：详细记录库 (../memory/)

**职责**：存储所有 L1/L2 无法容纳的详细信息。

**特征**：
- 文件类型：.md、.py 等各类文件均可
- 膨胀容限：无限制
- 组织：按功能分类（mail/、vision/ 等）或文件类型（SOP、工具脚本、日志）
- 文件命名：*_sop.md（流程）、*_log.md（日志）、.py（工具脚本）

**管理**：
- 工具脚本 + 详细 SOP → L3 对应文件
- 维护日志、过程记录 → L3 maintenance_log.md
- 单次修复、实验 → L3 存放或删除，不入 L1 LESSONS

---

## L1 ↔ L2 同步规则

| L2 操作 | L1 同步 |
|---------|--------|
| 新增事实 | 在 TOPICS.GLOBAL_MEM 添加导航行 |
| 删除事实 | 在 TOPICS.GLOBAL_MEM 删除导航行 |
| 修改值 | 保持导航行不变 |

---

## 信息分类快速决策树

```
"这条信息该放哪层？"

是『全局环保事实』? (IP、路径、凭证、ID、API 密钥等)
  ├─ YES → L2 (global_mem.txt)
  │        然后 → L1 [TOPICS.GLOBAL_MEM] 添加导航行
  │
  └─ NO
       ↓
       是『可重复使用的通用规律』? (工具用法、排查方法)
       ├─ YES → L1 [LESSONS_LEARNED]
       │        并可在 L3 写详细解释
       │
       └─ NO → L3 (../memory/)
               - 过程/日志 → maintenance_log.md
               - 工具文档 → *_sop.md
               - 代码 → .py 文件
               - 临时实验 → L3 或删除