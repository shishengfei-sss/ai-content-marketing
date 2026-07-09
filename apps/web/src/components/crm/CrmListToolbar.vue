<script setup>
defineProps({
  title: { type: String, required: true },
  activeView: { type: Object, default: null },
  filtersLocked: { type: Boolean, default: false },
  showFilterHint: { type: Boolean, default: false },
})

defineEmits(['clear-view', 'clear-filters'])
</script>

<template>
  <div class="crm-list-toolbar">
    <div class="crm-list-toolbar__head">
      <h2 class="crm-list-toolbar__title">{{ title }}</h2>
      <div class="crm-list-toolbar__head-actions">
        <slot name="actions" />
      </div>
    </div>

    <div class="crm-list-toolbar__bar">
      <div class="crm-list-toolbar__view">
        <slot name="view" />
      </div>

      <div class="crm-list-toolbar__divider" aria-hidden="true" />

      <div class="crm-list-toolbar__filters" :class="{ 'is-locked': filtersLocked }">
        <slot name="filters" />
      </div>

      <el-tag
        v-if="activeView"
        closable
        class="crm-list-toolbar__view-tag"
        type="primary"
        effect="light"
        round
        @close="$emit('clear-view')"
      >
        <el-icon class="crm-list-toolbar__view-tag-icon"><Filter /></el-icon>
        {{ activeView.name }}
      </el-tag>

      <span v-else-if="showFilterHint" class="crm-list-toolbar__filter-hint">
        已应用筛选
        <el-button link type="primary" size="small" @click="$emit('clear-filters')">清除</el-button>
      </span>
    </div>
  </div>
</template>

<style scoped>
.crm-list-toolbar {
  margin-bottom: 16px;
}

.crm-list-toolbar__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 10px;
}

.crm-list-toolbar__title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  line-height: 1.3;
  color: var(--el-text-color-primary);
}

.crm-list-toolbar__head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.crm-list-toolbar__bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 14px;
  background: linear-gradient(180deg, #fafbfd 0%, #f5f7fb 100%);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
}

.crm-list-toolbar__view {
  flex-shrink: 0;
}

.crm-list-toolbar__divider {
  width: 1px;
  height: 28px;
  background: var(--el-border-color);
  flex-shrink: 0;
}

.crm-list-toolbar__filters {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
  flex-wrap: wrap;
}

.crm-list-toolbar__filters.is-locked {
  opacity: 0.5;
}

.crm-list-toolbar__view-tag {
  flex-shrink: 0;
  max-width: 220px;
}

.crm-list-toolbar__view-tag :deep(.el-tag__content) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.crm-list-toolbar__view-tag-icon {
  font-size: 12px;
}

.crm-list-toolbar__filter-hint {
  flex-shrink: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
</style>
