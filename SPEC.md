# MusicPilot (MP) 自动化音乐处理系统架构与开发白皮书

本说明书是 MusicPilot (MP) 项目的顶层架构设计与技术实施纲领，完整收录了关于系统边界、技术哲学、全栈选型以及未来演进路线的决策。此文档不仅作为开发人员的参考蓝图，也作为 AI 辅助开发时的核心上下文库。

---

## 1. 项目愿景与技术理念 (Vision & Philosophy)

MusicPilot 致力于为自托管（Self-hosted）爱好者提供一个**轻量、无感、高可靠**的自动化音乐流转中枢。

* **I/O 驱动的极致并发**：系统的核心任务（网页爬取、API 请求、文件读写、下载状态轮询）属于纯粹的 I/O 密集型。系统摒弃多线程/多进程模型，全面拥抱 **单进程纯异步 (Async I/O)** 架构，在保证极低内存占用（控制在 100MB 左右）的同时，支持千级别的并发网络请求。
* **开箱即用与性能上限并存**：践行“渐进式增强”理念。默认采用无需配置的 SQLite 满足 90% 用户的零门槛部署需求；同时预留 PostgreSQL 接入能力，为海量订阅和极端并发提供企业级性能上限。
* **单一制成品 (Single Artifact)**：无论内部组件多么复杂，最终交付给用户的必须是一个包含前后端完整链路的极简 Docker 镜像。

---

## 2. 核心架构：端口与适配器模式 (Hexagonal Architecture)

系统采用典型的六边形架构，保护核心业务逻辑不被第三方服务的变动所污染。

### 核心调度层 (Core Domain)

* **Event Bus (事件总线)**：系统的心脏，基于 `asyncio.Queue` 构建。一切外部触发（用户点击、定时任务、下载完成 Webhook）均转化为标准事件（如 `SearchEvent`, `ScrapeEvent`）进入核心队列。
* **Pipeline (流水线)**：无状态的处理流，负责串联“检索 -> 下载 -> 刮削 -> 入库 -> 刷新”的完整生命周期。

### 外部适配器层 (Adapters)

核心层不直接依赖任何具体平台，而是通过协议（抽象基类）对接适配器：

* **Bot Adapter**：解耦交互入口。支持 Telegram (`aiogram`)，预留飞书/Lark、Discord 接入空间。
* **Web UI Adapter**：基于 FastAPI 的 RESTful/GraphQL 接口，供前端后台管理面板使用。
* **Indexer Adapter**：PT/BT 站点搜索引擎，内置针对 NexusPHP 架构的通用爬虫引擎。
* **Downloader Adapter**：种子分发与进度控制器，首发支持 qBittorrent。
* **Metadata Adapter**：音乐标签抓取引擎，聚合 MusicBrainz、QQ音乐、网易云等多源数据。
* **Notifier Adapter**：媒体库刷新通知器，首发支持 Navidrome (Subsonic API)。

---

## 3. 全栈技术选型矩阵

### 3.1 后端技术栈 (Backend)

* **运行时**：`Python 3.11+`
* **Web 与 API 框架**：`FastAPI` + `Uvicorn`
* **ORM 与 数据库管理**：`SQLAlchemy 2.0 (Async)` + `Alembic`
* **数据库引擎**：`aiosqlite` (默认) / `asyncpg` (高阶可选)
* **网络 I/O**：`httpx[http2]`
* **DOM 解析**：`BeautifulSoup4` + `lxml`
* **音频标签处理**：`mutagen`
* **任务调度**：`APScheduler` (AsyncIOScheduler)

### 3.2 前端技术栈 (Frontend - Web 管理后台)

* **核心框架**：`Vue 3` (Composition API) + `TypeScript`
* **构建工具**：`Vite`
* **UI 框架**：`Element Plus` 或 `Naive UI` (原生支持深色模式)
* **样式引擎**：`Tailwind CSS`
* **状态与路由**：`Pinia` + `Vue Router`

### 3.3 部署形态 (Deployment)

* **Docker 构建**：多阶段构建 (Multi-stage Build)。第一阶段 Node.js 编译 Vue3 代码；第二阶段 Python-slim 封装后端，并将前端静态资源 (`dist`) 挂载入 FastAPI 进行同源分发。

---

## 4. 关键技术方案设计 (Key Technical Designs)

### 4.1 数据库双轨制防雷设计

* **ORM 层屏蔽**：严格禁止手写特定数据库的 SQL。禁止使用 PostgreSQL 的 `JSONB` 或 `ARRAY`，必须统一采用 SQLAlchemy 标准的 `JSON` 或 `String` 确保向下兼容 SQLite。
* **SQLite 锁雪崩防御**：在初始化 SQLite 引擎时，必须通过事件监听（Event Listeners）执行 `PRAGMA journal_mode=WAL`，允许多读一写并发，彻底解决 `database is locked` 异常。
* **Alembic 降级策略**：配置 `render_as_batch=True`，规避 SQLite 极其受限的 `ALTER TABLE` 语法限制。

