<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { shopApi } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import ShopMaterialUpload from '../../components/shop/ShopMaterialUpload.vue'

const router = useRouter()
const auth = useAuthStore()

const loading = ref(false)
const submitting = ref(false)
const status = ref(null)
/** 展示用文件名：docType -> name */
const fileNames = ref({})
/** fileId -> blob object URL */
const previewUrls = ref({})

const ENTITY_CARDS = [
  {
    value: 'personal',
    title: '个人',
    desc: '以个人身份开通，需身份证信息',
  },
  {
    value: 'individual_business',
    title: '个体工商户',
    desc: '需营业执照、信用代码与法人信息',
  },
  {
    value: 'enterprise',
    title: '企业',
    desc: '需营业执照、法人及对公相关信息',
  },
]

const form = ref({
  entity_type: 'personal',
  legal_name: '',
  display_name: '',
  contact_name: '',
  contact_mobile: '',
  id_no: '',
  unified_social_credit_code: '',
  legal_rep_name: '',
  remark: '',
  qualification_files: {},
  ocr_results: [],
})

const state = computed(() => status.value?.state || 'not_onboarded')
const readonly = computed(() => state.value === 'reviewing')
const canEdit = computed(() => state.value === 'not_onboarded' || state.value === 'rejected')
const workspaceName = computed(
  () => auth.activeTenantName || status.value?.prefill?.tenant_name || '—',
)

function fileIdOf(docType) {
  const v = form.value.qualification_files?.[docType]
  if (!v) return ''
  if (typeof v === 'string') return v
  return v.file_id || ''
}

function fileNameOf(docType) {
  return fileNames.value[docType] || ''
}

function previewUrlOf(docType) {
  const id = fileIdOf(docType)
  return id ? previewUrls.value[id] || '' : ''
}

function revokePreviews() {
  Object.values(previewUrls.value).forEach((url) => {
    try {
      URL.revokeObjectURL(url)
    } catch {
      /* ignore */
    }
  })
  previewUrls.value = {}
}

async function loadMaterialPreviews() {
  revokePreviews()
  const ids = Object.values(form.value.qualification_files || {})
    .map((v) => (typeof v === 'string' ? v : v?.file_id || ''))
    .filter(Boolean)
  if (!ids.length) return
  const next = {}
  await Promise.all(
    ids.map(async (fileId) => {
      try {
        const { data } = await shopApi.downloadOnboardingFile(fileId)
        const blob = data instanceof Blob ? data : new Blob([data])
        next[fileId] = URL.createObjectURL(blob)
      } catch {
        /* 预览失败仍保留已上传状态 */
      }
    }),
  )
  previewUrls.value = next
}

function looksMasked(value) {
  return typeof value === 'string' && value.includes('*')
}

function applyPrefill(data) {
  const app = data.application
  const prefill = data.prefill
  if (app && (data.state === 'rejected' || data.state === 'reviewing')) {
    const qf = app.qualification_files || {}
    const names = {}
    const normalized = {}
    for (const [k, v] of Object.entries(qf)) {
      if (typeof v === 'string') {
        normalized[k] = v
        names[k] = '已上传文件'
      } else if (v && typeof v === 'object') {
        normalized[k] = v.file_id || ''
        names[k] = v.file_name || '已上传文件'
      }
    }
    const rejected = data.state === 'rejected'
    form.value = {
      entity_type: app.entity_type || 'personal',
      legal_name: app.legal_name || '',
      display_name: app.display_name || '',
      contact_name: app.contact_name || '',
      contact_mobile: rejected && looksMasked(app.contact_mobile) ? '' : (app.contact_mobile || ''),
      id_no: rejected && looksMasked(app.id_no) ? '' : (app.id_no || ''),
      unified_social_credit_code: app.unified_social_credit_code || '',
      legal_rep_name: app.legal_rep_name || '',
      remark: app.remark || '',
      qualification_files: normalized,
      ocr_results: app.ocr_results || [],
    }
    fileNames.value = names
    return
  }
  form.value.entity_type = 'personal'
  form.value.display_name = prefill?.display_name || auth.activeTenantName || ''
  form.value.contact_name = auth.user?.display_name || ''
  form.value.contact_mobile = auth.user?.phone || ''
  form.value.unified_social_credit_code = prefill?.unified_social_credit_code || ''
  form.value.legal_name = ''
  form.value.id_no = ''
  form.value.legal_rep_name = ''
  form.value.remark = ''
  form.value.qualification_files = {}
  form.value.ocr_results = []
  fileNames.value = {}
}

