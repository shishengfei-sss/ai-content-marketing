<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const displayName = ref('')
const phone = ref('')
const password = ref('')
const tenantName = ref('')
const loading = ref(false)

const phonePattern = /^1\d{10}$/

async function handleRegister() {
  const name = displayName.value.trim()
  const workspace = tenantName.value.trim()
  if (!name || !phone.value || !password.value || !workspace) {
    ElMessage.warning('请填写昵称、登录手机号、密码和工作台名称')
    return
  }
  if (name.length < 2) {
    ElMessage.warning('昵称至少 2 个字符')
    return
  }
  if (workspace.length < 2) {
    ElMessage.warning('工作台名称至少 2 个字符')
    return
  }
  if (!phonePattern.test(phone.value)) {
    ElMessage.warning('请输入正确的 11 位手机号')
    return
  }
  if (password.value.length < 8) {
    ElMessage.warning('密码至少 8 位')
    return
  }
  loading.value = true
  try {
    await auth.register({
      phone: phone.value,
      password: password.value,
      tenant_name: workspace,
      display_name: name,
    })
    ElMessage.success('注册成功')
    router.push('/dashboard')
  } catch (e) {
    ElMessage.error(e.message || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-card__brand">
        <span class="auth-card__logo">AI</span>
        <h1>注册账号</h1>
        <p>手机号注册 · 创建您的智营工作台</p>
      </div>
      <el-form label-position="top">
        <div class="auth-section-label">您的账号</div>
        <el-form-item label="昵称">
          <el-input
            v-model="displayName"
            placeholder="团队内显示的名称"
            size="large"
            maxlength="100"
          />
        </el-form-item>
        <el-form-item label="登录手机号">
          <el-input
            v-model="phone"
            placeholder="用于登录与接收重要通知"
            size="large"
            maxlength="11"
          />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="password"
            type="password"
            placeholder="至少 8 位"
            size="large"
            show-password
          />
        </el-form-item>
        <div class="auth-section-label">您的工作台</div>
        <el-form-item label="工作台名称">
          <el-input
            v-model="tenantName"
            placeholder="团队对外称呼，可与营业执照名称不同"
            size="large"
            maxlength="200"
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          style="width: 100%"
          :loading="loading"
          @click="handleRegister"
        >
          注册
        </el-button>
      </el-form>
      <p class="auth-card__note">
        注册即创建智营工作台与管理员账号；开通内容获客商城需在入驻流程中提交主体资质（个人/个体/企业），由平台审核。
      </p>
      <div class="auth-card__footer">
        已有账号？
        <router-link to="/login">去登录</router-link>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1677ff 0%, #0958d9 100%);
}

.auth-card {
  width: 400px;
  background: #fff;
  border-radius: var(--radius-card);
  padding: 40px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
}

.auth-card__brand {
  text-align: center;
  margin-bottom: 32px;
}

.auth-card__logo {
  display: inline-flex;
  width: 48px;
  height: 48px;
  background: var(--color-primary);
  color: #fff;
  border-radius: 8px;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 18px;
  margin-bottom: 12px;
}

.auth-card__brand h1 {
  font-size: 24px;
  margin-bottom: 4px;
}

.auth-card__brand p {
  color: var(--color-text-secondary);
  font-size: 14px;
}

.auth-section-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
  margin: 4px 0 8px;
  letter-spacing: 0.02em;
}

.auth-card__note {
  margin-top: 16px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--color-text-muted);
}

.auth-card__footer {
  margin-top: 20px;
  text-align: center;
  font-size: 14px;
  color: var(--color-text-secondary);
}

.auth-card__footer a {
  color: var(--color-primary);
}
</style>
