<template>

  <view class="page">

    <view class="assistant-picker">
      <view class="assistant-picker__avatar">AI</view>
      <view class="assistant-picker__body">
        <view class="assistant-picker__row">
          <text class="assistant-picker__name">{{ advisorName }}</text>
        </view>
        <text class="assistant-picker__desc">{{ advisorDesc }}</text>
      </view>
      <text class="assistant-picker__history" @click.stop="openSessionHistory">历史</text>
    </view>



    <scroll-view scroll-y class="chat-body" :scroll-into-view="scrollInto">

      <view v-for="(msg, idx) in messages" :key="idx" class="msg-row" :class="'msg-row--' + msg.role">

        <view v-if="msg.role === 'assistant'" class="avatar avatar--ai">AI</view>



        <view class="msg-content">

          <view v-if="msg.type === 'text'" class="bubble">{{ msg.content }}</view>



          <view v-else-if="msg.type === 'proposals'" class="proposals">

            <text class="proposals__title">请选择创作方向（{{ msg.proposals.length }} 个）：</text>

            <view v-for="(item, pi) in msg.proposals" :key="pi" class="proposal-card">

              <text class="proposal-card__direction">{{ item.title }}</text>

              <button

                class="btn-primary"

                size="mini"

                :loading="generating"

                @click="handleSelectProposal(item, msg.requestTopic, msg)"

              >

                选这个，生成正文

              </button>

            </view>

            <button class="btn-link" size="mini" :loading="proposing" @click="handleRefreshProposals(msg)">

              换一批方案

            </button>

          </view>



          <view v-else-if="msg.type === 'result'" class="result">

            <view class="result__meta">

              <text class="result__tag">{{ formatLabel(msg.contentFormat) }}</text>

            </view>

            <text class="result__text">{{ msg.content }}</text>

            <view class="result__actions">

              <button class="btn-outline" size="mini" @click="handleCopy(msg.content)">复制</button>

              <button

                v-if="canAutoPublish(msg)"

                class="btn-primary"

                size="mini"

                :disabled="!isDraft(msg)"

                :loading="publishingId === msg.contentId"

                @click="handlePublish(msg)"

              >

                {{ msg.status === 'published' ? '已发布' : '立即发布' }}

              </button>

              <button

                v-if="canExportXhs(msg)"

                class="btn-primary"

                size="mini"

                :disabled="!isDraft(msg)"

                @click="handleExport(msg, 'xhs')"

              >

                导出 ZIP

              </button>

              <button

                v-if="canExportScript(msg)"

                class="btn-primary"

                size="mini"

                :disabled="!isDraft(msg)"

                @click="handleExport(msg, 'script')"

              >

                导出脚本

              </button>

            </view>

          </view>

        </view>



        <view v-if="msg.role === 'user'" class="avatar avatar--me">我</view>

      </view>



      <view v-if="proposing || generating" class="msg-row msg-row--assistant">

        <view class="avatar avatar--ai">AI</view>

        <view class="bubble bubble--typing">{{ proposing ? '正在构思方案...' : '正在撰写正文...' }}</view>

      </view>

      <view id="bottom" />

    </scroll-view>



    <view class="chat-footer">
      <view class="compose-box">
        <view class="compose-meta">
          <view class="meta-track">
            <text class="meta-track__label">AI</text>
            <view class="meta-pills">
              <view
                class="meta-pill"
                :class="{ 'meta-pill--active': llmSource === 'platform' }"
                @click="pickLlmSource('platform')"
              >
                平台 {{ llmQuota.remaining }}/{{ llmQuota.quota_limit }}
              </view>
              <view
                class="meta-pill"
                :class="{ 'meta-pill--active': llmSource === 'tenant', 'meta-pill--disabled': !llmQuota.has_tenant_key }"
                @click="pickLlmSource('tenant')"
              >
                我的 Key
              </view>
            </view>
          </view>
          <view class="meta-track">
            <text class="meta-track__label">平台</text>
            <view class="meta-pills">
              <view
                v-for="p in platforms"
                :key="p.value"
                class="meta-pill"
                :class="{ 'meta-pill--active': platform === p.value }"
                @click="pickPlatform(p.value)"
              >
                {{ p.label }}
              </view>
            </view>
          </view>
          <view class="meta-track">
            <text class="meta-track__label">形态</text>
            <view class="meta-pills">
              <view
                v-for="f in formatOptions"
                :key="f.value"
                class="meta-pill"
                :class="{ 'meta-pill--active': contentFormat === f.value }"
                @click="pickContentFormat(f.value)"
              >
                {{ f.label }}
              </view>
            </view>
          </view>
        </view>

        <view class="compose-input">
          <input
            v-model="inputText"
            class="compose-input__field"
            placeholder="任意题材均可，如：少儿编程招生、火锅店开业…"
            confirm-type="send"
            :disabled="generating || proposing"
            @confirm="handleSend"
          />
          <button
            class="compose-send"
            :loading="generating || proposing"
            :disabled="generating || proposing"
            @click="handleSend"
          >
            发送
          </button>
        </view>
      </view>
    </view>

    <view v-if="sessionPanelVisible" class="session-panel">
      <view class="session-panel__mask" @click="sessionPanelVisible = false" />
      <view class="session-panel__body">
        <view class="session-panel__title">历史会话</view>
        <scroll-view scroll-y class="session-panel__list">
          <view
            v-for="s in sessionHistory"
            :key="s.id"
            class="session-panel__item"
            :class="{ 'session-panel__item--active': s.id === agentSessionId }"
            @click="switchToSession(s)"
          >
            <text class="session-panel__name">{{ s.title || '未命名会话' }}</text>
            <text class="session-panel__time">{{ formatSessionTime(s.updated_at) }}</text>
          </view>
          <view v-if="!sessionHistory.length" class="session-panel__empty">暂无历史会话</view>
        </scroll-view>
        <button class="btn-outline session-panel__new" size="mini" @click="startNewChat">新对话</button>
      </view>
    </view>

  </view>

