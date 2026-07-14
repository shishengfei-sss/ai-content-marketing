<script setup>
import { ref } from 'vue'
import { crmApi } from '@/utils/api'
import { QUOTE_STATUS_LABEL } from '@/utils/crmConstants'
import CrmEntityListPage from '@/components/crm/CrmEntityListPage.vue'
</script>

<template>
  <view class="page">
    <CrmEntityListPage
      entity-type="quote"
      entity-label="报价"
      all-view-label="全部报价"
      empty-text="暂无报价"
      search-placeholder="搜索报价主题、编号"
      title-field="subject"
      :format-status="(s) => QUOTE_STATUS_LABEL[s] || s"
      :fetch-list="(params) => crmApi.listQuotes(params)"
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
