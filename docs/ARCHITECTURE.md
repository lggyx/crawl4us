# crawl4us 架构

> 状态：草案 v0.1，待评审
> 关联文档：[`crawl4ai-analysis.md`](crawl4ai-analysis.md)（参照对象分析）、[`DESIGN.md`](DESIGN.md)（早期设计，部分结论已被本文档取代）

---

## 1. 设计原则

| # | 原则 | 含义 |
|---|---|---|
| 1 | **单能力单文件** | 一个能力对应一个源文件，文件即能力边界 |
| 2 | **四类测试同步交付** | 每个能力必须同时有 unit / smoke / e2e / perf 测试 |
| 3 | **大平层** | 源码与测试均不建子包，无嵌套目录 |
| 4 | **主文件即 CLI** | `cli.py` 是唯一入口，对外只暴露命令行 |
| 5 | **审计友好** | 结构本身降低 review 成本，不依赖流程保证质量 |

### 1.1 为什么这样设计

参照 [`crawl4ai-analysis.md`](crawl4ai-analysis.md) 第 7 章识别的问题：

| crawl4ai 的问题 | 本架构的应对 |
|---|---|
| 单文件 118KB（`extraction_strategy.py`） | 单文件设 300 行软上限，超限拆分 |
| 策略基类继承体系复杂 | 单文件单实现，跨文件用 `Protocol` |
| 配置对象 50+ 参数 | 每层只暴露自己需要的 dataclass |
| 测试与实现脱节，靠人工验证 | 四类测试随能力同步交付 |
| 全局状态、`__del__` 清理导致泄漏 | 显式传参，强制上下文管理器 |
| 无性能基线，回归靠人发现 | perf 阈值写成断言，回归自动失败 |

---

## 2. 源码布局（大平层）

```
src/crawl4us/
├── cli.py            # 主文件：CLI 入口，参数解析 + 输出
├── types.py          # 共享数据类型（词汇表，非能力）
├── crawl.py          # 能力：管线编排
├── fetch_http.py     # 能力：HTTP 静态抓取
├── parse_dom.py      # 能力：HTML → lxml DOM
├── prune.py          # 能力：O(N) 内容剪枝
└── render_md.py      # 能力：DOM → Markdown
```

### 2.1 文件职责

| 文件 | 职责 | 明确不做 |
|---|---|---|
| `cli.py` | 参数解析、调用管线、格式化输出 | 不含业务逻辑 |
| `types.py` | 跨文件共享的数据类型定义 | 不含函数 |
| `crawl.py` | 编排 fetch → parse → prune → render | 不实现任何单步逻辑 |
| `fetch_http.py` | HTTP 抓取，返回原始 HTML | 不解析、不过滤 |
| `parse_dom.py` | HTML 字符串 → lxml DOM | 不做内容判断 |
| `prune.py` | DOM → 精简 DOM（O(N) 单次遍历） | 不生成 Markdown |
| `render_md.py` | DOM → Markdown 字符串 | 不做内容判断 |

### 2.2 扩展规则

后续里程碑新增能力时**平铺加入**，不新建目录：

```
M3: fetch_browser.py      # Playwright 动态抓取
M4: extract_schema.py     # 结构化抽取
M5: cache.py              # 缓存
```

### 2.3 文件体积约束

- 软上限 **300 行**，超过则考虑拆分
- 拆分时优先按职责拆成新能力文件，而非加子目录

---

## 3. 测试布局（按类型分目录）

```
tests/
├── fixtures/              # 本地 HTML 样本
├── unit/                  # 纯逻辑，本地 fixture，毫秒级
├── smoke/                 # 单能力 happy path，验证"没坏"
├── e2e/                   # CLI 子进程全链路
└── perf/                  # 量化阈值断言
```

### 3.1 命名约定

测试文件名与能力文件名对应：

