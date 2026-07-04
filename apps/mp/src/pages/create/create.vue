<template>

  <view class="page">

    <view
      class="assistant-picker"
      :class="{ 'assistant-picker--clickable': assistants.length > 1 }"
      @click="showAssistantPicker"
    >
      <view class="assistant-picker__avatar">AI</view>
      <view class="assistant-picker__body">
        <view class="assistant-picker__row">
          <text class="assistant-picker__name">{{ selectedAssistant?.name || '智营 AI 创作助手' }}</text>
          <text v-if="assistants.length > 1" class="assistant-picker__badge">切换助手</text>
          <text v-if="assistants.length > 1" class="assistant-picker__arrow">▼</text>
        </view>
        <text class="assistant-picker__desc">{{ selectedAssistant?.description || '先出方案 · 再生成正文' }}</text>
      </view>
    </view>



    <scroll-view scroll-y class="chat-body" :scroll-into-view="scrollInto">

      <view v-for="(msg, idx) in messages" :key="idx" class="msg-row" :class="'msg-row--' + msg.role">

        <view v-if="msg.role === 'assistant'" class="avatar avatar--ai">AI</view>



        <view class="msg-content">

          <view v-if="msg.type === 'text'" class="bubble">{{ msg.content }}</view>



          <view v-else-if="msg.type === 'quick'" class="quick-list">

            <view

              v-for="item in msg.items"

              :key="item.text"

              class="quick-item"

              @click="handleQuick(item)"

            >

              {{ item.text }}

            </view>

          </view>



          <view v-else-if="msg.type === 'proposals'" class="proposals">

            <text class="proposals__title">请选择创作方向（{{ msg.proposals.length }} 个）：</text>

            <view v-for="(item, pi) in msg.proposals" :key="pi" class="proposal-card">

              <text class="proposal-card__direction">{{ item.title }}</text>

              <button

                class="btn-primary"

                size="mini"

                :loading="generating"

                @click="handleSelectProposal(item, msg.requestTopic)"

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
          <view class="meta-track meta-track--scene">
            <text class="meta-track__label">场景</text>
            <picker
              mode="selector"
              :range="scenePickerOptions"
              range-key="label"
              :value="scenePickerIndex"
              @change="onScenePick"
            >
              <view class="meta-scene">{{ sceneLabel }}</view>
            </picker>
          </view>
        </view>

        <view class="compose-input">
          <input
            v-model="inputText"
            class="compose-input__field"
            placeholder="描述想创作的内容，Enter 发送…"
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

  </view>

</template>



<script setup>

import { computed, ref } from 'vue'

import { onShow } from '@dcloudio/uni-app'



import { BASE_URL, assistantsApi, authApi, contentApi, templatesApi, wechatApi } from '@/utils/api'
import { getToken } from '@/utils/auth'



const platform = ref('wechat')

const contentFormat = ref('article')

const inputText = ref('')

const generating = ref(false)

const proposing = ref(false)

const publishingId = ref('')

const scrollInto = ref('')

const wechatSettings = ref({ can_auto_publish: false })

const pendingTopic = ref('')

const assistants = ref([])

const industryCode = ref('finance')

const scene = ref('')

const scenes = ref([])

const filteredScenes = ref([])

const defaultWelcome = '您好！告诉我创作需求，我会先给出 3～5 个方案供选择。'



function updateFilteredScenes() {

  if (!platform.value) {

    filteredScenes.value = scenes.value

    return

  }

  filteredScenes.value = scenes.value.filter((s) => s.platform === platform.value || !s.platform)

}



const scenePickerOptions = computed(() => [

  { value: '', label: '不限' },

  ...filteredScenes.value,

])



const sceneLabel = computed(() => {

  if (!scene.value) return '不限'

  return filteredScenes.value.find((s) => s.value === scene.value)?.label || '不限'

})



const scenePickerIndex = computed(() => {

  const idx = scenePickerOptions.value.findIndex((s) => s.value === scene.value)

  return idx >= 0 ? idx : 0

})



function onScenePick(e) {

  const item = scenePickerOptions.value[e.detail.value]

  scene.value = item?.value || ''

}



function defaultContentFormat(p) {

  if (p === 'xhs') return 'note'

  if (p === 'douyin') return 'video_script'

  return 'article'

}



function buildQuickStartsFromTemplates(templates) {

  const platformOrder = ['wechat', 'xhs', 'douyin']

  const picked = []

  for (const p of platformOrder) {

    const t = templates.find((x) => x.platform === p)

    if (t) {

      picked.push({

        text: t.name,

        platform: t.platform,

        scene: t.scene,

        format: defaultContentFormat(t.platform),

      })

    }

  }

  for (const t of templates) {

    if (picked.length >= 4) break

    if (!picked.some((x) => x.scene === t.scene && x.platform === t.platform)) {

      picked.push({

        text: t.name,

        platform: t.platform,

        scene: t.scene,

        format: defaultContentFormat(t.platform),

      })

    }

  }

  return picked.slice(0, 4)

}



const quickStarts = ref([

  { text: '公众号报税提醒', platform: 'wechat', scene: 'tax_deadline_reminder', format: 'article' },

  { text: '小红书代账笔记', platform: 'xhs', scene: 'bookkeeping_intro', format: 'note' },

  { text: '抖音注册指南脚本', platform: 'douyin', scene: 'small_company_register', format: 'video_script' },

])



