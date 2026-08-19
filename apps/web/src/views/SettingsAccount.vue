<script setup>
/**
 * S-ACCOUNT 我的账号。对照 PRD 01#s-account（A16 文内）
 */
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api, { authApi } from '../api/client'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const saving = ref(false)
const form = reactive({
  display_name: '',
  phone: '',
})
const initialDisplayName = ref('')

const pwdDialogVisible = ref(false)
const pwdSending = ref(false)
const pwdSaving = ref(false)
const pwdMockHint = ref('')
const pwdForm = reactive({
  code: '',
  password: '',
  confirm: '',
})

function maskPhone(p) {
  if (!p || p.length < 7) return p || '—'
  return `${p.slice(0, 3)}****${p.slice(-4)}`
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/api/v1/auth/me')
    form.display_name = data.display_name || ''
    form.phone = data.phone || ''
    initialDisplayName.value = form.display_name
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function cancelEdit() {
  form.display_name = initialDisplayName.value
}

async function save() {
  const name = (form.display_name || '').trim()
  if (name.length < 2 || name.length > 30) {
    ElMessage.warning('昵称须为 2–30 字')
    return
  }
  saving.value = true
  try {
    await api.patch('/api/v1/auth/me', { display_name: name })
    await auth.fetchMe?.()
    if (auth.user) auth.user.display_name = name
    initialDisplayName.value = name
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

function openPasswordDialog() {
  if (!form.phone) {
    ElMessage.warning('未获取到登录手机号')
    return
  }
  pwdForm.code = ''
  pwdForm.password = ''
  pwdForm.confirm = ''
  pwdMockHint.value = ''
  pwdDialogVisible.value = true
}

async function sendPasswordCode() {
  pwdSending.value = true
  try {
    const { data } = await authApi.forgotSendCode(form.phone)
    pwdMockHint.value = data.mock_hint || ''
    ElMessage.success('验证码已发送')
  } catch (e) {
    ElMessage.error(e.message || '发送失败')
  } finally {
    pwdSending.value = false
  }
}

async function submitPasswordChange() {
  if (!pwdForm.code.trim()) {
    ElMessage.warning('请输入验证码')
    return
  }
  if (pwdForm.password.length < 8) {
    ElMessage.warning('密码至少 8 位')
    return
  }
  if (pwdForm.password !== pwdForm.confirm) {
    ElMessage.warning('两次密码不一致')
    return
  }
  pwdSaving.value = true
  try {
    await authApi.forgotReset({
      phone: form.phone,
      code: pwdForm.code.trim(),
      password: pwdForm.password,
    })
    pwdDialogVisible.value = false
    ElMessage.success('密码已修改，请使用新密码重新登录')
    auth.logout()
    router.push('/login')
  } catch (e) {
    ElMessage.error(e.message || '修改失败')
  } finally {
    pwdSaving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="page-card s-account">
    <div class="hd">
      <div>
        <div class="crumb">设置 / <b>我的账号</b></div>
        <h3>我的账号</h3>
      </div>
      <el-button @click="router.push('/shop/settings')">返回设置中心</el-button>
    </div>

    <el-form label-position="top" class="account-form">
      <el-form-item label="昵称" required>
        <el-input v-model="form.display_name" maxlength="30" show-word-limit />
      </el-form-item>
      <el-form-item label="登录手机号">
        <el-input :model-value="maskPhone(form.phone)" disabled />
        <div class="hint">只读 · 换绑后续开放</div>
      </el-form-item>
      <el-form-item label="修改密码">
        <el-button link type="primary" class="pwd-link" @click="openPasswordDialog">
          去修改
        </el-button>
      </el-form-item>
    </el-form>

    <div class="form-actions">
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      <el-button @click="cancelEdit">取消</el-button>
    </div>

    <el-dialog v-model="pwdDialogVisible" title="修改密码" width="440px" destroy-on-close>
      <p v-if="pwdMockHint" class="pwd-hint">{{ pwdMockHint }}</p>
      <el-form label-position="top">
        <el-form-item label="登录手机号">
          <el-input :model-value="maskPhone(form.phone)" disabled />
        </el-form-item>
        <el-form-item label="验证码" required>
          <div class="code-row">
            <el-input v-model="pwdForm.code" maxlength="6" placeholder="短信验证码" />
            <el-button :loading="pwdSending" @click="sendPasswordCode">获取验证码</el-button>
          </div>
        </el-form-item>
        <el-form-item label="新密码" required>
          <el-input
            v-model="pwdForm.password"
            type="password"
            show-password
            placeholder="至少 8 位"
          />
        </el-form-item>
        <el-form-item label="确认密码" required>
          <el-input v-model="pwdForm.confirm" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="pwdSaving" @click="submitPasswordChange">确认修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.s-account .hd {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.s-account h3 {
  margin: 0;
  font-size: 18px;
}
.crumb {
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 2px;
}
.crumb b {
  color: #1677ff;
  font-weight: 600;
}
.account-form {
  max-width: 420px;
}
.hint {
  font-size: 11px;
  color: #999;
  margin-top: 4px;
}
.pwd-link {
  padding-left: 0;
}
.form-actions {
  max-width: 420px;
  margin-top: 8px;
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color-lighter);
  display: flex;
  gap: 8px;
}
.pwd-hint {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.code-row {
  display: flex;
  gap: 8px;
  width: 100%;
}
</style>
