<script setup>
import { ArrowLeft } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  loading: { type: Boolean, default: false },
  listPath: { type: String, required: true },
  entityLabel: { type: String, required: true },
  title: { type: String, default: '' },
})

const router = useRouter()

function goBack() {
  router.push(props.listPath)
}
</script>

<template>
  <div v-loading="loading" class="crm-detail">
    <nav class="crm-detail__nav">
      <button type="button" class="crm-detail__back" aria-label="返回列表" @click="goBack">
        <el-icon :size="16"><ArrowLeft /></el-icon>
      </button>
      <el-breadcrumb class="crm-detail__breadcrumb" separator="/">
        <el-breadcrumb-item>
          <span class="crm-detail__link" @click="goBack">{{ entityLabel }}</span>
        </el-breadcrumb-item>
        <el-breadcrumb-item v-if="title">
          <span class="crm-detail__current">{{ title }}</span>
        </el-breadcrumb-item>
      </el-breadcrumb>
    </nav>

    <slot />
  </div>
</template>

<style scoped>
.crm-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
}

.crm-detail__nav {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
}

.crm-detail__back {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border: none;
  border-radius: 8px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
  cursor: pointer;
  flex-shrink: 0;
  transition:
    background-color 0.15s ease,
    color 0.15s ease;
}

.crm-detail__back:hover {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}

.crm-detail__breadcrumb {
  flex: 1;
  min-width: 0;
  line-height: 1.4;
}

.crm-detail__breadcrumb :deep(.el-breadcrumb__inner) {
  font-weight: 400;
}

.crm-detail__link {
  color: var(--el-text-color-secondary);
  cursor: pointer;
  transition: color 0.15s ease;
}

.crm-detail__link:hover {
  color: var(--el-color-primary);
}

.crm-detail__current {
  display: inline-block;
  max-width: min(480px, 50vw);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: bottom;
  color: var(--el-text-color-primary);
  font-weight: 500;
}
</style>
