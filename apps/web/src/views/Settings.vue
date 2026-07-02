<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

const settingsMenu = [
  { title: '品牌设置', desc: '公司名、人设、语气、CTA', icon: 'Shop', path: '/settings' },
  { title: '我的偏好', desc: '个人风格与提示词', icon: 'User', path: '/settings' },
  { title: '公众号绑定', desc: '服务号 OAuth（部署后可用）', icon: 'ChatLineRound', path: '/settings' },
  { title: 'AI 模型', desc: 'DeepSeek / 其他大模型配置', icon: 'Cpu', path: '/settings/llm' },
]
</script>

<template>
  <div class="settings-page">
    <el-row :gutter="16">
      <el-col v-for="item in settingsMenu" :key="item.title" :span="12">
        <div
          class="page-card settings-card"
          @click="router.push(item.path)"
        >
          <el-icon :size="32" class="settings-card__icon">
            <component :is="item.icon" />
          </el-icon>
          <div>
            <div class="settings-card__title">{{ item.title }}</div>
            <div class="settings-card__desc">{{ item.desc }}</div>
          </div>
          <el-icon class="settings-card__arrow"><ArrowRight /></el-icon>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.settings-card {
  display: flex;
  align-items: center;
  gap: 16px;
  cursor: pointer;
  margin-bottom: 16px;
  transition: box-shadow 0.2s;
}

.settings-card:hover {
  box-shadow: 0 4px 12px rgba(22, 119, 255, 0.15);
}

.settings-card__icon {
  color: var(--color-primary);
}

.settings-card__title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 4px;
}

.settings-card__desc {
  font-size: 13px;
  color: var(--color-text-secondary);
}

.settings-card__arrow {
  margin-left: auto;
  color: var(--color-text-muted);
}
</style>
