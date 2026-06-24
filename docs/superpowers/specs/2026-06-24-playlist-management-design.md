# 1. MusicPilot 歌单管理设计

日期：2026-06-24

## 1.1 目标

新增歌单管理能力，让用户可以先在设置中关联音乐平台账号，再从已关联平台读取歌单、选择歌单导入 MusicPilot，并针对导入后的歌单查看歌曲明细和触发自动下载。

首个支持平台为 Spotify。Spotify 只作为歌单元数据来源，不直接下载或抓取 Spotify 音频内容。下载仍走 MusicPilot 现有站点搜索、种子提交、下载任务轮询和音乐库刷新流程。

## 1.2 范围

本阶段包含：

1. 设置页新增“音乐平台”配置入口。
2. 支持 Spotify 平台关联、重新登录和删除关联。
3. 支持从已关联 Spotify 账号读取歌单列表。
4. 支持勾选 Spotify 歌单并同步导入。
5. 支持查看导入歌单的歌曲明细。
6. 支持标记歌曲是否已存在于当前音乐库。
7. 支持点击歌单下载后自动处理缺失歌曲。
8. 歌单下载过程复用现有 `torrent_records` 下载任务。

本阶段不包含：

1. Spotify 音频下载或转存。
2. Spotify 歌单反向写入。
3. 多账号同平台并发关联之外的复杂账号权限模型。
4. 歌单定时自动同步。
5. 新增单元测试，除非后续明确要求。

## 1.3 设置中的音乐平台

设置页新增一个独立页签“音乐平台”。页面展示平台关联列表。

列表字段：

1. 平台名称，例如 Spotify。
2. 授权账号名。
3. 状态：未关联、已关联、需要重新登录、关联失败。
4. 授权时间。
5. Access Token 到期时间。
6. Refresh Token 到期时间。
7. 最近同步时间。
8. 最近错误。
9. 操作：关联、重新登录、删除关联。

关联流程：

1. 用户点击“关联”。
2. 弹窗选择平台，首期只有 Spotify。
3. 用户填写 Spotify App 配置：`client_id`、`client_secret`、`redirect_uri`。
4. 用户点击“下一步”。
5. 后端保存平台配置并生成 Spotify OAuth 授权地址。
6. 前端跳转到 Spotify 授权页。
7. 用户登录 Spotify 并同意权限。
8. Spotify 回调 MusicPilot 后端。
9. 后端换取 token，读取 Spotify 用户信息，平台状态更新为已关联。

歌单页面不再处理平台 OAuth 配置，只选择已关联平台读取歌单。

## 1.4 Spotify 授权

Spotify 采用后端 Authorization Code Flow。MusicPilot 用户需要先在 Spotify Developer Dashboard 自建 App，并把 `redirect_uri` 配置到该 App 的 Redirect URIs 中。

推荐本地回调地址：

```text
http://127.0.0.1:8000/api/integrations/spotify/callback
```

部署到域名时使用：

```text
https://你的域名/api/integrations/spotify/callback
```

请求权限首期只申请读取歌单和账号展示所需权限：

```text
playlist-read-private playlist-read-collaborative user-read-private
```

`user-read-private` 用于调用 Spotify `/me` 读取账号展示信息。实现时应避免申请与导入歌单无关的写入权限。

## 1.5 Token 生命周期

后端保存 `access_token`、`refresh_token`、`access_token_expires_at`、`refresh_token_expires_at` 和授权 scopes。

处理规则：

1. 调用 Spotify API 前先检查 `access_token_expires_at`。
2. Access token 未过期时直接调用 Spotify API。
3. Access token 过期时使用 refresh token 自动刷新。
4. 刷新成功后更新 access token 和到期时间，用户无感。
5. 刷新失败且错误表示授权无效时，将平台状态标记为“需要重新登录”。
6. 用户在“设置 -> 音乐平台”点击“重新登录”后重新走 OAuth 流程。
7. 后台任务遇到平台需要重新登录时不反复重试，只记录错误并停止本次同步或下载前置读取。

Spotify 文档说明 access token 有有限生命周期，Dashboard App 签发的 refresh token 也需要按平台规则处理过期和重新授权。

## 1.6 数据模型

