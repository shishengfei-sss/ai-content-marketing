<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { ArrowDown, Clock, Promotion, RefreshRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { contentApi, agentApi, llmApi, templatesApi, wechatApi, assistantsApi } from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

const platform = ref('wechat')
const scene = ref('')
const contentFormat = ref('article')
const inputText = ref('')
const generating = ref(false)
const proposing = ref(false)
const messagesEndRef = ref(null)
const modelTag = ref('未配置模型')
const wechatSettings = ref({ bound: false, can_auto_publish: false, account_type: 'service' })
const pendingRequest = ref(null)

const platformMap = {
  wechat: '公众号',
  xhs: '小红书',
  douyin: '抖音',
}

const formatMap = {
  article: '图文',
  note: '笔记',
  video_script: '视频脚本',
}

function defaultContentFormat(p) {
  if (p === 'xhs') return 'note'
  if (p === 'douyin') return 'video_script'
  return 'article'
}

function formatOptionsForPlatform(p) {
  if (p === 'wechat') {
    return [
      { value: 'article', label: '图文' },
      { value: 'video_script', label: '视频脚本' },
    ]
  }
  if (p === 'xhs') {
    return [
      { value: 'note', label: '笔记' },
      { value: 'video_script', label: '视频脚本' },
    ]
  }
  return [{ value: 'video_script', label: '视频脚本' }]
}

function resolveContentFormat(platform, currentFormat) {
  const options = formatOptionsForPlatform(platform)
  if (currentFormat && options.some((o) => o.value === currentFormat)) {
    return currentFormat
  }
  return defaultContentFormat(platform)
}

const formatOptions = computed(() => formatOptionsForPlatform(platform.value || 'wechat'))

const scenes = ref([
  { value: 'tax_deadline_reminder', label: '报税截止提醒' },
  { value: 'bookkeeping_intro', label: '代理记账介绍' },
])

const filteredScenes = ref([])

function updateFilteredScenes() {
  if (!platform.value) {
    filteredScenes.value = scenes.value
    return
  }
  filteredScenes.value = scenes.value.filter((s) => s.platform === platform.value || !s.platform)
}

const quickStarts = ref([
  { text: '写一篇公众号报税提醒', platform: 'wechat', scene: 'tax_deadline_reminder' },
  { text: '小红书代理记账服务介绍', platform: 'xhs', scene: 'bookkeeping_intro' },
  { text: '抖音新公司注册指南脚本', platform: 'douyin', scene: 'small_company_register' },
  { text: '税务处罚案例故事（公众号）', platform: 'wechat', scene: 'case_penalty_story' },
])

function buildQuickStartsFromTemplates(templates) {
  const platformOrder = ['wechat', 'xhs', 'douyin']
  const picked = []
  for (const p of platformOrder) {
    const t = templates.find((x) => x.platform === p)
    if (t) {
      picked.push({ text: t.name, platform: t.platform, scene: t.scene })
    }
  }
  for (const t of templates) {
    if (picked.length >= 4) break
    if (!picked.some((x) => x.scene === t.scene && x.platform === t.platform)) {
      picked.push({ text: t.name, platform: t.platform, scene: t.scene })
    }
  }
  return picked.slice(0, 4)
}

function syncQuickStarts() {
  const quickMsg = messages.value.find((m) => m.role === 'assistant' && m.type === 'quick')
  if (quickMsg) quickMsg.items = quickStarts.value
}

const publishingId = ref(null)
const assistants = ref([])
const industryCode = ref('finance')
const llmSource = ref('platform')
const llmQuota = ref({
  remaining: 100,
  quota_limit: 100,
  used_count: 0,
  has_tenant_key: false,
  platform_available: true,
})

const selectedAssistant = computed(
  () => assistants.value.find((a) => a.code === industryCode.value) || null,
)

const defaultWelcome =
  '您好，我是智营 AI 创作助手。直接告诉我您想创作什么，或点击下方快捷选题开始——我会帮您生成符合行业合规要求的营销内容。'

const messages = ref([
  {
    role: 'assistant',
    type: 'text',
    content: defaultWelcome,
  },
  {
    role: 'assistant',
    type: 'quick',
    items: quickStarts.value,
  },
])

const apiBase = import.meta.env.VITE_API_BASE_URL || ''
const agentFallback = import.meta.env.VITE_AGENT_FALLBACK === '1'
const AGENT_SESSION_KEY = 'agent_session_id'
const agentSessionId = ref(localStorage.getItem(AGENT_SESSION_KEY) || '')
const sessionDrawerVisible = ref(false)
const sessionHistory = ref([])

function formatSessionTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function mapApiMessagesToUi(apiMessages) {
  return (apiMessages || [])
    .filter((m) => m.role === 'user' || m.role === 'assistant')
    .map((m) => ({
      role: m.role,
      type: 'text',
      content: m.content || '',
    }))
}

async function loadSessionHistory() {
  const { data } = await agentApi.listSessions({ limit: 20 })
  sessionHistory.value = data || []
}

async function openSessionHistory() {
  sessionDrawerVisible.value = true
  try {
    await loadSessionHistory()
  } catch {
    ElMessage.error('加载历史会话失败')
  }
}

async function switchToSession(session) {
  if (!session?.id) return
  agentSessionId.value = session.id
  localStorage.setItem(AGENT_SESSION_KEY, session.id)
  sessionDrawerVisible.value = false
  try {
    const { data } = await agentApi.getMessages(session.id)
    const mapped = mapApiMessagesToUi(data)
    messages.value =
      mapped.length > 0
        ? mapped
        : [
            {
              role: 'assistant',
              type: 'text',
              content: `已打开会话「${session.title || '未命名'}」，继续输入即可。`,
            },
          ]
    await scrollToBottom()
  } catch {
    ElMessage.error('加载会话消息失败')
  }
}

async function createAgentSession() {
  const { data } = await agentApi.createSession({
    industry_code: industryCode.value || 'finance',
    title: '营销创作',
  })
  agentSessionId.value = data.id
  localStorage.setItem(AGENT_SESSION_KEY, data.id)
  return data.id
}

async function ensureAgentSession() {
  if (agentSessionId.value) return agentSessionId.value
  return createAgentSession()
}

function pushAgentChatResult(data, requestTopic) {
  if (data.action === 'clarify') {
    messages.value.push({
      role: 'assistant',
      type: 'text',
      content: data.clarify_question || data.assistant_message,
    })
    return
  }
  if (data.action === 'proposals' && data.proposals?.length) {
    messages.value.push({
      role: 'assistant',
      type: 'proposals',
      proposals: data.proposals,
      requestTopic: requestTopic || '',
    })
    return
  }
  if (data.action === 'generate' && data.content) {
    const c = data.content
    const usePlatform = c.platform || platform.value || 'wechat'
    messages.value.push({
      role: 'assistant',
      type: 'result',
      content: c.body,
      contentId: c.id,
      status: c.status,
      meta: {
        platformCode: usePlatform,
        platform: platformMap[usePlatform] || usePlatform,
        contentFormat: c.content_format,
        formatLabel: formatMap[c.content_format] || c.content_format,
        scene: scenes.value.find((s) => s.value === c.scene)?.label || '自定义',
        model: `${c.llm_provider} · ${c.llm_model}`,
      },
    })
    modelTag.value = `${c.llm_provider} · ${c.llm_model}`
    return
  }
  messages.value.push({
    role: 'assistant',
    type: 'text',
    content: data.assistant_message || '请补充更多信息后继续创作。',
  })
}

async function agentChat(message, { selectedProposalIndex = null } = {}) {
  const sessionId = await ensureAgentSession()
  const body = {
    message,
    llm_source: llmSource.value,
  }
  if (selectedProposalIndex !== null) {
    body.selected_proposal_index = selectedProposalIndex
  }
  const { data } = await agentApi.chat(sessionId, body)
  return data
}

async function loadTemplatesForAssistant(code) {
  try {
    const { data } = await templatesApi.list({ industry_code: code })
    scenes.value = data.map((t) => ({
      value: t.scene,
      label: t.name,
      platform: t.platform,
    }))
    if (data.length) {
      quickStarts.value = buildQuickStartsFromTemplates(data)
      syncQuickStarts()
    }
    updateFilteredScenes()
  } catch {
    /* keep defaults */
  }
}

function syncWelcomeMessage() {
  const welcome = selectedAssistant.value?.welcome_message || defaultWelcome
  const first = messages.value.find((m) => m.role === 'assistant' && m.type === 'text')
  if (first) first.content = welcome
}

async function loadAssistants() {
  try {
    const { data } = await assistantsApi.list()
    assistants.value = data
    const tenantCode = auth.user?.tenant?.industry_code
    if (tenantCode && data.some((a) => a.code === tenantCode)) {
      industryCode.value = tenantCode
    } else if (data.length) {
      industryCode.value = data[0].code
    }
    syncWelcomeMessage()
    await loadTemplatesForAssistant(industryCode.value)
  } catch {
    await loadTemplatesForAssistant('finance')
  }
}

async function loadLlmQuota() {
  try {
    const { data } = await llmApi.getQuota()
    llmQuota.value = data
    if (llmSource.value === 'platform') {
      if (data.remaining <= 0 && data.has_tenant_key) {
        llmSource.value = 'tenant'
      } else if (!data.platform_available && data.has_tenant_key) {
        llmSource.value = 'tenant'
      }
    }
  } catch {
    /* ignore */
  }
}

function pickLlmSource(source) {
  if (source === 'platform' && (llmQuota.value.remaining <= 0 || !llmQuota.value.platform_available)) {
    ElMessage.warning(
      llmQuota.value.remaining <= 0
        ? '平台免费额度已用完，请使用我的 API Key'
        : '平台 AI 未配置，请使用我的 API Key 或联系管理员',
    )
    return
  }
  if (source === 'tenant' && !llmQuota.value.has_tenant_key) {
    ElMessage.warning('请先在设置中配置我的 API Key')
    return
  }
  llmSource.value = source
}

function pickAssistant(code) {
  industryCode.value = code
  scene.value = ''
  syncWelcomeMessage()
  loadTemplatesForAssistant(code)
}

onMounted(async () => {
  if (auth.isLoggedIn && !auth.user) await auth.fetchMe()
  try {
    const { data } = await llmApi.get()
    modelTag.value = `${data.provider} · ${data.model}`
  } catch {
    modelTag.value = '未配置模型'
  }
  try {
    const { data } = await wechatApi.get()
    wechatSettings.value = data
  } catch {
    /* ignore */
  }
  await loadAssistants()
  await loadLlmQuota()
  await ensureAgentSession()
})

async function scrollToBottom() {
  await nextTick()
  messagesEndRef.value?.scrollIntoView({ behavior: 'smooth' })
}

function pickPlatform(p) {
  platform.value = p
  contentFormat.value = resolveContentFormat(p, contentFormat.value)
  updateFilteredScenes()
  if (scene.value && !filteredScenes.value.some((s) => s.value === scene.value)) {
    scene.value = ''
  }
}

function pickContentFormat(f) {
  contentFormat.value = f
}

function handleQuickStart(item) {
  platform.value = item.platform
  scene.value = item.scene
  contentFormat.value = defaultContentFormat(item.platform)
  inputText.value = item.text
  handleSend()
}

function buildUserPrompt(text) {
  const parts = [text]
  if (platform.value) parts.unshift(`[平台：${platformMap[platform.value]}]`)
  if (scene.value) {
    const label = scenes.value.find((s) => s.value === scene.value)?.label
    if (label) parts.unshift(`[场景：${label}]`)
  }
  return parts.join(' ')
}

function buildGeneratePayload(topic, selectedProposal = null) {
  const usePlatform = platform.value || 'wechat'
  const useScene =
    scene.value ||
    filteredScenes.value[0]?.value ||
    quickStarts.value[0]?.scene ||
    'tax_deadline_reminder'
  const useFormat = contentFormat.value || defaultContentFormat(usePlatform)
  return {
    industry_code: industryCode.value || 'finance',
    platform: usePlatform,
    scene: useScene,
    topic,
    content_format: useFormat,
    llm_source: llmSource.value,
    selected_proposal: selectedProposal,
  }
}

async function fetchProposals(topic) {
  const payload = buildGeneratePayload(topic)
  pendingRequest.value = { topic, ...payload }
  try {
    const data = await agentChat(buildUserPrompt(topic))
    if (data.action === 'proposals' && data.proposals?.length) {
      return data.proposals
    }
    pushAgentChatResult(data, topic)
    return null
  } catch (e) {
    if (!agentFallback) throw e
    const { data } = await contentApi.proposals(payload)
    return data.proposals
  }
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || generating.value || proposing.value) return

  messages.value = messages.value.filter((m) => m.type !== 'quick')
  messages.value.push({ role: 'user', type: 'text', content: buildUserPrompt(text) })
  inputText.value = ''
  proposing.value = true
  scrollToBottom()

  try {
    const data = await agentChat(buildUserPrompt(text))
    pushAgentChatResult(data, text)
  } catch (e) {
    if (agentFallback) {
      try {
        const proposals = await fetchProposals(text)
        if (proposals?.length) {
          messages.value.push({
            role: 'assistant',
            type: 'proposals',
            proposals,
            requestTopic: text,
          })
        }
      } catch (err) {
        ElMessage.error(err.message || '方案生成失败')
        messages.value.push({
          role: 'assistant',
          type: 'text',
          content: `方案生成失败：${err.message || '请检查 AI 模型配置'}`,
        })
      }
    } else {
      ElMessage.error(e.message || '方案生成失败')
      messages.value.push({
        role: 'assistant',
        type: 'text',
        content: `方案生成失败：${e.message || '请检查 AI 模型配置'}`,
      })
    }
  } finally {
    proposing.value = false
    await scrollToBottom()
  }
}

