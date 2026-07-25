<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Bell, ArrowRight } from '@element-plus/icons-vue'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { formatDateTime } from '../../utils/datetime'

const router = useRouter()
const auth = useAuthStore()

const visible = ref(false)
const loading = ref(false)
const items = ref([])
const unread = ref(0)
let pollTimer = null

const badge = computed(() => (unread.value > 99 ? '99+' : unread.value || ''))

const ENTITY_LABEL = {
  lead: '线索',
  customer: '客户',
  deal: '商机',
  contract: '合同',
  order: '订单',
}

async function refreshCount() {
  if (!auth.isLoggedIn) return
  try {
    const { data } = await crmApi.unreadNotificationCount()
    unread.value = Number(data?.count || 0)
  } catch {
    /* 旧 API / 无权限时静默 */
  }
}

async function loadList() {
  loading.value = true
  try {
    const { data } = await crmApi.listNotifications({ page: 1, page_size: 20 })
    items.value = Array.isArray(data?.items) ? data.items : []
    unread.value = Number(data?.unread || 0)
  } catch (e) {
    items.value = []
    if (e?.status !== 404) {
      ElMessage.error(e.message || '加载通知失败')
    }
  } finally {
    loading.value = false
  }
}

watch(visible, (v) => {
  if (v) loadList()
})

async function markOne(row, { navigate = false } = {}) {
  if (!row.is_read) {
    try {
      await crmApi.markNotificationRead(row.id)
      row.is_read = true
      unread.value = Math.max(0, unread.value - 1)
    } catch (e) {
      ElMessage.error(e.message || '标记失败')
      return
    }
  }
  if (navigate) navigateEntity(row)
}

async function markAll() {
  try {
    await crmApi.markAllNotificationsRead()
    items.value.forEach((x) => {
      x.is_read = true
    })
    unread.value = 0
    ElMessage.success('已全部标为已读')
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  }
}

function canNavigate(row) {
  return Boolean(row.entity_type && row.entity_id && ENTITY_LABEL[row.entity_type])
}

function navigateEntity(row) {
  if (!canNavigate(row)) return
  const map = {
    lead: `/crm/leads/${row.entity_id}`,
    customer: `/crm/customers/${row.entity_id}`,
    deal: `/crm/deals/${row.entity_id}`,
    contract: `/crm/contracts/${row.entity_id}`,
    order: `/crm/orders/${row.entity_id}`,
  }
  const path = map[row.entity_type]
  if (path) {
    visible.value = false
    router.push(path)
  }
}

function formatTime(v) {
  return formatDateTime(v, { empty: '', withSeconds: false })
}

function entityLabel(row) {
  return ENTITY_LABEL[row.entity_type] || ''
}

onMounted(() => {
  refreshCount()
  pollTimer = setInterval(refreshCount, 60000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <el-popover
    v-model:visible="visible"
    placement="bottom-end"
    :width="400"
    trigger="click"
    :show-arrow="false"
    popper-class="crm-notif-popper"
    :teleported="true"
  >
    <template #reference>
      <el-badge :value="badge" :hidden="!unread" class="notif-badge">
        <el-button class="notif-btn" text bg aria-label="通知">
          <el-icon :size="18"><Bell /></el-icon>
        </el-button>
      </el-badge>
    </template>

    <div class="notif-panel" @click.stop>
      <div class="notif-panel__head">
        <div class="notif-panel__title">
          <span>通知</span>
          <span v-if="unread" class="notif-panel__count">{{ unread }} 条未读</span>
        </div>
        <el-button link type="primary" size="small" :disabled="!unread" @click.stop="markAll">
          全部已读
        </el-button>
      </div>

      <div v-loading="loading" class="notif-panel__body">
        <div
          v-for="row in items"
          :key="row.id"
          class="notif-item"
          :class="{ 'is-unread': !row.is_read }"
          @click="markOne(row)"
        >
          <div class="notif-item__main">
            <span class="notif-item__dot" aria-hidden="true" />
            <div class="notif-item__content">
              <div class="notif-item__title">{{ row.title }}</div>
              <div v-if="row.body" class="notif-item__body">{{ row.body }}</div>
              <div class="notif-item__meta">
                <span class="notif-item__time">{{ formatTime(row.created_at) }}</span>
                <button
                  v-if="canNavigate(row)"
                  type="button"
                  class="notif-item__action"
                  @click.stop="markOne(row, { navigate: true })"
                >
                  查看{{ entityLabel(row) }}
                  <el-icon :size="12"><ArrowRight /></el-icon>
                </button>
              </div>
            </div>
          </div>
        </div>
        <el-empty v-if="!loading && !items.length" description="暂无通知" :image-size="56" />
      </div>
    </div>
  </el-popover>
</template>

<style scoped>
.notif-badge {
  margin-right: 8px;
}
.notif-btn {
  color: #fff !important;
  border: none;
  background: rgba(255, 255, 255, 0.12) !important;
}
.notif-panel {
  margin: -12px;
}
.notif-panel__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.notif-panel__title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.notif-panel__count {
  font-size: 12px;
  font-weight: 500;
  color: var(--el-color-primary);
}
.notif-panel__body {
  max-height: 420px;
  overflow: auto;
  padding: 6px 8px 8px;
}
.notif-item {
  padding: 12px 10px;
  border-radius: 10px;
  cursor: default;
  transition: background 0.15s ease;
}
.notif-item:hover {
  background: var(--el-fill-color-light);
}
.notif-item.is-unread {
  background: var(--el-color-primary-light-9);
  cursor: pointer;
}
.notif-item.is-unread:hover {
  background: var(--el-color-primary-light-8);
}
.notif-item__main {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.notif-item__dot {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: 50%;
  background: transparent;
}
.notif-item.is-unread .notif-item__dot {
  background: var(--el-color-primary);
  box-shadow: 0 0 0 3px var(--el-color-primary-light-7);
}
.notif-item__content {
  flex: 1;
  min-width: 0;
}
.notif-item__title {
  font-size: 14px;
  font-weight: 600;
  line-height: 1.4;
  color: var(--el-text-color-primary);
}
.notif-item__body {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.5;
  color: var(--el-text-color-regular);
  word-break: break-word;
}
.notif-item__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 10px;
}
.notif-item__time {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.notif-item__action {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px 0;
  border: none;
  background: none;
  font-size: 12px;
  font-weight: 500;
  color: var(--el-color-primary);
  cursor: pointer;
  line-height: 1.4;
}
.notif-item__action:hover {
  color: var(--el-color-primary-light-3);
  text-decoration: underline;
}
</style>

<style>
/* popper 挂到 body，需非 scoped */
.crm-notif-popper.el-popover.el-popper {
  padding: 0 !important;
  border-radius: 12px !important;
  box-shadow: 0 8px 28px rgba(15, 23, 42, 0.14) !important;
  border: 1px solid var(--el-border-color-lighter) !important;
}
</style>