### 4.2 零依赖的 NexusPHP 通用爬虫引擎

摒弃沉重的 Jackett/Prowlarr 外部依赖：

1. 构建 `NexusPHPCrawler` 基类。
2. 通过统一的 `torrents.php?search=xxx` 接口发起异步 GET 请求。
3. 通过 `BeautifulSoup` 结合配置文件 (`sites.yaml` 中定义的站点特定 DOM 节点差异) 解析表格。
4. 内置并发控制与请求频率限制 (Rate Limiting) 模块，避免被站点反作弊机制封禁 (Ban)。

### 4.3 多源级联元数据引擎 (Metadata Fallback Strategy)

音频文件元数据（ID3/Vorbis）的准确写入是本系统的核心价值：

* **精准定轨**：第一优先级请求 **MusicBrainz API**，依靠其严谨的 Release Group / Tracklist 层级结构，补全外文歌曲与古典音乐信息。
* **本土增强**：第二优先级请求 **国内流媒体 API (QQ音乐/网易云)**，用于抓取精确的逐字歌词 (LRC) 和中译版专辑名称。
* **安全写入**：在目标目录完成**硬链接 (Hardlink)** 创建后，使用 `asyncio.to_thread` 将同步的 `mutagen` 文件写入操作剥离出主事件循环，直接修改硬链接文件的二进制标签头，不破坏原种子文件的 Hash。

---

## 5. 核心事件工作流 (The Core Workflow)

1. **触达 (Trigger)**：用户通过 Telegram 发送歌曲名，或在 Web UI 填入关键词。
2. **聚变检索 (Scatter-Gather Search)**：系统并发调用所有启用的 NexusPHP 爬虫，将结果聚合、去重并按做种数 (Seeders) 排序返回给用户确认。
3. **下载注入 (Inject)**：将选定的 Torrent 链接推入 qBittorrent，打上 `MusicPilot` 专属标签，设定暂存目录。
4. **无感监听 (Listen)**：qBittorrent 下载完成后，触发内置的 `Run external program`，向 MP 的 Webhook API 发起回调，传递 Torrent Hash。
5. **刮削重构 (Process)**：
   * MP 找到对应下载目录。
   * 在配置的目标音乐库路径下，按照规范目录树（`Artist/Album (Year)/01 - Track.flac`）建立硬链接。
   * 并发请求多源元数据 API，合并最终的 Metadata 字典。
   * 将 Metadata 和封面图片一并封装写入该硬链接文件。
6. **感知刷新 (Notify)**：调用 Navidrome 的刷新接口，并在 Telegram/Web 界面下发“已入库”的含封面通知卡片。

---

## 6. 未来演进路径与扩展点预留 (Extension Points)

系统在 V1 版本阶段即为后续升级埋下伏笔，架构设计必须保证以下功能扩展时，核心代码的**零入侵或微小变动**：

### 扩展点 1：流媒体歌单同步 (Spotify / Apple Music)

* **设计预留**：只需在 `adapters/` 下新增 `PlaylistAdapter`。它读取 Spotify 歌单 URL，解析出每一首歌的元数据字典，转化为系统核心的 `SearchEvent` 推入事件队列。后续流程完美复用现有的检索与刮削体系。

### 扩展点 2：歌手/专辑自动化订阅 (Automated Subscriptions)

* **设计预留**：内置 `APScheduler`。数据库新增 `Subscriptions` 表。定时任务（例如每天凌晨 2 点）查询关注歌手的 MusicBrainz 发行记录，比对本地数据库，若有新专辑，自动生成无交互的静默 `SearchEvent` 与 `DownloadEvent`。

### 扩展点 3：多端机器人支持 (Lark/Discord)

* **设计预留**：Bot 交互层与业务核心已完全分离。实现飞书的 OpenAPI，只需继承 `BaseBotAdapter` 并在配置中切换鉴权密钥，业务核心发出的 `NotifyEvent(Title, Cover, Text)` 会被飞书适配器自动翻译为飞书的消息卡片 (Message Card) JSON 并发送。

### 扩展点 4：更多下载器与媒体服务器支持

* **设计预留**：增加对 Transmission 或 Aria2 的支持，只需实现 `DownloaderAdapter` 接口中的 `add_torrent()` 和 `get_status()`。接入 Plex 或 Emby，只需扩充 `NotifierAdapter` 的 Webhook 触发逻辑。
