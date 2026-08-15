<script setup>
/**
 * S-ACCOUNT 我的账号。对照 PRD 01#s-account（A16 文内）
 */
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api/client'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const saving = ref(false)
const form = reactive({
  display_name: '',
  phone: '',
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
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
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
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
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

    <el-form label-position="top" style="max-width: 420px">
      <el-form-item label="昵称" required>
        <el-input v-model="form.display_name" maxlength="30" show-word-limit />
      </el-form-item>
      <el-form-item label="登录手机号">
        <el-input :model-value="maskPhone(form.phone)" disabled />
        <div class="hint">只读 · 换绑后续开放</div>
      </el-form-item>
      <el-form-item label="修改密码">
        <el-button link type="primary" @click="router.push('/settings/preference')">
          去修改
        </el-button>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
        <el-button @click="load">取消</el-button>
      </el-form-item>
    </el-form>
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
.hint {
  font-size: 11px;
  color: #999;
  margin-top: 4px;
}
</style>