| 能力文件 | unit | smoke | perf |
|---|---|---|---|
| `prune.py` | `tests/unit/test_prune.py` | `tests/smoke/test_prune.py` | `tests/perf/test_prune_perf.py` |
| `fetch_http.py` | `tests/unit/test_fetch_http.py` | `tests/smoke/test_fetch_http.py` | — |
| `render_md.py` | `tests/unit/test_render_md.py` | `tests/smoke/test_render_md.py` | `tests/perf/test_render_md_perf.py` |

**审计某个能力时，三个目录里的同名文件就是它的全部测试。**

### 3.2 四类测试的职责边界

| 类型 | 测什么 | 网络 | 耗时 | 默认运行 |
|---|---|---|---|---|
| **unit** | 单函数纯逻辑，边界条件、异常输入 | 否 | 毫秒级 | 是 |
| **smoke** | 单能力 happy path，验证基本可用 | 否 | < 1s | 是 |
| **e2e** | CLI 子进程全链路，验证端到端可用 | 标记可选 | 秒级 | 是 |
| **perf** | 量化阈值断言，防性能回归 | 否 | 百毫秒级 | 单独 |

### 3.3 运行方式

```bash
# 默认：unit + smoke + e2e（快且确定性）
uv run pytest

# 性能测试单独跑
uv run pytest tests/perf

# 需要真实网络的 e2e
uv run pytest -m network
```

---

## 4. 数据流

```
URL
 │
 ▼
┌─────────────┐   ┌────────────┐   ┌──────────┐   ┌────────────┐
│ fetch_http  │──▶│ parse_dom  │──▶│  prune   │──▶│ render_md  │
│ 原始 HTML   │   │ lxml DOM   │   │ 精简 DOM │   │ Markdown   │
└─────────────┘   └────────────┘   └──────────┘   └────────────┘
                        │
                        └── crawl.py 负责按顺序编排上述四步
```

**关键在 `prune.py`**：从 DOM 中区分正文、导航、页脚、广告，决定输出质量。

---

## 5. 跨文件协作约定

### 5.1 用 Protocol 而非继承

```python
# types.py
from typing import Protocol

class Fetcher(Protocol):
    async def fetch(self, url: str) -> str: ...
```

实现方不需要显式继承，只关心输入输出类型。

### 5.2 配置按层隔离

每层只暴露自己需要的字段，不做统一的大 config 对象：

```python
# fetch_http.py
@dataclass
class FetchOptions:
    timeout: float = 30.0
    follow_redirects: bool = True
```

### 5.3 显式传参，无全局状态

- 不用模块级可变状态
- 不用单例
- 资源（连接、浏览器）用上下文管理器，**禁用 `__del__`**

---

## 6. 里程碑

| 里程碑 | 新增能力 | 完成标准 |
|---|---|---|
| **M1** | `fetch_http` `parse_dom` `prune` `render_md` `crawl` `cli` | `crwl <url> -o markdown` 输出合理 |
| **M2** | 剪枝质量调优 | fixture 上去掉导航页脚、保留正文 |
| **M3** | `fetch_browser` | 能抓需 JS 渲染的页面 |
| **M4** | `extract_schema` | 支持 CSS schema 抽结构化数据 |
| **M5** | `cache` | 缓存命中省一半以上时间 |

---

## 7. 技术栈

| 维度 | 选型 |
|---|---|
| Python | 3.11+ |
| 包管理 | uv |
| HTML 解析 | lxml |
| 静态抓取 | httpx |
| 动态抓取 | Playwright（M3） |
| Markdown 生成 | 自研 DOM→Markdown |
| 测试 | pytest + pytest-asyncio |
| Lint / Format | ruff |
| 类型检查 | mypy（strict） |

---

## 8. 待定问题

不阻塞 M1，实现过程中逐步明确：

1. **剪枝阈值策略**：固定 vs 动态自适应？M1 先固定
2. **缓存后端**：先文件系统，SQLite 留到有并发需求时
3. **schema 格式**：是否兼容 crawl4ai 的 JsonCss 格式？
4. **CLI 输出格式**：markdown / json / html 如何组织？

---

*本文档随架构演进更新。重大变更请在文首记录版本与日期。*
