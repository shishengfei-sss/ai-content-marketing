<script setup>
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { crmApi } from '../../api/client'
import { useTeamMembers } from '../../composables/useTeamMembers'

const props = defineProps({
  visible: { type: Boolean, default: false },
  entityType: { type: String, required: true },
  entityId: { type: String, default: '' },
  ownerUserId: { type: String, default: '' },
})

const emit = defineEmits(['update:visible', 'done'])

const { loadMembers, resolveMemberName, members: teamMembers } = useTeamMembers()
const selectedOwner = ref('')
const loading = ref(false)

const currentOwnerName = computed(() => resolveMemberName(props.ownerUserId, { withSelfTag: false }))
const members = computed(() => teamMembers.value.filter((m) => m.is_active))

watch(
  () => props.visible,
  async (open) => {
    if (!open) return
    selectedOwner.value = props.ownerUserId || ''
    loading.value = true
    try {
      await loadMembers(true)
    } catch (e) {
      ElMessage.error(e.message || '加载成员失败')
    } finally {
      loading.value = false
    }
  },
)

async function submit() {
  if (!selectedOwner.value) {
    ElMessage.warning('请选择负责人')
    return
  }
  try {
    const payload = { owner_user_id: selectedOwner.value }
    if (props.entityType === 'lead') {
      await crmApi.updateLead(props.entityId, payload)
    } else if (props.entityType === 'campaign') {
      await crmApi.updateCampaign(props.entityId, payload)
    } else {
      await crmApi.updateCustomer(props.entityId, payload)
    }
    ElMessage.success('已更新负责人')
    emit('update:visible', false)
    emit('done')
  } catch (e) {
    ElMessage.error(e.message || '分配失败')
  }
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="分配负责人"
    width="400px"
    @update:model-value="emit('update:visible', $event)"
  >
    <p v-if="ownerUserId" class="assign-owner__current">
      当前负责人：<strong>{{ currentOwnerName }}</strong>
    </p>
    <el-select v-model="selectedOwner" v-loading="loading" placeholder="选择成员" style="width: 100%">
      <el-option
        v-for="m in members"
        :key="m.user_id"
        :label="m.display_name || m.phone"
        :value="m.user_id"
      />
    </el-select>
    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button type="primary" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.assign-owner__current {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.assign-owner__current strong {
  color: var(--el-text-color-primary);
}
</style>
