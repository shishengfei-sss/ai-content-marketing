<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authApi } from '../api/client'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loginMode = ref('password')
const phone = ref('')
const password = ref('')
const smsCode = ref('')
const loading = ref(false)
const sendingCode = ref(false)
const countdown = ref(0)
const mockHint = ref('')
let countdownTimer = null

const phonePattern = /^1\d{10}$/

function afterLoginSuccess() {
  ElMessage.success('登录成功')
  if (auth.user?.role === 'platform_admin') {
    router.push('/admin')
  } else {
    router.push('/dashboard')
  }
}

async function handlePasswordLogin() {
  if (!phone.value || !password.value) {
    ElMessage.warning('请输入手机号和密码')
    return
  }
  loading.value = true
  try {
    await auth.login(phone.value.trim(), password.value)
    afterLoginSuccess()
  } catch (e) {
    ElMessage.error(e.message || '登录失败')
  } finally {
    loading.value = false
  }
}

function startCountdown() {
  countdown.value = 60
  clearInterval(countdownTimer)
  countdownTimer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0) clearInterval(countdownTimer)
  }, 1000)
}

async function handleSendCode() {
  if (!phonePattern.test(phone.value.trim())) {
    ElMessage.warning('请输入正确的手机号')
    return
  }
  if (countdown.value > 0) return
  sendingCode.value = true
  try {
    const { data } = await authApi.sendSmsCode(phone.value.trim())
    mockHint.value = data.mock_hint || ''
    ElMessage.success(data.message || '验证码已发送')
    startCountdown()
  } catch (e) {
    ElMessage.error(e.message || '发送失败')
  } finally {
    sendingCode.value = false
  }
}

async function handleSmsLogin() {
  if (!phonePattern.test(phone.value.trim())) {
    ElMessage.warning('请输入正确的手机号')
    return
  }
  if (!smsCode.value.trim()) {
    ElMessage.warning('请输入验证码')
    return
  }
  loading.value = true
  try {
    await auth.loginBySms(phone.value.trim(), smsCode.value.trim())
    afterLoginSuccess()
  } catch (e) {
    ElMessage.error(e.message || '登录失败')
  } finally {
    loading.value = false
  }
}

function handleSubmit() {
  if (loginMode.value === 'password') {
    handlePasswordLogin()
  } else {
    handleSmsLogin()
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

      <el-segmented v-model="loginMode" :options="[
        { label: '密码登录', value: 'password' },
        { label: '验证码登录', value: 'sms' },
      ]" block style="margin-bottom: 20px" />

      <el-form label-position="top" @submit.prevent="handleSubmit">
        <el-form-item label="手机号">
          <el-input
            v-model="phone"
            placeholder="请输入手机号"
            size="large"
            maxlength="11"
          />
        </el-form-item>

        <el-form-item v-if="loginMode === 'password'" label="密码">
          <el-input
            v-model="password"
            type="password"
            placeholder="请输入密码"
            size="large"
            show-password
          />
        </el-form-item>

        <el-form-item v-else label="验证码">
          <div class="sms-row">
            <el-input
              v-model="smsCode"
              placeholder="请输入验证码"
              size="large"
              maxlength="6"
            />
            <el-button
              size="large"
              :disabled="countdown > 0"
              :loading="sendingCode"
              @click="handleSendCode"
            >
              {{ countdown > 0 ? `${countdown}s` : '获取验证码' }}
            </el-button>
          </div>
          <p v-if="mockHint" class="mock-hint">{{ mockHint }}</p>
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          style="width: 100%"
          :loading="loading"
          @click="handleSubmit"
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
  margin-bottom: 24px;
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

.sms-row {
  display: flex;
  gap: 12px;
  width: 100%;
}

.sms-row .el-input {
  flex: 1;
}

.mock-hint {
  margin: 8px 0 0;
  font-size: 12px;
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
