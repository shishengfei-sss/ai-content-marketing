<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi } from '../../api/client'

const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const statusFilter = ref('')
const searchQ = ref('')
const filterRegion = ref('')
const filterIndustry = ref('')
const filterCategory = ref('')
const filterMethod = ref('')
const filterAgent = ref('')
const filterProjectNo = ref('')
const filterSme = ref(null)
const filterDeadlineRange = ref([])
const filterPublishedRange = ref([])

const METHOD_OPTIONS = ['公开招标', '询价', '竞争性谈判', '竞争性磋商', '邀请招标', '单一来源']

const dialogVisible = ref(false)
const editing = ref(false)
const saving = ref(false)
const form = ref(emptyForm())

const excelVisible = ref(false)
const excelFile = ref(null)
const excelPreview = ref(null)
const excelBusy = ref(false)

const parseVisible = ref(false)
const parseStep = ref(0)
const parseBusy = ref(false)
const parseJobId = ref('')
const parseMode = ref('paste') // paste | file
const parsePasteText = ref('')
const parseForm = ref(emptyParseForm())
let parsePollTimer = null

function emptyParseForm() {
  return {
    buyer_name: '',
    industry: '',
    region: '',
    product_name: '',
    quantity: '',
    budget_min: null,
    budget_max: null,
    deadline: '',
    contact_name: '',
    contact_phone: '',
    source_url: '',
    summary: '',
    project_no: '',
    published_at: '',
    procurement_method: '',
    agent_name: '',
    buyer_address: '',
    category: '',
    bid_open_date: '',
    sme_preference: null,
    qualification_summary: '',
    max_price_limit: null,
    has_source_document: false,
  }
}

const STATUS_OPTIONS = [
  { value: 'draft', label: '草稿', type: 'info' },
  { value: 'published', label: '已发布', type: 'success' },
  { value: 'unpublished', label: '已下架', type: 'warning' },
]

function emptyForm() {
  return {
    id: '',
    buyer_name: '',
    industry: '',
    region: '',
    product_name: '',
    quantity: '',
    budget_min: null,
    budget_max: null,
    deadline: '',
    contact_name: '',
    contact_phone: '',
    source_url: '',
    summary: '',
    project_no: '',
    published_at: '',
    procurement_method: '',
    agent_name: '',
    buyer_address: '',
    category: '',
    bid_open_date: '',
    sme_preference: null,
    qualification_summary: '',
    max_price_limit: null,
    status: 'draft',
    has_source_document: true,
  }
}

function statusMeta(s) {
  return STATUS_OPTIONS.find((x) => x.value === s) || { label: s, type: '' }
}

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (statusFilter.value) params.status = statusFilter.value
    if (searchQ.value.trim()) params.q = searchQ.value.trim()
    if (filterRegion.value.trim()) params.region = filterRegion.value.trim()
    if (filterIndustry.value.trim()) params.industry = filterIndustry.value.trim()
    if (filterCategory.value.trim()) params.category = filterCategory.value.trim()
    if (filterMethod.value) params.procurement_method = filterMethod.value
    if (filterAgent.value.trim()) params.agent_name = filterAgent.value.trim()
    if (filterProjectNo.value.trim()) params.project_no = filterProjectNo.value.trim()
    if (filterSme.value !== null && filterSme.value !== undefined && filterSme.value !== '') {
      params.sme_preference = filterSme.value
    }
    if (filterDeadlineRange.value?.length === 2) {
      params.deadline_from = filterDeadlineRange.value[0]
      params.deadline_to = filterDeadlineRange.value[1]
    }
    if (filterPublishedRange.value?.length === 2) {
      params.published_from = filterPublishedRange.value[0]
      params.published_to = filterPublishedRange.value[1]
    }
    const { data } = await adminApi.listPlatformTenderLeads(params)
    items.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function onFilterChange() {
  page.value = 1
  load()
}

