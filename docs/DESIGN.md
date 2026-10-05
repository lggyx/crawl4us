# crawl4us 设计文档

> 状态：草案 v0.1，待评审
> 关联文档：[`crawl4ai-analysis.md`](crawl4ai-analysis.md) — 参照对象的完整功能整理与遗留问题分析

---

## 1. 定位

**一句话**：把任意网页变成干净的、LLM 可直接消费的 Markdown。

### 1.1 目标

- 单页抓取 → 内容识别 → 清洗 → Markdown，一条主线跑通
- 同时输出 `raw_markdown`（全量）与 `fit_markdown`（精简），兼顾不同消费场景
- 静态与动态页面都能处理
- 结构化抽取不强制依赖 LLM

### 1.2 非目标

明确**不做**的事，避免范围蔓延：

| 不做 | 原因 |
|---|---|
| 分布式调度 | 单机场景用不到，引入消息队列代价过大 |
| 反爬对抗 | 属于持续军备竞赛，无终点 |
| 商业化云服务 | 与开源定位冲突 |
| RAG 检索层 | 是下游消费者的事，不是抓取工具的事 |
| 站点专用爬虫 | 维护成本高，通用能力优先 |
| PDF 抓取 | crawl4ai 在此连出 5 个安全公告，风险高收益低 |
| MCP / Docker Server | 留到核心稳定后再评估 |

---

## 2. 从 crawl4ai 学到的三件事

详见 [`crawl4ai-analysis.md`](crawl4ai-analysis.md) 第 7、8 章，这里只列影响设计的结论。

### 2.1 性能大头在浏览器，不在算法

crawl4ai 把剪枝从 134ms 优化到 13ms（10 倍），但单页抓取总耗时是**秒级**——浏览器渲染才是绝对大头。

**对我们的含义**：浏览器生命周期管理是性能关键模块，值得投入主要设计精力；剪枝算法保证 O(N) 即可，不必过度优化常数。

### 2.2 信任边界必须从第一天就划清

crawl4ai 在 v0.9.3 + v0.9.4 连发 8 个安全公告，共性是**多处未区分"可信配置"与"不可信请求体"**，导致不可信输入能触达危险能力（任意文件写、SSRF、读取环境变量）。

**对我们的含义**：入口处即区分配置来源。库调用视为可信；未来若加 Server，不可信请求体走独立的受限路径，默认禁用危险能力。

### 2.3 剪枝算法必须一开始就是 O(N)

crawl4ai 早期实现是"每个节点重新遍历子树"，复杂度超线性，直到 v0.9.4 才改成"一次自底向上遍历"。

**对我们的含义**：从第一行代码就采用单次遍历。这不是优化，是初始设计的正确形态。

---

## 3. 核心流程

```
URL
 │
 ▼
┌─────────┐   ┌──────────┐   ┌───────────┐   ┌──────────┐   ┌───────────┐
│ Fetcher │──▶│  Parser  │──▶│ Extractor │──▶│ Renderer │──▶│  Result   │
│ 抓取    │   │ DOM 解析 │   │ 内容识别  │   │ MD 生成  │   │ raw + fit │
└─────────┘   └──────────┘   └───────────┘   └──────────┘   └───────────┘
    │                             │
    │ 静态: httpx                  │ 剪枝（O(N) 单次遍历）
    │ 动态: Playwright             │ CSS 选择 / 标签排除 / 词数阈值
    │                             │
    └── 缓存命中则跳过抓取          └── 可选：schema 结构化抽取
```

**关键在 Extractor**：从 DOM 中区分正文、导航、页脚、广告，这决定输出质量，是整套系统的核心。

---

## 4. 模块划分

```
src/crawl4us/
├── __init__.py          # 公开 API
├── config.py            # BrowserConfig / CrawlConfig 数据类
├── models.py            # CrawlResult 等数据模型
├── fetcher/
│   ├── __init__.py
│   ├── base.py          # Fetcher 抽象基类
│   ├── http.py          # HttpFetcher（httpx，静态）
│   └── browser.py       # BrowserFetcher（Playwright，动态）
├── parser.py            # lxml DOM 解析与遍历
├── extractor/
│   ├── __init__.py
│   ├── base.py          # ContentFilter 抽象基类
│   ├── pruning.py       # PruningFilter（O(N) 剪枝）
│   └── selector.py      # CSS 选择 / 标签排除 / 阈值
├── renderer.py          # DOM → Markdown
├── schema.py            # 结构化抽取（Regex / CSS schema）
├── cache.py             # 缓存
└── cli.py               # crwl 命令行入口
```

### 4.1 各模块职责与边界

| 模块 | 输入 | 输出 | 明确不做 |
|---|---|---|---|
| `fetcher/` | URL + 配置 | 原始 HTML | 不解析、不过滤 |
| `parser.py` | HTML | DOM 树 | 不做内容判断 |
| `extractor/` | DOM + 配置 | 精简后 DOM | 不生成 Markdown |
| `renderer.py` | DOM | Markdown 字符串 | 不做内容判断 |
| `schema.py` | DOM + schema | `List[Dict]` | 不依赖 LLM |
| `cache.py` | URL | 命中则返回缓存 | 不管缓存失效策略之外的逻辑 |

### 4.2 策略接口

参照 crawl4ai 最值得继承的设计——每个环节可插拔：

