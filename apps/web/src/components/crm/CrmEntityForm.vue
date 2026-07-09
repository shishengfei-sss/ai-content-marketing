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



const sections = computed(() =>

  groupFormFields(props.fields).map((section) => ({

    ...section,

    fields:

      section.id === 'address' ? fieldsWithoutRegionParts(section.fields) : section.fields,

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

    tasks.push(

      crmApi.listTerritories().then(({ data }) => {

        territories.value = Array.isArray(data) ? data : data?.items || []

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

              @update:province="updateField('province', $event)"

              @update:city="updateField('city', $event)"

              @update:district="updateField('district', $event)"

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

            <el-select

              v-else-if="field.field_key === 'territory_id'"

              :model-value="values[field.field_key]"

              :disabled="readonly"

              clearable

              filterable

              placeholder="选择归属地区"

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

.entity-form :deep(.el-form-item__label) {
  font-weight: 500;
  color: var(--el-text-color-regular);
}
</style>


