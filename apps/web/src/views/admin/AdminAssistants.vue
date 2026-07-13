<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { adminApi, isBenignEmptyError } from '../../api/client'

const loading = ref(false)
const saving = ref(false)
const items = ref([])
const searchQ = ref('')
const filterActive = ref('')
const dialogVisible = ref(false)
const editingCode = ref('')
const form = ref(emptyForm())

function emptyForm() {
  return {
    code: 'marketing',
    name: '通用营销创作顾问',
    description: '面向任意题材的营销内容创作与多平台发布准备',
    system_role:
      '你是通用营销创作顾问，帮助用户完成选题、写稿与发布准备。当前平台：{platform}，形态：{format}。',
    compliance_rules: `1. 内容必须合规，不得夸大承诺或误导用户
2. 必须包含免责声明（图文文末；视频脚本在最后一镜口播/字幕中体现）：{disclaimer}
3. 语气{tone}，适合目标受众阅读
4. 直接输出正文内容，不要输出 JSON 或多余解释`,
    disclaimer: '本文仅供参考，具体以相关部门最新规定为准',
    default_tone: '专业亲切',
    welcome_message:
      '您好，我是{assistant_name}。告诉我您想创作什么（公众号、小红书、抖音均可），或点击下方快捷选题开始。',
    sort_order: 0,
    is_active: true,
  }
}

async function loadItems() {
  loading.value = true
  try {
    const params = {}
    if (searchQ.value.trim()) params.q = searchQ.value.trim()
    if (filterActive.value !== '') params.is_active = filterActive.value
    const { data } = await adminApi.listAssistants(params)
    items.value = Array.isArray(data) ? data : []
  } catch (e) {
    if (isBenignEmptyError(e)) {
      items.value = []
    } else {
      ElMessage.error(e.message || '加载失败')
    }
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  searchQ.value = ''
  filterActive.value = ''
  loadItems()
}

function openCreate() {
  editingCode.value = ''
  form.value = emptyForm()
  dialogVisible.value = true
}

function openEdit(row) {
  editingCode.value = row.code
  form.value = { ...row }
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.value.name?.trim() || !form.value.system_role?.trim()) {
    ElMessage.warning('请填写名称与 System 角色')
    return
  }
  saving.value = true
  try {
    if (editingCode.value) {
      const { code, ...payload } = form.value
      await adminApi.updateAssistant(editingCode.value, payload)
      ElMessage.success('已更新')
    } else {
      if (!/^[a-z][a-z0-9_]*$/.test(form.value.code)) {
        ElMessage.warning('code 需为小写字母开头，仅含字母数字下划线')
        saving.value = false
        return
      }
      await adminApi.createAssistant(form.value)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    loadItems()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(loadItems)
</script>

<template>
  <div class="page-card">
    <el-alert
      title="营销顾问配置：管理通用创作顾问的 System Prompt、合规规则与欢迎语。创作页不再切换助手，统一使用 marketing 顾问。占位符：{platform} {format} {disclaimer} {tone} {assistant_name}"
      type="info"
      :closable="false"
      show-icon
    />
    <div class="toolbar">
      <el-input
        v-model="searchQ"
        placeholder="搜索 Code / 名称 / 简介"
        style="width: 240px"
        clearable
        @keyup.enter="loadItems"
        @clear="loadItems"
      />
      <el-select v-model="filterActive" placeholder="状态" clearable style="width: 120px">
        <el-option label="上架" :value="true" />
        <el-option label="下架" :value="false" />
      </el-select>
      <el-button type="primary" @click="loadItems">查询</el-button>
      <el-button @click="resetFilters">重置</el-button>
      <div class="toolbar__spacer" />
    </div>

    <el-table v-loading="loading" :data="items" stripe style="margin-top: 16px">
      <el-table-column prop="code" label="Code" width="120" />
      <el-table-column prop="name" label="名称" width="160" />
      <el-table-column prop="description" label="简介" min-width="200" show-overflow-tooltip />
      <el-table-column prop="sort_order" label="排序" width="70" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '上架' : '下架' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="editingCode ? `编辑营销顾问 · ${editingCode}` : '编辑营销顾问'"
      width="640px"
    >
      <el-form label-width="110px">
        <el-form-item v-if="!editingCode" label="Code">
          <el-input v-model="form.code" placeholder="如 legal、education" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="简介">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="System 角色">
          <el-input v-model="form.system_role" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="合规规则">
          <el-input v-model="form.compliance_rules" type="textarea" :rows="5" />
        </el-form-item>
        <el-form-item label="免责声明">
          <el-input v-model="form.disclaimer" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="默认语气">
          <el-input v-model="form.default_tone" />
        </el-form-item>
        <el-form-item label="欢迎语">
          <el-input v-model="form.welcome_message" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" :max="999" />
        </el-form-item>
        <el-form-item label="上架">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
  flex-wrap: wrap;
}

.toolbar__spacer {
  flex: 1;
}
</style>
