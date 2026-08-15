<script setup>
/**
 * 分配管家抽屉。对照 PRD 06-平台端UI.html#p02e
 * 单户 / 批量（已选 N 家，单次 ≤50）。缺口：改派站内信未接通。
 */
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi } from '../../api/client'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  tenantId: { type: String, default: '' },
  tenantIds: { type: Array, default: () => [] },
  displayName: { type: String, default: '' },
  currentManagerId: { type: String, default: '' },
  currentManagerName: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'success'])

const loading = ref(false)
const submitting = ref(false)
const csUsers = ref([])
const form = ref({ account_manager_user_id: '', remark: '' })

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const ids = computed(() => {
  const fromProp = (props.tenantIds || []).map((x) => String(x || '')).filter(Boolean)
  if (fromProp.length) return [...new Set(fromProp)]
  return props.tenantId ? [String(props.tenantId)] : []
})

const isBatch = computed(() => ids.value.length > 1)
const merchantLabel = computed(() => (isBatch.value ? `已选 ${ids.value.length} 家` : props.displayName))
const currentLabel = computed(() => {
  if (isBatch.value) return '以各行当前管家为准'
  return props.currentManagerName || '未分配'
})

async function loadUsers() {
  loading.value = true
  try {
    const { data } = await adminApi.listShopCsUsers()
    csUsers.value = data.items || []
  } catch (e) {
    ElMessage.error(e.message || '加载管家失败')
    csUsers.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    form.value = { account_manager_user_id: '', remark: '' }
    loadUsers()
  },
)

async function confirmAssign() {
  if (!form.value.account_manager_user_id) {
    ElMessage.warning('请选择新管家')
    return
  }
  if (!ids.value.length) {
    ElMessage.warning('请选择商家')
    return
  }
  if (ids.value.length > 50) {
    ElMessage.warning('单次最多分配 50 家')
    return
  }
  submitting.value = true
  try {
    if (isBatch.value) {
      const { data } = await adminApi.batchAssignShopMerchants({
        tenant_ids: ids.value,
        account_manager_user_id: form.value.account_manager_user_id,
        remark: form.value.remark || undefined,
      })
      ElMessage.success(`已分配 ${data.assigned || ids.value.length} 家`)
    } else {
      await adminApi.assignShopMerchant(ids.value[0], {
        account_manager_user_id: form.value.account_manager_user_id,
        remark: form.value.remark || undefined,
      })
      ElMessage.success('已分配')
    }
    emit('success')
    visible.value = false
  } catch (e) {
    ElMessage.error(e.message || '分配失败')
  } finally {
    submitting.value = false
  }
}

async function clearManager() {
  try {
    await ElMessageBox.confirm('确认清空管家？商家将进入未分配池。', '清空管家', {
      confirmButtonText: '确认清空',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  submitting.value = true
  try {
    await adminApi.assignShopMerchant(ids.value[0], { clear: true })
    ElMessage.success('已清空管家')
    emit('success')
    visible.value = false
  } catch (e) {
    ElMessage.error(e.message || '清空失败')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="分配商家管家" width="480px" destroy-on-close>
    <div v-loading="loading" data-testid="shop-assign-manager">
      <el-form label-width="120px">
        <el-form-item label="商家（只读）">
          {{ merchantLabel }}
        </el-form-item>
        <el-form-item label="当前管家（只读）">
          <span :class="{ 'text-muted': isBatch || !currentManagerName }">{{ currentLabel }}</span>
        </el-form-item>
        <el-form-item label="新管家" required>
          <el-select
            v-model="form.account_manager_user_id"
            filterable
            placeholder="请选择新管家"
            style="width: 100%"
          >
            <el-option
              v-for="u in csUsers"
              :key="u.id"
              :label="u.display_name"
              :value="u.id"
              :disabled="!isBatch && u.id === currentManagerId"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="备注（选填）">
          <el-input v-model="form.remark" type="textarea" :rows="2" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="影响说明（只读）">
          <div class="impact">
            ① 新管家「我的客户」可见该商家<br />
            ② 原管家不再看到该客户<br />
            ③ 写操作日志「分配管家」<br />
            ④ 在途流程不取消<br />
            ⑤ 在途若被运营取消/驳回，通知发给当时的当前管家
          </div>
        </el-form-item>
      </el-form>
    </div>
    <template #footer>
      <el-button v-if="!isBatch && currentManagerId" :disabled="submitting" @click="clearManager">
        清空管家
      </el-button>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="confirmAssign">确认分配</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.impact {
  font-size: 12px;
  line-height: 1.7;
  color: var(--el-text-color-regular);
  background: var(--el-fill-color-light);
  padding: 8px 10px;
  border-radius: 6px;
}
.text-muted {
  color: var(--el-text-color-placeholder);
}
</style>
