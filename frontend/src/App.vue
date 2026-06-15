<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

type ParserField = {
  selector: string
  attribute?: string
  regex?: string | null
  index?: number | null
  remove?: string[]
  filters?: string[]
}

type ParserConfig = {
  list_selector: string
  fields: Record<string, ParserField>
}

type SearchResult = {
  title: string
  download_url: string
  source: string
  seeders: number
  leechers?: number
  size_bytes?: number | null
  details_url?: string | null
  subtitle?: string | null
  published_at?: string | null
  promotion?: string | null
}

type DownloadTask = {
  torrent_hash: string
  name: string
  state: string
  progress: number
  save_path?: string | null
}

type MediaFile = {
  id: number
  torrent_hash?: string | null
  source_path: string
  library_path: string
  title?: string | null
  artist?: string | null
  album?: string | null
  year?: number | null
  track_number?: number | null
}

type Site = {
  id?: string | null
  name: string
  base_url: string
  cookie?: string | null
  user_agent?: string | null
  parser?: ParserConfig
  max_concurrency: number
}

type DownloaderConfig = {
  id?: string | null
  name: string
  type: string
  base_url: string
  username: string
  download_path: string
  is_default: boolean
}

type NotifierConfig = {
  id?: string | null
  name: string
  type: string
  chat_ids: string
  use_proxy: boolean
}

type SystemSettings = {
  proxy: {
    host: string
    port: number
    username: string
    password: string
  }
}

type LogEntry = {
  timestamp: string
  level: string
  message: string
  category: string
}

type TestResponse = {
  ok: boolean
  message: string
}

const loggedIn = ref(false)
const loginLoading = ref(false)
const loginForm = ref({ username: 'admin', password: 'musicpilot' })
const activePage = ref('search')
const settingsTab = ref('downloaders')
const drawer = ref(true)

const searchDialog = ref(false)
const searchLoading = ref(false)
const searchText = ref('')
const activeSearchSource = ref('')
const searchResults = ref<SearchResult[]>([])
const searchPage = ref(1)
const searchPageSize = ref(20)
const pendingDownload = ref<SearchResult | null>(null)

const logs = ref<LogEntry[]>([])
const logsLoading = ref(false)
const logPaused = ref(false)
const logLevel = ref('ALL')
const logQuery = ref('')
let logTimer: number | undefined

const downloads = ref<DownloadTask[]>([])
const mediaFiles = ref<MediaFile[]>([])
const sites = ref<Site[]>([])
const downloaders = ref<DownloaderConfig[]>([])
const notifiers = ref<NotifierConfig[]>([])

const siteDialog = ref(false)
const downloaderDialog = ref(false)
const notifierDialog = ref(false)
const siteTesting = ref(false)
const downloaderTesting = ref(false)
const notifierTesting = ref(false)
const systemSaving = ref(false)
const editingSiteId = ref<string | null>(null)
const editingDownloaderId = ref<string | null>(null)
const editingNotifierId = ref<string | null>(null)

const snackbar = ref({ show: false, color: 'success', text: '' })

const siteForm = ref({
  name: '',
  base_url: '',
  cookie: '',
  user_agent: '',
  max_concurrency: 2
})

const downloaderForm = ref({
  id: null as string | null,
  name: 'qBittorrent',
  type: 'qbittorrent',
  base_url: '',
  username: '',
  password: '',
  download_path: '',
  is_default: true
})

const notifierForm = ref({
  id: null as string | null,
  name: 'Telegram Bot',
  type: 'telegram',
  bot_token: '',
  chat_ids: '',
  use_proxy: false
})

const systemForm = ref<SystemSettings>({
  proxy: {
    host: '',
    port: 0,
    username: '',
    password: ''
  }
})

