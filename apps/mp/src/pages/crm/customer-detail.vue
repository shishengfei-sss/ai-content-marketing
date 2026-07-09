<script setup>
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { crmApi, teamApi } from '@/utils/api'
import { ensureSession } from '@/utils/session'
import { hasPermission } from '@/utils/permissions'
import CrmEntityTasks from '@/components/crm/CrmEntityTasks.vue'

const customerId = ref('')
const loading = ref(false)
const customer = ref(null)
const contacts = ref([])
const activities = ref([])
const tasks = ref([])
const taskPanelRef = ref(null)
const permissions = ref([])
const members = ref([])

const activityForm = ref({ content: '' })
const assignVisible = ref(false)
const selectedOwner = ref('')

const canActivity = () => hasPermission(permissions.value, 'crm.activity.create')
const canAssign = () => hasPermission(permissions.value, 'crm.customer.assign')

const ownerLabel = computed(() => {
  if (!customer.value?.owner_user_id) return '未分配'
  const m = members.value.find((x) => x.user_id === customer.value.owner_user_id)
  return m?.display_name || m?.phone || '负责人'
})

async function loadDetail() {
  if (!customerId.value) return
  loading.value = true
  try {
    const user = await ensureSession()
    permissions.value = user?.permissions || []
    if (canAssign()) {
      try {
        members.value = await teamApi.listMembers()
        if (!Array.isArray(members.value)) members.value = []
      } catch {
        members.value = []
      }
    }
    const [custData, contactList, timeline] = await Promise.all([
      crmApi.getCustomer(customerId.value),
      crmApi.listContacts(customerId.value),
      crmApi.listActivities({ customer_id: customerId.value }),
    ])
    customer.value = custData
    contacts.value = Array.isArray(contactList) ? contactList : []
    activities.value = Array.isArray(timeline) ? timeline : []
    await taskPanelRef.value?.reload()
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function openAssign() {
  selectedOwner.value = customer.value?.owner_user_id || ''
  assignVisible.value = true
}

async function submitAssign() {
  if (!selectedOwner.value) {
    uni.showToast({ title: '请选择负责人', icon: 'none' })
    return
  }
  try {
    await crmApi.updateCustomer(customerId.value, { owner_user_id: selectedOwner.value })
    uni.showToast({ title: '已分配', icon: 'success' })
    assignVisible.value = false
    loadDetail()
  } catch (e) {
    uni.showToast({ title: e.message || '分配失败', icon: 'none' })
  }
}

async function submitActivity() {
  if (!activityForm.value.content.trim()) {
    uni.showToast({ title: '请填写跟进内容', icon: 'none' })
    return
  }
  try {
    await crmApi.createActivity({
      customer_id: customerId.value,
      activity_type: 'call',
      content: activityForm.value.content,
    })
    uni.showToast({ title: '已添加跟进', icon: 'success' })
    activityForm.value.content = ''
    activities.value = await crmApi.listActivities({ customer_id: customerId.value })
  } catch (e) {
    uni.showToast({ title: e.message || '失败', icon: 'none' })
  }
}

function onTasksChanged(list) {
  tasks.value = list
}

onLoad((query) => {
  customerId.value = query.id || ''
  loadDetail()
})
</script>

<template>
  <view class="page">
    <view v-if="loading" class="empty">加载中…</view>
    <view v-else-if="customer" class="card">
      <view class="head">
        <text class="title">{{ customer.company_name }}</text>
        <text class="status">{{ customer.status }}</text>
      </view>
      <text class="meta">{{ customer.mobile || '—' }}</text>
      <text class="meta">负责人：{{ ownerLabel }}</text>
      <view v-if="canAssign()" class="acts">
        <button class="btn btn--primary" size="mini" @click="openAssign">分配负责人</button>
      </view>
      <view v-if="contacts.length" class="contacts">
        <text v-for="item in contacts" :key="item.id" class="contact">
          {{ item.name || '联系人' }} · {{ item.mobile || '—' }}
        </text>
      </view>
    </view>

    <view class="section">
      <text class="section__title">跟进</text>
      <view v-if="canActivity()" class="form">
        <textarea
          v-model="activityForm.content"
          class="textarea"
          placeholder="跟进内容"
          :adjust-position="true"
          :cursor-spacing="20"
        />
        <button class="btn btn--primary" size="mini" hover-class="none" @tap="submitActivity">提交</button>
      </view>
      <view v-for="item in activities" :key="item.id" class="line">
        <text class="line__time">{{ item.created_at }}</text>
        <text>{{ item.content }}</text>
      </view>
      <view v-if="!activities.length" class="empty">暂无跟进</view>
    </view>

    <view class="section">
      <text class="section__title">任务</text>
      <CrmEntityTasks
        ref="taskPanelRef"
        entity-type="customer"
        :entity-id="customerId"
        @changed="onTasksChanged"
      />
    </view>

    <view v-if="assignVisible" class="mask" @click="assignVisible = false">
      <view class="dialog" @click.stop>
        <text class="dialog__title">分配负责人</text>
        <picker
          mode="selector"
          :range="members.map((m) => m.display_name || m.phone)"
          @change="(e) => (selectedOwner = members[e.detail.value]?.user_id || '')"
        >
          <view class="picker">{{ ownerLabel }}</view>
        </picker>
        <view class="dialog__acts">
          <button class="btn" @click="assignVisible = false">取消</button>
          <button class="btn btn--primary" @click="submitAssign">保存</button>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 12px;
}

.card {
  background: #fff;
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 12px;
}

.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title {
  font-size: 18px;
  font-weight: 600;
}

.status {
  font-size: 12px;
  color: #1677ff;
}

.meta {
  display: block;
  margin-top: 8px;
  color: #64748b;
  font-size: 13px;
}

.acts {
  margin-top: 10px;
}

.mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.dialog {
  width: 100%;
  max-width: 360px;
  background: #fff;
  border-radius: 12px;
  padding: 16px;
}

.dialog__title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
  display: block;
}

.picker {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 12px;
}

.dialog__acts {
  display: flex;
  gap: 10px;
}

.btn {
  flex: 1;
  font-size: 14px;
}

.contacts {
  margin-top: 8px;
}

.contact {
  display: block;
  font-size: 13px;
  color: #64748b;
  margin-top: 4px;
}

.section {
  background: #fff;
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 12px;
}

.section__title {
  font-weight: 600;
  margin-bottom: 10px;
  display: block;
}

.form {
  margin-bottom: 10px;
}

.input,
.textarea {
  width: 100%;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 8px;
  font-size: 14px;
  box-sizing: border-box;
  background: #fff;
  color: #1e293b;
  pointer-events: auto;
}

.input {
  min-height: 40px;
  height: 40px;
  line-height: 20px;
}

.textarea {
  min-height: 80px;
}

.line {
  padding: 8px 0;
  border-bottom: 1px solid #f1f5f9;
  font-size: 14px;
}

.line__time {
  display: block;
  color: #94a3b8;
  font-size: 12px;
}

.btn--primary {
  background: #1677ff;
  color: #fff;
}

.empty {
  text-align: center;
  color: #94a3b8;
  padding: 16px 0;
}
</style>