```python
class Fetcher(Protocol):
    async def fetch(self, url: str, config: CrawlConfig) -> FetchOutput: ...

class ContentFilter(Protocol):
    def filter(self, dom: HtmlElement, config: CrawlConfig) -> HtmlElement: ...
```

M1 阶段每类只做一个实现，但接口先立住，避免后期重构。

---

## 5. 技术选型

| 维度 | 选型 | 理由 |
|---|---|---|
| Python | **3.11+** | `TaskGroup`、`Self` 类型、更快解释器 |
| 包管理 | **uv** | 快 10-100 倍，`pyproject.toml` 标准，lock 确定性强 |
| HTML 解析 | **lxml** | C 实现快，XPath 完整，crawl4ai 实测主力 |
| 静态抓取 | **httpx** | 异步原生、HTTP/2、API 现代 |
| 动态抓取 | **Playwright** | 多浏览器、自动等待、生态最成熟 |
| Markdown 生成 | **自研 DOM→Markdown** | 完全可控，能配合剪枝单次遍历产出 |
| 测试 | **pytest + pytest-asyncio** | 事实标准 |
| Lint / Format | **ruff** | 单工具覆盖，极快，取代 flake8/black/isort 三件套 |
| 类型检查 | **mypy** | 最主流 |

### 5.1 选型说明

**为什么用 lxml 而不是 selectolax**：selectolax 更快，但 API 较新、生态小、XPath 支持不完整。我们的剪枝算法需要频繁的父子遍历与 XPath，lxml 更稳。若后续 profiling 证明解析是瓶颈，可替换——`parser.py` 已隔离这层。

**为什么自研 Markdown 生成**：html2text、markdownify 等现成库的输出格式不可精细控制，且无法与剪枝算法共享同一次 DOM 遍历。自研的成本主要在表格与代码块处理，但这正是输出质量的关键。

**为什么 Playwright**：crawl4ai 的选择，自动等待机制能省掉大量显式 sleep。DrissionPage 反检测更强但生态小，而我们明确不做反爬对抗。

---

## 6. 仓库结构

```
crawl4us/
├── src/crawl4us/           # 源码（src 布局）
├── tests/
│   ├── unit/               # 单元测试，纯本地 fixture
│   ├── integration/        # 集成测试，需网络（默认跳过）
│   └── fixtures/           # 本地 HTML 样本
├── docs/
│   ├── crawl4ai-analysis.md
│   └── DESIGN.md
├── pyproject.toml
├── README.md
├── LICENSE                 # Apache-2.0
└── .gitignore
```

### 6.1 测试策略

- **单元测试用本地 fixture HTML，不跑真实网络** — 保证快速、可重复、CI 友好
- 集成测试标记 `@pytest.mark.network`，默认跳过
- 每个 `extractor` 改动都要有对应的 fixture 断言输出

---

## 7. 里程碑

| 里程碑 | 内容 | 完成标准 |
|---|---|---|
| **M1** | 静态页 → Markdown 跑通 | `crwl https://example.com -o markdown` 输出合理 |
| **M2** | 剪枝算法 + `fit_markdown` | 在 fixture 上能去掉导航/页脚，保留正文 |
| **M3** | Playwright 动态抓取 | 能抓取需 JS 渲染的页面 |
| **M4** | CLI 完善 + schema 抽取 | 支持 CSS schema 抽结构化数据 |
| **M5** | 缓存 + 批量并发 | `arun_many` 可用，缓存命中省一半以上时间 |

**M1 范围界定**：只做静态抓取（httpx）+ lxml 解析 + 基础 Markdown 渲染。不含剪枝、不含动态抓取。先把主线打通，再逐步加能力。

---

## 8. 从 crawl4ai 继承与规避对照

| crawl4ai 的做法 | crawl4us 的做法 |
|---|---|
| 剪枝算法超线性，v0.9.4 才修 | 一开始就单次自底向上遍历，O(N) |
| BeautifulSoup 遗留实现 | 只用 lxml，不引入第二套解析器 |
| 浏览器上下文劣化后靠回收（200 页） | 明确生命周期边界，从设计上避免劣化 |
| `__del__` 做异步清理导致泄漏 | 强制上下文管理器，禁用 `__del__` |
| 信任边界混乱，8 个安全公告 | 入口处区分可信/不可信配置 |
| PDF 在浏览器管控外抓取 | 不做 PDF；所有出口统一策略 |
| 单文件 100+ KB | 模块设体积上限，超限拆分 |
| `legacy/` 兼容层膨胀 | 未到 1.0 不承诺 API 稳定，到 1.0 果断断裂 |

---

## 9. 待定问题

以下问题在实现过程中逐步明确，不阻塞 M1：

1. **剪枝阈值策略**：固定阈值 vs 动态阈值（按页面统计自适应）？crawl4ai 两种都支持，我们 M2 先做固定，动态作为后续
2. **缓存存储后端**：先做文件系统，SQLite 留到有并发需求时
3. **批量并发的调度模型**：信号量 vs 内存自适应？M5 先用信号量，够用就不升级
4. **schema 抽取的 schema 格式**：是否兼容 crawl4ai 的 JsonCss 格式？兼容有利于迁移，但也继承其限制

---

*本文档随设计演进更新。重大变更请在文首记录版本与日期。*
