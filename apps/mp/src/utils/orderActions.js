/**
 * 订单状态与可操作矩阵（与 Web apps/web/src/composables/orderActions.js 保持一致）。
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
    submit: canPlace && mutate && (status === 'draft' || status === 'rejected'),
    withdraw: canPlace && mutate && status === 'pending_approval',
    approve: canApprove && status === 'pending_approval',
    reject: canApprove && status === 'pending_approval',
    revise: canPlace && mutate && (status === 'confirmed' || status === 'executing'),
    complete: canEdit && mutate && (status === 'confirmed' || status === 'executing'),
    cancel:
      canEdit &&
      mutate &&
      ['pending_approval', 'approved', 'confirmed', 'executing'].includes(status),
    clone: canCreate,
    saveAsTemplate: canCreate,
    delete: canDelete && mutate && ['draft', 'cancelled', 'rejected'].includes(status),
  }
}
