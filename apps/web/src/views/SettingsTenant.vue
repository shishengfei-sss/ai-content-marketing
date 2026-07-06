<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { shouldSilenceLoadError, tenantApi, isRouteNotFoundError } from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const loading = ref(false)
const saving = ref(false)
const form = ref({
  name: '',
  industry_code: 'finance',
  credit_code: '',
})

function applyActiveTenantFallback() {
  const tenant = auth.user?.active_tenant
  if (!tenant) return false
  form.value = {
    name: tenant.name || '',
    industry_code: tenant.industry_code || 'finance',
    credit_code: form.value.credit_code || '',
  }
  return true
}

async function load() {
  loading.value = true
  try {
    if (!auth.user && auth.isLoggedIn) {
      await auth.fetchMe()
    }
    const { data } = await tenantApi.getProfile()
    form.value = {
      name: data.name,
      industry_code: data.industry_code,
      credit_code: data.credit_code || '',
    }
  } catch (e) {
    if (shouldSilenceLoadError(e)) {
      applyActiveTenantFallback()
      return
    }
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!form.value.name.trim()) {
    ElMessage.warning('请填写公司名称')
    return
  }
  if (form.value.name.trim().length < 2) {
    ElMessage.warning('公司名称至少 2 个字符')
    return
  }
  saving.value = true
  try {
    await tenantApi.updateProfile({
      name: form.value.name.trim(),
      industry_code: form.value.industry_code,
      credit_code: form.value.credit_code || null,
    })
    ElMessage.success('已保存')
    await auth.fetchMe()
    await load()
  } catch (e) {
    if (isRouteNotFoundError(e)) {
      ElMessage.error('企业信息接口不可用，请重启后端 API 并确认 Web 代理端口一致')
      return
    }
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="page-card" style="max-width: 640px">
    <el-form label-width="120px" @submit.prevent="save">
      <el-form-item label="公司名称">
        <el-input v-model="form.name" maxlength="200" />
      </el-form-item>
      <el-form-item label="主行业">
        <el-select v-model="form.industry_code" style="width: 100%">
          <el-option label="财税 / 代理记账" value="finance" />
          <el-option label="法律" value="legal" />
        </el-select>
      </el-form-item>
      <el-form-item label="统一社会信用代码">
        <el-input v-model="form.credit_code" maxlength="18" placeholder="选填，18 位" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>
