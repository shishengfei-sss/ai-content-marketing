<script setup>
/**
 * A09-A/B/C 写操作弹窗。对照 PRD 01-管理端UI.html #a09a #a09b #a09c · #a09-select-spec
 * 列表 A09 / 详情 A10 共用。
 */
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api/client'

const emit = defineEmits(['done'])

const CLOSE_REASONS = [
  { value: 'buyer_abandon', label: '买家放弃' },
  { value: 'wrong_duplicate', label: '错拍重复' },
  { value: 'merchant_cancel', label: '商家取消' },
  { value: 'other', label: '其他' },
]
const REFUND_REASONS = [
  { value: 'buyer_request', label: '买家申请' },
  { value: 'wrong_order', label: '错拍' },
  { value: 'fulfill_dispute', label: '履约纠纷' },
  { value: 'other', label: '其他' },
]

const closeVisible = ref(false)
const refundVisible = ref(false)
const resendVisible = ref(false)
const submitting = ref(false)
const order = ref(null)
const invoiceHint = ref(null)

const closeForm = reactive({ reason_code: '', reason_text: '' })
const refundForm = reactive({ reason_code: '', remark: '' })

const orderTail = computed(() => {
  const no = order.value?.order_no || ''
  return no.length > 3 ? `…${no.slice(-3)}` : no || '—'
})

const refundAmountLabel = computed(() => {
  const cents = order.value?.paid_amount_cents ?? order.value?.amount_cents ?? 0
  return `¥${(cents / 100).toFixed(2)}（全额，Phase 1 不可改）`
})

const resendMobile = computed(
  () => order.value?.buyer_mobile_masked || order.value?.buyer_mobile || '买家手机'
)

function resetForms() {
  closeForm.reason_code = ''
  closeForm.reason_text = ''
  refundForm.reason_code = ''
  refundForm.remark = ''
  invoiceHint.value = null
}

function openClose(row) {
  resetForms()
  order.value = row
  closeVisible.value = true
}

async function openRefund(row) {
  resetForms()
  order.value = row
  if (row.invoice_status === 'issued') {
    try {
      const { data } = await api.get('/api/v1/shop/invoices', {
        params: { q: row.order_no, page: 1, page_size: 5 },
      })
      const hit = (data.items || []).find(
        (i) => i.order_id === row.id || i.order_no === row.order_no
      )
      if (hit) {
        invoiceHint.value = {
          invoice_no: hit.invoice_no || '—',
          amount: `¥${((hit.amount_cents ?? row.paid_amount_cents ?? row.amount_cents) / 100).toFixed(2)}`,
        }
      } else {
        invoiceHint.value = {
          invoice_no: '—',
          amount: `¥${((row.paid_amount_cents ?? row.amount_cents) / 100).toFixed(2)}`,
        }
      }
    } catch {
      invoiceHint.value = {
        invoice_no: '—',
        amount: `¥${((row.paid_amount_cents ?? row.amount_cents) / 100).toFixed(2)}`,
      }
    }
  }
  refundVisible.value = true
}

function openResend(row) {
  resetForms()
  order.value = row
  resendVisible.value = true
}

function validateOther(code, text) {
  if (code !== 'other') return true
  if ((text || '').trim().length < 4) {
    ElMessage.warning('其他原因至少 4 字')
    return false
  }
  return true
}

async function submitClose() {
  if (!closeForm.reason_code) {
    ElMessage.warning('请选择关闭原因')
    return
  }
  if (!validateOther(closeForm.reason_code, closeForm.reason_text)) return
  submitting.value = true
  try {
    await api.post(`/api/v1/shop/orders/${order.value.id}/close`, {
      reason_code: closeForm.reason_code,
      reason_text: closeForm.reason_text || null,
    })
    ElMessage.success('已关闭')
    closeVisible.value = false
    emit('done')
  } catch (e) {
    ElMessage.error(e.message || '关闭失败')
  } finally {
    submitting.value = false
  }
}

