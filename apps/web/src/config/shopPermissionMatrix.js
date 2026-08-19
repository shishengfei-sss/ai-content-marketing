/** A16 商城权限矩阵展示。对照 05-角色权限.html #matrix */

export const SHOP_PERMISSION_LABELS = {
  'shop.analytics.read': '交易看板查看',
  'shop.product.read': '商品查看',
  'shop.product.write': '商品编辑',
  'shop.product.submit_review': '提交商品审核',
  'shop.product.publish': '商品上架/下架',
  'shop.product.delete': '商品删除',
  'shop.content.read': '内容查看',
  'shop.content.write': '内容编辑',
  'shop.redemption.read': '核销查询',
  'shop.redemption.execute': '核销确认',
  'shop.redemption.list_all': '核销记录（全店）',
  'shop.redemption.list_own': '核销记录（本人）',
  'shop.order.view': '订单查看',
  'shop.order.export': '订单导出',
  'shop.order.close': '关闭待付款订单',
  'shop.order.refund': '订单退款',
  'shop.order.resend_notify': '重发领权/通知',
  'shop.order.list_all': '订单列表（全部）',
  'shop.order.list_own': '订单列表（本人）',
  'shop.buyer.view': '买家查看',
  'shop.buyer.list_all': '买家列表（全部）',
  'shop.entitlement.view': '权益查看',
  'shop.entitlement.revoke': '权益关闭',
  'shop.entitlement.list_all': '权益列表（全部）',
  'shop.invoice.view': '开票查看',
  'shop.invoice.process': '开票处理',
  'shop.invoice.list_all': '开票列表（全部）',
  'shop.channel.read': '公域对接查看',
  'shop.channel.write': '公域对接配置',
  'shop.channel.map': '商品映射',
  'shop.settings.read': '支付/短信进件查看',
  'shop.settings.write': '支付/短信进件编辑',
  'shop.subscription.usage.read': '套餐权益查看',
  'shop.store.manage': '店铺管理',
  'shop.store.settings.read': '单店设置查看',
  'shop.store.settings.write': '单店设置编辑',
  'shop.role.manage': '角色与成员管理',
}

export const SHOP_MATRIX_GROUPS = [
  {
    title: '看板',
    codes: ['shop.analytics.read'],
  },
  {
    title: '商品',
    codes: [
      'shop.product.read',
      'shop.product.write',
      'shop.product.submit_review',
      'shop.product.publish',
      'shop.product.delete',
    ],
  },
  {
    title: '内容',
    codes: ['shop.content.read', 'shop.content.write'],
  },
  {
    title: '核销',
    codes: [
      'shop.redemption.read',
      'shop.redemption.execute',
      'shop.redemption.list_all',
      'shop.redemption.list_own',
    ],
  },
  {
    title: '订单',
    codes: [
      'shop.order.view',
      'shop.order.export',
      'shop.order.close',
      'shop.order.refund',
      'shop.order.resend_notify',
      'shop.order.list_all',
      'shop.order.list_own',
    ],
  },
  {
    title: '买家 / 权益',
    codes: [
      'shop.buyer.view',
      'shop.buyer.list_all',
      'shop.entitlement.view',
      'shop.entitlement.revoke',
      'shop.entitlement.list_all',
    ],
  },
  {
    title: '开票',
    codes: ['shop.invoice.view', 'shop.invoice.process', 'shop.invoice.list_all'],
  },
  {
    title: '公域对接',
    codes: ['shop.channel.read', 'shop.channel.write', 'shop.channel.map'],
  },
  {
    title: '支付与进件',
    codes: ['shop.settings.read', 'shop.settings.write'],
  },
  {
    title: '套餐',
    codes: ['shop.subscription.usage.read'],
  },
  {
    title: '店铺',
    codes: ['shop.store.manage', 'shop.store.settings.read', 'shop.store.settings.write'],
  },
  {
    title: '角色',
    codes: ['shop.role.manage'],
  },
]

export const ALL_SHOP_PERMISSION_CODES = [
  ...new Set(SHOP_MATRIX_GROUPS.flatMap((g) => g.codes)),
]

export const ROLE_CAPABILITY_SUMMARY = {
  admin: '商城全部能力 + 角色成员管理 + 公域对接配置',
  shop_admin: '商品/内容读写 · 订单/买家/权益/开票 · 核销 · 公域映射 · 店铺与单店设置',
  shop_content: '商品与内容读写 · 交易看板只读',
  shop_support: '订单/买家/权益/开票 · 核销查询 · 商品只读',
  shop_clerk: '核销确认与本人核销记录',
}

export function resolveRoleShopPermissions(role) {
  if (!role?.permissions?.length) return new Set()
  if (role.permissions.includes('*')) return new Set(ALL_SHOP_PERMISSION_CODES)
  return new Set(role.permissions.filter((p) => p.startsWith('shop.')))
}

export function shopPermissionLabel(code) {
  return SHOP_PERMISSION_LABELS[code] || code
}

export function roleCapabilitySummary(role) {
  if (!role) return '—'
  return ROLE_CAPABILITY_SUMMARY[role.code] || `共 ${resolveRoleShopPermissions(role).size} 项商城权限`
}