</template>



<script setup>

import { computed, ref } from 'vue'

import { onShow } from '@dcloudio/uni-app'



import { BASE_URL, assistantsApi, agentApi, contentApi, llmApi, wechatApi } from '@/utils/api'
import { ensureSession } from '@/utils/session'

const agentFallback = import.meta.env.VITE_AGENT_FALLBACK === '1'
const useWorkflow = import.meta.env.VITE_AGENT_WORKFLOW !== '0'

const platform = ref('wechat')

const contentFormat = ref('article')

const inputText = ref('')

const generating = ref(false)

const proposing = ref(false)

const publishingId = ref('')

const scrollInto = ref('')

const wechatSettings = ref({ can_auto_publish: false })

const pendingTopic = ref('')

const advisor = ref(null)

const llmSource = ref('platform')

const llmQuota = ref({ remaining: 100, quota_limit: 100, has_tenant_key: false })

const agentSessionId = ref(uni.getStorageSync('agent_session_id') || '')
const sessionPanelVisible = ref(false)
const sessionHistory = ref([])

function formatSessionTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${m}-${day} ${h}:${min}`
}

function mapApiMessagesToUi(apiMessages) {
  return (apiMessages || [])
    .filter((m) => m.role === 'user' || m.role === 'assistant')
    .map((m) => ({ role: m.role, type: 'text', content: m.content || '' }))
}

async function loadSessionHistory() {
  sessionHistory.value = (await agentApi.listSessions({ limit: 20 })) || []
}

async function openSessionHistory() {
  sessionPanelVisible.value = true
  try {
    await loadSessionHistory()
  } catch {
    uni.showToast({ title: '加载历史失败', icon: 'none' })
  }
}

async function switchToSession(session) {
  if (!session?.id) return
  agentSessionId.value = session.id
  uni.setStorageSync('agent_session_id', session.id)
  sessionPanelVisible.value = false
  try {
    const data = await agentApi.getMessages(session.id)
    const mapped = mapApiMessagesToUi(data)
    messages.value =
      mapped.length > 0
        ? mapped
        : [{ role: 'assistant', type: 'text', content: `已打开「${session.title || '未命名'}」，继续输入即可。` }]
  } catch {
    uni.showToast({ title: '加载消息失败', icon: 'none' })
  }
}

function startNewChat() {
  sessionPanelVisible.value = false
  agentSessionId.value = ''
  uni.removeStorageSync('agent_session_id')
  messages.value = [
    { role: 'assistant', type: 'text', content: defaultWelcome },
  ]
  createAgentSession().catch(() => {})
}

async function createAgentSession() {
  try {
    const data = await agentApi.createSession({
      title: '营销创作',
    })
    agentSessionId.value = data.id
    uni.setStorageSync('agent_session_id', data.id)
    return data.id
  } catch (e) {
    if (isAgentSessionNotFound(e)) {
      throw new Error('Agent 接口不可用，请确认后端已启动（端口 8003）并已执行 alembic upgrade head')
    }
    throw e
  }
}

function clearAgentSession() {
  agentSessionId.value = ''
  uni.removeStorageSync('agent_session_id')
}

async function ensureAgentSession() {
  if (agentSessionId.value) return agentSessionId.value
  return createAgentSession()
}

function isAgentSessionNotFound(err) {
  return err?.status === 404 || /Not Found|会话不存在/.test(String(err?.message || ''))
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
    messages.value.push({
      role: 'assistant',
      type: 'result',
      content: c.body,
      contentId: c.id,
      status: c.status,
      platformCode: c.platform || platform.value,
      contentFormat: c.content_format,
    })
    return
  }
  messages.value.push({
    role: 'assistant',
    type: 'text',
    content: data.assistant_message || '请补充更多信息后继续创作。',
  })
}

async function agentChat(message, { selectedProposalIndex = null, retried = false } = {}) {
  const sessionId = await ensureAgentSession()
  const body = { message, llm_source: llmSource.value }
  if (selectedProposalIndex !== null) {
    body.selected_proposal_index = selectedProposalIndex
  }
  try {
    return await agentApi.chat(sessionId, body)
  } catch (e) {
    if (!retried && isAgentSessionNotFound(e)) {
      clearAgentSession()
      return agentChat(message, { selectedProposalIndex, retried: true })
    }
    throw e
  }
}

const defaultWelcome =
  '你好！我是小营，你的 AI 营销创作顾问。请选择平台与内容形态，描述想写的主题（任意行业/题材）；信息不足时我会先请您补充，再给出方案。'

const advisorName = computed(() => advisor.value?.name || '小营 · 营销创作顾问')
const advisorDesc = computed(
  () => advisor.value?.description || '通用营销创作顾问，支持公众号 / 小红书 / 抖音',
)

const GREETING_RE = /^(你好|您好|hi|hello|在吗|试试|测试|help)[!.?。！？\s]*$/i
const TOO_VAGUE_RE = /^(写(一)?篇|帮我写|生成(一个)?|来(一)?个|写个|写脚本|写笔记|创作)[!.?。！？\s]*$/i

function localPreflightCheck(text) {
  const t = text.trim()
  if (t.length < 6) {
    return '请补充更具体的创作需求，例如：主题、目标读者或想强调的核心要点。'
  }
  if (GREETING_RE.test(t)) {
    return '请告诉我您想创作的主题、目标读者或核心卖点，我再为您生成方案。'
  }
  if (TOO_VAGUE_RE.test(t)) {
    return '请补充具体主题与要点，例如：「抖音视频脚本，讲新公司注册流程，面向首次创业的老板」。'
  }
  return null
}

function defaultContentFormat(p) {

  if (p === 'xhs') return 'note'

  if (p === 'douyin') return 'video_script'

  return 'article'

}



const platforms = [

  { value: 'wechat', label: '公众号' },

  { value: 'xhs', label: '小红书' },

  { value: 'douyin', label: '抖音' },

]



const formatMap = {

  article: '图文',

  note: '笔记',

  video_script: '视频脚本',

}

const platformMap = {
  wechat: '公众号',
  xhs: '小红书',
  douyin: '抖音',
}



const messages = ref([
  {
    role: 'assistant',
    type: 'text',
    content: defaultWelcome,
  },
])



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



const formatOptions = computed(() => formatOptionsForPlatform(platform.value))



async function loadAdvisor() {
  try {
    const data = await assistantsApi.list()
    advisor.value = data?.[0] || null
    const welcome = advisor.value?.welcome_message || defaultWelcome
    const first = messages.value.find((m) => m.role === 'assistant' && m.type === 'text')
    if (first) first.content = welcome
  } catch {
    /* ignore */
  }
}



function pickContentFormat(f) {

  contentFormat.value = f

}



function formatLabel(fmt) {

  return formatMap[fmt] || fmt || '内容'

}



function pickPlatform(p) {

  platform.value = p

  contentFormat.value = resolveContentFormat(p, contentFormat.value)

}



function buildPayload(topic, selectedProposal = null) {
  const usePlatform = platform.value || 'wechat'
  const useFormat = contentFormat.value || defaultContentFormat(usePlatform)
  return {
    platform: usePlatform,
    topic,
    content_format: useFormat,
    industry_code: 'marketing',
    llm_source: llmSource.value,
    selected_proposal: selectedProposal,
  }
}

function buildUserPrompt(text) {
  const parts = [text]
  if (platform.value) parts.unshift(`[平台：${platformMap[platform.value] || platform.value}]`)
  return parts.join(' ')
}

async function runPreflight(text) {
  const localQ = localPreflightCheck(text)
  if (localQ) {
    return { ready: false, action: 'clarify', clarify_question: localQ, topic: null }
  }
  await ensureAgentSession()
  try {
    return await agentApi.preflight(agentSessionId.value, {
      message: text,
      platform: platform.value || 'wechat',
      content_format: contentFormat.value || defaultContentFormat(platform.value || 'wechat'),
      llm_source: llmSource.value,
    })
  } catch (e) {
    if (e?.status === 404 || /Not Found/i.test(String(e?.message || ''))) {
      return { ready: true, action: 'proceed', topic: text }
    }
    throw e
  }
}

function pushClarifyMessage(question) {
  messages.value.push({
    role: 'assistant',
    type: 'text',
    content: question || '请补充更多信息后继续创作。',
  })
}

function buildWorkflowInput(topic, proposalCount = null) {
  const payload = buildPayload(topic)
  const input = {
    platform: payload.platform,
    scene: payload.scene,
    topic: payload.topic,
    content_format: payload.content_format,
    industry_code: 'marketing',
    llm_source: payload.llm_source,
    search_query: payload.topic,
  }
  if (proposalCount != null && proposalCount >= 1) {
    input.proposal_count = proposalCount
  }
  return input
}

function parseWorkflowOutput(workflow) {
  if (!workflow?.output_json) return {}
  try {
    return typeof workflow.output_json === 'string'
      ? JSON.parse(workflow.output_json)
      : workflow.output_json
  } catch {
    return {}
  }
}

function pushWorkflowProposals(proposals, requestTopic, workflowId) {
  messages.value.push({
    role: 'assistant',
    type: 'proposals',
    proposals,
    requestTopic: requestTopic || '',
    workflowId,
  })
}

function pushContentResult(content, payload) {
  const usePlatform = content.platform || payload.platform
  messages.value.push({
    role: 'assistant',
    type: 'result',
    content: content.body,
    contentId: content.id,
    status: content.status,
    platformCode: usePlatform,
    contentFormat: content.content_format,
  })
}

async function runProposeWorkflow(topic, proposalCount = null) {
  await ensureAgentSession()
  const wf = await agentApi.createWorkflow({
    pipeline_code: 'content_propose',
    auto_run: true,
    session_id: agentSessionId.value || undefined,
    input: buildWorkflowInput(topic, proposalCount),
  })
  if (wf.status === 'paused') {
    const output = parseWorkflowOutput(wf)
    const proposals = output.proposals || []
    if (!proposals.length) throw new Error('未生成选题方案')
    return { workflowId: wf.id, proposals }
  }
  if (wf.status === 'failed') {
    throw new Error(wf.error_message || '方案生成失败')
  }
  throw new Error('工作流未返回方案')
}

async function runFinishWorkflow(workflowId, proposalIndex) {
  const wf = await agentApi.resumeWorkflow(workflowId, {
    selected_proposal_index: proposalIndex >= 0 ? proposalIndex : 0,
  })
  if (wf.status !== 'completed') {
    throw new Error(wf.error_message || '生成正文失败')
  }
  const output = parseWorkflowOutput(wf)
  if (!output.content_id) throw new Error('未生成正文')
  const content = await contentApi.get(output.content_id)
  return { workflow: wf, content, output }
}

async function fetchProposals(topic) {
  const payload = buildPayload(topic)
  try {
    const data = await agentChat(buildUserPrompt(topic))
    if (data.action === 'proposals' && data.proposals?.length) {
      return data.proposals
    }
    pushAgentChatResult(data, topic)
    return null
  } catch (e) {
    if (!agentFallback) throw e
    const res = await contentApi.proposals(payload)
    return res.proposals
  }
}



async function loadLlmQuota() {
  try {

    const data = await llmApi.getQuota()

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
    uni.showToast({
      title: llmQuota.value.remaining <= 0 ? '平台额度已用完' : '平台 AI 未配置',
      icon: 'none',
    })
    return
  }

  if (source === 'tenant' && !llmQuota.value.has_tenant_key) {

    uni.showToast({ title: '请先在设置中配置 API Key', icon: 'none' })

    return

  }

  llmSource.value = source

}



async function loadWechatSettings() {

  try {

    wechatSettings.value = await wechatApi.get()

  } catch {

    wechatSettings.value = { can_auto_publish: false }

  }

}



async function handleSend() {
  const text = inputText.value.trim()
  if (!text || generating.value || proposing.value) return

  messages.value.push({ role: 'user', type: 'text', content: buildUserPrompt(text) })
  inputText.value = ''
  pendingTopic.value = text
  proposing.value = true
  scrollInto.value = 'bottom'

  try {
    if (useWorkflow) {
      const pre = await runPreflight(text)
      if (!pre.ready) {
        pushClarifyMessage(pre.clarify_question)
        return
      }
      const topic = pre.topic || text
      const { workflowId, proposals } = await runProposeWorkflow(topic, pre.proposal_count ?? null)
      pushWorkflowProposals(proposals, topic, workflowId)
    } else {
      const data = await agentChat(buildUserPrompt(text))
      pushAgentChatResult(data, text)
    }
  } catch (e) {
    if (useWorkflow && agentFallback) {
      try {
        const proposals = await fetchProposals(text)
        if (proposals?.length) {
          pushWorkflowProposals(proposals, text, null)
        }
      } catch (err) {
        messages.value.push({
          role: 'assistant',
          type: 'text',
          content: `方案生成失败：${err.message || '请检查 API 与模型配置'}`,
        })
      }
    } else {
      messages.value.push({
        role: 'assistant',
        type: 'text',
        content: `方案生成失败：${e.message || '请检查 API 与模型配置'}`,
      })
    }
  } finally {
    proposing.value = false
    scrollInto.value = 'bottom'
  }
}



async function handleSelectProposal(proposal, requestTopic, msg) {
  if (generating.value) return
  generating.value = true
  scrollInto.value = 'bottom'
  const proposalIndex = msg?.proposals?.findIndex((p) => p.title === proposal.title) ?? 0
  const payload = buildPayload(requestTopic, proposal)
  try {
    if (useWorkflow && msg?.workflowId) {
      const { content } = await runFinishWorkflow(msg.workflowId, proposalIndex)
      pushContentResult(content, payload)
      if (llmSource.value === 'platform') await loadLlmQuota()
    } else {
      const data = await agentChat('生成正文', {
        selectedProposalIndex: proposalIndex >= 0 ? proposalIndex : 0,
      })
      pushAgentChatResult(data, requestTopic)
      if (data.action === 'generate' && llmSource.value === 'platform') await loadLlmQuota()
    }
  } catch (e) {
    if (agentFallback) {
      try {
        const content = await contentApi.generate(payload)
        pushContentResult(content, payload)
        if (llmSource.value === 'platform') await loadLlmQuota()
      } catch (err) {
        messages.value.push({
          role: 'assistant',
          type: 'text',
          content: `生成失败：${err.message || '请检查 API 与模型配置'}`,
        })
      }
    } else {
      messages.value.push({
        role: 'assistant',
        type: 'text',
        content: `生成失败：${e.message || '请检查 API 与模型配置'}`,
      })
    }
  } finally {
    generating.value = false
    scrollInto.value = 'bottom'
  }
}



async function handleRefreshProposals(msg) {
  if (proposing.value || !msg.requestTopic) return
  proposing.value = true
  try {
    if (useWorkflow) {
      const { workflowId, proposals } = await runProposeWorkflow(msg.requestTopic)
      msg.proposals = proposals
      msg.workflowId = workflowId
      uni.showToast({ title: '已刷新方案', icon: 'success' })
    } else {
      const data = await agentChat(buildUserPrompt(msg.requestTopic))
      if (data.action === 'proposals' && data.proposals?.length) {
        msg.proposals = data.proposals
        uni.showToast({ title: '已刷新方案', icon: 'success' })
      } else {
        pushAgentChatResult(data, msg.requestTopic)
      }
    }
  } catch (e) {
    if (agentFallback) {
      const proposals = await fetchProposals(msg.requestTopic)
      if (proposals?.length) {
        msg.proposals = proposals
        uni.showToast({ title: '已刷新方案', icon: 'success' })
      }
    } else {
      uni.showToast({ title: e.message || '刷新失败', icon: 'none' })
    }
  } finally {
    proposing.value = false
  }
}



function canAutoPublish(msg) {

  return (

    msg.platformCode === 'wechat' &&

    msg.contentFormat === 'article' &&

    wechatSettings.value.can_auto_publish

  )

}



function isVideoScript(msg) {

  return msg.contentFormat === 'video_script'

}



function canExportXhs(msg) {

  return msg.platformCode === 'xhs' && msg.contentFormat === 'note'

}



function canExportScript(msg) {

  return isVideoScript(msg)

}



function handleCopy(text) {

  uni.setClipboardData({

    data: text || '',

    success: () => uni.showToast({ title: '已复制', icon: 'success' }),

  })

}



function isDraft(msg) {

  return !msg.status || msg.status === 'draft' || msg.status === 'failed'

}



async function handlePublish(msg) {

  if (!msg.contentId || !isDraft(msg)) return

  publishingId.value = msg.contentId

  try {

    const data = await contentApi.publish(msg.contentId)

    msg.status = data.status

    uni.showToast({ title: '发布成功', icon: 'success' })

    // #ifdef H5

    if (data.preview_url) window.open(BASE_URL + data.preview_url, '_blank')

    // #endif

  } catch (e) {

    uni.showToast({ title: e.message || '发布失败', icon: 'none' })

  } finally {

    publishingId.value = ''

  }

}



async function handleExport(msg, type) {

  if (!msg.contentId) return

  try {

    let data

    if (type === 'xhs') data = await contentApi.exportXhs(msg.contentId)

    else if (type === 'script') data = await contentApi.exportScript(msg.contentId)

    else data = await contentApi.exportDouyin(msg.contentId)

    msg.status = 'exported'

    uni.showToast({ title: '导出成功', icon: 'success' })

    // #ifdef H5

    window.open(BASE_URL + data.download_url, '_blank')

    // #endif

  } catch (e) {

    uni.showToast({ title: e.message || '导出失败', icon: 'none' })

  }

}



onShow(async () => {
  const user = await ensureSession()
  if (!user) return
  await loadWechatSettings()
  await loadAdvisor()
  await loadLlmQuota()
  await ensureAgentSession()
})

</script>



<style scoped>

.page {

  display: flex;

  flex-direction: column;

  flex: 1;

  height: 100%;

  min-height: 0;

  overflow: hidden;

  background: #f5f5f5;

  box-sizing: border-box;

}



.assistant-picker {

  display: flex;

  align-items: center;

  gap: 16rpx;

  margin: 16rpx 24rpx 0;

  padding: 20rpx 24rpx 20rpx 20rpx;

  border-radius: 24rpx;

  border: 1rpx solid #d6e8ff;

  background: linear-gradient(135deg, #f0f7ff 0%, #fff 60%);

  flex-shrink: 0;

}



.assistant-picker--clickable:active {

  border-color: #1677ff;

  box-shadow: 0 8rpx 24rpx rgba(22, 119, 255, 0.12);

}



.assistant-picker__avatar {

  width: 80rpx;

  height: 80rpx;

  background: #1677ff;

  color: #fff;

  border-radius: 50%;

  display: flex;

  align-items: center;

  justify-content: center;

  font-size: 26rpx;

  font-weight: 600;

  flex-shrink: 0;

}



.assistant-picker__body {

  flex: 1;

  min-width: 0;

}



.assistant-picker__row {

  display: flex;

  align-items: center;

  flex-wrap: wrap;

  gap: 12rpx;

}



.assistant-picker__name {

  font-size: 32rpx;

  font-weight: 600;

  color: #333;

}



.assistant-picker__badge {

  font-size: 22rpx;

  color: #1677ff;

  background: #e6f4ff;

  border: 1rpx solid #91caff;

  padding: 4rpx 16rpx;

  border-radius: 999rpx;

}



.assistant-picker__arrow {

  font-size: 20rpx;

  color: #1677ff;

}



.assistant-picker__desc {

  display: block;

  margin-top: 8rpx;

  font-size: 22rpx;

  color: #999;

  line-height: 1.45;

  overflow: hidden;

  text-overflow: ellipsis;

  white-space: nowrap;

}

.assistant-picker__history {
  flex-shrink: 0;
  font-size: 24rpx;
  color: #1677ff;
  padding: 8rpx 12rpx;
}

.session-panel {
  position: fixed;
  inset: 0;
  z-index: 1000;
}

.session-panel__mask {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
}

.session-panel__body {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  max-height: 70vh;
  background: #fff;
  border-radius: 24rpx 24rpx 0 0;
  padding: 24rpx;
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.session-panel__title {
  font-size: 30rpx;
  font-weight: 600;
  color: #333;
}

.session-panel__list {
  max-height: 50vh;
}

.session-panel__item {
  padding: 20rpx 16rpx;
  border-bottom: 1rpx solid #f0f0f0;
}

.session-panel__item--active {
  background: #ecf5ff;
}

.session-panel__name {
  display: block;
  font-size: 28rpx;
  color: #333;
}

.session-panel__time {
  display: block;
  margin-top: 8rpx;
  font-size: 22rpx;
  color: #999;
}

.session-panel__empty {
  padding: 32rpx;
  text-align: center;
  color: #999;
  font-size: 26rpx;
}

.session-panel__new {
  align-self: flex-start;
}



.chat-body {

  flex: 1;

  height: 0;

  min-height: 0;

  padding: 24rpx;

  box-sizing: border-box;

}



.msg-row {

  display: flex;

  gap: 16rpx;

  margin-bottom: 24rpx;

  align-items: flex-start;

}



.msg-row--user {

  flex-direction: row-reverse;

}



.avatar {

  width: 64rpx;

  height: 64rpx;

  border-radius: 50%;

  display: flex;

  align-items: center;

  justify-content: center;

  font-size: 22rpx;

  flex-shrink: 0;

}



.avatar--ai {

  background: #1677ff;

  color: #fff;

}



.avatar--me {

  background: #52c41a;

  color: #fff;

}



.msg-content {

  max-width: 85%;

}



.bubble {

  background: #fff;

  padding: 20rpx 24rpx;

  border-radius: 16rpx;

  font-size: 28rpx;

  line-height: 1.6;

}



.msg-row--user .bubble {

  background: #e6f4ff;

}



.bubble--typing {

  color: #999;

  font-size: 26rpx;

}


.proposals {

  background: #fff;

  border-radius: 16rpx;

  padding: 20rpx;

  border: 1rpx solid #e8e8e8;

}



.proposals__title {

  display: block;

  font-size: 26rpx;

  color: #666;

  margin-bottom: 16rpx;

}



.proposal-card {

  border: 1rpx solid #f0f0f0;

  border-radius: 12rpx;

  padding: 16rpx;

  margin-bottom: 16rpx;

  background: #fafafa;

}



.proposal-card__direction {

  display: block;

  font-size: 28rpx;

  line-height: 1.55;

  color: #333;

  margin-bottom: 16rpx;

}



.btn-link {

  background: transparent;

  color: #1677ff;

  font-size: 24rpx;

}



.result {

  background: #fff;

  border-radius: 16rpx;

  overflow: hidden;

  border: 1rpx solid #e8e8e8;

}



.result__meta {

  padding: 12rpx 24rpx;

  background: #fafafa;

  border-bottom: 1rpx solid #f0f0f0;

}



.result__tag {

  font-size: 22rpx;

  color: #1677ff;

  background: #e6f4ff;

  padding: 4rpx 12rpx;

  border-radius: 6rpx;

}



.result__text {

  display: block;

  padding: 24rpx;

  font-size: 28rpx;

  line-height: 1.6;

  white-space: pre-wrap;

}



.result__actions {

  display: flex;

  flex-wrap: wrap;

  justify-content: flex-end;

  gap: 12rpx;

  padding: 16rpx 24rpx;

  border-top: 1rpx solid #f0f0f0;

  background: #fafafa;

}



.btn-outline {

  background: #fff;

  color: #666;

  font-size: 24rpx;

  border: 1rpx solid #ddd;

}



.btn-primary {

  background: #1677ff;

  color: #fff;

  font-size: 24rpx;

}



.chat-footer {

  padding: 16rpx 24rpx;

  flex-shrink: 0;

  padding-bottom: calc(16rpx + env(safe-area-inset-bottom));

  background: #f5f7fa;

}



.compose-box {

  background: #fff;

  border: 1rpx solid #e8e8e8;

  border-radius: 24rpx;

  overflow: hidden;

  box-shadow: 0 4rpx 24rpx rgba(0, 0, 0, 0.04);

}



.compose-meta {

  display: flex;

  flex-wrap: wrap;

  align-items: center;

  gap: 16rpx 20rpx;

  padding: 16rpx 20rpx;

  background: #fafbfc;

  border-bottom: 1rpx solid #f0f0f0;

}



.meta-track {

  display: inline-flex;

  align-items: center;

  gap: 12rpx;

}



.meta-track--scene {

  flex: 1;

  min-width: 200rpx;

}



.meta-track__label {

  font-size: 22rpx;

  color: #999;

  flex-shrink: 0;

}



.meta-pills {

  display: inline-flex;

  align-items: center;

  gap: 4rpx;

  padding: 6rpx;

  background: #eef0f3;

  border-radius: 16rpx;

}



.meta-pill {

  padding: 12rpx 24rpx;

  border-radius: 12rpx;

  font-size: 24rpx;

  color: #666;

  white-space: nowrap;

}



.meta-pill--active {

  background: #fff;

  color: #1677ff;

  font-weight: 600;

  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.08);

}



.meta-pill--disabled {

  opacity: 0.45;

}



.meta-scene {

  min-width: 120rpx;

  max-width: 280rpx;

  padding: 12rpx 20rpx;

  background: #fff;

  border: 1rpx solid #e8e8e8;

  border-radius: 12rpx;

  font-size: 24rpx;

  color: #666;

  overflow: hidden;

  text-overflow: ellipsis;

  white-space: nowrap;

}



.compose-input {

  display: flex;

  align-items: flex-end;

  gap: 16rpx;

  padding: 16rpx 20rpx 20rpx;

  border-top: 1rpx solid #f0f2f5;

}



.compose-input__field {

  flex: 1;

  min-height: 80rpx;

  font-size: 28rpx;

  line-height: 1.5;

  background: transparent;

}



.compose-send {

  flex-shrink: 0;

  min-width: 128rpx;

  height: 72rpx;

  line-height: 72rpx;

  padding: 0 28rpx;

  border-radius: 18rpx;

  font-size: 28rpx;

  font-weight: 600;

  background: #1677ff;

  color: #fff;

  margin: 0;

}

</style>


