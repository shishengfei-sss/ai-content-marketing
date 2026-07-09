<script setup>
import { computed, ref, watch } from 'vue'
import {
  findRegionIndexes,
  formatRegionDisplay,
  regionLabelTree,
} from '@/utils/regionData'

const props = defineProps({
  province: { type: String, default: '' },
  city: { type: String, default: '' },
  district: { type: String, default: '' },
  placeholder: { type: String, default: '请选择省 / 市 / 区' },
})

const emit = defineEmits(['update:province', 'update:city', 'update:district'])

const visible = ref(false)
const colIndex = ref([0, 0, 0])

const provinces = computed(() => regionLabelTree)

const cities = computed(() => provinces.value[colIndex.value[0]]?.children || [])

const districts = computed(() => cities.value[colIndex.value[1]]?.children || [])

const displayText = computed(() =>
  formatRegionDisplay(props.province, props.city, props.district),
)

function normalizeIndexes(next) {
  let [pi, ci, di] = next
  const pList = provinces.value
  if (!pList.length) return [0, 0, 0]
  if (pi >= pList.length) pi = 0

  const cList = pList[pi]?.children || []
  if (!cList.length) return [pi, 0, 0]
  if (ci >= cList.length) ci = 0

  const dList = cList[ci]?.children || []
  if (!dList.length) return [pi, ci, 0]
  if (di >= dList.length) di = 0
  return [pi, ci, di]
}

function openPicker() {
  colIndex.value = normalizeIndexes(
    findRegionIndexes(regionLabelTree, props.province, props.city, props.district),
  )
  visible.value = true
}

function closePicker() {
  visible.value = false
}

function onPickerChange(e) {
  const next = normalizeIndexes(e?.detail?.value || colIndex.value)
  const prev = colIndex.value
  if (next[0] !== prev[0]) {
    colIndex.value = [next[0], 0, 0]
    return
  }
  if (next[1] !== prev[1]) {
    colIndex.value = [next[0], next[1], 0]
    return
  }
  colIndex.value = next
}

function confirmPicker() {
  const [pi, ci, di] = colIndex.value
  emit('update:province', provinces.value[pi]?.label || '')
  emit('update:city', cities.value[ci]?.label || '')
  emit('update:district', districts.value[di]?.label || '')
  closePicker()
}

function clearPicker() {
  emit('update:province', '')
  emit('update:city', '')
  emit('update:district', '')
  closePicker()
}

watch(
  () => [props.province, props.city, props.district],
  () => {
    if (!visible.value) {
      colIndex.value = normalizeIndexes(
        findRegionIndexes(regionLabelTree, props.province, props.city, props.district),
      )
    }
  },
)
</script>

<template>
  <view class="region-picker">
    <view class="region-picker__field" @click="openPicker">
      <text class="region-picker__value" :class="{ 'region-picker__value--ph': !displayText }">
        {{ displayText || placeholder }}
      </text>
      <text class="region-picker__arrow">▾</text>
    </view>

    <view v-if="visible" class="region-picker__mask" @click="closePicker">
      <view class="region-picker__sheet" @click.stop>
        <view class="region-picker__bar">
          <text class="region-picker__action" @click="closePicker">取消</text>
          <text class="region-picker__title">选择省市区</text>
          <text class="region-picker__action region-picker__action--ok" @click="confirmPicker">
            完成
          </text>
        </view>
        <picker-view
          class="region-picker__view"
          :value="colIndex"
          indicator-style="height: 44px;"
          @change="onPickerChange"
        >
          <picker-view-column>
            <view
              v-for="(item, idx) in provinces"
              :key="`p-${idx}-${item.label}`"
              class="region-picker__item"
            >
              {{ item.label }}
            </view>
          </picker-view-column>
          <picker-view-column>
            <view
              v-for="(item, idx) in cities"
              :key="`c-${idx}-${item.label}`"
              class="region-picker__item"
            >
              {{ item.label }}
            </view>
          </picker-view-column>
          <picker-view-column>
            <view
              v-for="(item, idx) in districts"
              :key="`d-${idx}-${item.label}`"
              class="region-picker__item"
            >
              {{ item.label }}
            </view>
          </picker-view-column>
        </picker-view>
        <view v-if="displayText" class="region-picker__clear" @click="clearPicker">清空已选</view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.region-picker__field {
  width: 100%;
  box-sizing: border-box;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 11px 12px;
  font-size: 15px;
  color: #0f172a;
  line-height: 1.4;
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.region-picker__value--ph {
  color: #94a3b8;
}

.region-picker__arrow {
  color: #94a3b8;
  font-size: 12px;
  margin-left: 8px;
}

.region-picker__mask {
  position: fixed;
  inset: 0;
  z-index: 1300;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: flex-end;
}

.region-picker__sheet {
  width: 100%;
  background: #fff;
  border-radius: 16px 16px 0 0;
  overflow: hidden;
}

.region-picker__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #f1f5f9;
}

.region-picker__title {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
}

.region-picker__action {
  font-size: 14px;
  color: #64748b;
  min-width: 40px;
}

.region-picker__action--ok {
  color: #1677ff;
  text-align: right;
}

.region-picker__view {
  width: 100%;
  height: 220px;
}

.region-picker__item {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 44px;
  font-size: 15px;
  color: #334155;
}

.region-picker__clear {
  text-align: center;
  padding: 12px 0 calc(12px + env(safe-area-inset-bottom));
  font-size: 14px;
  color: #ef4444;
  border-top: 1px solid #f8fafc;
}
</style>