async function submitRefund() {
  if (!refundForm.reason_code) {
    ElMessage.warning('请选择退款原因')
    return
  }
  if (!validateOther(refundForm.reason_code, refundForm.remark)) return
  submitting.value = true
  try {
    await api.post(`/api/v1/shop/orders/${order.value.id}/refund`, {
      reason_code: refundForm.reason_code,
      remark: refundForm.remark || null,
    })
    ElMessage.success('退款成功')
    refundVisible.value = false
    emit('done')
  } catch (e) {
    ElMessage.error(e.message || '退款失败')
  } finally {
    submitting.value = false
  }
}

async function submitResend() {
  submitting.value = true
  try {
    await api.post(`/api/v1/shop/orders/${order.value.id}/resend-notify`, {})
    ElMessage.success('已重发')
    resendVisible.value = false
    emit('done')
  } catch (e) {
    ElMessage.error(e.message || '重发失败')
  } finally {
    submitting.value = false
  }
}

defineExpose({ openClose, openRefund, openResend })
</script>

<template>
  <!-- A09-A -->
  <el-dialog
    v-model="closeVisible"
    :title="`确认关闭订单 ${orderTail}？`"
    width="480px"
    destroy-on-close
  >
    <el-form label-position="top">
      <el-form-item label="关闭影响（只读）">
        <div class="readonly">关闭后买家不可再支付；未支付不产生权益</div>
      </el-form-item>
      <el-form-item label="关闭原因" required>
        <el-select v-model="closeForm.reason_code" placeholder="请选择" style="width: 100%">
          <el-option
            v-for="o in CLOSE_REASONS"
            :key="o.value"
            :label="o.label"
            :value="o.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="说明（选填）">
        <el-input
          v-model="closeForm.reason_text"
          type="textarea"
          :rows="2"
          maxlength="200"
          show-word-limit
          placeholder="选「其他」时必填且 ≥4 字"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="closeVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitClose">确认关闭</el-button>
    </template>
  </el-dialog>

  <!-- A09-B -->
  <el-dialog v-model="refundVisible" :title="`发起退款 · 订单 ${orderTail}`" width="480px" destroy-on-close>
    <el-alert
      v-if="order?.invoice_status === 'issued'"
      type="warning"
      :closable="false"
      show-icon
      class="inv-alert"
      title="本订单已开具发票，退款后须办理红冲"
    >
      <template #default>
        <div>
          发票号 <b>{{ invoiceHint?.invoice_no || '—' }}</b> · 金额
          <b>{{ invoiceHint?.amount || refundAmountLabel }}</b>
          （与买家实付一致，不含平台服务费）
        </div>
        <div class="inv-hint">
          退款成功后系统将标记需红冲，请安排财务在税控系统办理红冲。开票单状态保持「已开票」，不会自动冲红。
        </div>
      </template>
    </el-alert>
    <el-form label-position="top">
      <el-form-item label="退款金额" required>
        <div class="readonly">{{ refundAmountLabel }}</div>
      </el-form-item>
      <el-form-item label="退款原因" required>
        <el-select v-model="refundForm.reason_code" placeholder="请选择" style="width: 100%">
          <el-option
            v-for="o in REFUND_REASONS"
            :key="o.value"
            :label="o.label"
            :value="o.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="说明（选填）">
        <el-input
          v-model="refundForm.remark"
          type="textarea"
          :rows="2"
          maxlength="200"
          show-word-limit
          placeholder="选「其他」时必填且 ≥4 字"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="refundVisible = false">取消</el-button>
      <el-button type="danger" :loading="submitting" @click="submitRefund">提交退款</el-button>
    </template>
  </el-dialog>

  <!-- A09-C -->
  <el-dialog
    v-model="resendVisible"
    :title="`重发领权短信至 ${resendMobile}？`"
    width="480px"
    destroy-on-close
  >
    <el-form label-position="top">
      <el-form-item label="发送说明（只读）">
        <div class="readonly">将占用 1 条领权短信额度</div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="resendVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitResend">确认发送</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.readonly {
  color: #595959;
  font-size: 13px;
  line-height: 1.5;
}
.inv-alert {
  margin-bottom: 12px;
}
.inv-hint {
  margin-top: 6px;
  color: #8c8c8c;
  font-size: 12px;
  line-height: 1.5;
}
</style>
