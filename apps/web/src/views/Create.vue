<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { Promotion, RefreshRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { contentApi, llmApi } from '../api/client'

const platform = ref('')
const scene = ref('')
const inputText = ref('')
const generating = ref(false)
const messagesEndRef = ref(null)
const modelTag = ref('未配置模型')

const platformMap = {
  wechat: '公众号',
  xhs: '小红书',
  douyin: '抖音',
}

const scenes = [
  { value: 'tax_deadline_reminder', label: '报税截止提醒' },
  { value: 'bookkeeping_intro', label: '代理记账介绍' },
  { value: 'small_company_register', label: '新公司注册指南' },
  { value: 'case_penalty_story', label: '税务处罚案例' },
]

const quickStarts = [
  { text: '写一篇公众号报税提醒', platform: 'wechat', scene: 'tax_deadline_reminder' },
  { text: '小红书代理记账服务介绍', platform: 'xhs', scene: 'bookkeeping_intro' },
  { text: '抖音新公司注册指南脚本', platform: 'douyin', scene: 'small_company_register' },
  { text: '税务处罚案例故事（公众号）', platform: 'wechat', scene: 'case_penalty_story' },
]

const messages = ref([
  {
    role: 'assistant',
    type: 'text',
    content:
      '您好，我是智营 AI 创作助手。直接告诉我您想创作什么，或点击下方快捷选题开始——我会帮您生成符合财税合规要求的营销内容。',
  },
  {
    role: 'assistant',
    type: 'quick',
    items: quickStarts,
  },
])

const mockResult = '' // removed mock

onMounted(async () => {
  try {
    const { data } = await llmApi.get()
    modelTag.value = `${data.provider} · ${data.model}`
  } catch {
    modelTag.value = '未配置模型'
  }
})

async function scrollToBottom() {
  await nextTick()
  messagesEndRef.value?.scrollIntoView({ behavior: 'smooth' })
}

function pickPlatform(p) {
  platform.value = p
}

function pickScene(s) {
  scene.value = s
}

function handleQuickStart(item) {
  platform.value = item.platform
  scene.value = item.scene
  inputText.value = item.text
  handleSend()
}

function buildUserPrompt(text) {
  const parts = [text]
  if (platform.value) parts.unshift(`[平台：${platformMap[platform.value]}]`)
  if (scene.value) {
    const label = scenes.find((s) => s.value === scene.value)?.label
    if (label) parts.unshift(`[场景：${label}]`)
  }
  return parts.join(' ')
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || generating.value) return

  const usePlatform = platform.value || 'wechat'
  const useScene = scene.value || 'tax_deadline_reminder'

  messages.value = messages.value.filter((m) => m.type !== 'quick')
  messages.value.push({ role: 'user', type: 'text', content: buildUserPrompt(text) })
  inputText.value = ''
  generating.value = true
  scrollToBottom()

  try {
    const { data } = await contentApi.generate({
      industry_code: 'finance',
      platform: usePlatform,
      scene: useScene,
      topic: text,
    })
    messages.value.push({
      role: 'assistant',
      type: 'result',
      content: data.body,
      contentId: data.id,
      status: data.status,
      meta: {
        platform: platformMap[usePlatform] || usePlatform,
        scene: scenes.find((s) => s.value === useScene)?.label || '自定义',
        model: `${data.llm_provider} · ${data.llm_model}`,
      },
    })
    modelTag.value = `${data.llm_provider} · ${data.llm_model}`
  } catch (e) {
    ElMessage.error(e.message || '生成失败')
    messages.value.push({
      role: 'assistant',
      type: 'text',
      content: `生成失败：${e.message || '请检查 AI 模型配置'}`,
    })
  } finally {
    generating.value = false
    await scrollToBottom()
  }
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
  inputText.value = ''
  generating.value = false
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
      items: quickStarts,
    },
  ]
}