async function handleSelectProposal(proposal, requestTopic, msg) {
  if (generating.value) return
  generating.value = true
  scrollToBottom()
  const proposalIndex = msg?.proposals?.findIndex((p) => p.title === proposal.title) ?? 0
  try {
    const data = await agentChat('生成正文', { selectedProposalIndex: proposalIndex >= 0 ? proposalIndex : 0 })
    pushAgentChatResult(data, requestTopic)
    if (data.action === 'generate' && llmSource.value === 'platform') await loadLlmQuota()
  } catch (e) {
    if (agentFallback) {
      try {
        const payload = buildGeneratePayload(requestTopic, proposal)
        const { data } = await contentApi.generate(payload)
        const usePlatform = payload.platform
        messages.value.push({
          role: 'assistant',
          type: 'result',
          content: data.body,
          contentId: data.id,
          status: data.status,
          meta: {
            platformCode: usePlatform,
            platform: platformMap[usePlatform] || usePlatform,
            contentFormat: data.content_format,
            formatLabel: formatMap[data.content_format] || data.content_format,
            scene: scenes.value.find((s) => s.value === payload.scene)?.label || '自定义',
            model: `${data.llm_provider} · ${data.llm_model}`,
          },
        })
        modelTag.value = `${data.llm_provider} · ${data.llm_model}`
        if (llmSource.value === 'platform') await loadLlmQuota()
      } catch (err) {
        ElMessage.error(err.message || '生成失败')
        messages.value.push({
          role: 'assistant',
          type: 'text',
          content: `生成失败：${err.message || '请检查 AI 模型配置'}`,
        })
      }
    } else {
      ElMessage.error(e.message || '生成失败')
      messages.value.push({
        role: 'assistant',
        type: 'text',
        content: `生成失败：${e.message || '请检查 AI 模型配置'}`,
      })
    }
  } finally {
    generating.value = false
    await scrollToBottom()
  }
}

