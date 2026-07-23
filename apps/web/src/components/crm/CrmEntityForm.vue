<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { crmApi } from '../../api/client'
import {
  fieldsWithoutRegionParts,
  groupFormFields,
  hasRegionFields,
  isFormFieldRequired,
} from '../../utils/entityForm'
import DynamicField from './DynamicField.vue'
import RegionCascader from './RegionCascader.vue'

const props = defineProps({
  entityType: { type: String, required: true },
  fields: { type: Array, default: () => [] },
  modelValue: { type: Object, required: true },
  readonly: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const campaigns = ref([])
const territories = ref([])
const territoriesError = ref('')

const sections = computed(() =>
  groupFormFields(props.fields).map((section) => ({
    ...section,
    fields: section.id === 'address' ? fieldsWithoutRegionParts(section.fields) : section.fields,
  })),
)

const values = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

function fieldRequired(field) {
  return isFormFieldRequired(props.entityType, field)
}

function updateField(key, val) {
  values.value = { ...values.value, [key]: val }
}

function updateRegion({ province, city, district }) {
  values.value = {
    ...values.value,
    province: province || '',
    city: city || '',
    district: district || '',
  }
}

function sectionHasRegion(section) {
  return section.id === 'address' && hasRegionFields(props.fields)
}

async function loadRefOptions() {
  const needsCampaign = props.fields.some((f) => f.field_key === 'campaign_id')
  const needsTerritory = props.fields.some((f) => f.field_key === 'territory_id')
  const tasks = []
  if (needsCampaign) {
    tasks.push(
      crmApi.listCampaigns({ page: 1, page_size: 100 }).then(({ data }) => {
        campaigns.value = data.items || []
      }),
    )
  }
  if (needsTerritory) {
    territoriesError.value = ''
    tasks.push(
      crmApi
        .listTerritories()
        .then(({ data }) => {
          territories.value = Array.isArray(data) ? data : data?.items || []
        })
        .catch((e) => {
          territories.value = []
          territoriesError.value = e?.message || '加载归属地区失败'
        }),
    )
  }
  await Promise.allSettled(tasks)
}

onMounted(loadRefOptions)
watch(() => props.fields, loadRefOptions, { deep: true })
</script>

<template>
  <div class="entity-form">
    <section v-for="section in sections" :key="section.id" class="entity-form__section">
      <div class="entity-form__title">{{ section.title }}</div>
      <el-row v-if="sectionHasRegion(section)" :gutter="16" class="entity-form__region-row">
        <el-col :span="24">
          <el-form-item label="省市区">
            <RegionCascader
              :province="values.province || ''"
              :city="values.city || ''"
              :district="values.district || ''"
              :readonly="readonly"
              @change="updateRegion"
            />
          </el-form-item>
        </el-col>
      </el-row>
      <el-row :gutter="16">
        <el-col
          v-for="field in section.fields"
          :key="field.field_key"
          :span="field.field_type === 'textarea' ? 24 : 12"
        >
          <el-form-item :label="field.label" :required="fieldRequired(field)">
            <el-select
              v-if="field.field_key === 'campaign_id'"
              :model-value="values[field.field_key]"
              :disabled="readonly"
              clearable
              filterable
              placeholder="选择营销活动"
              style="width: 100%"
              @update:model-value="updateField(field.field_key, $event)"
            >
              <el-option v-for="item in campaigns" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
            <template v-else-if="field.field_key === 'territory_id'">
              <el-select
                :model-value="values[field.field_key]"
                :disabled="readonly"
                :clearable="!fieldRequired(field)"
                filterable
                placeholder="选择销售区域"
                style="width: 100%"
                @update:model-value="updateField(field.field_key, $event)"
              >
                <el-option
                  v-for="item in territories"
                  :key="item.id"
                  :label="item.name"
                  :value="item.id"
                />
              </el-select>
              <div v-if="territoriesError" class="entity-form__hint entity-form__hint--error">
                {{ territoriesError }}
              </div>
              <div v-else-if="!territories.length" class="entity-form__hint">
                暂无地区，可到「设置 → 销售组织」维护
              </div>
            </template>
            <DynamicField
              v-else
              :field="field"
              :model-value="values[field.field_key]"
              :readonly="readonly"
              @update:model-value="updateField(field.field_key, $event)"
            />
          </el-form-item>
        </el-col>
      </el-row>
    </section>
  </div>
</template>

<style scoped>
.entity-form__section {
  margin-bottom: 14px;
  padding: 14px 14px 2px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  background: linear-gradient(180deg, #fcfdff 0%, #f8fafc 100%);
}

.entity-form__section:last-child {
  margin-bottom: 0;
}

.entity-form__title {
  margin-bottom: 12px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--el-text-color-primary);
}

.entity-form__region-row {
  margin-bottom: 4px;
}

.entity-form__hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
}

.entity-form__hint--error {
  color: var(--el-color-danger);
}

.entity-form :deep(.el-form-item__label) {
  font-weight: 500;
  color: var(--el-text-color-regular);
}
</style>