新增 `music_platform_connections` 表，保存音乐平台关联状态。

核心字段：

1. `id`
2. `platform`，首期为 `spotify`
3. `display_name`
4. `external_user_id`
5. `client_id`
6. `client_secret`
7. `redirect_uri`
8. `access_token`
9. `refresh_token`
10. `scopes`
11. `status`
12. `access_token_expires_at`
13. `refresh_token_expires_at`
14. `last_synced_at`
15. `last_error`
16. `payload`
17. `created_at`
18. `updated_at`

新增 `playlists` 表，保存已导入歌单。

核心字段：

1. `id`
2. `platform_connection_id`
3. `platform`
4. `external_id`
5. `name`
6. `owner_name`
7. `description`
8. `cover_url`
9. `track_count`
10. `status`
11. `last_synced_at`
12. `last_download_started_at`
13. `last_error`
14. `raw_payload`
15. `created_at`
16. `updated_at`

新增 `playlist_tracks` 表，保存歌单歌曲明细和下载状态。

核心字段：

1. `id`
2. `playlist_id`
3. `platform`
4. `external_id`
5. `position`
6. `title`
7. `artist`
8. `album`
9. `duration`
10. `isrc`
11. `cover_url`
12. `exists_in_library`
13. `matched_library_track_id`
14. `download_status`
15. `torrent_record_id`
16. `last_checked_at`
17. `last_download_attempt_at`
18. `last_error`
19. `raw_payload`
20. `created_at`
21. `updated_at`

`download_status` 使用明确状态：

1. `pending`：导入后尚未下载扫描。
2. `existing`：已存在于音乐库。
3. `waiting`：不存在，等待自动下载。
4. `searching`：正在站点搜索。
5. `submitted`：已创建并提交下载任务。
6. `not_found`：站点搜索无可用结果。
7. `failed`：下载流程失败。

下载任务仍复用 `torrent_records`，`playlist_tracks.torrent_record_id` 关联标准下载任务。

## 1.7 歌单导入流程

歌单页新增“新增”按钮。

交互流程：

1. 用户点击“新增”。
2. 弹窗选择已关联音乐平台。
3. 用户点击“读取歌单”。
4. 后端调用 Spotify `/me/playlists` 分页读取歌单列表。
5. 前端展示可同步歌单，用户勾选目标歌单。
6. 用户点击“确认”。
7. 后端分页读取每个歌单的歌曲明细。
8. 后端 upsert `playlists` 和 `playlist_tracks`。
9. 后端对导入歌曲执行一次音乐库匹配。
10. 前端刷新歌单列表。

如果平台状态为“需要重新登录”，歌单页提示用户到“设置 -> 音乐平台”重新登录。

## 1.8 音乐库匹配

匹配来源为现有 `music_library_tracks` 表。

匹配时机：

1. 歌单歌曲首次导入后立即匹配。
2. 每次手动音乐库同步完成后匹配。
3. 每次后台音乐库刷新后延迟同步完成时匹配。
4. 点击歌单下载时先重新扫描一次。
5. 单首歌进入下载流程前再次查询一次。

首期匹配规则保持可解释：

1. 标题规范化后相同。
2. 艺术家规范化后相同或包含。
3. 同时满足标题和艺术家条件才标记存在。

规范化沿用现有搜索文本规范化思路，处理大小写、空白、全半角和繁简转换。首期不做模糊猜测，避免把不同歌曲误判为已存在。

## 1.9 歌单下载流程

用户在歌单列表点击“下载”。

后端创建后台下载流程：

1. 读取歌单所有明细。
2. 扫描每首歌是否已存在于音乐库。
3. 已存在则标记 `download_status = existing`。
4. 不存在则标记 `download_status = waiting`。
5. 扫描结束后取出 `waiting` 列表。
6. 逐首循环下载。
7. 每首歌下载前再次查询音乐库。
8. 如果此时已存在，标记为 `existing` 并跳过。
9. 如果仍不存在，按标题和艺术家生成搜索请求。
10. 调用现有站点搜索能力。
11. 先按艺术家过滤，再选择做种数最高的结果。
12. 调用现有下载提交逻辑，创建 `torrent_records`。
13. 更新歌单明细状态和 `torrent_record_id`。