async function handleRefreshProposals(msg) {
  if (proposing.value || !msg.requestTopic) return
  proposing.value = true
  try {
    const data = await agentChat(buildUserPrompt(msg.requestTopic))
    if (data.action === 'proposals' && data.proposals?.length) {
      msg.proposals = data.proposals
      ElMessage.success('已刷新方案')
    } else {
      pushAgentChatResult(data, msg.requestTopic)
    }
  } catch (e) {
    if (agentFallback) {
      msg.proposals = await fetchProposals(msg.requestTopic)
      ElMessage.success('已刷新方案')
    } else {
      ElMessage.error(e.message || '刷新失败')
    }
  } finally {
    proposing.value = false
  }
}

function canAutoPublish(msg) {
  return (
    msg.meta?.platformCode === 'wechat' &&
    msg.meta?.contentFormat === 'article' &&
    wechatSettings.value.can_auto_publish
  )
}

function isVideoScript(msg) {
  return msg.meta?.contentFormat === 'video_script'
}

function canExportXhs(msg) {
  return msg.meta?.platformCode === 'xhs' && msg.meta?.contentFormat === 'note'
}

function canExportScript(msg) {
  return isVideoScript(msg)
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function handleNewChat() {
  platform.value = ''
  scene.value = ''
  contentFormat.value = 'article'
  inputText.value = ''
  generating.value = false
  proposing.value = false
  pendingRequest.value = null
  agentSessionId.value = ''
  localStorage.removeItem(AGENT_SESSION_KEY)
  messages.value = [
    {
      role: 'assistant',
      type: 'text',
      content:
        '已开启新对话。告诉我您想创作的内容，或选择快捷选题开始。',
    },
    {
      role: 'assistant',
      type: 'quick',
      items: quickStarts.value,
    },
  ]
  createAgentSession().catch(() => {})
}

async function handlePublish(msg) {
  if (!msg.contentId) return
  if (msg.status !== 'draft' && msg.status !== 'failed') {
    ElMessage.info('该内容已处理')
    return
  }
  if (msg.meta?.platformCode !== 'wechat') {
    ElMessage.warning('当前平台请使用导出功能')
    return
  }
  publishingId.value = msg.contentId
  try {
    const { data } = await contentApi.publish(msg.contentId)
    msg.status = data.status
    ElMessage.success('Mock 发布成功')
    if (data.preview_url) {
      window.open(`${apiBase}${data.preview_url}`, '_blank')
    }
  } catch (e) {
    ElMessage.error(e.message || '发布失败，请先在设置中绑定公众号')
  } finally {
    publishingId.value = null
  }
}

async function handleExport(msg, type) {
  if (!msg.contentId) return
  try {
    let data
    if (type === 'xhs') {
      ;({ data } = await contentApi.exportXhs(msg.contentId))
    } else if (type === 'script') {
      ;({ data } = await contentApi.exportScript(msg.contentId))
    } else {
      ;({ data } = await contentApi.exportDouyin(msg.contentId))
    }
    msg.status = 'exported'
    ElMessage.success('导出成功')
    window.open(`${apiBase}${data.download_url}`, '_blank')
  } catch (e) {
    ElMessage.error(e.message || '导出失败')
  }
}

function isDraft(msg) {
  return !msg.status || msg.status === 'draft' || msg.status === 'failed'
}

function handleCopy(text) {
  navigator.clipboard.writeText(text).then(
    () => ElMessage.success('已复制到剪贴板'),
    () => ElMessage.error('复制失败'),
  )
}
</script>

<template>
  <div class="ai-chat-page">
    <div class="ai-chat-page__card page-card">
      <!-- 顶栏 -->
      <div class="chat-header">
        <el-dropdown
          trigger="click"
          :disabled="assistants.length <= 1"
          @command="pickAssistant"
        >
          <div
            class="assistant-picker"
            :class="{ 'assistant-picker--clickable': assistants.length > 1 }"
          >
            <el-avatar :size="44" class="assistant-picker__avatar">AI</el-avatar>
            <div class="assistant-picker__body">
              <div class="assistant-picker__row">
                <span class="assistant-picker__name">
                  {{ selectedAssistant?.name || '智营 AI 创作助手' }}
                </span>
                <span v-if="assistants.length > 1" class="assistant-picker__badge">切换助手</span>
                <el-icon v-if="assistants.length > 1" class="assistant-picker__arrow"><ArrowDown /></el-icon>
              </div>
              <div class="assistant-picker__desc">
                {{ selectedAssistant?.description || '对话式营销内容创作' }}
              </div>
            </div>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item
                v-for="a in assistants"
                :key="a.code"
                :command="a.code"
                :class="{ 'is-active-assistant': industryCode === a.code }"
              >
                <div class="assistant-option">
                  <span class="assistant-option__name">{{ a.name }}</span>
                  <span v-if="a.description" class="assistant-option__desc">{{ a.description }}</span>
                </div>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <div class="chat-header__right">
          <el-tag type="success" size="small">{{ modelTag }}</el-tag>
          <el-button circle @click="openSessionHistory" title="历史会话">
            <el-icon><Clock /></el-icon>
          </el-button>
          <el-button :icon="RefreshRight" circle @click="handleNewChat" title="新对话" />
        </div>
      </div>

      <el-drawer v-model="sessionDrawerVisible" title="历史会话" size="320px" direction="rtl">
        <div class="session-drawer">
          <el-button type="primary" link @click="handleNewChat(); sessionDrawerVisible = false">
            + 新对话
          </el-button>
          <div
            v-for="s in sessionHistory"
            :key="s.id"
            class="session-item"
            :class="{ 'session-item--active': s.id === agentSessionId }"
            @click="switchToSession(s)"
          >
            <div class="session-item__title">{{ s.title || '未命名会话' }}</div>
            <div class="session-item__time">{{ formatSessionTime(s.updated_at) }}</div>
          </div>
          <el-empty v-if="!sessionHistory.length" description="暂无历史会话" />
        </div>
      </el-drawer>

      <!-- 消息区 -->
      <div class="chat-body">
        <div
          v-for="(msg, idx) in messages"
          :key="idx"
          class="chat-row"
          :class="`chat-row--${msg.role}`"
        >
          <el-avatar
            v-if="msg.role === 'assistant'"
            :size="36"
            style="background: #1677ff; flex-shrink: 0"
          >
            AI
          </el-avatar>

          <div class="chat-row__content">
            <!-- 纯文本 -->
            <div
              v-if="msg.type === 'text'"
              class="bubble"
              :class="msg.role === 'user' ? 'bubble--user' : 'bubble--assistant'"
            >
              {{ msg.content }}
            </div>

            <!-- 快捷选题 -->
            <div v-else-if="msg.type === 'quick'" class="quick-grid">
              <button
                v-for="item in msg.items"
                :key="item.text"
                class="quick-chip"
                @click="handleQuickStart(item)"
              >
                {{ item.text }}
              </button>
            </div>

            <!-- 创作方案 -->
            <div v-else-if="msg.type === 'proposals'" class="proposals-block">
              <div class="proposals-block__title">为您准备了 {{ msg.proposals.length }} 个创作方向，请选择后再生成正文：</div>
              <div
                v-for="(item, pi) in msg.proposals"
                :key="pi"
                class="proposal-card"
              >
                <div class="proposal-card__direction">{{ item.title }}</div>
                <el-button
                  type="primary"
                  size="small"
                  :loading="generating"
                  @click="handleSelectProposal(item, msg.requestTopic, msg)"
                >
                  选这个，生成正文
                </el-button>
              </div>
              <el-button link type="primary" :loading="proposing" @click="handleRefreshProposals(msg)">
                都不满意？换一批方案
              </el-button>
            </div>

            <!-- 生成结果 -->
            <div v-else-if="msg.type === 'result'" class="result-block">
              <div class="result-block__meta">
                <el-tag size="small">{{ msg.meta.platform }}</el-tag>
                <el-tag size="small" type="info">{{ msg.meta.formatLabel || msg.meta.scene }}</el-tag>
              </div>
              <pre class="result-block__text">{{ msg.content }}</pre>
              <div class="result-block__actions">
                <el-button size="small" @click="handleCopy(msg.content)">复制</el-button>
                <el-button
                  v-if="canAutoPublish(msg)"
                  type="primary"
                  size="small"
                  :disabled="!isDraft(msg)"
                  :loading="publishingId === msg.contentId"
                  @click="handlePublish(msg)"
                >
                  {{ msg.status === 'published' ? '已发布' : '立即发布' }}
                </el-button>
                <el-button
                  v-if="canExportXhs(msg)"
                  type="primary"
                  size="small"
                  :disabled="!isDraft(msg) && msg.status !== 'exported'"
                  @click="handleExport(msg, 'xhs')"
                >
                  导出 ZIP
                </el-button>
                <el-button
                  v-if="canExportScript(msg)"
                  type="primary"
                  size="small"
                  :disabled="!isDraft(msg) && msg.status !== 'exported'"
                  @click="handleExport(msg, 'script')"
                >
                  导出脚本
                </el-button>
              </div>
            </div>
          </div>

          <el-avatar
            v-if="msg.role === 'user'"
            :size="36"
            style="background: #52c41a; flex-shrink: 0"
          >
            我
          </el-avatar>
        </div>

        <!-- 打字中 -->
        <div v-if="proposing || generating" class="chat-row chat-row--assistant">
          <el-avatar :size="36" style="background: #1677ff">AI</el-avatar>
          <div class="bubble bubble--assistant bubble--typing">
            <span /><span /><span />
          </div>
        </div>

        <div ref="messagesEndRef" />
      </div>

      <!-- 底部输入区 -->
      <div class="chat-footer">
        <div class="compose-box">
          <div class="compose-meta">
            <div class="meta-track">
              <span class="meta-track__label">AI</span>
              <div class="meta-pills">
                <button
                  type="button"
                  class="meta-pill"
                  :class="{ 'meta-pill--active': llmSource === 'platform' }"
                  :disabled="llmQuota.remaining <= 0 || !llmQuota.platform_available"
                  @click="pickLlmSource('platform')"
                >
                  平台额度 {{ llmQuota.remaining }}/{{ llmQuota.quota_limit }}
                </button>
                <button
                  type="button"
                  class="meta-pill"
                  :class="{ 'meta-pill--active': llmSource === 'tenant' }"
                  :disabled="!llmQuota.has_tenant_key"
                  @click="pickLlmSource('tenant')"
                >
                  我的 Key
                </button>
              </div>
            </div>
            <div class="meta-track">
              <span class="meta-track__label">平台</span>
              <div class="meta-pills">
                <button
                  v-for="(label, key) in platformMap"
                  :key="key"
                  type="button"
                  class="meta-pill"
                  :class="{ 'meta-pill--active': platform === key }"
                  @click="pickPlatform(key)"
                >
                  {{ label }}
                </button>
              </div>
            </div>
            <div class="meta-track">
              <span class="meta-track__label">形态</span>
              <div class="meta-pills">
                <button
                  v-for="f in formatOptions"
                  :key="f.value"
                  type="button"
                  class="meta-pill"
                  :class="{ 'meta-pill--active': contentFormat === f.value }"
                  @click="pickContentFormat(f.value)"
                >
                  {{ f.label }}
                </button>
              </div>
            </div>
            <div class="meta-track meta-track--scene">
              <span class="meta-track__label">场景</span>
              <el-select
                v-model="scene"
                clearable
                filterable
                size="small"
                placeholder="可选"
                class="meta-scene"
              >
                <el-option
                  v-for="s in filteredScenes"
                  :key="s.value"
                  :label="s.label"
                  :value="s.value"
                />
              </el-select>
            </div>
          </div>

          <div class="compose-input">
            <el-input
              v-model="inputText"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 4 }"
              placeholder="描述想创作的内容，Enter 发送…"
              :disabled="generating || proposing"
              @keydown="handleKeydown"
            />
            <el-button
              type="primary"
              class="compose-send"
              :icon="Promotion"
              :loading="generating || proposing"
              :disabled="!inputText.trim() || generating || proposing"
              @click="handleSend"
            >
              发送
            </el-button>
          </div>
        </div>
        <div class="chat-footer__hint">先出 3～5 个方案 · 选定后再生成正文 · 服务号图文可自动发布</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ai-chat-page {
  height: calc(100vh - 120px);
  min-height: 520px;
}