const navItems = [
  { title: '搜索', value: 'search', icon: 'mdi-magnify' },
  { title: '下载', value: 'downloads', icon: 'mdi-download' },
  { title: '整理', value: 'media', icon: 'mdi-music-box-multiple' },
  { title: '站点', value: 'sites', icon: 'mdi-server-network' },
  { title: '日志', value: 'logs', icon: 'mdi-text-box-search-outline' },
  { title: '设置', value: 'settings', icon: 'mdi-cog-outline' }
]

const pageTitle = computed(() => navItems.find((item) => item.value === activePage.value)?.title ?? 'MusicPilot')

const pagedSearchResults = computed(() => {
  const start = (searchPage.value - 1) * searchPageSize.value
  return searchResults.value.slice(start, start + searchPageSize.value)
})

const filteredLogs = computed(() => {
  const keyword = logQuery.value.trim().toLowerCase()
  return logs.value.filter((entry) => {
    const levelMatches = logLevel.value === 'ALL' || entry.level === logLevel.value
    const text = `${entry.timestamp} ${entry.category} ${entry.level} ${entry.message}`.toLowerCase()
    return levelMatches && (!keyword || text.includes(keyword))
  })
})

async function api<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, {
    credentials: 'include',
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers ?? {})
    }
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return response.json() as Promise<T>
}

async function readError(response: Response) {
  const text = await response.text()
  if (!text) return response.statusText
  try {
    const data = JSON.parse(text) as { detail?: unknown; message?: unknown }
    if (typeof data.detail === 'string') return data.detail
    if (typeof data.message === 'string') return data.message
    return text
  } catch {
    return text
  }
}

function notify(text: string, color = 'success') {
  snackbar.value = { show: true, color, text }
}

async function login() {
  loginLoading.value = true
  try {
    await api('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(loginForm.value)
    })
    loggedIn.value = true
    await loadInitialData()
  } catch {
    notify('用户名或密码错误', 'error')
  } finally {
    loginLoading.value = false
  }
}

async function loadInitialData() {
  await Promise.all([
    loadSites(),
    loadDownloaders(),
    loadNotifiers(),
    loadSystemSettings(),
    loadMedia(),
    loadDownloads(),
    loadLogs()
  ])
  startLogPolling()
}

function runSearch() {
  if (!searchText.value.trim()) return
  searchDialog.value = false
  searchLoading.value = true
  activeSearchSource.value = ''
  searchResults.value = []
  searchPage.value = 1

  const params = new URLSearchParams({ query: searchText.value.trim(), limit: '100' })
  const stream = new EventSource(`/api/search/stream?${params.toString()}`, {
    withCredentials: true
  })

  stream.addEventListener('result', (event) => {
    const result = JSON.parse((event as MessageEvent).data) as SearchResult
    activeSearchSource.value = result.source
    searchResults.value.push(result)
  })

  stream.addEventListener('error', () => {
    stream.close()
    searchLoading.value = false
    activeSearchSource.value = ''
  })

  stream.addEventListener('done', () => {
    stream.close()
    searchLoading.value = false
    activeSearchSource.value = ''
  })
}

function viewResult(row: SearchResult) {
  if (!row.details_url) {
    notify('没有详情页地址', 'warning')
    return
  }
  window.open(row.details_url, '_blank', 'noopener,noreferrer')
}

function openDownloadConfirm(result: SearchResult) {
  pendingDownload.value = result
}

async function confirmDownload() {
  if (!pendingDownload.value) return
  await addDownload(pendingDownload.value)
  pendingDownload.value = null
}

async function addDownload(result: SearchResult) {
  await api('/api/downloads', {
    method: 'POST',
    body: JSON.stringify(result)
  })
  notify('已发送到默认下载器')
}

async function loadDownloads() {
  downloads.value = await api<DownloadTask[]>('/api/downloads')
}

async function loadMedia() {
  mediaFiles.value = await api<MediaFile[]>('/api/media')
}

async function loadSites() {
  sites.value = await api<Site[]>('/api/sites')
}