function syncQuickStarts() {

  const quickMsg = messages.value.find((m) => m.role === 'assistant' && m.type === 'quick')

  if (quickMsg) quickMsg.items = quickStarts.value

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



const messages = ref([

  {

    role: 'assistant',

    type: 'text',

    content: defaultWelcome,

  },

  { role: 'assistant', type: 'quick', items: quickStarts.value },

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



const selectedAssistant = computed(

  () => assistants.value.find((a) => a.code === industryCode.value) || null,

)



function syncWelcomeMessage() {

  const welcome = selectedAssistant.value?.welcome_message || defaultWelcome

  const first = messages.value.find((m) => m.role === 'assistant' && m.type === 'text')

  if (first) first.content = welcome

}



async function loadTemplatesForAssistant(code) {

  if (!getToken()) return

  try {

    const data = await templatesApi.list({ industry_code: code })

    if (data.length) {

      scenes.value = data.map((t) => ({

        value: t.scene,

        label: t.name,

        platform: t.platform,

      }))

      quickStarts.value = buildQuickStartsFromTemplates(data)

      updateFilteredScenes()

      syncQuickStarts()

    }

  } catch {

    /* keep defaults */

  }

}



async function loadAssistants() {

  if (!getToken()) return

  try {

    const data = await assistantsApi.list()

    assistants.value = data

    try {

      const me = await authApi.me()

      const tenantCode = me.tenant?.industry_code

      if (tenantCode && data.some((a) => a.code === tenantCode)) {

        industryCode.value = tenantCode

      } else if (data.length) {

        industryCode.value = data[0].code

      }

    } catch {

      if (data.length) industryCode.value = data[0].code

    }

    syncWelcomeMessage()

    await loadTemplatesForAssistant(industryCode.value)

  } catch {

    /* ignore */

  }

}



function pickAssistant(code) {

  industryCode.value = code

  scene.value = ''

  syncWelcomeMessage()

  loadTemplatesForAssistant(code)

}



function showAssistantPicker() {

  if (assistants.value.length <= 1) return

  uni.showActionSheet({

    itemList: assistants.value.map((a) => a.name),

    success(res) {

      const picked = assistants.value[res.tapIndex]

      if (picked) pickAssistant(picked.code)

    },

  })

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

  updateFilteredScenes()

  if (scene.value && !filteredScenes.value.some((s) => s.value === scene.value)) {

    scene.value = ''

  }

}



function buildPayload(topic, selectedProposal = null) {

  return {

    industry_code: industryCode.value || 'finance',

    platform: platform.value,

    scene:

      scene.value ||

      filteredScenes.value[0]?.value ||

      quickStarts.value[0]?.scene ||

      'tax_deadline_reminder',

    topic,

    content_format: contentFormat.value,

    selected_proposal: selectedProposal,

  }

}



async function loadWechatSettings() {

  try {

    wechatSettings.value = await wechatApi.get()

  } catch {

    wechatSettings.value = { can_auto_publish: false }

  }

}



function handleQuick(item) {

  platform.value = item.platform

  scene.value = item.scene || ''

  contentFormat.value = item.format || defaultContentFormat(item.platform)

  inputText.value = item.text

  handleSend()

}



async function handleSend() {

  const text = inputText.value.trim()

  if (!text || generating.value || proposing.value) return



  messages.value = messages.value.filter((m) => m.type !== 'quick')

  messages.value.push({ role: 'user', type: 'text', content: text })

  inputText.value = ''

  pendingTopic.value = text

  proposing.value = true

  scrollInto.value = 'bottom'



  try {

    const data = await contentApi.proposals(buildPayload(text))

    messages.value.push({

      role: 'assistant',

      type: 'proposals',

      proposals: data.proposals,

      requestTopic: text,

    })

  } catch (e) {

    messages.value.push({

      role: 'assistant',

      type: 'text',

      content: `方案生成失败：${e.message || '请检查 API 与模型配置'}`,

    })

  } finally {

    proposing.value = false

    scrollInto.value = 'bottom'

  }

}



async function handleSelectProposal(proposal, requestTopic) {

  if (generating.value) return

  generating.value = true

  scrollInto.value = 'bottom'

  try {

    const data = await contentApi.generate(buildPayload(requestTopic, proposal))

    messages.value.push({

      role: 'assistant',

      type: 'result',

      content: data.body,

      contentId: data.id,

      status: data.status,

      platformCode: platform.value,

      contentFormat: data.content_format,

    })

  } catch (e) {

    messages.value.push({

      role: 'assistant',

      type: 'text',

      content: `生成失败：${e.message || '请检查 API 与模型配置'}`,

    })

  } finally {

    generating.value = false

    scrollInto.value = 'bottom'

  }

}



async function handleRefreshProposals(msg) {

  if (proposing.value || !msg.requestTopic) return

  proposing.value = true

  try {

    const data = await contentApi.proposals(buildPayload(msg.requestTopic))

    msg.proposals = data.proposals

    uni.showToast({ title: '已刷新方案', icon: 'success' })

  } catch (e) {

    uni.showToast({ title: e.message || '刷新失败', icon: 'none' })

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

  await loadWechatSettings()

  await loadAssistants()

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



.quick-list {

  display: flex;

  flex-wrap: wrap;

  gap: 12rpx;

}



.quick-item {

  width: calc(50% - 6rpx);

  box-sizing: border-box;

  background: #fff;

  border: 1rpx solid #e8e8e8;

  padding: 24rpx 20rpx;

  border-radius: 16rpx;

  font-size: 26rpx;

  line-height: 1.4;

  min-height: 88rpx;

  display: flex;

  align-items: center;

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

  padding: 16rpx 20rpx;

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

  height: 80rpx;

  line-height: 80rpx;

  background: #1677ff;

  color: #fff;

  font-size: 28rpx;

  font-weight: 600;

  border-radius: 16rpx;

  margin: 0;

  padding: 0 28rpx;

}

</style>