.ai-chat-page__card {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
  background: #fff;
}

.assistant-picker {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px 10px 10px;
  border-radius: 14px;
  border: 1px solid #d6e8ff;
  background: linear-gradient(135deg, #f0f7ff 0%, #fff 60%);
  max-width: min(520px, 100%);
  outline: none;
}

.assistant-picker--clickable {
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.assistant-picker--clickable:hover {
  border-color: #1677ff;
  box-shadow: 0 4px 14px rgba(22, 119, 255, 0.12);
}

.assistant-picker__avatar {
  background: #1677ff !important;
  flex-shrink: 0;
}

.assistant-picker__body {
  min-width: 0;
  flex: 1;
}

.assistant-picker__row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.assistant-picker__name {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.assistant-picker__badge {
  font-size: 12px;
  color: #1677ff;
  background: #e6f4ff;
  border: 1px solid #91caff;
  padding: 2px 10px;
  border-radius: 999px;
  line-height: 1.4;
}

.assistant-picker__arrow {
  color: #1677ff;
  font-size: 14px;
}

.assistant-picker__desc {
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.assistant-option {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-width: 280px;
}

.assistant-option__name {
  font-size: 14px;
  font-weight: 500;
}

.assistant-option__desc {
  font-size: 12px;
  color: var(--color-text-muted);
  line-height: 1.4;
}

:deep(.is-active-assistant) {
  color: var(--color-primary);
  font-weight: 600;
}

.chat-header__right {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
  flex-shrink: 0;
}

.session-drawer {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.session-item {
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--color-border);
  cursor: pointer;
  transition: background 0.15s;
}

.session-item:hover {
  background: #f5f7fa;
}

.session-item--active {
  border-color: #1677ff;
  background: #ecf5ff;
}

.session-item__title {
  font-size: 14px;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.session-item__time {
  font-size: 12px;
  color: #909399;
}

.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.chat-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  max-width: 820px;
}

.chat-row--user {
  margin-left: auto;
  flex-direction: row;
  justify-content: flex-end;
}

.chat-row--user .chat-row__content {
  display: flex;
  justify-content: flex-end;
}

.bubble {
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.65;
  max-width: 100%;
}

.bubble--assistant {
  background: #f5f5f5;
  border-top-left-radius: 4px;
}

.bubble--user {
  background: #e6f4ff;
  border-top-right-radius: 4px;
}

.bubble--typing {
  display: flex;
  gap: 5px;
  padding: 16px 20px;
}

.bubble--typing span {
  width: 8px;
  height: 8px;
  background: var(--color-primary);
  border-radius: 50%;
  animation: blink 1.4s infinite both;
}

.bubble--typing span:nth-child(2) {
  animation-delay: 0.2s;
}

.bubble--typing span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes blink {
  0%,
  80%,
  100% {
    opacity: 0.3;
  }
  40% {
    opacity: 1;
  }
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  max-width: 520px;
}

.quick-chip {
  padding: 12px 16px;
  min-height: 44px;
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  font-size: 13px;
  color: var(--color-text-primary);
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
}

.quick-chip:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: #e6f4ff;
}

.result-block {
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  overflow: hidden;
  width: 100%;
  max-width: 640px;
}

.result-block__meta {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  background: #fafafa;
  border-bottom: 1px solid var(--color-border);
}

.result-block__text {
  padding: 16px;
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.7;
  margin: 0;
}

.result-block__actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--color-border);
  background: #fafafa;
}

.proposals-block {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 640px;
}

.proposals-block__title {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-bottom: 4px;
}

.proposal-card {
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 14px 16px;
  background: #fff;
}

.proposal-card__direction {
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 12px;
  color: var(--color-text-primary);
}

.chat-footer {
  border-top: 1px solid var(--color-border);
  padding: 14px 20px 16px;
  flex-shrink: 0;
  background: #f5f7fa;
}

.compose-box {
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}

.compose-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px 16px;
  padding: 10px 14px;
  background: #fafbfc;
  border-bottom: 1px solid #f0f0f0;
}

.meta-track {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.meta-track--scene {
  flex: 1;
  min-width: 160px;
}

.meta-track__label {
  font-size: 12px;
  color: var(--color-text-muted);
  flex-shrink: 0;
}

.meta-pills {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 3px;
  background: #eef0f3;
  border-radius: 10px;
}

.meta-pill {
  border: none;
  background: transparent;
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
  line-height: 1.4;
}

.meta-pill:hover {
  color: var(--color-primary);
}

.meta-pill--active {
  background: #fff;
  color: #1677ff;
  font-weight: 600;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.meta-scene {
  flex: 1;
  min-width: 140px;
  max-width: 220px;
}

.compose-input {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 12px 14px;
}

.compose-input :deep(.el-textarea__inner) {
  box-shadow: none !important;
  border: none;
  padding: 4px 0;
  resize: none;
  background: transparent;
}

.compose-send {
  flex-shrink: 0;
  min-width: 88px;
  border-radius: 10px;
}

.chat-footer__hint {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-top: 8px;
  text-align: center;
}
</style>
