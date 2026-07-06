<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authApi } from '../api/client'

const router = useRouter()
const phone = ref('')
const code = ref('')
const password = ref('')
const confirm = ref('')
const sending = ref(false)
const loading = ref(false)
const mockHint = ref('测试环境验证码：1111')

async function sendCode() {
  sending.value = true
  try {
    const { data } = await authApi.forgotSendCode(phone.value.trim())
    mockHint.value = data.mock_hint || mockHint.value
    ElMessage.success('验证码已发送')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    sending.value = false
  }
}

async function submit() {
  if (password.value !== confirm.value) {
    ElMessage.warning('两次密码不一致')
    return
  }
  loading.value = true
  try {
    await authApi.forgotReset({
      phone: phone.value.trim(),
      code: code.value.trim(),
      password: password.value,
    })
    ElMessage.success('密码已重置，请登录')
    router.push('/login')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="forgot-page">
    <div class="forgot-card">
      <h2>忘记密码</h2>
      <p class="hint">{{ mockHint }}</p>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="手机号">
          <el-input v-model="phone" maxlength="11" />
        </el-form-item>
        <el-form-item label="验证码">
          <div class="row">
            <el-input v-model="code" maxlength="6" />
            <el-button :loading="sending" @click="sendCode">获取验证码</el-button>
          </div>
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="password" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="confirm" type="password" show-password />
        </el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading" style="width: 100%">
          重置密码
        </el-button>
        <el-button link type="primary" @click="router.push('/login')">返回登录</el-button>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.forgot-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
}
.forgot-card {
  width: 420px;
  padding: 32px;
  background: #fff;
  border-radius: 12px;
}
.row {
  display: flex;
  gap: 8px;
  width: 100%;
}
.hint {
  color: #888;
  font-size: 13px;
  margin-bottom: 16px;
}
</style>