async function load() {
  loading.value = true
  try {
    const { data } = await shopApi.getOnboardingStatus()
    status.value = data
    applyPrefill(data)
    if (data.state === 'reviewing' || data.state === 'rejected') {
      await loadMaterialPreviews()
    } else {
      revokePreviews()
    }
  } catch (e) {
    ElMessage.error(e.message || '加载入驻状态失败')
  } finally {
    loading.value = false
  }
}

function onMaterialUploaded({ docType, fileId, fileName }) {
  form.value.qualification_files = {
    ...form.value.qualification_files,
    [docType]: fileId,
  }
  fileNames.value = { ...fileNames.value, [docType]: fileName }
}

function onMaterialCleared({ docType }) {
  const next = { ...form.value.qualification_files }
  delete next[docType]
  form.value.qualification_files = next
  const names = { ...fileNames.value }
  delete names[docType]
  fileNames.value = names
  form.value.ocr_results = (form.value.ocr_results || []).filter((r) => r.doc_type !== docType)
}

function onOcrFilled({ docType, fileId, fields, confidence, stub, raw }) {
  form.value.ocr_results = [
    ...(form.value.ocr_results || []).filter((r) => r.doc_type !== docType),
    {
      doc_type: docType,
      file_id: fileId,
      fields: fields || {},
      confidence,
      stub,
      ...(raw || {}),
    },
  ]
  if (docType === 'id_card_front' || docType === 'legal_id_front') {
    if (fields.name) {
      if (docType === 'id_card_front' && form.value.entity_type === 'personal') {
        form.value.legal_name = fields.name
      }
      if (docType === 'legal_id_front') {
        form.value.legal_rep_name = fields.name
      }
    }
    if (fields.id_no && docType === 'id_card_front') {
      form.value.id_no = fields.id_no
    }
  }
  if (docType === 'business_license') {
    if (fields.legal_name) form.value.legal_name = fields.legal_name
    if (fields.unified_social_credit_code) {
      form.value.unified_social_credit_code = fields.unified_social_credit_code
    }
    if (fields.legal_rep_name) form.value.legal_rep_name = fields.legal_rep_name
  }
}

function payload() {
  return {
    entity_type: form.value.entity_type,
    legal_name: form.value.legal_name,
    display_name: form.value.display_name || undefined,
    contact_name: form.value.contact_name,
    contact_mobile: form.value.contact_mobile,
    id_no: form.value.id_no || undefined,
    unified_social_credit_code: form.value.unified_social_credit_code || undefined,
    legal_rep_name: form.value.legal_rep_name || undefined,
    remark: form.value.remark || undefined,
    qualification_files: form.value.qualification_files || {},
    ocr_results: form.value.ocr_results || [],
  }
}

function validateBeforeSubmit() {
  if (!form.value.legal_name?.trim()) {
    ElMessage.warning('请填写主体名称')
    return false
  }
  if (!form.value.display_name?.trim()) {
    ElMessage.warning('请填写商家展示名')
    return false
  }
  if (!form.value.contact_name?.trim() || !form.value.contact_mobile?.trim()) {
    ElMessage.warning('请填写经营联系人与联系电话')
    return false
  }
  if (form.value.entity_type === 'personal') {
    if (!form.value.id_no?.trim()) {
      ElMessage.warning('请填写身份证号')
      return false
    }
    if (!fileIdOf('id_card_front')) {
      ElMessage.warning('请先选择并上传身份证正面')
      return false
    }
    if (!fileIdOf('id_card_back')) {
      ElMessage.warning('请先选择并上传身份证反面')
      return false
    }
  } else {
    if (!form.value.unified_social_credit_code?.trim() || !form.value.legal_rep_name?.trim()) {
      ElMessage.warning('请填写统一社会信用代码与法定代表人')
      return false
    }
    if (!fileIdOf('business_license')) {
      ElMessage.warning('请先选择并上传营业执照')
      return false
    }
    if (!fileIdOf('legal_id_front')) {
      ElMessage.warning('请先选择并上传法人身份证正面')
      return false
    }
    if (!fileIdOf('legal_id_back')) {
      ElMessage.warning('请先选择并上传法人身份证反面')
      return false
    }
  }
  return true
}

