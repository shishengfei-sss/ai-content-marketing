<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { crmApi } from '../../api/client'
import { formatFieldDisplay, groupFormFields } from '../../utils/entityForm'

const props = defineProps({
  record: { type: Object, required: true },
  fields: { type: Array, default: () => [] },
  campaignName: { type: String, default: '' },
  ownerName: { type: String, default: '' },
  /** 可选；不传时组件会自行拉取销售区域列表做名称解析 */
  territoryName: { type: String, default: '' },
})

const territories = ref([])
const sections = computed(() => groupFormFields(props.fields))
const needsTerritory = computed(() => props.fields.some((f) => f.field_key === 'territory_id'))

function normId(id) {
  return String(id || '')
    .replace(/-/g, '')
    .toLowerCase()
}

function resolveTerritoryName() {
  if (props.territoryName) return props.territoryName
  const tid = props.record?.territory_id
  if (!tid) return ''
  const hit = territories.value.find((t) => normId(t.id) === normId(tid))
  return hit?.name || ''
}

async function loadTerritories() {
  if (!needsTerritory.value) return
  try {
    const { data } = await crmApi.listTerritories()
    territories.value = Array.isArray(data) ? data : data?.items || []
  } catch {
    territories.value = []
  }
}

function displayValue(field) {
  if (field.field_key === 'campaign_id' && props.campaignName) {
    return props.campaignName
  }
  if (field.field_key === 'territory_id') {
    return resolveTerritoryName() || formatFieldDisplay(field, props.record)
  }
  return formatFieldDisplay(field, props.record)
}

onMounted(loadTerritories)
watch(needsTerritory, (v) => {
  if (v && !territories.value.length) loadTerritories()
})
</script>

<template>
  <div class="fields-view">
    <el-descriptions v-if="ownerName" :column="2" border class="fields-view__owner">
      <el-descriptions-item label="负责人">{{ ownerName }}</el-descriptions-item>
    </el-descriptions>

    <section v-for="section in sections" :key="section.id" class="fields-view__section">
      <div class="fields-view__title">{{ section.title }}</div>
      <el-descriptions :column="2" border>
        <el-descriptions-item
          v-for="field in section.fields"
          :key="field.field_key"
          :label="field.label"
          :span="field.field_type === 'textarea' ? 2 : 1"
        >
          <template v-if="field.field_key === 'status'">
            <el-tag size="small">{{ displayValue(field) }}</el-tag>
          </template>
          <template v-else>{{ displayValue(field) }}</template>
        </el-descriptions-item>
      </el-descriptions>
    </section>
  </div>
</template>

<style scoped>
.fields-view__owner {
  margin-bottom: 16px;
}

.fields-view__section + .fields-view__section {
  margin-top: 20px;
}

.fields-view__title {
  margin-bottom: 10px;
  padding-left: 10px;
  border-left: 3px solid var(--el-color-primary);
  font-size: 14px;
  font-weight: 600;
  line-height: 1.2;
}

.fields-view :deep(.el-descriptions__label) {
  width: 120px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-lighter) !important;
}

.fields-view :deep(.el-descriptions__content) {
  color: var(--el-text-color-primary);
}
</style>