async function loadLogs() {
  if (logPaused.value) return
  logsLoading.value = true
  try {
    logs.value = await api<LogEntry[]>('/api/logs?limit=300')
  } finally {
    logsLoading.value = false
  }
}

function startLogPolling() {
  window.clearInterval(logTimer)
  logTimer = window.setInterval(() => {
    void loadLogs()
  }, 5000)
}

function openNewSiteDialog() {
  editingSiteId.value = null
  siteForm.value = {
    name: '',
    base_url: '',
    cookie: '',
    user_agent: '',
    max_concurrency: 2
  }
  siteDialog.value = true
}

function editSite(site: Site) {
  editingSiteId.value = site.id ?? null
  siteForm.value = {
    name: site.name,
    base_url: site.base_url,
    cookie: site.cookie ?? '',
    user_agent: site.user_agent ?? '',
    max_concurrency: site.max_concurrency
  }
  siteDialog.value = true
}

function sitePayload() {
  return { ...siteForm.value }
}

async function saveSite() {
  try {
    const editing = Boolean(editingSiteId.value)
    const site = await api<Site>(editing ? `/api/sites/${editingSiteId.value}` : '/api/sites', {
      method: editing ? 'PUT' : 'POST',
      body: JSON.stringify(sitePayload())
    })
    if (editing) {
      sites.value = sites.value.map((item) => (item.id === site.id ? site : item))
    } else {
      sites.value.push(site)
    }
    siteDialog.value = false
    notify('站点已保存')
  } catch (error) {
    notify(error instanceof Error ? error.message : '站点保存失败', 'error')
  }
}

async function testSite() {
  siteTesting.value = true
  try {
    const result = await api<TestResponse>('/api/sites/test', {
      method: 'POST',
      body: JSON.stringify(sitePayload())
    })
    notify(result.message, result.ok ? 'success' : 'error')
  } catch (error) {
    notify(error instanceof Error ? error.message : '站点测试失败', 'error')
  } finally {
    siteTesting.value = false
  }
}

async function loadDownloaders() {
  downloaders.value = await api<DownloaderConfig[]>('/api/settings/downloaders')
}

function openNewDownloaderDialog() {
  editingDownloaderId.value = null
  downloaderForm.value = {
    id: null,
    name: 'qBittorrent',
    type: 'qbittorrent',
    base_url: '',
    username: '',
    password: '',
    download_path: '',
    is_default: true
  }
  downloaderDialog.value = true
}

function editDownloader(downloader: DownloaderConfig) {
  editingDownloaderId.value = downloader.id ?? null
  downloaderForm.value = {
    id: downloader.id ?? null,
    name: downloader.name,
    type: downloader.type,
    base_url: downloader.base_url,
    username: downloader.username,
    password: '',
    download_path: downloader.download_path ?? '',
    is_default: downloader.is_default
  }
  downloaderDialog.value = true
}

async function testDownloader() {
  downloaderTesting.value = true
  try {
    const result = await api<TestResponse>('/api/settings/downloaders/test', {
      method: 'POST',
      body: JSON.stringify(downloaderForm.value)
    })
    notify(result.message, result.ok ? 'success' : 'error')
  } catch (error) {
    notify(error instanceof Error ? error.message : '下载器测试失败', 'error')
  } finally {
    downloaderTesting.value = false
  }
}

async function saveDownloader() {
  const editing = Boolean(editingDownloaderId.value)
  const downloader = await api<DownloaderConfig>(
    editing
      ? `/api/settings/downloaders/${editingDownloaderId.value}`
      : '/api/settings/downloaders',
    {
      method: editing ? 'PUT' : 'POST',
      body: JSON.stringify(downloaderForm.value)
    }
  )
  if (editing) {
    downloaders.value = downloaders.value.map((item) =>
      item.id === downloader.id ? downloader : item
    )
  } else {
    downloaders.value.push(downloader)
  }
  downloaderDialog.value = false
  notify('下载器已保存')
}

async function loadNotifiers() {
  notifiers.value = await api<NotifierConfig[]>('/api/settings/notifiers')
}

