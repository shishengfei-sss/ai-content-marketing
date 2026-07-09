<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import { crmApi } from '../../api/client'
import { useEntitySchema } from '../../composables/useEntitySchema'
import {
  emptyContactDraft,
  entityToFormValues,
  formValuesToPayload,
  getFormFields,
  validateLeadMobile,
} from '../../utils/entityForm'
import CrmEntityForm from './CrmEntityForm.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  entityType: { type: String, required: true },
  mode: { type: String, default: 'create' },
  record: { type: Object, default: null },
  /** 新建时预填字段，如 { campaign_id } */
  initialValues: { type: Object, default: null },
})

const emit = defineEmits(['update:visible', 'saved'])

const { fields, loadSchema } = useEntitySchema(props.entityType)
const formValues = ref({})
const contacts = ref([emptyContactDraft(true)])
const saving = ref(false)

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const isCustomerCreate = computed(
  () => props.entityType === 'customer' && props.mode === 'create',
)

const formEntityType = computed(() =>
  isCustomerCreate.value ? 'customer_create' : props.entityType,
)

const formFields = computed(() => getFormFields(fields.value, formEntityType.value))

const dialogTitle = computed(() => {
  const label = props.entityType === 'customer' ? '客户' : '线索'
  return props.mode === 'edit' ? `编辑${label}` : `新建${label}`
})

const dialogSubtitle = computed(() => {
  if (props.entityType === 'customer') {
    return props.mode === 'edit'
      ? '更新客户资料与业务信息'
      : '填写客户资料，并可同时添加多个联系人'
  }
  return props.mode === 'edit' ? '更新线索资料' : '录入潜在客户信息，便于后续跟进转化'
})

async function initForm() {
  await loadSchema()
  if (props.mode === 'edit' && props.record) {
    formValues.value = entityToFormValues(props.record, formFields.value)
  } else {
    formValues.value = entityToFormValues({}, formFields.value)
    if (props.entityType === 'lead') formValues.value.status = '待跟进'
    if (props.entityType === 'customer') formValues.value.status = '潜在'
    if (props.initialValues && typeof props.initialValues === 'object') {
      formValues.value = { ...formValues.value, ...props.initialValues }
    }
  }
  contacts.value = [emptyContactDraft(true)]
}

watch(
  () => props.visible,
  (open) => {
    if (open) initForm()
  },
)

function addContact() {
  contacts.value.push(emptyContactDraft(false))
}

function removeContact(index) {
  if (contacts.value.length <= 1) {
    contacts.value = [emptyContactDraft(true)]
    return
  }
  const removedPrimary = contacts.value[index]?.is_primary
  contacts.value.splice(index, 1)
  if (removedPrimary && contacts.value.length) {
    contacts.value[0].is_primary = true
  }
}

function setPrimaryContact(index) {
  contacts.value.forEach((c, i) => {
    c.is_primary = i === index
  })
}

function normalizeContactsPayload() {
  return contacts.value
    .map((c) => ({
      name: String(c.name || '').trim(),
      mobile: String(c.mobile || '').trim() || null,
      phone: String(c.phone || '').trim() || null,
      email: String(c.email || '').trim() || null,
      wechat: String(c.wechat || '').trim() || null,
      title: String(c.title || '').trim() || null,
      department: String(c.department || '').trim() || null,
      is_primary: !!c.is_primary,
      is_decision_maker: !!c.is_decision_maker,
    }))
    .filter((c) => c.name || c.mobile || c.phone || c.email || c.wechat || c.title)
}

function validateContacts(list) {
  if (!list.length) return null
  const named = list.filter((c) => c.name)
  if (!named.length) {
    return '请至少填写一位联系人姓名，或清空联系人区块'
  }
  for (const c of named) {
    if (!c.name) return '联系人姓名不能为空'
    if (c.mobile) {
      const err = validateLeadMobile(c.mobile, { required: false })
      if (err) return `联系人「${c.name}」${err}`
    }
  }
  if (!named.some((c) => c.is_primary)) {
    named[0].is_primary = true
  }
  return null
}

