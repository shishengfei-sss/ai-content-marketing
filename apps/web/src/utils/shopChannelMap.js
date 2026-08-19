/** A14 公域映射：同一渠道一条活跃映射。对照 PRD #a14a-step1「未映射过同 channel」。 */

export const CHANNEL_MOUNT_BLOCK_TIPS = {
  mapped: '该商品已映射抖店，同一渠道只能映射一次。请到公域对接列表暂停或恢复。',
  pending: '该商品正在外部审核中，无法重复新建映射。',
  syncing: '该商品正在同步抖店，请稍后再试。',
  rejected: '该商品挂载被拒，请到公域对接列表查看原因并重新提交。',
}

const CHANNEL_API_ERR = {
  product_already_mapped: CHANNEL_MOUNT_BLOCK_TIPS.mapped,
  channel_product_already_mapped: '该抖店商品已映射其他本地商品，无法重复绑定。',
  product_not_on_sale: '商品未在售，无法新建映射。',
  product_not_reviewed: '商品未过审，无法新建映射。',
  merchant_not_active: '商家未经营中，无法新建映射。',
  shop_not_active: '店铺未经营中，无法新建映射。',
}

export function mappingBlockTip(product) {
  const mount = product?.channel_mount
  if (!mount || mount === 'none') return ''
  return CHANNEL_MOUNT_BLOCK_TIPS[mount] || '该商品暂不可新建映射。'
}

export function channelApiError(err, fallback = '操作失败') {
  const raw = String(err?.message || '').trim()
  if (CHANNEL_API_ERR[raw]) return CHANNEL_API_ERR[raw]
  if (raw.includes('product_already_mapped')) return CHANNEL_API_ERR.product_already_mapped
  if (raw.includes('channel_product_already_mapped')) {
    return CHANNEL_API_ERR.channel_product_already_mapped
  }
  return raw || fallback
}
