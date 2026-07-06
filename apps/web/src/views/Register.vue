<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { assistantsApi } from '../api/client'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const phone = ref('')
const password = ref('')
const tenantName = ref('')
const industryCode = ref('finance')
const assistants = ref([])
const loading = ref(false)

const phonePattern = /^1\d{10}$/

onMounted(async () => {
  try {
    const { data } = await assistantsApi.list()
    assistants.value = data
    if (data.length) industryCode.value = data[0].code
  } catch {
    /* public list needs auth - fallback finance on register page before login */
  }
})

async function handleRegister() {
  if (!phone.value || !password.value || !tenantName.value.trim()) {
    ElMessage.warning('请填写手机号、密码和公司名称')
    return
  }
  if (tenantName.value.trim().length < 2) {
    ElMessage.warning('公司名称至少 2 个字符')
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
      tenant_name: tenantName.value.trim(),
      industry_code: industryCode.value,
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
        <p>手机号注册，一人一号专属工作台</p>
      </div>
      <el-form label-position="top">
        <el-form-item label="手机号">
          <el-input
            v-model="phone"
            placeholder="请输入 11 位手机号"
            size="large"
            maxlength="11"
          />
        </el-form-item>
        <el-form-item label="公司名称">
          <el-input
            v-model="tenantName"
            placeholder="请输入公司全称，全平台唯一"
            size="large"
            maxlength="200"
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
        <el-form-item v-if="assistants.length" label="默认 AI 助手">
          <el-select v-model="industryCode" size="large" style="width: 100%">
            <el-option
              v-for="a in assistants"
              :key="a.code"
              :label="a.name"
              :value="a.code"
            />
          </el-select>
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
