<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const visible = ref(false)
const loading = ref(false)
const items = ref([])
const unread = ref(0)
let pollTimer = null

const badge = computed(() => (unread.value > 99 ? '99+' : unread.value || ''))

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

async function openPanel() {
  visible.value = true
  await loadList()
}

async function markOne(row) {
  if (row.is_read) {
    navigateEntity(row)
    return
  }
  try {
    await crmApi.markNotificationRead(row.id)
    row.is_read = true
    unread.value = Math.max(0, unread.value - 1)
    navigateEntity(row)
  } catch (e) {
    ElMessage.error(e.message || '标记失败')
  }
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

function navigateEntity(row) {
  if (!row.entity_type || !row.entity_id) return
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
  if (!v) return ''
  return String(v).replace('T', ' ').slice(0, 16)
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
  <el-popover :visible="visible" placement="bottom-end" :width="380" trigger="click" @update:visible="(v) => (visible = v)">
    <template #reference>
      <el-badge :value="badge" :hidden="!unread" class="notif-badge">
        <el-button class="notif-btn" text bg @click="openPanel">
          <el-icon :size="18"><Bell /></el-icon>
        </el-button>
      </el-badge>
    </template>
    <div class="notif-panel">
      <div class="notif-panel__head">
        <span>通知</span>
        <el-button link type="primary" size="small" :disabled="!unread" @click="markAll">全部已读</el-button>
      </div>
      <div v-loading="loading" class="notif-panel__body">
        <div
          v-for="row in items"
          :key="row.id"
          class="notif-item"
          :class="{ 'is-unread': !row.is_read }"
          @click="markOne(row)"
        >
          <div class="notif-item__title">{{ row.title }}</div>
          <div v-if="row.body" class="notif-item__body">{{ row.body }}</div>
          <div class="notif-item__time">{{ formatTime(row.created_at) }}</div>
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
.notif-panel__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-weight: 600;
}
.notif-panel__body {
  max-height: 360px;
  overflow: auto;
}
.notif-item {
  padding: 10px 8px;
  border-radius: 8px;
  cursor: pointer;
}
.notif-item:hover {
  background: var(--el-fill-color-light);
}
.notif-item.is-unread {
  background: var(--el-color-primary-light-9);
}
.notif-item__title {
  font-size: 13px;
  font-weight: 600;
}
.notif-item__body {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
}
.notif-item__time {
  margin-top: 4px;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}
</style>
