<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)

async function selectTenant(tenantId) {
  loading.value = true
  try {
    await auth.selectTenant(tenantId)
    ElMessage.success('已进入工作空间')
    router.push('/dashboard')
  } catch (e) {
    ElMessage.error(e.message || '选择失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="select-page">
    <div class="select-card">
      <h2>选择公司</h2>
      <p class="hint">您的账号加入了多家公司，请选择要进入的工作空间</p>
      <el-space direction="vertical" fill style="width: 100%">
        <el-button
          v-for="t in auth.user?.tenants || []"
          :key="t.id"
          size="large"
          style="width: 100%; justify-content: flex-start"
          :loading="loading"
          @click="selectTenant(t.id)"
        >
          <div class="tenant-item">
            <strong>{{ t.name }}</strong>
            <span>{{ t.role_name }}</span>
          </div>
        </el-button>
      </el-space>
    </div>
  </div>
</template>

<style scoped>
.select-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
}
.select-card {
  width: 420px;
  padding: 32px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
}
.hint {
  color: #666;
  margin-bottom: 20px;
}
.tenant-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}
.tenant-item span {
  font-size: 12px;
  color: #888;
}
</style>
