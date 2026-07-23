/**
 * 合同状态与可操作矩阵（列表 / 详情 / H5 共用）。
 */

export const CONTRACT_STATUS_META = {
  draft: { label: '草稿', type: 'info' },
  sent: { label: '已发送', type: 'warning' },
  pending_approval: { label: '待审批', type: 'warning' },
  rejected: { label: '已驳回', type: 'danger' },
  signed: { label: '已签署', type: 'success' },
  executing: { label: '执行中', type: 'success' },
  expired: { label: '已过期', type: 'info' },
  terminated: { label: '已终止', type: 'danger' },
}

export const CONTRACT_TYPE_META = { new: '新签', renewal: '续约', addon: '增订' }

export function contractStatusMeta(status) {
  return CONTRACT_STATUS_META[status] || { label: status || '—', type: '' }
}

/**
 * @param {object} opts
 */
export function contractActions(opts) {
  const {
    status,
    isOwner = false,
    canEdit = false,
    canSign = false,
    canApprove = false,
    canCreate = false,
    canDelete = false,
    canConvert = false,
    canRenewDeal = false,
  } = opts || {}
  const mutate = isOwner
  return {
    edit: canEdit && mutate && ['draft', 'sent', 'rejected'].includes(status),
    send: canEdit && mutate && ['draft', 'rejected'].includes(status),
    submit: canSign && mutate && ['draft', 'sent', 'rejected'].includes(status),
    withdraw: canSign && mutate && status === 'pending_approval',
    approve: canApprove && status === 'pending_approval',
    reject: canApprove && status === 'pending_approval',
    sign: canSign && mutate && ['draft', 'sent'].includes(status),
    activate: canEdit && mutate && status === 'signed',
    terminate: canEdit && mutate && ['signed', 'executing'].includes(status),
    convert: canConvert && mutate && ['signed', 'executing'].includes(status),
    amend: canEdit && mutate && ['signed', 'executing'].includes(status),
    renewDeal: canRenewDeal && ['signed', 'executing', 'expired'].includes(status),
    renewContract: canCreate && ['signed', 'executing', 'expired'].includes(status),
    clone: canCreate,
    delete: canDelete && mutate && ['draft', 'sent', 'rejected'].includes(status),
  }
}