function resetFilters() {
  statusFilter.value = ''
  searchQ.value = ''
  filterRegion.value = ''
  filterIndustry.value = ''
  filterCategory.value = ''
  filterMethod.value = ''
  filterAgent.value = ''
  filterProjectNo.value = ''
  filterSme.value = null
  filterDeadlineRange.value = []
  filterPublishedRange.value = []
  onFilterChange()
}

function openCreate() {
  editing.value = false
  form.value = emptyForm()
  dialogVisible.value = true
}

function openEdit(row) {
  editing.value = true
  form.value = {
    id: row.id,
    buyer_name: row.buyer_name,
    industry: row.industry || '',
    region: row.region || '',
    product_name: row.product_name || '',
    quantity: row.quantity || '',
    budget_min: row.budget_min != null ? Number(row.budget_min) : null,
    budget_max: row.budget_max != null ? Number(row.budget_max) : null,
    deadline: row.deadline || '',
    contact_name: row.contact_name || '',
    contact_phone: row.contact_phone || '',
    source_url: row.source_url || '',
    summary: row.summary || '',
    project_no: row.project_no || '',
    published_at: row.published_at || '',
    procurement_method: row.procurement_method || '',
    agent_name: row.agent_name || '',
    buyer_address: row.buyer_address || '',
    category: row.category || '',
    bid_open_date: row.bid_open_date || '',
    sme_preference: row.sme_preference ?? null,
    qualification_summary: row.qualification_summary || '',
    max_price_limit: row.max_price_limit != null ? Number(row.max_price_limit) : null,
    status: row.status,
    has_source_document: !!row.source_url,
  }
  dialogVisible.value = true
}

function buildPayload() {
  return {
    buyer_name: form.value.buyer_name.trim(),
    industry: form.value.industry || null,
    region: form.value.region || null,
    product_name: form.value.product_name || null,
    quantity: form.value.quantity || null,
    budget_min: form.value.budget_min,
    budget_max: form.value.budget_max,
    deadline: form.value.deadline || null,
    contact_name: form.value.contact_name || null,
    contact_phone: form.value.contact_phone || null,
    source_url: form.value.source_url || null,
    summary: form.value.summary || null,
    project_no: form.value.project_no || null,
    published_at: form.value.published_at || null,
    procurement_method: form.value.procurement_method || null,
    agent_name: form.value.agent_name || null,
    buyer_address: form.value.buyer_address || null,
    category: form.value.category || null,
    bid_open_date: form.value.bid_open_date || null,
    sme_preference: form.value.sme_preference,
    qualification_summary: form.value.qualification_summary || null,
    max_price_limit: form.value.max_price_limit,
    status: form.value.status,
    has_source_document: !!form.value.has_source_document,
    source_channel: 'manual',
  }
}

