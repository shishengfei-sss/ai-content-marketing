import { regionData } from 'element-china-area-data'

/** 级联 value 使用中文名称，与 extra_data 存量数据一致 */
export function toRegionLabelTree(nodes) {
  return (nodes || []).map((node) => ({
    label: node.label,
    children: node.children?.length ? toRegionLabelTree(node.children) : [],
  }))
}

export function toRegionLabelOptions(nodes) {
  return (nodes || []).map((node) => ({
    value: node.label,
    label: node.label,
    children: node.children?.length ? toRegionLabelOptions(node.children) : undefined,
  }))
}

export const regionLabelTree = toRegionLabelTree(regionData)
export const regionLabelOptions = toRegionLabelOptions(regionData)

export function formatRegionDisplay(province, city, district) {
  return [province, city, district].filter(Boolean).join(' / ')
}
