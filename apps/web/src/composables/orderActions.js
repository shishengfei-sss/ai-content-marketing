/**
 * 订单状态与可操作矩阵（列表 / 详情 / H5 共用）。
 */

export const ORDER_STATUS_META = {
  draft: { label: '草稿', type: 'info' },
  pending_approval: { label: '待审批', type: 'warning' },
  approved: { label: '已审批', type: 'success' },
  rejected: { label: '已驳回', type: 'danger' },
  confirmed: { label: '已确认', type: 'success' },
  executing: { label: '执行中', type: 'warning' },
  completed: { label: '已完成', type: 'success' },
  cancelled: { label: '已取消', type: 'danger' },
  superseded: { label: '已修订', type: 'info' },
}

export const ORDER_SOURCE_META = { deal: '商机', quote: '报价', contract: '合同' }

export function orderStatusMeta(status) {
  return ORDER_STATUS_META[status] || { label: status || '—', type: '' }
}

/**
 * @param {object} opts
 * @param {string} opts.status
 * @param {boolean} opts.isOwner
 * @param {boolean} opts.canEdit
 * @param {boolean} opts.canPlace
 * @param {boolean} opts.canApprove
 * @param {boolean} opts.canCreate
 * @param {boolean} opts.canDelete
 */
export function orderActions(opts) {
  const {
    status,
    isOwner = false,
    canEdit = false,
    canPlace = false,
    canApprove = false,
    canCreate = false,
    canDelete = false,
  } = opts || {}
  const mutate = isOwner
  return {
    edit: canEdit && mutate && (status === 'draft' || status === 'rejected'),
    /** 统一提交：无规则直确认，有规则进审批 */
    submit: canPlace && mutate && (status === 'draft' || status === 'rejected'),
    withdraw: canPlace && mutate && status === 'pending_approval',
    approve: canApprove && status === 'pending_approval',
    reject: canApprove && status === 'pending_approval',
    revise: canPlace && mutate && (status === 'confirmed' || status === 'executing'),
    complete: canEdit && mutate && (status === 'confirmed' || status === 'executing'),
    /** 取消：已进入流程的订单；与删除互斥（草稿/驳回/已取消走删除） */
    cancel:
      canEdit &&
      mutate &&
      ['pending_approval', 'approved', 'confirmed', 'executing'].includes(status),
    clone: canCreate,
    saveAsTemplate: canCreate,
    /** 删除：草稿/驳回/已取消；与取消互斥 */
    delete: canDelete && mutate && ['draft', 'cancelled', 'rejected'].includes(status),
  }
}