async function submit() {
  if (!validateBeforeSubmit()) return
  submitting.value = true
  try {
    if (state.value === 'rejected' && status.value?.application?.id) {
      await shopApi.resubmitOnboarding(status.value.application.id, payload())
      ElMessage.success('已重新提交，请等待平台审核')
    } else {
      await shopApi.submitOnboarding(payload())
      ElMessage.success('提交成功，请等待平台审核')
    }
    await load()
  } catch (e) {
    ElMessage.error(e.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

onMounted(load)
onBeforeUnmount(revokePreviews)
</script>

<template>
  <div v-loading="loading" class="page-card onboarding-apply">
    <el-alert
      v-if="state === 'reviewing'"
      type="warning"
      show-icon
      :closable="false"
      title="入驻申请审核中"
      description="资料已提交，暂不可修改。审核结果将通知到联系电话。"
      class="status-alert"
    />
    <el-alert
      v-if="state === 'rejected'"
      type="error"
      show-icon
      :closable="false"
      title="入驻申请未通过"
      :description="status?.application?.reject_reason || '请根据驳回原因修改后重新提交'"
      class="status-alert"
    />

    <el-result
      v-if="state === 'onboarded'"
      icon="success"
      title="已开通内容获客商城"
      sub-title="可继续使用智营工作台；商城经营功能将陆续开放。"
    >
      <template #extra>
        <el-button type="primary" @click="router.push('/dashboard')">返回工作台</el-button>
      </template>
    </el-result>

    <template v-if="state !== 'onboarded'">
      <div class="section-head">
        <span>选择主体类型</span>
        <el-tag type="info" size="small" effect="plain">工作台：{{ workspaceName }}</el-tag>
      </div>
      <el-radio-group
        v-model="form.entity_type"
        :disabled="readonly"
        class="entity-radios"
      >
        <el-radio-button
          v-for="card in ENTITY_CARDS"
          :key="card.value"
          :value="card.value"
        >
          {{ card.title }}
        </el-radio-button>
      </el-radio-group>
      <p class="entity-hint">
        {{ ENTITY_CARDS.find((c) => c.value === form.entity_type)?.desc }}
      </p>

      <el-divider content-position="left">填写入驻资料</el-divider>

      <el-form label-position="top" :disabled="readonly" @submit.prevent>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="主体名称" required>
              <el-input v-model="form.legal_name" placeholder="请与证照姓名或执照名称一致" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="商家展示名" required>
              <el-input v-model="form.display_name" placeholder="买家与运营看到的名称" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item v-if="form.entity_type === 'personal'" label="身份证号" required>
          <el-input
            v-model="form.id_no"
            :placeholder="state === 'rejected' ? '请重新填写身份证号（已脱敏）' : '请输入 18 位身份证号'"
            maxlength="18"
          />
        </el-form-item>
        <el-row v-else :gutter="16">
          <el-col :span="12">
            <el-form-item label="统一社会信用代码" required>
              <el-input v-model="form.unified_social_credit_code" placeholder="请输入信用代码" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="法定代表人" required>
              <el-input v-model="form.legal_rep_name" placeholder="请输入法定代表人姓名" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="经营联系人" required>
              <el-input v-model="form.contact_name" placeholder="审核与服务联系人" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系电话" required>
              <el-input
                v-model="form.contact_mobile"
                maxlength="11"
                :placeholder="state === 'rejected' ? '请重新填写联系电话（已脱敏）' : '用于接收审核通知'"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="资质材料" required>
          <p class="form-tip">
            {{ readonly ? '审核期间仅可查看已上传材料，不可修改。' : '请先选择文件上传；支持识别的材料可自动填入上方信息，请核对后再提交' }}
          </p>
          <div class="materials-list">
            <template v-if="form.entity_type === 'personal'">
              <ShopMaterialUpload
                doc-type="id_card_front"
                title="身份证正面"
                required
                ocr-enabled
                :disabled="readonly"
                :file-id="fileIdOf('id_card_front')"
                :file-name="fileNameOf('id_card_front')"
                :preview-url="previewUrlOf('id_card_front')"
                @uploaded="onMaterialUploaded"
                @ocr-filled="onOcrFilled"
                @cleared="onMaterialCleared"
              />
              <ShopMaterialUpload
                doc-type="id_card_back"
                title="身份证反面"
                required
                ocr-enabled
                :disabled="readonly"
                :file-id="fileIdOf('id_card_back')"
                :file-name="fileNameOf('id_card_back')"
                :preview-url="previewUrlOf('id_card_back')"
                @uploaded="onMaterialUploaded"
                @ocr-filled="onOcrFilled"
                @cleared="onMaterialCleared"
              />
              <ShopMaterialUpload
                doc-type="handheld"
                title="手持照"
                optional
                :disabled="readonly"
                :file-id="fileIdOf('handheld')"
                :file-name="fileNameOf('handheld')"
                :preview-url="previewUrlOf('handheld')"
                @uploaded="onMaterialUploaded"
                @cleared="onMaterialCleared"
              />
            </template>
            <template v-else>
              <ShopMaterialUpload
                doc-type="business_license"
                title="营业执照"
                required
                ocr-enabled
                :disabled="readonly"
                :file-id="fileIdOf('business_license')"
                :file-name="fileNameOf('business_license')"
                :preview-url="previewUrlOf('business_license')"
                @uploaded="onMaterialUploaded"
                @ocr-filled="onOcrFilled"
                @cleared="onMaterialCleared"
              />
              <ShopMaterialUpload
                doc-type="legal_id_front"
                title="法人身份证正面"
                required
                ocr-enabled
                :disabled="readonly"
                :file-id="fileIdOf('legal_id_front')"
                :file-name="fileNameOf('legal_id_front')"
                :preview-url="previewUrlOf('legal_id_front')"
                @uploaded="onMaterialUploaded"
                @ocr-filled="onOcrFilled"
                @cleared="onMaterialCleared"
              />
              <ShopMaterialUpload
                doc-type="legal_id_back"
                title="法人身份证反面"
                required
                ocr-enabled
                :disabled="readonly"
                :file-id="fileIdOf('legal_id_back')"
                :file-name="fileNameOf('legal_id_back')"
                :preview-url="previewUrlOf('legal_id_back')"
                @uploaded="onMaterialUploaded"
                @ocr-filled="onOcrFilled"
                @cleared="onMaterialCleared"
              />
              <ShopMaterialUpload
                v-if="form.entity_type === 'enterprise'"
                doc-type="bank_permit"
                title="对公账户"
                optional
                :disabled="readonly"
                :file-id="fileIdOf('bank_permit')"
                :file-name="fileNameOf('bank_permit')"
                :preview-url="previewUrlOf('bank_permit')"
                @uploaded="onMaterialUploaded"
                @cleared="onMaterialCleared"
              />
              <ShopMaterialUpload
                v-if="form.entity_type === 'enterprise'"
                doc-type="icp"
                title="ICP 备案 / 类目资质"
                optional
                :disabled="readonly"
                :file-id="fileIdOf('icp')"
                :file-name="fileNameOf('icp')"
                :preview-url="previewUrlOf('icp')"
                @uploaded="onMaterialUploaded"
                @cleared="onMaterialCleared"
              />
            </template>
          </div>
        </el-form-item>

        <el-form-item label="备注">
          <el-input
            v-model="form.remark"
            type="textarea"
            :rows="2"
            placeholder="选填，可补充说明"
          />
        </el-form-item>

        <div class="actions">
          <el-button
            v-if="canEdit"
            type="primary"
            :loading="submitting"
            @click="submit"
          >
            {{ state === 'rejected' ? '修改并重新提交' : '提交入驻申请' }}
          </el-button>
          <el-button @click="router.push('/dashboard')">取消</el-button>
        </div>
      </el-form>
    </template>
  </div>
</template>

<style scoped>
.onboarding-apply {
  max-width: 800px;
}

.status-alert {
  margin-bottom: 16px;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  font-weight: 600;
  color: #262626;
}

.entity-radios {
  margin-bottom: 8px;
}

.entity-hint {
  margin: 0 0 8px;
  font-size: 12px;
  color: #8c8c8c;
}

.form-tip {
  margin: 0 0 8px;
  font-size: 12px;
  color: #8c8c8c;
  line-height: 1.4;
}

.materials-list {
  width: 100%;
}

.actions {
  display: flex;
  gap: 12px;
  padding-top: 4px;
}
</style>
