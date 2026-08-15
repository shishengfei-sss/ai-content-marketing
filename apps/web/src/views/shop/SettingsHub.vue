<script setup>
/**
 * A-SET 设置中心。对照 PRD 01-管理端UI.html #a-settings
 * 侧栏「设置」先进本页（卡片导航），再进各子页。
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { hasAnyPermission, hasPermission } from '../../config/permissions'

const router = useRouter()
const auth = useAuthStore()

const cards = computed(() => {
  const p = auth.permissions || []
  return [
    {
      key: 'account',
      title: '我的账号',
      desc: '昵称 · 登录手机（只读）· 改密码',
      path: '/settings/account',
      show: true,
    },
    {
      key: 'payment',
      title: '支付与进件',
      desc: '微信进件材料 · 子商户状态 · 商家级',
      path: '/shop/payment',
      show: hasAnyPermission(p, ['shop.settings.read', 'shop.settings.write']),
    },
    {
      key: 'sms',
      title: '短信 / 领权',
      desc: '领权域名/过期天数 · 签名模板只读 · 商家级',
      path: '/shop/sms-settings',
      show: hasAnyPermission(p, ['shop.settings.read', 'shop.settings.write']),
    },
    {
      key: 'channel',
      title: '公域对接',
      desc: '选链路/路径、绑店、回调验通 · 租户级',
      path: '/shop/channel-settings',
      show: hasAnyPermission(p, ['shop.channel.read', 'shop.channel.map', 'shop.channel.write']),
    },
    {
      key: 'subscription',
      title: '套餐信息',
      desc: '合并权益只读 · 商家级',
      path: '/shop/subscription',
      show: hasPermission(p, 'shop.subscription.usage.read'),
    },
    {
      key: 'store',
      title: '单店设置',
      desc: 'Logo / 简介 / 退款默认 · 当前店',
      path: '/shop/store-settings',
      show: hasAnyPermission(p, ['shop.store.settings.read', 'shop.store.settings.write']),
    },
    {
      key: 'roles',
      title: '角色与成员',
      desc: '内置角色、成员绑定、权限矩阵只读',
      path: '/shop/roles-members',
      show: hasAnyPermission(p, ['shop.role.manage', 'team.member.view']),
    },
  ].filter((c) => c.show)
})

function open(path) {
  router.push(path)
}
</script>

<template>
  <div class="page-card a-set">
    <div class="hd">
      <h3>设置</h3>
    </div>
    <p class="intro">
      侧栏「公域对接」= 日常商品映射；下方卡片「公域对接」= 一次性租户配置（选链路/绑店/验通）。
    </p>
    <div class="grid">
      <button
        v-for="c in cards"
        :key="c.key"
        type="button"
        class="card"
        @click="open(c.path)"
      >
        <div class="title">{{ c.title }}</div>
        <div class="desc">{{ c.desc }}</div>
        <div class="link">打开 →</div>
      </button>
    </div>
  </div>
</template>

<style scoped>
.a-set .hd h3 {
  margin: 0 0 8px;
  font-size: 18px;
}
.intro {
  font-size: 12px;
  color: #666;
  line-height: 1.6;
  margin: 0 0 14px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
@media (max-width: 960px) {
  .grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 640px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
.card {
  border: 1px solid var(--el-border-color, #e5e7eb);
  border-radius: 8px;
  padding: 14px;
  background: #fff;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.card:hover {
  border-color: #91caff;
  box-shadow: 0 2px 8px rgba(22, 119, 255, 0.08);
}
.title {
  font-weight: 700;
  margin-bottom: 4px;
  font-size: 14px;
}
.desc {
  font-size: 12px;
  color: #666;
  margin-bottom: 10px;
  line-height: 1.5;
  min-height: 36px;
}
.link {
  font-size: 12px;
  color: #1677ff;
}
</style>
