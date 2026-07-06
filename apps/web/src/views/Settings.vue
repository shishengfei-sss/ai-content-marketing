<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { hasAnyPermission, hasPermission } from '../config/permissions'

const router = useRouter()
const auth = useAuthStore()

const settingsMenu = computed(() => {
  const p = auth.permissions
  const items = [
    {
      title: '企业信息',
      desc: '公司名称、行业、信用代码',
      icon: 'OfficeBuilding',
      path: '/settings/tenant',
      show: hasPermission(p, 'tenant.manage'),
    },
    {
      title: '角色与成员',
      desc: '企业角色、成员与权限',
      icon: 'UserFilled',
      path: '/settings/team',
      show: hasAnyPermission(p, ['team.member.view', 'team.role.manage']),
    },
    {
      title: '品牌设置',
      desc: '公司名、人设、语气、CTA',
      icon: 'Shop',
      path: '/settings/brand',
      show: hasPermission(p, 'brand.manage'),
    },
    {
      title: '我的偏好',
      desc: '个人风格与提示词',
      icon: 'User',
      path: '/settings/preference',
      show: hasPermission(p, 'preference.manage'),
    },
    {
      title: '公众号绑定',
      desc: 'Mock / 服务号 OAuth',
      icon: 'ChatLineRound',
      path: '/settings/wechat',
      show: hasPermission(p, 'wechat.manage'),
    },
    {
      title: 'AI 模型',
      desc: 'DeepSeek / 其他大模型配置',
      icon: 'Cpu',
      path: '/settings/llm',
      show: hasPermission(p, 'llm.manage'),
    },
  ]
  return items.filter((i) => i.show)
})
</script>

<template>
  <div class="settings-page">
    <el-empty v-if="!settingsMenu.length" description="当前角色暂无可用的设置项" />
    <el-row v-else :gutter="16">
      <el-col v-for="item in settingsMenu" :key="item.title" :span="12">
        <div class="page-card settings-card" @click="router.push(item.path)">
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
