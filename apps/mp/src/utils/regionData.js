import { regionData } from 'element-china-area-data'

/** 级联 value 使用中文名称，与 Web 端及 extra_data 存量数据一致 */
export function toRegionLabelTree(nodes) {
  return (nodes || []).map((node) => ({
    label: node.label,
    children: node.children?.length ? toRegionLabelTree(node.children) : [],
  }))
}

export const regionLabelTree = toRegionLabelTree(regionData)

export function formatRegionDisplay(province, city, district) {
  return [province, city, district].filter(Boolean).join(' / ')
}

export function findRegionIndexes(tree, province, city, district) {
  let pi = 0
  let ci = 0
  let di = 0
  if (!province) return [pi, ci, di]

  const pIdx = tree.findIndex((p) => p.label === province)
  if (pIdx < 0) return [pi, ci, di]
  pi = pIdx

  const cities = tree[pi]?.children || []
  if (!city) return [pi, 0, 0]
  const cIdx = cities.findIndex((c) => c.label === city)
  if (cIdx < 0) return [pi, 0, 0]
  ci = cIdx

  const districts = cities[ci]?.children || []
  if (!district) return [pi, ci, 0]
  const dIdx = districts.findIndex((d) => d.label === district)
  di = dIdx >= 0 ? dIdx : 0
  return [pi, ci, di]
}
