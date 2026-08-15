<script setup>
/** 对照 PRD 06#p06e · #p02b-payment 进件材料只读区 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { formatDateTime } from '../../utils/datetime'

const props = defineProps({
  detail: { type: Object, default: null },
  variant: { type: String, default: 'p06e' },
  canChannel: { type: Boolean, default: false },
  acting: { type: Boolean, default: false },
})

const emit = defineEmits([
  'refresh',
  'submit-wechat',
  'notify',
  'reveal',
  'approve',
  'reject',
])

const router = useRouter()

const materialLabels = {
  id_card_front: '身份证正面',
  id_card_back: '身份证反面',
  business_license: '营业执照',
  legal_id_front: '法人证正面',
  legal_id_back: '法人证反面',
  bank_permit: '对公账户',
  icp: 'ICP 备案 / 类目资质',
  handheld: '手持照',
}

const statusTag = {
  not_submitted: 'info',
  submitted: 'warning',
  rejected: 'danger',
  approved: 'success',
}

const entity = computed(() => props.detail?.entity || {})
const files = computed(() => {
  const raw = props.detail?.qualification_files || {}
  return Object.entries(raw).map(([key, fileId]) => ({
    key,
    label: materialLabels[key] || key,
    fileId: String(fileId || ''),
  }))
})
const actions = computed(() => props.detail?.actions || [])
const isP02b = computed(() => props.variant === 'p02b')

function goMaterials() {
  if (!props.detail?.tenant_id) return
  router.push(`/admin/shop/merchants/${props.detail.tenant_id}?tab=materials`)
}

function goP06() {
  if (!props.detail?.tenant_id) return
  router.push({
    path: '/admin/shop/channels',
    query: { tab: 'onboarding', tenant_id: props.detail.tenant_id },
  })
}

function goList() {
  router.push({ path: '/admin/shop/channels', query: { tab: 'onboarding' } })
}

function goAudit() {
  if (!props.detail?.tenant_id) return
  router.push(`/admin/shop/merchants/${props.detail.tenant_id}?tab=audit`)
}
</script>

<template>
  <div v-if="detail" class="pay-panel">
    <div class="pay-head">
      <el-tag :type="statusTag[detail.onboarding_status] || 'info'" size="large">
        {{ detail.onboarding_status_label }}
      </el-tag>
      <span v-if="detail.onboarding_status === 'approved'" class="muted">
        子商户号 {{ detail.wx_sub_mch_id_masked || '—' }}
        <span v-if="detail.approved_at"> · {{ formatDateTime(detail.approved_at, { withSeconds: false }) }} 微信审核通过</span>
      </span>
      <el-button v-if="isP02b" class="ml-auto" @click="goP06">进件详情 →</el-button>
    </div>

    <div v-if="!isP02b" class="stat-row">
      <div class="stat-card">
        <div class="k">提交时间</div>
        <b>{{ formatDateTime(detail.submitted_at, { withSeconds: false }) }}</b>
      </div>
      <div class="stat-card">
        <div class="k">子商户号</div>
        <b>{{ detail.wx_sub_mch_id_masked || '—' }}</b>
        <span v-if="detail.onboarding_status === 'submitted'" class="muted">（待微信下发）</span>
      </div>
      <div class="stat-card">
        <div class="k">最近刷新</div>
        <b>{{ formatDateTime(detail.last_refresh_at, { withSeconds: false }) }}</b>
      </div>
    </div>

    <div v-if="detail.onboarding_status === 'rejected' && detail.reject_reason" class="reject-box">
      驳回原因：{{ detail.reject_reason }}
    </div>

    <el-descriptions :column="2" border class="block">
      <el-descriptions-item v-if="isP02b" label="进件状态（只读）">
        <el-tag :type="statusTag[detail.onboarding_status] || 'info'" size="small">
          {{ detail.onboarding_status_label }}
        </el-tag>
      </el-descriptions-item>
      <el-descriptions-item v-if="isP02b" label="子商户号（只读）">
        {{ detail.wx_sub_mch_id_masked || '—' }}
      </el-descriptions-item>
      <el-descriptions-item label="主体名称（只读）">{{ entity.legal_name || '—' }}</el-descriptions-item>
      <el-descriptions-item label="统一社会信用代码（只读）">
        {{ entity.unified_social_credit_code || '—' }}
      </el-descriptions-item>
      <el-descriptions-item label="法人姓名（只读）">{{ entity.legal_rep_name || '—' }}</el-descriptions-item>
      <el-descriptions-item label="主体类型（只读）">{{ entity.entity_type_label || detail.entity_type_label || '—' }}</el-descriptions-item>
      <el-descriptions-item label="结算开户行（只读）">{{ detail.settlement_bank || '—' }}</el-descriptions-item>
      <el-descriptions-item label="开户名（只读）">{{ detail.settlement_account_name || '—' }}</el-descriptions-item>
      <el-descriptions-item label="结算账号（脱敏）" :span="2">
        <span>{{ detail.settlement_account || detail.settlement_account_masked || '—' }}</span>
        <el-button
          v-if="detail.settlement_account_masked && !detail.settlement_account"
          link
          type="primary"
          title="查看完整账号"
          @click="emit('reveal')"
        >
          👁
        </el-button>
      </el-descriptions-item>
      <el-descriptions-item v-if="isP02b" label="最近提交（只读）" :span="2">
        {{ formatDateTime(detail.submitted_at, { withSeconds: false }) }}
        <span v-if="detail.submitted_at"> · 商家 A15 提交</span>
      </el-descriptions-item>
      <el-descriptions-item label="资质证照（只读）" :span="2">
        <div v-if="files.length" class="mat-list">
          <div v-for="m in files" :key="m.key">
            <template v-if="m.fileId">
              {{ m.label }}
              <el-tag size="small" type="success">已提交</el-tag>
              ·
              <el-button link type="primary" @click="goMaterials">预览</el-button>
            </template>
            <template v-else>{{ m.label }}：未归档</template>
          </div>
        </div>
        <span v-else>未归档 · 与入驻材料主体一致时请到入驻材料 Tab 查看</span>
        <el-button link type="primary" @click="goMaterials">入驻材料</el-button>
      </el-descriptions-item>
      <el-descriptions-item v-if="!isP02b" label="商家补充说明（只读）" :span="2">
        {{ detail.remark || '—' }}
      </el-descriptions-item>
    </el-descriptions>

    <div class="section-label">{{ isP02b ? '状态时间线（只读）' : '开通状态时间线' }}</div>
    <div v-if="(detail.timeline || []).length" class="timeline">
      <div v-for="(ev, idx) in detail.timeline" :key="idx">
        {{ formatDateTime(ev.at, { withSeconds: false }) }} · {{ ev.event }}
      </div>
    </div>
    <el-empty v-else description="暂无时间线" :image-size="48" />

    <div class="ops">
      <el-button
        v-if="canChannel && (actions.includes('refresh') || detail.onboarding_status === 'submitted' || detail.onboarding_status === 'rejected')"
        type="primary"
        :loading="acting"
        @click="emit('refresh')"
      >
        刷新微信状态
      </el-button>
      <el-button
        v-if="!isP02b && canChannel && actions.includes('submit_wechat')"
        :loading="acting"
        @click="emit('submit-wechat')"
      >
        代提微信进件
      </el-button>
      <el-button
        v-if="!isP02b && canChannel && actions.includes('approve')"
        type="success"
        :loading="acting"
        @click="emit('approve')"
      >
        开通
      </el-button>
      <el-button
        v-if="!isP02b && canChannel && actions.includes('reject')"
        type="danger"
        :loading="acting"
        @click="emit('reject')"
      >
        驳回
      </el-button>
      <el-button
        v-if="!isP02b && (actions.includes('notify') || actions.includes('remind'))"
        :loading="acting"
        @click="emit('notify')"
      >
        {{ actions.includes('remind') ? '提醒商家' : '通知商家补充' }}
      </el-button>
      <el-button v-if="isP02b" @click="goList">进件列表</el-button>
      <el-button
        v-if="isP02b && actions.includes('remind')"
        :loading="acting"
        @click="emit('notify')"
      >
        提醒商家
      </el-button>
      <el-button v-if="!isP02b" @click="goAudit">查看操作日志</el-button>
    </div>
    <p v-if="detail.onboarding_status === 'not_submitted'" class="gap-note">
      未提交时仅可提醒商家在支付与进件补充材料。
    </p>
  </div>
  <el-empty v-else description="暂无进件记录" />
</template>

<style scoped>
.pay-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.ml-auto {
  margin-left: auto;
}
.muted {
  color: #666;
  font-size: 12px;
}
.stat-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 12px;
}
.stat-card {
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  padding: 8px 10px;
  background: #fff;
  font-size: 12px;
}
.stat-card .k {
  color: #666;
  margin-bottom: 4px;
}
.reject-box {
  background: #fff2f0;
  border: 1px solid #ffccc7;
  border-radius: 6px;
  padding: 8px 12px;
  margin-bottom: 12px;
  color: #a8071a;
  font-size: 13px;
}
.block {
  margin-bottom: 12px;
}
.section-label {
  font-size: 13px;
  font-weight: 600;
  margin: 8px 0;
}
.timeline {
  font-size: 12px;
  line-height: 1.9;
  padding: 10px;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  background: #fafafa;
  margin-bottom: 12px;
}
.ops {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.mat-list {
  font-size: 12px;
  line-height: 1.8;
}
.gap-note {
  color: #909399;
  font-size: 12px;
  margin-top: 8px;
}
@media (max-width: 720px) {
  .stat-row {
    grid-template-columns: 1fr;
  }
}
</style>