async function handleSubmitReview(msg) {
  if (!msg.contentId) return
  if (msg.status !== 'draft') {
    ElMessage.info('该内容已提交审核')
    return
  }
  try {
    const { data } = await contentApi.submitReview(msg.contentId)
    msg.status = data.status
    ElMessage.success('已提交审核，可在内容库查看')
  } catch (e) {
    ElMessage.error(e.message || '提交失败')
  }
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
        <div class="chat-header__left">
          <el-avatar :size="40" style="background: #1677ff">AI</el-avatar>
          <div>
            <div class="chat-header__title">智营 AI 创作助手</div>
            <div class="chat-header__sub">对话式生成 · 财税营销内容</div>
          </div>
        </div>
        <div class="chat-header__right">
          <el-tag type="success" size="small">{{ modelTag }}</el-tag>
          <el-button :icon="RefreshRight" circle @click="handleNewChat" title="新对话" />
        </div>
      </div>

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

            <!-- 生成结果 -->
            <div v-else-if="msg.type === 'result'" class="result-block">
              <div class="result-block__meta">
                <el-tag size="small">{{ msg.meta.platform }}</el-tag>
                <el-tag size="small" type="info">{{ msg.meta.scene }}</el-tag>
              </div>
              <pre class="result-block__text">{{ msg.content }}</pre>
              <div class="result-block__actions">
                <el-button size="small" @click="handleCopy(msg.content)">复制全文</el-button>
                <el-button size="small" disabled>已保存草稿</el-button>
                <el-button
                  type="primary"
                  size="small"
                  :disabled="msg.status && msg.status !== 'draft'"
                  @click="handleSubmitReview(msg)"
                >
                  {{ msg.status === 'pending_review' ? '已提交' : '提交审核' }}
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
        <div v-if="generating" class="chat-row chat-row--assistant">
          <el-avatar :size="36" style="background: #1677ff">AI</el-avatar>
          <div class="bubble bubble--assistant bubble--typing">
            <span /><span /><span />
          </div>
        </div>

        <div ref="messagesEndRef" />
      </div>

      <!-- 底部输入区 -->
      <div class="chat-footer">
        <div class="chat-footer__toolbar">
          <span class="toolbar-label">平台</span>
          <button
            v-for="(label, key) in platformMap"
            :key="key"
            class="toolbar-chip"
            :class="{ 'toolbar-chip--active': platform === key }"
            @click="pickPlatform(key)"
          >
            {{ label }}
          </button>
          <span class="toolbar-divider" />
          <span class="toolbar-label">场景</span>
          <button
            v-for="s in scenes"
            :key="s.value"
            class="toolbar-chip toolbar-chip--sm"
            :class="{ 'toolbar-chip--active': scene === s.value }"
            @click="pickScene(s.value)"
          >
            {{ s.label }}
          </button>
        </div>

        <div class="chat-footer__input-wrap">
          <el-input
            v-model="inputText"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 4 }"
            placeholder="描述您想创作的内容，例如：写一篇3月小规模纳税人报税提醒…"
            :disabled="generating"
            @keydown="handleKeydown"
          />
          <el-button
            type="primary"
            circle
            class="chat-footer__send"
            :icon="Promotion"
            :loading="generating"
            :disabled="!inputText.trim()"
            @click="handleSend"
          />
        </div>
        <div class="chat-footer__hint">Enter 发送 · Shift+Enter 换行 · 可先选平台/场景再描述需求</div>
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
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}

.chat-header__left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.chat-header__title {
  font-size: 16px;
  font-weight: 600;
}

.chat-header__sub {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 2px;
}

.chat-header__right {
  display: flex;
  align-items: center;
  gap: 12px;
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
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.quick-chip {
  padding: 10px 16px;
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: 20px;
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
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--color-border);
  background: #fafafa;
}

.chat-footer {
  border-top: 1px solid var(--color-border);
  padding: 12px 20px 16px;
  flex-shrink: 0;
  background: #fafafa;
}

.chat-footer__toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.toolbar-label {
  font-size: 12px;
  color: var(--color-text-muted);
}

.toolbar-divider {
  width: 1px;
  height: 16px;
  background: var(--color-border);
  margin: 0 4px;
}

.toolbar-chip {
  padding: 4px 12px;
  border-radius: 14px;
  border: 1px solid var(--color-border);
  background: #fff;
  font-size: 12px;
  cursor: pointer;
  color: var(--color-text-secondary);
  transition: all 0.15s;
}

.toolbar-chip--sm {
  font-size: 12px;
}

.toolbar-chip:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.toolbar-chip--active {
  background: #e6f4ff;
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.chat-footer__input-wrap {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 8px 8px 8px 16px;
}

.chat-footer__input-wrap :deep(.el-textarea__inner) {
  box-shadow: none !important;
  border: none;
  padding: 4px 0;
  resize: none;
}

.chat-footer__send {
  flex-shrink: 0;
}

.chat-footer__hint {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-top: 8px;
  text-align: center;
}
</style>
