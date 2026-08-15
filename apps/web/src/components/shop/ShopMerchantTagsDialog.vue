<script setup>
/**
 * 编辑商家标签抽屉。对照 PRD 06-平台端UI.html#p02b-tags
 * 缺口：标签字典治理（重命名/归档）Phase2。
 */
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { adminApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  tenantId: { type: String, default: '' },
  displayName: { type: String, default: '' },
  selected: { type: Array, default: () => [] },
  readonly: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'success'])
const auth = useAuthStore()

const COMMON_NAMES = ['续费意向', '高价值', '需回访', '华东区', '对公客户']
const COLOR_TYPE = {
  orange: 'warning',
  gray: 'info',
  blue: '',
  purple: '',
  green: 'success',
}

const loading = ref(false)
const submitting = ref(false)
const dict = ref([])
const selectedIds = ref([])
const createInput = ref('')

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const canCreate = computed(() => auth.hasPlatformShopPermission('platform.shop.merchant.tag.manage'))

const selectedItems = computed(() =>
  dict.value.filter((t) => selectedIds.value.includes(t.id)),
)

const commonItems = computed(() =>
  dict.value.filter((t) => COMMON_NAMES.includes(t.name) && !t.is_archived),
)

async function loadDict() {
  loading.value = true
  try {
    const { data } = await adminApi.listShopMerchantTags()
    dict.value = data.items || []
    const fromDetail = (props.selected || []).map((t) => t.id || t).filter(Boolean)
    const byName = (props.selected || [])
      .map((t) => (typeof t === 'string' ? t : t.name))
      .filter(Boolean)
    const ids = new Set(fromDetail)
    for (const tag of dict.value) {
      if (byName.includes(tag.name)) ids.add(tag.id)
    }
    selectedIds.value = [...ids]
  } catch (e) {
    ElMessage.error(e.message || '加载标签失败')
    dict.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    createInput.value = ''
    loadDict()
  },
)

function toggle(id) {
  if (props.readonly) return
  const i = selectedIds.value.indexOf(id)
  if (i >= 0) selectedIds.value.splice(i, 1)
  else {
    if (selectedIds.value.length >= 20) {
      ElMessage.warning('标签过多')
      return
    }
    selectedIds.value.push(id)
  }
}

function remove(id) {
  selectedIds.value = selectedIds.value.filter((x) => x !== id)
}

async function save() {
  if (props.readonly) {
    visible.value = false
    return
  }
  const names = []
  const extra = createInput.value.trim()
  if (extra) {
    if (!canCreate.value) {
      ElMessage.warning('请联系运营创建标签')
      return
    }
    if (extra.length < 2 || extra.length > 12) {
      ElMessage.warning('标签名须为 2～12 字')
      return
    }
    names.push(extra)
  }
  if (selectedIds.value.length + names.length > 20) {
    ElMessage.warning('标签过多')
    return
  }
  submitting.value = true
  try {
    await adminApi.putShopMerchantTags(props.tenantId, {
      tag_ids: selectedIds.value,
      create_names: names,
    })
    ElMessage.success('已保存')
    emit('success')
    visible.value = false
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="编辑标签" width="480px" destroy-on-close>
    <div v-loading="loading" data-testid="shop-merchant-tags">
      <el-form label-width="110px">
        <el-form-item label="商家（只读）">{{ displayName }}</el-form-item>
        <el-form-item label="已选标签">
          <div class="chip-wrap">
            <el-tag
              v-for="tag in selectedItems"
              :key="tag.id"
              closable
              :disable-transitions="true"
              :type="COLOR_TYPE[tag.color] || 'info'"
              size="small"
              @close="remove(tag.id)"
            >
              {{ tag.name }}
            </el-tag>
            <span v-if="!selectedItems.length" class="hint">点击 × 解除；至少保留 0 个</span>
          </div>
        </el-form-item>
        <el-form-item label="添加标签">
          <el-select
            v-model="selectedIds"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="输入或选择…"
            style="width: 100%"
            :disabled="readonly"
            :multiple-limit="20"
          >
            <el-option v-for="tag in dict" :key="tag.id" :label="tag.name" :value="tag.id" />
          </el-select>
          <el-input
            v-if="canCreate && !readonly"
            v-model="createInput"
            placeholder="回车创建新标签（仅运营）"
            style="margin-top: 8px"
            maxlength="12"
            @keyup.enter="save"
          />
          <div v-else class="hint">搜索并选择已有标签。新建仅运营可操作；管家无权限时请联系运营创建标签</div>
        </el-form-item>
        <el-form-item label="常用（点击添加）">
          <div class="chip-wrap">
            <el-tag
              v-for="tag in commonItems"
              :key="tag.id"
              size="small"
              effect="plain"
              class="common-chip"
              @click="toggle(tag.id)"
            >
              {{ tag.name }}
            </el-tag>
          </div>
        </el-form-item>
        <el-form-item label="规则（只读）">
          <div class="hint">单商家最多 20 个标签；同名标签全站复用；清退商家只读不可改</div>
        </el-form-item>
      </el-form>
    </div>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button v-if="!readonly" type="primary" :loading="submitting" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.chip-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  min-height: 32px;
}
.hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}
.common-chip {
  cursor: pointer;
}
</style>
