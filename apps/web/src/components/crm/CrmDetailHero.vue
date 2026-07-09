<script setup>
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  avatarText: { type: String, default: '客' },
  status: { type: String, default: '' },
  statusType: { type: String, default: 'info' },
  ownerName: { type: String, default: '' },
  meta: { type: Array, default: () => [] },
  stats: { type: Array, default: () => [] },
})
</script>

<template>
  <section class="crm-hero page-card">
    <div class="crm-hero__main">
      <div class="crm-hero__avatar">{{ avatarText }}</div>
      <div class="crm-hero__content">
        <div class="crm-hero__title-row">
          <h1 class="crm-hero__title">{{ title }}</h1>
          <el-tag v-if="status" size="small" :type="statusType" effect="light">{{ status }}</el-tag>
        </div>
        <p v-if="subtitle" class="crm-hero__subtitle">{{ subtitle }}</p>
        <div v-if="ownerName" class="crm-hero__owner">
          <span class="crm-hero__owner-label">负责人</span>
          <span class="crm-hero__owner-value">{{ ownerName }}</span>
        </div>
        <div v-if="meta.length" class="crm-hero__meta">
          <span v-for="item in meta" :key="item.label" class="crm-hero__meta-item">
            <span class="crm-hero__meta-label">{{ item.label }}</span>
            <span class="crm-hero__meta-value">{{ item.value }}</span>
          </span>
        </div>
      </div>
      <div v-if="$slots.actions" class="crm-hero__actions">
        <slot name="actions" />
      </div>
    </div>

    <div v-if="stats.length" class="crm-hero__stats">
      <div v-for="item in stats" :key="item.label" class="crm-hero__stat">
        <div class="crm-hero__stat-value">{{ item.value }}</div>
        <div class="crm-hero__stat-label">{{ item.label }}</div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.crm-hero {
  padding: 0;
  overflow: hidden;
}

.crm-hero__main {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 20px 20px 16px;
  background: linear-gradient(135deg, #f8fbff 0%, #ffffff 58%);
  border-bottom: 1px solid var(--el-border-color-extra-light);
}

.crm-hero__avatar {
  flex-shrink: 0;
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: linear-gradient(135deg, var(--el-color-primary), #79bbff);
  color: #fff;
  font-size: 22px;
  font-weight: 700;
  line-height: 52px;
  text-align: center;
  box-shadow: 0 8px 20px rgba(64, 158, 255, 0.22);
}

.crm-hero__content {
  flex: 1;
  min-width: 0;
}

.crm-hero__title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.crm-hero__title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  line-height: 1.3;
  color: var(--el-text-color-primary);
}

.crm-hero__subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.crm-hero__owner {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  padding: 6px 12px;
  border-radius: 8px;
  background: rgba(64, 158, 255, 0.08);
  border: 1px solid var(--el-color-primary-light-8);
}

.crm-hero__owner-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.crm-hero__owner-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-color-primary);
}

.crm-hero__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
}

.crm-hero__meta-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid var(--el-border-color-lighter);
  font-size: 12px;
}

.crm-hero__meta-label {
  color: var(--el-text-color-secondary);
}

.crm-hero__meta-value {
  color: var(--el-text-color-primary);
  font-weight: 500;
}

.crm-hero__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.crm-hero__stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.crm-hero__stat {
  padding: 14px 16px;
  text-align: center;
  border-right: 1px solid var(--el-border-color-extra-light);
}

.crm-hero__stat:last-child {
  border-right: none;
}

.crm-hero__stat-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--el-color-primary);
  line-height: 1.2;
}

.crm-hero__stat-label {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

@media (max-width: 900px) {
  .crm-hero__main {
    flex-direction: column;
  }

  .crm-hero__actions {
    width: 100%;
    justify-content: flex-start;
  }

  .crm-hero__stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .crm-hero__stat:nth-child(2n) {
    border-right: none;
  }

  .crm-hero__stat:nth-child(-n + 2) {
    border-bottom: 1px solid var(--el-border-color-extra-light);
  }
}
</style>
