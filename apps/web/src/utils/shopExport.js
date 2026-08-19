import { ElMessage } from 'element-plus'
import api from '../api/client'

/** 与 PRD / 后端 export_limits.SHOP_EXPORT_ROW_LIMIT 一致 */
export const SHOP_EXPORT_ROW_LIMIT = 5000

/** 导出下拉：区别在 CSV 列范围（数据范围均为当前筛选） */
export const SHOP_EXPORT_COLUMN_MODE_LABELS = {
  allColumns: '全部默认列',
  visibleColumns: '当前可见列',
}

/** 导出下拉：区别在数据范围（如买家列表） */
export const SHOP_EXPORT_SCOPE_LABELS = {
  filtered: '筛选结果',
  selected: '选中行',
}

export function assertExportWithinLimit(total) {
  const n = Number(total) || 0
  if (n > SHOP_EXPORT_ROW_LIMIT) {
    throw new Error(
      `当前筛选共 ${n.toLocaleString()} 条，超过单次导出上限 ${SHOP_EXPORT_ROW_LIMIT.toLocaleString()} 条，请缩小筛选范围`,
    )
  }
}

export async function downloadShopExportFile(taskBasePath, taskId, filename) {
  const res = await api.get(`${taskBasePath}/${taskId}/file`, { responseType: 'blob' })
  const blob =
    res.data instanceof Blob ? res.data : new Blob([res.data], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

/**
 * 创建导出任务后立即下载 CSV。
 * @param {number|null|undefined} totalCount 当前筛选总条数；传入时在请求前校验 ≤5000
 */
export async function submitShopExport(postUrl, body, taskBasePath, defaultFilename, totalCount) {
  if (totalCount != null) {
    assertExportWithinLimit(totalCount)
  }
  const { data } = await api.post(postUrl, body)
  if (!data?.id) throw new Error('导出失败')
  await downloadShopExportFile(taskBasePath, data.id, data.file_name || defaultFilename)
  const rows = data.row_count ?? 0
  ElMessage.success(
    rows >= SHOP_EXPORT_ROW_LIMIT
      ? `已导出 ${rows.toLocaleString()} 条（已达单次上限）`
      : `已导出 ${rows.toLocaleString()} 条`,
  )
  return data
}