async function submit() {
  if (!form.value.buyer_name?.trim()) {
    ElMessage.warning('请填写采购方')
    return
  }
  if (form.value.has_source_document && !form.value.source_url?.trim()) {
    ElMessage.warning('有原文时必须填写原文链接')
    return
  }
  saving.value = true
  try {
    const payload = buildPayload()
    if (editing.value) {
      await adminApi.updatePlatformTenderLead(form.value.id, payload)
      ElMessage.success('已保存')
    } else {
      await adminApi.createPlatformTenderLead(payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    load()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handlePublish(row) {
  try {
    await adminApi.publishPlatformTenderLead(row.id)
    ElMessage.success('已发布')
    load()
  } catch (e) {
    ElMessage.error(e.message || '发布失败')
  }
}

async function handleUnpublish(row) {
  try {
    await adminApi.unpublishPlatformTenderLead(row.id)
    ElMessage.success('已下架')
    load()
  } catch (e) {
    ElMessage.error(e.message || '下架失败')
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`删除「${row.buyer_name}」？`, '删除')
    await adminApi.deletePlatformTenderLead(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

async function downloadTemplate() {
  try {
    const res = await adminApi.downloadPlatformTenderTemplate()
    const blob = new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'platform_tender_leads_template.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error(e.message || '下载失败')
  }
}

function onExcelChange(file) {
  excelFile.value = file?.raw || null
  excelPreview.value = null
}

async function previewExcel() {
  if (!excelFile.value) {
    ElMessage.warning('请选择 Excel 文件')
    return
  }
  excelBusy.value = true
  try {
    const fd = new FormData()
    fd.append('file', excelFile.value)
    const { data } = await adminApi.previewPlatformTenderExcel(fd)
    excelPreview.value = data
  } catch (e) {
    ElMessage.error(e.message || '预览失败')
  } finally {
    excelBusy.value = false
  }
}

async function confirmExcel() {
  if (!excelFile.value) return
  excelBusy.value = true
  try {
    const fd = new FormData()
    fd.append('file', excelFile.value)
    const { data } = await adminApi.confirmPlatformTenderExcel(fd)
    ElMessage.success(`已导入 ${data.created} 条，跳过 ${data.skipped} 条`)
    excelVisible.value = false
    excelFile.value = null
    excelPreview.value = null
    load()
  } catch (e) {
    ElMessage.error(e.message || '导入失败')
  } finally {
    excelBusy.value = false
  }
}

function stopParsePoll() {
  if (parsePollTimer) {
    clearInterval(parsePollTimer)
    parsePollTimer = null
  }
}

async function openParse() {
  stopParsePoll()
  parseStep.value = 0
  parseJobId.value = ''
  parseMode.value = 'paste'
  parsePasteText.value = ''
  parseForm.value = emptyParseForm()
  parseVisible.value = true
  // 提醒：若后端热重载失败，解析仍会跑旧逻辑
  try {
    const res = await fetch('/health')
    const h = await res.json()
    if (!h?.tender_parser_version) {
      ElMessage.warning('API 未返回解析版本，可能仍是旧进程，建议运行 scripts/restart-api.ps1')
    }
  } catch {
    ElMessage.warning('无法连接 API /health，请确认后端已启动')
  }
}

async function startParseJob(getJob) {
  parseBusy.value = true
  parseStep.value = 1
  try {
    const data = await getJob()
    parseJobId.value = data.id
    if (data.status === 'succeeded') {
      applyParseResult(data.result_json)
      parseStep.value = 2
      parseBusy.value = false
    } else {
      stopParsePoll()
      parsePollTimer = setInterval(pollParseJob, 800)
      setTimeout(pollParseJob, 200)
    }
  } catch (e) {
    parseBusy.value = false
    parseStep.value = 0
    ElMessage.error(e.message || '解析失败')
  }
}

async function onParseUpload(file) {
  const raw = file?.raw
  if (!raw) return
  await startParseJob(async () => {
    const fd = new FormData()
    fd.append('file', raw)
    const { data } = await adminApi.parsePlatformTenderAttachment(fd)
    return data
  })
}

async function onParsePaste() {
  const text = parsePasteText.value?.trim()
  if (!text) {
    ElMessage.warning('请先粘贴招投标正文')
    return
  }
  await startParseJob(async () => {
    const { data } = await adminApi.parsePlatformTenderText({ text })
    return data
  })
}

function applyParseResult(result) {
  if (!result || typeof result !== 'object') return
  if (!result._parser_version) {
    ElMessage.warning('解析结果无版本标记，后端可能未加载最新代码，请重启 API 后重试')
  }
  parseForm.value = {
    buyer_name: result.buyer_name || '',
    industry: result.industry || '',
    region: result.region || '',
    product_name: result.product_name || '',
    quantity: result.quantity || '',
    budget_min: result.budget_min != null ? Number(result.budget_min) : null,
    budget_max: result.budget_max != null ? Number(result.budget_max) : null,
    deadline: result.deadline || '',
    contact_name: result.contact_name || '',
    contact_phone: result.contact_phone || '',
    source_url: result.source_url || '',
    summary: result.summary || '',
    project_no: result.project_no || '',
    published_at: result.published_at || '',
    procurement_method: result.procurement_method || '',
    agent_name: result.agent_name || '',
    buyer_address: result.buyer_address || '',
    category: result.category || '',
    bid_open_date: result.bid_open_date || '',
    sme_preference: result.sme_preference ?? null,
    qualification_summary: result.qualification_summary || '',
    max_price_limit: result.max_price_limit != null ? Number(result.max_price_limit) : null,
    has_source_document: !!result.source_url,
  }
}

async function pollParseJob() {
  if (!parseJobId.value) return
  try {
    const { data } = await adminApi.getPlatformTenderParseJob(parseJobId.value)
    if (data.status === 'succeeded') {
      stopParsePoll()
      applyParseResult(data.result_json)
      parseStep.value = 2
      parseBusy.value = false
    } else if (data.status === 'failed') {
      stopParsePoll()
      parseBusy.value = false
      ElMessage.error(data.error_message || '解析失败')
      parseStep.value = 0
    }
  } catch (e) {
    stopParsePoll()
    parseBusy.value = false
    ElMessage.error(e.message || '查询解析状态失败')
  }
}

async function confirmParse() {
  if (!parseForm.value.buyer_name?.trim()) {
    ElMessage.warning('请填写采购方')
    return
  }
  if (parseForm.value.has_source_document && !parseForm.value.source_url?.trim()) {
    ElMessage.warning('有原文时必须填写原文链接')
    return
  }
  parseBusy.value = true
  try {
    const payload = {
      buyer_name: parseForm.value.buyer_name.trim(),
      industry: parseForm.value.industry || null,
      region: parseForm.value.region || null,
      product_name: parseForm.value.product_name || null,
      quantity: parseForm.value.quantity || null,
      budget_min: parseForm.value.budget_min,
      budget_max: parseForm.value.budget_max,
      deadline: parseForm.value.deadline || null,
      contact_name: parseForm.value.contact_name || null,
      contact_phone: parseForm.value.contact_phone || null,
      source_url: parseForm.value.source_url || null,
      summary: parseForm.value.summary || null,
      project_no: parseForm.value.project_no || null,
      published_at: parseForm.value.published_at || null,
      procurement_method: parseForm.value.procurement_method || null,
      agent_name: parseForm.value.agent_name || null,
      buyer_address: parseForm.value.buyer_address || null,
      category: parseForm.value.category || null,
      bid_open_date: parseForm.value.bid_open_date || null,
      sme_preference: parseForm.value.sme_preference,
      qualification_summary: parseForm.value.qualification_summary || null,
      max_price_limit: parseForm.value.max_price_limit,
      has_source_document: !!parseForm.value.has_source_document,
    }
    const { data } = await adminApi.confirmPlatformTenderParseJob(parseJobId.value, payload)
    ElMessage.success(`已写入草稿（${data.lead?.buyer_name || ''}），请人工发布`)
    parseVisible.value = false
    stopParsePoll()
    load()
  } catch (e) {
    ElMessage.error(e.message || '确认失败')
  } finally {
    parseBusy.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="admin-page">
    <div class="toolbar filters">
      <el-input
        v-model="searchQ"
        clearable
        placeholder="关键词：采购方/标的/编号/代理"
        style="width: 220px"
        @keyup.enter="onFilterChange"
        @clear="onFilterChange"
      />
      <el-input
        v-model="filterProjectNo"
        clearable
        placeholder="项目编号"
        style="width: 140px"
        @keyup.enter="onFilterChange"
        @clear="onFilterChange"
      />
      <el-input
        v-model="filterRegion"
        clearable
        placeholder="地区"
        style="width: 110px"
        @keyup.enter="onFilterChange"
        @clear="onFilterChange"
      />
      <el-input
        v-model="filterCategory"
        clearable
        placeholder="品目"
        style="width: 120px"
        @keyup.enter="onFilterChange"
        @clear="onFilterChange"
      />
      <el-input
        v-model="filterIndustry"
        clearable
        placeholder="行业"
        style="width: 110px"
        @keyup.enter="onFilterChange"
        @clear="onFilterChange"
      />
      <el-select
        v-model="filterMethod"
        clearable
        filterable
        allow-create
        default-first-option
        placeholder="采购方式"
        style="width: 130px"
        @change="onFilterChange"
      >
        <el-option v-for="m in METHOD_OPTIONS" :key="m" :label="m" :value="m" />
      </el-select>
      <el-input
        v-model="filterAgent"
        clearable
        placeholder="代理单位"
        style="width: 150px"
        @keyup.enter="onFilterChange"
        @clear="onFilterChange"
      />
      <el-select v-model="filterSme" clearable placeholder="中小企业" style="width: 120px" @change="onFilterChange">
        <el-option :value="true" label="面向中小企业" />
        <el-option :value="false" label="非面向中小企业" />
      </el-select>
      <el-select v-model="statusFilter" clearable placeholder="状态" style="width: 110px" @change="onFilterChange">
        <el-option v-for="s in STATUS_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
      <el-date-picker
        v-model="filterDeadlineRange"
        type="daterange"
        value-format="YYYY-MM-DD"
        start-placeholder="投标截止起"
        end-placeholder="截止止"
        style="width: 240px"
        @change="onFilterChange"
      />
      <el-date-picker
        v-model="filterPublishedRange"
        type="daterange"
        value-format="YYYY-MM-DD"
        start-placeholder="发布日起"
        end-placeholder="发布止"
        style="width: 240px"
        @change="onFilterChange"
      />
      <el-button type="primary" @click="onFilterChange">查询</el-button>
      <el-button @click="resetFilters">重置</el-button>
      <div class="toolbar__spacer" />
      <el-button @click="downloadTemplate">下载模板</el-button>
      <el-button @click="excelVisible = true">Excel 导入</el-button>
      <el-button @click="openParse">AI 解析入库</el-button>
      <el-button type="primary" @click="openCreate">新建</el-button>
    </div>

    <el-table v-loading="loading" :data="items" border>
      <el-table-column prop="project_no" label="项目编号" width="130" show-overflow-tooltip />
      <el-table-column prop="buyer_name" label="采购方" min-width="140" show-overflow-tooltip />
      <el-table-column prop="agent_name" label="代理单位" min-width="120" show-overflow-tooltip />
      <el-table-column prop="product_name" label="标的" min-width="110" show-overflow-tooltip />
      <el-table-column prop="category" label="品目" width="100" show-overflow-tooltip />
      <el-table-column prop="procurement_method" label="采购方式" width="100" />
      <el-table-column prop="region" label="地区" width="90" />
      <el-table-column prop="deadline" label="投标截止" width="110" />
      <el-table-column prop="published_at" label="发布日" width="110" />
      <el-table-column label="原文链接" width="90">
        <template #default="{ row }">
          <el-link v-if="row.source_url" :href="row.source_url" target="_blank" type="primary">打开</el-link>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="statusMeta(row.status).type" size="small">{{ statusMeta(row.status).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="source_channel" label="来源" width="90" />
      <el-table-column label="操作" width="240" fixed="right" align="center">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button
            v-if="row.status !== 'published'"
            link
            type="success"
            @click="handlePublish(row)"
          >发布</el-button>
          <el-button
            v-if="row.status === 'published'"
            link
            type="warning"
            @click="handleUnpublish(row)"
          >下架</el-button>
          <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="load"
      />
    </div>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑招标线索' : '新建招标线索'" width="760px">
      <el-form label-width="110px">
        <el-form-item label="采购方" required>
          <el-input v-model="form.buyer_name" maxlength="200" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="项目编号">
              <el-input v-model="form.project_no" maxlength="100" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="采购方式">
              <el-input v-model="form.procurement_method" placeholder="公开招标/询价/…" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="代理单位">
          <el-input v-model="form.agent_name" maxlength="200" />
        </el-form-item>
        <el-form-item label="产品/标的">
          <el-input v-model="form.product_name" maxlength="200" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="品目分类">
              <el-input v-model="form.category" placeholder="如：泵及真空设备" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="行业">
              <el-input v-model="form.industry" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="地区">
              <el-input v-model="form.region" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="采购人地址">
              <el-input v-model="form.buyer_address" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="数量">
              <el-input v-model="form.quantity" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="面向中小企业">
              <el-select v-model="form.sme_preference" clearable placeholder="未知" style="width: 100%">
                <el-option :value="true" label="是" />
                <el-option :value="false" label="否" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="发布日">
              <el-date-picker v-model="form.published_at" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="投标截止">
              <el-date-picker v-model="form.deadline" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="开标日">
              <el-date-picker v-model="form.bid_open_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="预算下限">
              <el-input-number v-model="form.budget_min" :min="0" :controls="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="预算上限">
              <el-input-number v-model="form.budget_max" :min="0" :controls="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="最高限价">
              <el-input-number v-model="form.max_price_limit" :min="0" :controls="false" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="资格要求">
          <el-input v-model="form.qualification_summary" type="textarea" :rows="2" placeholder="资格要求摘要" />
        </el-form-item>
        <el-form-item label="原文链接" required>
          <el-input v-model="form.source_url" placeholder="https://..." />
          <el-checkbox v-model="form.has_source_document" style="margin-top: 6px">有原文（必须填链接）</el-checkbox>
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="form.summary" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width: 160px">
            <el-option v-for="s in STATUS_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="excelVisible" title="Excel 导入 L1" width="720px">
      <el-upload :auto-upload="false" :limit="1" accept=".xlsx,.xls" :on-change="onExcelChange">
        <el-button>选择文件</el-button>
      </el-upload>
      <div class="excel-actions">
        <el-button :loading="excelBusy" @click="previewExcel">预览校验</el-button>
        <el-button
          type="primary"
          :loading="excelBusy"
          :disabled="!excelPreview || !excelPreview.valid_count"
          @click="confirmExcel"
        >确认入库</el-button>
      </div>
      <div v-if="excelPreview" class="excel-preview">
        <p>有效 {{ excelPreview.valid_count }} / 错误 {{ excelPreview.error_count }}</p>
        <el-table :data="excelPreview.rows" border size="small" max-height="320">
          <el-table-column prop="row_num" label="行" width="60" />
          <el-table-column label="采购方" min-width="120">
            <template #default="{ row }">{{ row.data.buyer_name }}</template>
          </el-table-column>
          <el-table-column label="原文链接" min-width="160">
            <template #default="{ row }">{{ row.data.source_url || '—' }}</template>
          </el-table-column>
          <el-table-column label="错误" min-width="160">
            <template #default="{ row }">
              <span v-if="row.errors?.length" class="err">{{ row.errors.join('；') }}</span>
              <span v-else class="ok">OK</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>

    <el-dialog
      v-model="parseVisible"
      title="AI 解析（人审后入库）"
      width="760px"
      @closed="stopParsePoll"
    >
      <el-steps :active="parseStep" finish-status="success" align-center style="margin-bottom: 20px">
        <el-step title="上传/粘贴" />
        <el-step title="解析中" />
        <el-step title="人审确认" />
      </el-steps>
      <div v-if="parseStep < 2">
        <el-radio-group v-model="parseMode" :disabled="parseBusy" style="margin-bottom: 12px">
          <el-radio-button value="paste">粘贴原文</el-radio-button>
          <el-radio-button value="file">上传附件</el-radio-button>
        </el-radio-group>
        <div v-if="parseMode === 'paste'">
          <el-input
            v-model="parsePasteText"
            type="textarea"
            :rows="10"
            :disabled="parseBusy"
            maxlength="100000"
            show-word-limit
            placeholder="将招投标公告/文件正文粘贴到此处，系统会抽取采购方、产品、预算等字段供人审确认"
          />
          <div style="margin-top: 12px">
            <el-button type="primary" :loading="parseBusy" @click="onParsePaste">开始解析</el-button>
          </div>
        </div>
        <div v-else>
          <el-upload
            :auto-upload="false"
            :limit="1"
            accept=".txt,.md,.pdf,.doc,.docx,.png,.jpg,.jpeg,.webp"
            :on-change="onParseUpload"
            :disabled="parseBusy"
          >
            <el-button type="primary" :loading="parseBusy">选择并上传</el-button>
          </el-upload>
        </div>
        <p class="muted" style="margin-top: 12px">解析未确认前不会写入/发布公共池。</p>
      </div>
      <el-form v-else label-width="110px">
        <el-alert type="warning" :closable="false" style="margin-bottom: 12px" title="请核对字段后确认；确认仅写入草稿，需另点发布" />
        <el-form-item label="采购方" required>
          <el-input v-model="parseForm.buyer_name" maxlength="200" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="项目编号">
              <el-input v-model="parseForm.project_no" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="采购方式">
              <el-input v-model="parseForm.procurement_method" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="代理单位">
          <el-input v-model="parseForm.agent_name" />
        </el-form-item>
        <el-form-item label="产品/标的">
          <el-input v-model="parseForm.product_name" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="品目分类">
              <el-input v-model="parseForm.category" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="行业">
              <el-input v-model="parseForm.industry" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="地区">
              <el-input v-model="parseForm.region" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="采购人地址">
              <el-input v-model="parseForm.buyer_address" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="数量">
              <el-input v-model="parseForm.quantity" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="面向中小企业">
              <el-select v-model="parseForm.sme_preference" clearable placeholder="未知" style="width: 100%">
                <el-option :value="true" label="是" />
                <el-option :value="false" label="否" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="发布日">
              <el-date-picker v-model="parseForm.published_at" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="投标截止">
              <el-date-picker v-model="parseForm.deadline" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="开标日">
              <el-date-picker v-model="parseForm.bid_open_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="预算下限">
              <el-input-number v-model="parseForm.budget_min" :min="0" :controls="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="预算上限">
              <el-input-number v-model="parseForm.budget_max" :min="0" :controls="false" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="最高限价">
              <el-input-number v-model="parseForm.max_price_limit" :min="0" :controls="false" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="联系人">
              <el-input v-model="parseForm.contact_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系电话">
              <el-input v-model="parseForm.contact_phone" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="资格要求">
          <el-input v-model="parseForm.qualification_summary" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="原文链接">
          <el-input v-model="parseForm.source_url" placeholder="https://..." />
          <el-checkbox v-model="parseForm.has_source_document" style="margin-top: 6px">有原文（必须填链接）</el-checkbox>
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="parseForm.summary" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="parseVisible = false">取消</el-button>
        <el-button
          v-if="parseStep >= 2"
          type="primary"
          :loading="parseBusy"
          @click="confirmParse"
        >确认写入草稿</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 12px; }
.filters { row-gap: 10px; }
.toolbar__spacer { flex: 1; min-width: 8px; }
.pager { margin-top: 12px; display: flex; justify-content: flex-end; }
.muted { color: var(--el-text-color-placeholder); }
.excel-actions { margin: 12px 0; display: flex; gap: 8px; }
.excel-preview { margin-top: 8px; }
.err { color: var(--el-color-danger); font-size: 12px; }
.ok { color: var(--el-color-success); font-size: 12px; }
</style>
