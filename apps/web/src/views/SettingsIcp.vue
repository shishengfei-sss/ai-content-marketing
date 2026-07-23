<script setup>
import { onMounted, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { crmApi } from '../api/client'

const loading = ref(false)
const saving = ref(false)
const form = ref({
  target_industries: [],
  target_regions: [],
  company_size_min: null,
  company_size_max: null,
  min_budget_threshold: null,
  include_keywords: [],
  exclude_keywords: [],
  weight_industry: 30,
  weight_company_size: 20,
  weight_region: 15,
  weight_budget: 20,
  weight_urgency: 15,
  is_active: true,
})

const weightSum = computed(
  () =>
    Number(form.value.weight_industry || 0)
    + Number(form.value.weight_company_size || 0)
    + Number(form.value.weight_region || 0)
    + Number(form.value.weight_budget || 0)
    + Number(form.value.weight_urgency || 0),
)

async function load() {
  loading.value = true
  try {
    const { data } = await crmApi.getIcpConfig()
    if (data) {
      form.value = {
        target_industries: data.target_industries || [],
        target_regions: data.target_regions || [],
        company_size_min: data.company_size_min,
        company_size_max: data.company_size_max,
        min_budget_threshold: data.min_budget_threshold != null ? Number(data.min_budget_threshold) : null,
        include_keywords: data.include_keywords || [],
        exclude_keywords: data.exclude_keywords || [],
        weight_industry: data.weight_industry,
        weight_company_size: data.weight_company_size,
        weight_region: data.weight_region,
        weight_budget: data.weight_budget,
        weight_urgency: data.weight_urgency,
        is_active: data.is_active !== false,
      }
    }
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function save() {
  if (weightSum.value !== 100) {
    ElMessage.warning(`五维权重之和须为 100，当前 ${weightSum.value}`)
    return
  }
  saving.value = true
  try {
    await crmApi.saveIcpConfig({ ...form.value })
    ElMessage.success('已保存并重算匹配')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="page-card">
    <h2 class="title">ICP 画像配置</h2>
    <p class="hint">用于平台招标线索匹配打分。五维权重之和必须为 100%。保存后自动重算本租户匹配池。</p>

    <el-form label-width="120px" style="max-width: 720px">
      <el-form-item label="目标行业">
        <el-select v-model="form.target_industries" multiple filterable allow-create default-first-option style="width: 100%" placeholder="输入后回车" />
      </el-form-item>
      <el-form-item label="目标地区">
        <el-select v-model="form.target_regions" multiple filterable allow-create default-first-option style="width: 100%" placeholder="输入后回车" />
      </el-form-item>
      <el-form-item label="企业规模下限">
        <el-input-number v-model="form.company_size_min" :min="0" :controls="false" style="width: 100%" placeholder="人数下限" />
      </el-form-item>
      <el-form-item label="企业规模上限">
        <el-input-number v-model="form.company_size_max" :min="0" :controls="false" style="width: 100%" placeholder="人数上限" />
      </el-form-item>
      <el-form-item label="最低预算">
        <el-input-number v-model="form.min_budget_threshold" :min="0" :controls="false" style="width: 100%" />
      </el-form-item>
      <el-form-item label="包含关键词">
        <el-select v-model="form.include_keywords" multiple filterable allow-create default-first-option style="width: 100%" />
      </el-form-item>
      <el-form-item label="排除关键词">
        <el-select v-model="form.exclude_keywords" multiple filterable allow-create default-first-option style="width: 100%" />
      </el-form-item>

      <el-divider content-position="left">权重（合计 {{ weightSum }} / 100）</el-divider>
      <el-form-item label="行业">
        <el-input-number v-model="form.weight_industry" :min="0" :max="100" />
      </el-form-item>
      <el-form-item label="企业规模">
        <el-input-number v-model="form.weight_company_size" :min="0" :max="100" />
      </el-form-item>
      <el-form-item label="地区">
        <el-input-number v-model="form.weight_region" :min="0" :max="100" />
      </el-form-item>
      <el-form-item label="预算">
        <el-input-number v-model="form.weight_budget" :min="0" :max="100" />
      </el-form-item>
      <el-form-item label="紧迫度">
        <el-input-number v-model="form.weight_urgency" :min="0" :max="100" />
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="form.is_active" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<style scoped>
.title { margin: 0 0 8px; font-size: 18px; font-weight: 600; }
.hint { margin: 0 0 16px; font-size: 13px; color: var(--el-text-color-secondary); }
</style>
