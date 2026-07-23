<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { crmApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import { hasAnyPermission } from '../../config/permissions'

const props = defineProps({
  entityType: { type: String, required: true },
  entityId: { type: String, required: true },
  editable: { type: Boolean, default: false },
})

const router = useRouter()
const auth = useAuthStore()

const loading = ref(false)
const saving = ref(false)
const entityTags = ref([])
const allTags = ref([])
const selectValue = ref('')

const canManageCatalog = computed(() =>
  hasAnyPermission(auth.permissions, ['crm.schema.manage', 'crm.pipeline.manage', 'crm.lead.edit', 'crm.customer.edit']),
)

async function load() {
  if (!props.entityId) return
  loading.value = true
  try {
    const [{ data: bound }, { data: catalog }] = await Promise.all([
      crmApi.listEntityTags({ entity_type: props.entityType, entity_id: props.entityId }),
      crmApi.listTags(),
    ])
    entityTags.value = Array.isArray(bound) ? bound : []
    allTags.value = Array.isArray(catalog) ? catalog : []
  } catch {
    entityTags.value = []
    allTags.value = []
  } finally {
    loading.value = false
  }
}

const unboundTags = () => {
  const boundIds = new Set(entityTags.value.map((t) => t.tag_id))
  return allTags.value.filter((t) => !boundIds.has(t.id))
}

async function bindExisting(tagId) {
  if (!tagId) return
  saving.value = true
  try {
    await crmApi.bindEntityTag({
      entity_type: props.entityType,
      entity_id: props.entityId,
      tag_id: tagId,
    })
    selectValue.value = ''
    await load()
  } catch (e) {
    ElMessage.error(e.message || '绑定失败')
  } finally {
    saving.value = false
  }
}

async function unbind(tag) {
  saving.value = true
  try {
    await crmApi.unbindEntityTag({
      entity_type: props.entityType,
      entity_id: props.entityId,
      tag_id: tag.tag_id,
    })
    await load()
  } catch (e) {
    ElMessage.error(e.message || '移除失败')
  } finally {
    saving.value = false
  }
}

function goSettings() {
  router.push('/settings/tags')
}

watch(
  () => [props.entityType, props.entityId],
  () => load(),
)

onMounted(load)

defineExpose({ reload: load })
</script>

<template>
  <div v-loading="loading" class="crm-entity-tags">
    <el-tag
      v-for="tag in entityTags"
      :key="tag.id"
      :closable="editable"
      :disable-transitions="false"
      class="crm-entity-tags__tag"
      @close="unbind(tag)"
    >
      {{ tag.tag_name }}
    </el-tag>

    <template v-if="editable">
      <el-select
        v-if="unboundTags().length"
        v-model="selectValue"
        clearable
        filterable
        placeholder="选择标签"
        size="small"
        class="crm-entity-tags__select"
        :disabled="saving"
        @change="bindExisting"
      >
        <el-option
          v-for="t in unboundTags()"
          :key="t.id"
          :label="t.name"
          :value="t.id"
        />
      </el-select>
      <el-button
        v-if="canManageCatalog"
        size="small"
        link
        type="primary"
        @click="goSettings"
      >
        {{ allTags.length ? '管理标签' : '去设置添加标签' }}
      </el-button>
      <span v-else-if="!allTags.length" class="crm-entity-tags__empty">
        暂无可用标签，请联系管理员在设置中维护
      </span>
    </template>

    <span v-if="!entityTags.length && !editable" class="crm-entity-tags__empty">暂无标签</span>
  </div>
</template>

<style scoped>
.crm-entity-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  min-height: 28px;
}
.crm-entity-tags__tag { margin: 0; }
.crm-entity-tags__select { width: 160px; }
.crm-entity-tags__empty {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
</style>
