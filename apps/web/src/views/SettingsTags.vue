<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../api/client'
import { formatApiError } from '../utils/apiError'
import { formatDateTime } from '../utils/datetime'

const loading = ref(false)
const saving = ref(false)
const tags = ref([])
const dialogVisible = ref(false)
const editingId = ref(null)
const form = ref({ name: '', color: '#409EFF', category: '' })

const COLOR_PRESETS = ['#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#909399', '#9B59B6']

function resetForm() {
  editingId.value = null
  form.value = { name: '', color: '#409EFF', category: '' }
}

async function load() {
  loading.value = true
  try {
    const { data } = await crmApi.listTags()
    tags.value = Array.isArray(data) ? data : []
  } catch (e) {
    ElMessage.error(formatApiError(e, '加载标签失败'))
  } finally {
    loading.value = false
  }
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.value = {
    name: row.name || '',
    color: row.color || '#409EFF',
    category: row.category || '',
  }
  dialogVisible.value = true
}

async function save() {
  if (!form.value.name.trim()) {
    ElMessage.warning('请填写标签名称')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.value.name.trim(),
      color: form.value.color || null,
      category: form.value.category?.trim() || null,
    }
    if (editingId.value) {
      await crmApi.updateTag(editingId.value, payload)
      ElMessage.success('标签已更新')
    } else {
      await crmApi.createTag(payload)
      ElMessage.success('标签已创建')
    }
    dialogVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(formatApiError(e, '保存失败'))
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      `删除标签「${row.name}」？已绑定的线索/客户等会同步去掉该标签。`,
      '确认删除',
      { type: 'warning' },
    )
    await crmApi.deleteTag(row.id)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(formatApiError(e, '删除失败'))
  }
}

onMounted(load)
</script>

<template>
  <div class="page-card">
    <div class="page-head">
      <div>
        <h2>业务标签</h2>
        <p class="hint">
          在此维护标签字典；线索、客户、商机等详情页只能选择已有标签，不可临时新建。
        </p>
      </div>
      <el-button type="primary" @click="openCreate">新建标签</el-button>
    </div>

    <el-table v-loading="loading" :data="tags" border>
      <el-table-column label="颜色" width="80" align="center">
        <template #default="{ row }">
          <span class="color-dot" :style="{ background: row.color || '#909399' }" />
        </template>
      </el-table-column>
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column prop="category" label="分类" width="140">
        <template #default="{ row }">{{ row.category || '—' }}</template>
      </el-table-column>
      <el-table-column label="创建时间" width="170">
        <template #default="{ row }">
          {{ formatDateTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" align="center" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && !tags.length" description="暂无标签，请先新建" />

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑标签' : '新建标签'"
      width="440px"
      destroy-on-close
    >
      <el-form label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" maxlength="50" show-word-limit placeholder="如：高意向" />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="form.category" maxlength="50" placeholder="可选，如：意向 / 行业" />
        </el-form-item>
        <el-form-item label="颜色">
          <div class="color-row">
            <button
              v-for="c in COLOR_PRESETS"
              :key="c"
              type="button"
              class="color-swatch"
              :class="{ 'is-active': form.color === c }"
              :style="{ background: c }"
              @click="form.color = c"
            />
            <el-color-picker v-model="form.color" />
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;
}
.page-head h2 {
  margin: 0 0 6px;
  font-size: 18px;
}
.hint {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.color-dot {
  display: inline-block;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  vertical-align: middle;
}
.color-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.color-swatch {
  width: 22px;
  height: 22px;
  border: 2px solid transparent;
  border-radius: 4px;
  cursor: pointer;
  padding: 0;
}
.color-swatch.is-active {
  border-color: var(--el-text-color-primary);
}
</style>
