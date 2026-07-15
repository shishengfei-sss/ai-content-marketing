<script setup>
import { crmApi } from '@/utils/api'
import CrmEntityListPage from '@/components/crm/CrmEntityListPage.vue'

function formatActive(v) {
  if (v === true || v === 'true' || v === 1) return '启用'
  if (v === false || v === 'false' || v === 0) return '停用'
  return String(v ?? '—')
}
</script>

<template>
  <view class="page">
    <CrmEntityListPage
      entity-type="product"
      entity-label="产品"
      all-view-label="全部产品"
      empty-text="暂无产品"
      search-placeholder="搜索产品名称、编码"
      title-field="name"
      status-field="is_active"
      :format-status="formatActive"
      :fetch-list="(params) => crmApi.listProducts(params)"
    />
  </view>
</template>

<style scoped>
.page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f0f2f5;
  padding: 12px;
  box-sizing: border-box;
}
</style>