function openNewNotifierDialog() {
  editingNotifierId.value = null
  notifierForm.value = {
    id: null,
    name: 'Telegram Bot',
    type: 'telegram',
    bot_token: '',
    chat_ids: '',
    use_proxy: false
  }
  notifierDialog.value = true
}

function editNotifier(notifier: NotifierConfig) {
  editingNotifierId.value = notifier.id ?? null
  notifierForm.value = {
    id: notifier.id ?? null,
    name: notifier.name,
    type: notifier.type,
    bot_token: '',
    chat_ids: notifier.chat_ids,
    use_proxy: notifier.use_proxy
  }
  notifierDialog.value = true
}

async function testNotifier() {
  notifierTesting.value = true
  try {
    const result = await api<TestResponse>('/api/settings/notifiers/test', {
      method: 'POST',
      body: JSON.stringify(notifierForm.value)
    })
    notify(result.message, result.ok ? 'success' : 'error')
  } catch (error) {
    notify(error instanceof Error ? error.message : '通知测试失败', 'error')
  } finally {
    notifierTesting.value = false
  }
}

async function saveNotifier() {
  const editing = Boolean(editingNotifierId.value)
  const notifier = await api<NotifierConfig>(
    editing ? `/api/settings/notifiers/${editingNotifierId.value}` : '/api/settings/notifiers',
    {
      method: editing ? 'PUT' : 'POST',
      body: JSON.stringify(notifierForm.value)
    }
  )
  if (editing) {
    notifiers.value = notifiers.value.map((item) => (item.id === notifier.id ? notifier : item))
  } else {
    notifiers.value.push(notifier)
  }
  notifierDialog.value = false
  notify('通知已保存')
}

async function loadSystemSettings() {
  systemForm.value = await api<SystemSettings>('/api/settings/system')
}

async function saveSystemSettings() {
  systemSaving.value = true
  try {
    systemForm.value = await api<SystemSettings>('/api/settings/system', {
      method: 'PUT',
      body: JSON.stringify(systemForm.value)
    })
    notify('系统设置已保存')
  } catch (error) {
    notify(error instanceof Error ? error.message : '绯荤粺设置保存澶辫触', 'error')
  } finally {
    systemSaving.value = false
  }
}

function progressPercent(value: number) {
  return Math.round(value * 100)
}

function formatSize(value?: number | null) {
  if (!value) return '-'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = value
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex += 1
  }
  return `${size.toFixed(unitIndex === 0 ? 0 : 2)} ${units[unitIndex]}`
}

function formatTime(value: string) {
  return new Date(value).toLocaleString()
}

function logColor(level: string) {
  if (level === 'ERROR') return 'error'
  if (level === 'WARNING') return 'warning'
  if (level === 'INFO') return 'info'
  return 'secondary'
}

onMounted(async () => {
  try {
    await api('/api/sites')
    loggedIn.value = true
    await loadInitialData()
  } catch {
    loggedIn.value = false
  }
})

onUnmounted(() => {
  window.clearInterval(logTimer)
})
</script>

