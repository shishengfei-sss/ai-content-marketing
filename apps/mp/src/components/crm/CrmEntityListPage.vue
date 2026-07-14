<script setup>
import { computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { buildCardMetaItems } from '@/utils/crmListMeta'
import { useCrmEntityListPage } from '@/composables/useCrmEntityListPage'

const props = defineProps({
  entityType: { type: String, required: true },
  entityLabel: { type: String, required: true },
  allViewLabel: { type: String, required: true },
  emptyText: { type: String, required: true },
  searchPlaceholder: { type: String, default: '搜索' },
  titleField: { type: String, required: true },
  statusField: { type: String, default: 'status' },
  formatStatus: { type: Function, default: null },
  fetchList: { type: Function, required: true },
  createPermission: { type: String, default: '' },
  createUrl: { type: String, default: '' },
  enableSearch: { type: Boolean, default: true },
  enableFilter: { type: Boolean, default: true },
  enableColumns: { type: Boolean, default: true },
  extraParams: { type: Function, default: () => ({}) },
  headExtra: { type: Array, default: () => [] },
})

const emit = defineEmits(['card-click', 'create'])

const page = useCrmEntityListPage({
  entityType: props.entityType,
  allViewLabel: props.allViewLabel,
  fetchList: props.fetchList,
  enableSearch: props.enableSearch,
  enableFilter: props.enableFilter,
  enableColumns: props.enableColumns,
  extraParams: props.extraParams,
})

const {
  loading,
  loadingMore,
  items,
  total,
  hasMore,
  views,
  viewPickerVisible,
  filterVisible,
  filterDraft,
  searchKeyword,
  appliedSearchKeyword,
  selectSheet,
  columnVisible,
  columnDraft,
  columnSaving,
  listColumns,
  fieldMap,
  formatCell,
  hasActiveFilter,
  filterSummary,
  advancedFilterCount,
  modalOpen,
  columnVisibleCount,
  loadData,
  loadMore,
  currentViewLabel,
  openViewPicker,
  selectView,
  openFilter,
  fieldLabel,
  opLabel,
  openSelectSheet,
  closeSelectSheet,
  pickSheetOption,
  confirmSelectSheet,
  addFilterRow,
  removeFilterRow,
  applyFilter,
  resetFilter,
  clearSearch,
  applySearch,
  clearAllFilters,
  openColumnSettings,
  toggleColumn,
  jumpColumnOrder,
  submitColumnSettings,
  canCreate,
} = page

const showStatusInHead = computed(() =>
  listColumns.value.some((c) => c.field_key === props.statusField && c.visible !== false),
)

function cardTitle(item) {
  return item[props.titleField] || '—'
}

function cardStatus(item) {
  const raw = item[props.statusField]
  if (props.formatStatus) return props.formatStatus(raw, item)
  return raw || '—'
}

function cardMetaItems(item) {
  return buildCardMetaItems(item, listColumns.value, formatCell, {
    entityType: props.entityType,
    headExtra: props.headExtra,
  })
}

function onCardClick(item) {
  emit('card-click', item)
}

function onCreate() {
  if (props.createUrl) {
    uni.navigateTo({ url: props.createUrl })
  }
  emit('create')
}

onShow(loadData)
defineExpose({ reload: loadData })
</script>

<template>
  <view class="crm-list">
    <view class="toolbar">
      <slot name="toolbar-top" />

      <view v-if="enableSearch" class="toolbar__search-row">
        <view class="search-box">
          <text class="search-box__icon">⌕</text>
          <input
            v-model="searchKeyword"
            class="search-input"
            type="text"
            :placeholder="searchPlaceholder"
            confirm-type="search"
            :adjust-position="true"
            @confirm="applySearch"
          />
          <text v-if="searchKeyword" class="search-clear" @tap="clearSearch">×</text>
        </view>
        <view
          v-if="enableFilter"
          class="toolbar-btn toolbar-btn--filter"
          :class="{ 'toolbar-btn--filter-active': advancedFilterCount > 0 || filterVisible }"
          @tap="openFilter"
        >
          <text class="toolbar-btn__text">筛选</text>
          <text v-if="advancedFilterCount" class="toolbar-btn__badge">{{ advancedFilterCount }}</text>
        </view>
      </view>

      <view v-if="hasActiveFilter" class="filter-tags">
        <text v-for="(tag, i) in filterSummary" :key="i" class="filter-tag">{{ tag }}</text>
        <text v-if="appliedSearchKeyword.trim()" class="filter-tag">搜索：{{ appliedSearchKeyword.trim() }}</text>
        <text class="filter-tag filter-tag--clear" @tap="clearAllFilters">清除</text>
      </view>

      <view class="toolbar__action-row">
        <view class="view-chip" @tap="openViewPicker">
          <text class="view-chip__text">{{ currentViewLabel() }}</text>
          <text class="view-chip__count">{{ loading ? '…' : total }}</text>
          <text class="view-chip__arrow">▾</text>
        </view>
        <view class="toolbar__actions">
          <slot name="toolbar-actions" />
          <view v-if="enableColumns" class="toolbar-btn" @tap="openColumnSettings">
            <text class="toolbar-btn__icon toolbar-btn__icon--sm">☰</text>
            <text class="toolbar-btn__text">列设置</text>
          </view>
          <view
            v-if="createPermission && createUrl && canCreate(createPermission)"
            class="toolbar-btn toolbar-btn--primary"
            @tap="onCreate"
          >
            <text class="toolbar-btn__icon">+</text>
            <text class="toolbar-btn__text">新建</text>
          </view>
        </view>
      </view>
    </view>

    <scroll-view
      scroll-y
      class="scroll"
      :class="{ 'scroll--locked': modalOpen }"
      :lower-threshold="100"
      @scrolltolower="loadMore"
    >
      <view v-if="loading" class="empty">{{ entityLabel }}加载中…</view>
      <view v-else-if="!items.length" class="empty">{{ emptyText }}</view>
      <view v-else class="list">
        <view v-for="item in items" :key="item.id" class="card" @click="onCardClick(item)">
          <view class="card__head">
            <view class="card__title-wrap">
              <text class="card__title">{{ cardTitle(item) }}</text>
              <text v-if="showStatusInHead" class="status">{{ cardStatus(item) }}</text>
            </view>
          </view>
          <view v-if="cardMetaItems(item).length" class="card__meta">
            <view v-for="meta in cardMetaItems(item)" :key="meta.field_key" class="card__meta-row">
              <text class="card__meta-label">{{ meta.label }}</text>
              <text class="card__meta-value">{{ meta.value }}</text>
            </view>
          </view>
          <text v-else class="card__meta card__meta--empty">暂无更多信息</text>
          <slot name="card-footer" :item="item" />
        </view>
        <view v-if="loadingMore" class="list-foot">加载中…</view>
        <view v-else-if="!hasMore && items.length" class="list-foot">没有更多了</view>
      </view>
    </scroll-view>

    <view v-if="viewPickerVisible" class="mask" @tap.self="viewPickerVisible = false">
      <view class="dialog dialog--tall" @tap.stop>
        <text class="dialog__title">切换视图</text>
        <scroll-view scroll-y class="column-scroll">
          <view class="column-item" @tap="selectView('')">
            <text>{{ allViewLabel }}</text>
          </view>
          <view v-for="view in views" :key="view.id" class="column-item" @tap="selectView(view.id)">
            <text>{{ view.name }}</text>
          </view>
        </scroll-view>
      </view>
    </view>

    <view v-if="filterVisible" class="mask" @tap.self="filterVisible = false; closeSelectSheet()">
      <view class="dialog dialog--tall" @tap.stop>
        <text class="dialog__title">高级筛选</text>
        <text class="filter-tip">满足以下全部条件（AND）</text>
        <scroll-view scroll-y class="column-scroll">
          <view v-for="(row, idx) in filterDraft" :key="idx" class="adv-filter-row">
            <view class="adv-filter-pick" @tap="openSelectSheet('field', idx)">{{ fieldLabel(row.field_key) }}</view>
            <view
              v-if="row.field_key"
              class="adv-filter-pick adv-filter-pick--sm"
              @tap="openSelectSheet('op', idx)"
            >
              {{ opLabel(row) }}
            </view>
            <view
              v-if="row.field_key && row.op !== 'is_empty' && fieldMap[row.field_key]?.field_type === 'select'"
              class="adv-filter-pick"
              @tap="openSelectSheet('value', idx)"
            >
              {{ row.value || '请选择值' }}
            </view>
            <input
              v-else-if="row.field_key && row.op !== 'is_empty'"
              v-model="row.value"
              class="adv-filter-input"
              type="text"
              placeholder="请输入"
            />
            <text v-else-if="row.field_key && row.op === 'is_empty'" class="adv-filter-empty">无需填写</text>
            <text class="adv-filter-remove" @tap="removeFilterRow(idx)">删除</text>
          </view>
          <view class="adv-filter-add" @tap="addFilterRow">+ 添加条件</view>
        </scroll-view>
        <view class="dialog__acts">
          <button class="btn" hover-class="none" @tap="resetFilter">重置</button>
          <button class="btn btn--primary" hover-class="none" @tap="applyFilter">确定</button>
        </view>
      </view>
      <view v-if="selectSheet.visible" class="select-sheet" @tap.stop>
        <view class="select-sheet__bar">
          <text class="select-sheet__cancel" @tap="closeSelectSheet">取消</text>
          <text class="select-sheet__ok" @tap="confirmSelectSheet">完成</text>
        </view>
        <scroll-view scroll-y class="select-sheet__scroll">
          <view
            v-for="opt in selectSheet.options"
            :key="String(opt.value)"
            class="select-sheet__opt"
            :class="{ 'select-sheet__opt--active': opt.value === selectSheet.tempValue }"
            @tap="pickSheetOption(opt.value)"
          >
            {{ opt.label }}
          </view>
        </scroll-view>
      </view>
    </view>

    <view v-if="columnVisible" class="mask" @tap.self="columnVisible = false">
      <view class="dialog dialog--tall" @tap.stop>
        <text class="dialog__title">列设置</text>
        <text class="column-settings-tip">勾选控制显示；带「固定」标签的列无法隐藏</text>
        <text class="column-settings-meta">已显示 {{ columnVisibleCount }} / {{ columnDraft.length }} 列</text>
        <scroll-view scroll-y class="column-scroll">
          <view v-if="!columnDraft.length" class="empty">暂无可用列</view>
          <view v-else class="column-settings-table">
            <view class="column-settings-head">
              <text class="column-settings-head__show">显示</text>
              <text class="column-settings-head__name">列名</text>
              <text class="column-settings-head__order">序号</text>
            </view>
            <view
              v-for="(col, idx) in columnDraft"
              :key="col.field_key"
              class="column-settings-row"
              :class="{ 'column-settings-row--locked': col.list_locked, 'column-settings-row--hidden': col.visible === false }"
            >
              <checkbox
                :checked="col.visible !== false"
                :disabled="col.list_locked"
                class="column-settings-check"
                @click.stop="toggleColumn(col)"
              />
              <view class="column-settings-name">
                <text class="column-settings-label">{{ col.label }}</text>
                <text v-if="col.list_locked" class="column-settings-tag">固定</text>
              </view>
              <input
                type="text"
                inputmode="numeric"
                class="column-settings-order"
                :value="String(idx + 1)"
                @click.stop
                @confirm="(e) => jumpColumnOrder(idx, e.detail.value)"
                @blur="(e) => jumpColumnOrder(idx, e.detail.value)"
              />
            </view>
          </view>
        </scroll-view>
        <view class="dialog__acts">
          <button class="btn" hover-class="none" :disabled="columnSaving" @tap="columnVisible = false">取消</button>
          <button class="btn btn--primary" hover-class="none" :disabled="columnSaving" @tap="submitColumnSettings">
            {{ columnSaving ? '保存中…' : '保存' }}
          </button>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped src="@/styles/crm-entity-list.css"></style>