自动选种规则：

1. 搜索关键词为歌曲标题。
2. 搜索结果必须通过艺术家匹配过滤。
3. 过滤后按 `seeders` 倒序选择第一个结果。
4. 没有结果则标记 `not_found`。

自动下载不直接改变现有下载任务生命周期。下载提交后由现有轮询流程推进：

```text
queued -> submitted -> downloading -> completed -> refreshing_library -> library_refreshed
```

## 1.10 歌单查看

点击歌单“查看”按钮打开弹窗。

弹窗展示：

1. 歌曲序号。
2. 标题。
3. 艺术家。
4. 专辑。
5. 时长。
6. 是否存在于音乐库。
7. 下载状态。
8. 错误信息。

存在于音乐库时使用绿色对勾展示。

## 1.11 后端 API

音乐平台 API：

1. `GET /api/music-platforms`
2. `POST /api/music-platforms/connect/start`
3. `GET /api/integrations/spotify/callback`
4. `POST /api/music-platforms/{connection_id}/reauthorize/start`
5. `DELETE /api/music-platforms/{connection_id}`

歌单 API：

1. `GET /api/playlists`
2. `GET /api/playlists/available?connection_id=...`
3. `POST /api/playlists/import`
4. `GET /api/playlists/{playlist_id}/tracks`
5. `POST /api/playlists/{playlist_id}/sync`
6. `POST /api/playlists/{playlist_id}/download`

`available` 只读取平台当前歌单，不写入 MusicPilot。`import` 才写入本地库。

## 1.12 前端菜单

新增一级菜单“歌单”。

歌单列表展示：

1. 封面。
2. 名称。
3. 平台。
4. 歌曲数。
5. 已存在数。
6. 等待下载数。
7. 已提交下载数。
8. 失败数。
9. 最近同步时间。
10. 操作：查看、同步、下载。

设置页新增“音乐平台”页签。为了和已有设置结构一致，这个页签放在现有设置页面中，不新增独立设置入口。

## 1.13 错误处理

错误处理原则：

1. 平台授权错误落在 `music_platform_connections.last_error`。
2. 歌单读取错误落在 `playlists.last_error`。
3. 单曲搜索和下载错误落在 `playlist_tracks.last_error`。
4. 下载任务提交成功后，后续下载错误由 `torrent_records.last_error` 承接。
5. Spotify token 失效时平台状态改为“需要重新登录”。
6. 歌单页遇到平台需要重新登录时只提示，不自动弹授权窗口。

## 1.14 验证

实现后做以下验证：

1. 后端启动成功。
2. 前端构建成功。
3. 设置页能新增 Spotify 关联并生成授权 URL。
4. Spotify 回调能保存 token 和用户信息。
5. 歌单页能读取已关联平台的歌单。
6. 勾选歌单后能导入歌单和歌曲明细。
7. 查看弹窗能展示音乐库绿色对勾。
8. 音乐库同步后能刷新歌单明细存在状态。
9. 歌单下载能把已存在歌曲标记为 `existing`。
10. 缺失歌曲能按艺术家过滤和做种数最高规则自动提交下载任务。
11. 提交后的任务出现在现有下载任务列表。

不默认新增额外单元测试；若后续要求测试，优先覆盖 Spotify token 刷新、歌单导入 upsert、音乐库匹配和自动选种。

## 1.15 官方文档参考

1. Spotify Apps：https://developer.spotify.com/documentation/web-api/concepts/apps
2. Spotify Authorization Code Flow：https://developer.spotify.com/documentation/web-api/tutorials/code-flow
3. Spotify Refreshing Tokens：https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens
4. Spotify Current User Playlists：https://developer.spotify.com/documentation/web-api/reference/get-a-list-of-current-users-playlists
5. Spotify Playlist Items：https://developer.spotify.com/documentation/web-api/reference/get-playlists-tracks

## 1.16 自审结论

本设计不再把 Spotify OAuth 配置放在歌单新增流程中，而是放到设置页“音乐平台”中统一管理。歌单页面只依赖已关联平台读取歌单。下载任务复用现有 `torrent_records`，没有引入重复下载任务模型。Spotify token 过期、失效和重新登录路径已明确。
