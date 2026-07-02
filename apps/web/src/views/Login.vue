<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const email = ref('')
const password = ref('')
const loading = ref(false)

async function handleLogin() {
  if (!email.value || !password.value) {
    ElMessage.warning('请输入邮箱和密码')
    return
  }
  loading.value = true
  try {
    await auth.login(email.value, password.value)
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch (e) {
    ElMessage.error(e.message || '登录失败')
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
        <h1>智营获客</h1>
        <p>AI 内容营销工作台</p>
      </div>
      <el-form label-position="top" @submit.prevent="handleLogin">
        <el-form-item label="邮箱">
          <el-input v-model="email" placeholder="admin@example.com" size="large" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="password"
            type="password"
            placeholder="请输入密码"
            size="large"
            show-password
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          style="width: 100%"
          :loading="loading"
          @click="handleLogin"
        >
          登录
        </el-button>
      </el-form>
      <div class="auth-card__footer">
        还没有账号？
        <router-link to="/register">立即注册</router-link>
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