<template>
  <v-app>
    <main v-if="!loggedIn" class="login-screen">
      <v-card class="login-card">
        <v-card-title class="text-h5 font-weight-bold">MusicPilot</v-card-title>
        <v-card-text>
          <v-form @submit.prevent="login">
            <v-text-field v-model="loginForm.username" label="用户名" autocomplete="username" />
            <v-text-field
              v-model="loginForm.password"
              label="密码"
              type="password"
              autocomplete="current-password"
              @keyup.enter="login"
            />
            <v-btn block color="primary" size="large" :loading="loginLoading" @click="login">
              登录
            </v-btn>
          </v-form>
        </v-card-text>
      </v-card>
    </main>

    <template v-else>
      <v-navigation-drawer v-model="drawer" width="244">
        <div class="brand-block">
          <div class="brand-title">MusicPilot</div>
          <div class="brand-subtitle">音乐库自动化</div>
        </div>
        <v-list nav density="compact">
          <v-list-item
            v-for="item in navItems"
            :key="item.value"
            :active="activePage === item.value"
            :prepend-icon="item.icon"
            :title="item.title"
            rounded="lg"
            @click="activePage = item.value"
          />
        </v-list>
      </v-navigation-drawer>

      <v-app-bar height="64" flat border>
        <v-app-bar-nav-icon @click="drawer = !drawer" />
        <v-toolbar-title>{{ pageTitle }}</v-toolbar-title>
        <v-spacer />
        <v-btn prepend-icon="mdi-text-box-search-outline" variant="tonal" @click="activePage = 'logs'">
          日志
        </v-btn>
      </v-app-bar>

      <v-main>
        <div class="content">
          <section v-if="activePage === 'search'" class="page-stack">
            <div class="toolbar-row">
              <v-btn color="primary" prepend-icon="mdi-magnify" @click="searchDialog = true">
                搜索
              </v-btn>
              <v-chip v-if="searchLoading" color="info" variant="tonal">
                正在返回：{{ activeSearchSource || '站点' }}
              </v-chip>
            </div>

            <v-card class="search-panel">
              <div v-if="!pagedSearchResults.length" class="empty-cell">暂无搜索结果</div>
              <div v-else class="result-card-grid">
                <article
                  v-for="row in pagedSearchResults"
                  :key="row.download_url"
                  class="result-card"
                  @click="openDownloadConfirm(row)"
                >
                  <div class="result-card-body">
                    <div class="result-card-head">
                      <h3>{{ row.title }}</h3>
                    </div>
                    <div class="result-card-source">
                      <v-icon icon="mdi-server-network" size="22" />
                      <span>{{ row.source }}</span>
                    </div>
                    <p class="result-card-subtitle">{{ row.subtitle || row.title }}</p>
                    <div class="result-card-meta">
                      <span><v-icon icon="mdi-clock-outline" size="16" />{{ row.published_at || '-' }}</span>
                      <span class="seeders"><v-icon icon="mdi-arrow-up" size="18" />{{ row.seeders }}</span>
                      <span class="leechers"><v-icon icon="mdi-arrow-down" size="18" />{{ row.leechers || 0 }}</span>
                    </div>
                    <div class="result-card-tags">
                      <v-chip v-if="row.promotion" color="success" size="small" variant="flat">
                        {{ row.promotion }}
                      </v-chip>
                      <v-chip color="secondary" size="small" variant="tonal">{{ row.source }}</v-chip>
                    </div>
                  </div>
                  <div class="result-card-footer">
                    <v-chip color="primary" size="small" variant="flat">
                      {{ formatSize(row.size_bytes) }}
                    </v-chip>
                    <v-btn
                      icon="mdi-information-outline"
                      color="primary"
                      variant="text"
                      size="small"
                      title="查看原站点"
                      @click.stop="viewResult(row)"
                    />
                  </div>
                </article>
              </div>
              <div class="pagination-row">
                <v-select
                  v-model="searchPageSize"
                  :items="[10, 20, 50, 100]"
                  label="每页"
                  hide-details
                  class="page-size"
                />
                <v-pagination
                  v-model="searchPage"
                  :length="Math.max(1, Math.ceil(searchResults.length / searchPageSize))"
                  density="comfortable"
                />
              </div>
            </v-card>
          </section>

          <section v-if="activePage === 'downloads'" class="page-stack">
            <div class="toolbar-row">
              <v-btn prepend-icon="mdi-refresh" variant="tonal" @click="loadDownloads">刷新</v-btn>
            </div>
            <v-card>
              <v-table>
                <thead>
                  <tr>
                    <th>名称</th>
                    <th>状态</th>
                    <th>进度</th>
                    <th>保存路径</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="!downloads.length"><td colspan="4" class="empty-cell">暂无下载任务</td></tr>
                  <tr v-for="row in downloads" :key="row.torrent_hash">
                    <td>{{ row.name }}</td>
                    <td><v-chip size="small" variant="tonal">{{ row.state }}</v-chip></td>
                    <td><v-progress-linear :model-value="progressPercent(row.progress)" height="8" rounded /></td>
                    <td class="path-cell">{{ row.save_path || '-' }}</td>
                  </tr>
                </tbody>
              </v-table>
            </v-card>
          </section>

          <section v-if="activePage === 'media'" class="page-stack">
            <div class="toolbar-row">
              <v-btn prepend-icon="mdi-refresh" variant="tonal" @click="loadMedia">刷新</v-btn>
            </div>
            <v-card>
              <v-table>
                <thead>
                  <tr>
                    <th>标题</th>
                    <th>艺人</th>
                    <th>专辑</th>
                    <th>入库路径</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="!mediaFiles.length"><td colspan="4" class="empty-cell">暂无整理记录</td></tr>
                  <tr v-for="row in mediaFiles" :key="row.id">
                    <td>{{ row.title || '-' }}</td>
                    <td>{{ row.artist || '-' }}</td>
                    <td>{{ row.album || '-' }}</td>
                    <td class="path-cell">{{ row.library_path }}</td>
                  </tr>
                </tbody>
              </v-table>
            </v-card>
          </section>

          <section v-if="activePage === 'sites'" class="page-stack">
            <div class="toolbar-row">
              <v-btn color="primary" prepend-icon="mdi-plus" @click="openNewSiteDialog">新增站点</v-btn>
            </div>
            <div class="card-grid">
              <v-card v-for="site in sites" :key="site.id || site.name" class="config-card" @click="editSite(site)">
                <v-card-title>{{ site.name }}</v-card-title>
                <v-card-text>
                  <div class="muted">{{ site.base_url }}</div>
                  <v-chip size="small" variant="tonal">{{ site.max_concurrency }} 并发</v-chip>
                </v-card-text>
              </v-card>
            </div>
          </section>

          <section v-if="activePage === 'logs'" class="page-stack">
            <v-card>
              <v-card-text class="log-toolbar">
                <v-select
                  v-model="logLevel"
                  :items="['ALL', 'INFO', 'WARNING', 'ERROR']"
                  label="级别"
                  hide-details
                  class="log-level"
                />
                <v-text-field
                  v-model="logQuery"
                  label="搜索日志"
                  prepend-inner-icon="mdi-magnify"
                  hide-details
                />
                <v-btn
                  :prepend-icon="logPaused ? 'mdi-play' : 'mdi-pause'"
                  variant="tonal"
                  @click="logPaused = !logPaused"
                >
                  {{ logPaused ? '继续' : '暂停' }}
                </v-btn>
                <v-btn prepend-icon="mdi-refresh" :loading="logsLoading" variant="tonal" @click="loadLogs">
                  刷新
                </v-btn>
              </v-card-text>
              <div class="log-list">
                <div v-if="!filteredLogs.length" class="empty-cell">暂无日志</div>
                <div v-for="entry in filteredLogs" :key="`${entry.timestamp}-${entry.message}`" class="log-line">
                  <span class="log-time">{{ formatTime(entry.timestamp) }}</span>
                  <v-chip :color="logColor(entry.level)" size="x-small" variant="tonal">{{ entry.level }}</v-chip>
                  <span class="log-category">{{ entry.category }}</span>
                  <span class="log-message">{{ entry.message }}</span>
                </div>
              </div>
            </v-card>
          </section>

          <section v-if="activePage === 'settings'" class="page-stack">
            <v-tabs v-model="settingsTab" color="primary">
              <v-tab value="downloaders">下载器</v-tab>
              <v-tab value="notifiers">通知</v-tab>
              <v-tab value="system">系统设置</v-tab>
            </v-tabs>

            <v-window v-model="settingsTab">
              <v-window-item value="downloaders">
                <div class="toolbar-row">
                  <v-btn color="primary" prepend-icon="mdi-plus" @click="openNewDownloaderDialog">新增下载器</v-btn>
                </div>
                <div class="card-grid">
                  <v-card
                    v-for="downloader in downloaders"
                    :key="downloader.id || downloader.base_url"
                    class="config-card"
                    @click="editDownloader(downloader)"
                  >
                    <v-card-title>{{ downloader.name }}</v-card-title>
                    <v-card-text>
                      <div class="muted">{{ downloader.base_url }}</div>
                      <div class="muted">{{ downloader.download_path || '未设置下载目录' }}</div>
                      <v-chip v-if="downloader.is_default" color="success" size="small" variant="tonal">默认</v-chip>
                    </v-card-text>
                  </v-card>
                </div>
              </v-window-item>

              <v-window-item value="notifiers">
                <div class="toolbar-row">
                  <v-btn color="primary" prepend-icon="mdi-plus" @click="openNewNotifierDialog">新增通知</v-btn>
                </div>
                <div class="card-grid">
                  <v-card
                    v-for="notifier in notifiers"
                    :key="notifier.id || notifier.name"
                    class="config-card"
                    @click="editNotifier(notifier)"
                  >
                    <v-card-title>{{ notifier.name }}</v-card-title>
                    <v-card-text>
                      <v-chip size="small" variant="tonal">{{ notifier.type }}</v-chip>
                      <v-chip v-if="notifier.use_proxy" color="warning" size="small" variant="tonal">代理</v-chip>
                      <div class="muted">{{ notifier.chat_ids || '未指定会话' }}</div>
                    </v-card-text>
                  </v-card>
                </div>
              </v-window-item>

              <v-window-item value="system">
                <v-card class="settings-card">
                  <v-card-title>网络设置</v-card-title>
                  <v-card-text class="settings-grid">
                    <v-text-field v-model="systemForm.proxy.host" label="代理地址" placeholder="127.0.0.1 或 http://127.0.0.1:7890" />
                    <v-text-field v-model.number="systemForm.proxy.port" label="端口" type="number" />
                    <v-text-field v-model="systemForm.proxy.username" label="用户名" />
                    <v-text-field v-model="systemForm.proxy.password" label="密码" type="password" />
                  </v-card-text>
                  <v-card-actions>
                    <v-spacer />
                    <v-btn color="primary" :loading="systemSaving" @click="saveSystemSettings">
                      保存系统设置
                    </v-btn>
                  </v-card-actions>
                </v-card>
              </v-window-item>
            </v-window>
          </section>
        </div>
      </v-main>
    </template>

    <v-dialog v-model="searchDialog" max-width="460">
      <v-card title="搜索">
        <v-card-text>
          <v-text-field v-model="searchText" label="搜索文本" autofocus @keyup.enter="runSearch" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="searchDialog = false">取消</v-btn>
          <v-btn color="primary" :loading="searchLoading" @click="runSearch">搜索</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog
      :model-value="Boolean(pendingDownload)"
      max-width="560"
      @update:model-value="(value) => { if (!value) pendingDownload = null }"
    >
      <v-card class="download-confirm-card">
        <v-card-title class="download-confirm-title">
          <v-icon icon="mdi-monitor-arrow-down-variant" size="36" />
          <div>
            <div>确认下载</div>
            <div class="download-confirm-subtitle">
              {{ pendingDownload?.source }} - {{ pendingDownload?.title }}
            </div>
          </div>
        </v-card-title>
        <v-card-text v-if="pendingDownload" class="download-confirm-body">
          <div class="confirm-row">
            <v-icon icon="mdi-web" size="34" />
            <div>
              <div class="confirm-main-text">{{ pendingDownload.subtitle || pendingDownload.title }}</div>
              <div class="confirm-seeders">
                <span class="seeders"><v-icon icon="mdi-arrow-up" size="18" />{{ pendingDownload.seeders }}</span>
                <span class="leechers"><v-icon icon="mdi-arrow-down" size="18" />{{ pendingDownload.leechers || 0 }}</span>
              </div>
            </div>
          </div>
          <div class="confirm-row">
            <v-icon icon="mdi-database" size="34" />
            <v-chip size="large" variant="tonal">{{ formatSize(pendingDownload.size_bytes) }}</v-chip>
          </div>
          <div class="confirm-row muted">
            <v-icon icon="mdi-clock-outline" size="28" />
            <span>{{ pendingDownload.published_at || '发布时间未知' }}</span>
            <v-chip v-if="pendingDownload.promotion" color="success" size="small" variant="flat">
              {{ pendingDownload.promotion }}
            </v-chip>
          </div>
        </v-card-text>
        <v-card-actions class="download-confirm-actions">
          <v-btn variant="text" @click="pendingDownload = null">取消</v-btn>
          <v-btn color="primary" prepend-icon="mdi-download" size="large" @click="confirmDownload">
            开始下载
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="siteDialog" max-width="820">
      <v-card :title="editingSiteId ? '编辑站点' : '新增站点'">
        <v-card-text class="dialog-stack">
          <v-text-field v-model="siteForm.name" label="站点名称" />
          <v-text-field v-model="siteForm.base_url" label="站点地址" />
          <v-textarea v-model="siteForm.cookie" label="Cookie" rows="3" />
          <v-text-field v-model="siteForm.user_agent" label="User-Agent" />
          <v-text-field v-model.number="siteForm.max_concurrency" label="最大并发" type="number" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="siteDialog = false">取消</v-btn>
          <v-btn :loading="siteTesting" variant="tonal" @click="testSite">测试</v-btn>
          <v-btn color="primary" @click="saveSite">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="downloaderDialog" max-width="560">
      <v-card :title="editingDownloaderId ? '编辑下载器' : '新增下载器'">
        <v-card-text class="dialog-stack">
          <v-select v-model="downloaderForm.type" :items="['qbittorrent']" label="类型" />
          <v-text-field v-model="downloaderForm.name" label="名称" />
          <v-text-field v-model="downloaderForm.base_url" label="地址" />
          <v-text-field v-model="downloaderForm.username" label="用户名" />
          <v-text-field
            v-model="downloaderForm.password"
            label="密码"
            type="password"
            :placeholder="editingDownloaderId ? '留空则保持原密码' : ''"
          />
          <v-text-field v-model="downloaderForm.download_path" label="下载目录" placeholder="/downloads/music" />
          <v-switch v-model="downloaderForm.is_default" color="primary" label="设为默认" hide-details />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="downloaderDialog = false">取消</v-btn>
          <v-btn :loading="downloaderTesting" variant="tonal" @click="testDownloader">测试</v-btn>
          <v-btn color="primary" @click="saveDownloader">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="notifierDialog" max-width="560">
      <v-card :title="editingNotifierId ? '编辑通知' : '新增通知'">
        <v-card-text class="dialog-stack">
          <v-select v-model="notifierForm.type" :items="['telegram']" label="类型" />
          <v-text-field v-model="notifierForm.name" label="名称" />
          <v-text-field
            v-model="notifierForm.bot_token"
            label="Bot Token"
            :placeholder="editingNotifierId ? '留空则保持原 Token' : ''"
          />
          <v-text-field v-model="notifierForm.chat_ids" label="Chat IDs" />
          <v-switch v-model="notifierForm.use_proxy" color="primary" label="使用系统代理" hide-details />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="notifierDialog = false">取消</v-btn>
          <v-btn :loading="notifierTesting" variant="tonal" @click="testNotifier">测试</v-btn>
          <v-btn color="primary" @click="saveNotifier">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-snackbar v-model="snackbar.show" :color="snackbar.color" location="top right">
      {{ snackbar.text }}
    </v-snackbar>
  </v-app>
</template>