async function submit() {
  if (!String(formValues.value.company_name || '').trim()) {
    ElMessage.warning('请填写公司名称')
    return
  }
  if (props.entityType === 'lead') {
    if (!String(formValues.value.contact_name || '').trim()) {
      ElMessage.warning('请填写联系人姓名')
      return
    }
    const mobileErr = validateLeadMobile(formValues.value.mobile)
    if (mobileErr) {
      ElMessage.warning(mobileErr)
      return
    }
  }

  let contactPayloads = []
  if (isCustomerCreate.value) {
    contactPayloads = normalizeContactsPayload()
    const contactErr = validateContacts(contactPayloads)
    if (contactErr) {
      ElMessage.warning(contactErr)
      return
    }
  }

  saving.value = true
  try {
    const payload = formValuesToPayload(formEntityType.value, formValues.value, formFields.value)
    if (props.entityType === 'lead' && payload.mobile) {
      payload.mobile = String(payload.mobile).trim()
    }

    if (props.mode === 'edit') {
      if (props.entityType === 'lead') {
        await crmApi.updateLead(props.record.id, payload)
      } else {
        await crmApi.updateCustomer(props.record.id, payload)
      }
      ElMessage.success('保存成功')
    } else if (props.entityType === 'lead') {
      await crmApi.createLead(payload)
      ElMessage.success('线索已创建，请在详情中「转化客户」后出现在客户列表')
    } else {
      // 用首要联系人同步客户主联系方式
      const primary = contactPayloads.find((c) => c.is_primary) || contactPayloads[0]
      if (primary) {
        if (primary.mobile) payload.mobile = primary.mobile
        if (primary.phone) payload.phone = primary.phone
        if (primary.email) payload.email = primary.email
        if (primary.wechat) {
          payload.extra_data = { ...(payload.extra_data || {}), wechat: primary.wechat }
        }
      }
      const { data: customer } = await crmApi.createCustomer(payload)
      for (const c of contactPayloads.filter((x) => x.name)) {
        await crmApi.createContact(customer.id, c)
      }
      ElMessage.success(
        contactPayloads.filter((x) => x.name).length
          ? `客户已创建，已添加 ${contactPayloads.filter((x) => x.name).length} 位联系人`
          : '客户已创建',
      )
    }
    dialogVisible.value = false
    emit('saved')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    width="820px"
    top="3vh"
    destroy-on-close
    align-center
    class="crm-entity-form-dialog"
  >
    <template #header>
      <div class="crm-entity-form-dialog__header">
        <div class="crm-entity-form-dialog__badge" aria-hidden="true">
          {{ entityType === 'customer' ? '客' : '线' }}
        </div>
        <div>
          <h3 class="crm-entity-form-dialog__title">{{ dialogTitle }}</h3>
          <p class="crm-entity-form-dialog__subtitle">{{ dialogSubtitle }}</p>
        </div>
      </div>
    </template>

    <el-scrollbar max-height="70vh">
      <el-form
        label-width="108px"
        require-asterisk-position="right"
        class="crm-entity-form-dialog__body"
        @submit.prevent
      >
        <CrmEntityForm
          v-model="formValues"
          :entity-type="entityType"
          :fields="formFields"
        />

        <section v-if="isCustomerCreate" class="crm-contacts-block">
          <div class="crm-contacts-block__head">
            <div>
              <div class="crm-contacts-block__title">联系人</div>
              <div class="crm-contacts-block__hint">可添加多位联系人，建议指定一位首要联系人</div>
            </div>
            <el-button type="primary" plain :icon="Plus" @click="addContact">添加联系人</el-button>
          </div>

          <div
            v-for="(contact, index) in contacts"
            :key="index"
            class="crm-contact-card"
            :class="{ 'crm-contact-card--primary': contact.is_primary }"
          >
            <div class="crm-contact-card__head">
              <div class="crm-contact-card__meta">
                <span class="crm-contact-card__index">联系人 {{ index + 1 }}</span>
                <el-tag v-if="contact.is_primary" size="small" type="primary" effect="light" round>
                  首要
                </el-tag>
                <el-tag v-if="contact.is_decision_maker" size="small" type="warning" effect="plain" round>
                  决策人
                </el-tag>
              </div>
              <div class="crm-contact-card__actions">
                <el-button
                  v-if="!contact.is_primary"
                  link
                  type="primary"
                  size="small"
                  @click="setPrimaryContact(index)"
                >
                  设为首要
                </el-button>
                <el-button
                  link
                  type="danger"
                  size="small"
                  :icon="Delete"
                  @click="removeContact(index)"
                >
                  删除
                </el-button>
              </div>
            </div>

            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="姓名" required>
                  <el-input v-model="contact.name" placeholder="联系人姓名" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="职位">
                  <el-input v-model="contact.title" placeholder="如：财务经理" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="手机">
                  <el-input v-model="contact.mobile" placeholder="11 位手机号" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="电话">
                  <el-input v-model="contact.phone" placeholder="固定电话" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="邮箱">
                  <el-input v-model="contact.email" placeholder="邮箱" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="微信">
                  <el-input v-model="contact.wechat" placeholder="微信号" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="部门">
                  <el-input v-model="contact.department" placeholder="所属部门" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="角色">
                  <el-checkbox v-model="contact.is_decision_maker">决策人</el-checkbox>
                </el-form-item>
              </el-col>
            </el-row>
          </div>
        </section>
      </el-form>
    </el-scrollbar>

    <template #footer>
      <div class="crm-entity-form-dialog__footer">
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.crm-entity-form-dialog__body {
  padding: 4px 8px 8px;
}

.crm-contacts-block {
  margin-top: 8px;
  padding: 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  background: linear-gradient(180deg, #fcfdff 0%, #f7f9fc 100%);
}

.crm-contacts-block__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.crm-contacts-block__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.crm-contacts-block__hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.crm-contact-card {
  padding: 14px 14px 2px;
  margin-bottom: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: #fff;
}

.crm-contact-card:last-child {
  margin-bottom: 0;
}

.crm-contact-card--primary {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 0 0 1px var(--el-color-primary-light-8);
}

.crm-contact-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.crm-contact-card__meta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.crm-contact-card__index {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-regular);
}

.crm-contact-card__actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.crm-entity-form-dialog__footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>

<style>
.crm-entity-form-dialog.el-dialog {
  border-radius: 16px;
  overflow: hidden;
}

.crm-entity-form-dialog .el-dialog__header {
  margin: 0;
  padding: 18px 24px 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.crm-entity-form-dialog .el-dialog__body {
  padding: 12px 16px 4px;
}

.crm-entity-form-dialog .el-dialog__footer {
  padding: 12px 24px 18px;
  border-top: 1px solid var(--el-border-color-lighter);
  background: #fafbfc;
}

.crm-entity-form-dialog__header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding-right: 28px;
}

.crm-entity-form-dialog__badge {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: linear-gradient(145deg, var(--el-color-primary-light-7), var(--el-color-primary-light-9));
  color: var(--el-color-primary);
  font-size: 14px;
  font-weight: 700;
}

.crm-entity-form-dialog__title {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  line-height: 1.35;
  color: var(--el-text-color-primary);
}

.crm-entity-form-dialog__subtitle {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.45;
  color: var(--el-text-color-secondary);
}
</style>
