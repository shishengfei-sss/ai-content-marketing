<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { agentApi, shouldSilenceLoadError } from '../api/client'
import { useAuthStore } from '../stores/auth'
import { hasPermission } from '../config/permissions'

const auth = useAuthStore()
const loading = ref(false)
const activeTab = ref('user')
const userMemories = ref([])
const tenantMemories = ref([])

const isAdmin = computed(() => hasPermission(auth.permissions, 'tenant.manage'))

const pendingMemories = computed(() =>
  userMemories.value.filter((m) => m.source === 'inferred' && !m.is_confirmed)
)

const categoryLabel = (c) =>
  ({ preference: '偏好', style: '风格', brand: '品牌', industry: '行业' }[c] || c)

function sourceLabel(m) {
  return m.source === 'inferred' ? 'AI 推断' : '手动'
}

async function loadMemories() {
  loading.value = true
  try {
    const [userRes, tenantRes] = await Promise.all([
      agentApi.listMemories({ scope: 'user' }),
      agentApi.listMemories({ scope: 'tenant' }),
    ])
    userMemories.value = userRes.data || []
    tenantMemories.value = tenantRes.data || []
  } catch (e) {
    if (!shouldSilenceLoadError(e)) {
      ElMessage.error(e.message || '加载失败')
    }
  } finally {
    loading.value = false
  }
}

function canDelete(item) {
  if (item.scope === 'user') return true
  return isAdmin.value
}

async function handleConfirm(item) {
  try {
    await agentApi.confirmMemory(item.id)
    ElMessage.success('已确认并记住')
    await loadMemories()
  } catch (e) {
    ElMessage.error(e.message || '确认失败')
  }
}

async function handleDelete(item) {
  try {
    await ElMessageBox.confirm('删除后 Agent 将不再使用这条记忆，确定删除？', '删除记忆', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await agentApi.deleteMemory(item.id)
    ElMessage.success('已删除')
    await loadMemories()
  } catch (e) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error(e.message || '删除失败')
    }
  }
}

onMounted(loadMemories)
</script>

<template>
  <div class="page-card" v-loading="loading">
    <h2 style="margin: 0 0 8px">AI 记忆</h2>
    <p style="color: #666; margin-bottom: 16px; font-size: 14px">
      Agent 在创作时会参考已确认的记忆。与「我的偏好」不同，此处为结构化事实条目。
    </p>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="我的记忆" name="user">
        <el-empty v-if="!userMemories.length" description="暂无个人记忆" />
        <div v-for="item in userMemories" :key="item.id" class="memory-item">
          <div class="memory-item__body">
            <div class="memory-item__text">{{ item.fact_text }}</div>
            <div class="memory-item__meta">
              <el-tag size="small" type="info">{{ sourceLabel(item) }}</el-tag>
              <el-tag v-if="!item.is_confirmed" size="small" type="warning">待确认</el-tag>
              <span>{{ categoryLabel(item.category) }}</span>
            </div>
          </div>
          <div class="memory-item__actions">
            <el-button
              v-if="item.source === 'inferred' && !item.is_confirmed"
              type="primary"
              link
              @click="handleConfirm(item)"
            >
              确认
            </el-button>
            <el-button type="danger" link @click="handleDelete(item)">删除</el-button>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="企业记忆" name="tenant">
        <el-alert
          v-if="!isAdmin"
          type="info"
          :closable="false"
          show-icon
          title="企业记忆全公司可见；仅管理员可删除。"
          style="margin-bottom: 12px"
        />
        <el-empty v-if="!tenantMemories.length" description="暂无企业记忆" />
        <div v-for="item in tenantMemories" :key="item.id" class="memory-item">
          <div class="memory-item__body">
            <div class="memory-item__text">{{ item.fact_text }}</div>
            <div class="memory-item__meta">
              <el-tag size="small" type="info">{{ sourceLabel(item) }}</el-tag>
              <span>{{ categoryLabel(item.category) }}</span>
            </div>
          </div>
          <div v-if="canDelete(item)" class="memory-item__actions">
            <el-button type="danger" link @click="handleDelete(item)">删除</el-button>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane name="pending">
        <template #label>
          待确认
          <el-badge v-if="pendingMemories.length" :value="pendingMemories.length" class="tab-badge" />
        </template>
        <el-empty v-if="!pendingMemories.length" description="暂无待确认的 AI 推断记忆" />
        <div v-for="item in pendingMemories" :key="item.id" class="memory-item">
          <div class="memory-item__body">
            <div class="memory-item__text">{{ item.fact_text }}</div>
            <div class="memory-item__meta">
              <el-tag size="small" type="warning">AI 推断 · 待确认</el-tag>
            </div>
          </div>
          <div class="memory-item__actions">
            <el-button type="primary" link @click="handleConfirm(item)">确认并记住</el-button>
            <el-button type="danger" link @click="handleDelete(item)">不要记住</el-button>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.memory-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 0;
  border-bottom: 1px solid var(--color-border, #f0f0f0);
}

.memory-item__text {
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 8px;
}

.memory-item__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--color-text-secondary, #999);
}

.memory-item__actions {
  flex-shrink: 0;
  display: flex;
  gap: 4px;
}

.tab-badge {
  margin-left: 6px;
}
</style>
