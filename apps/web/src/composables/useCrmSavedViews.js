import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../api/client'
import { notifyPinnedViewsChanged } from './usePinnedViews'

export function canEditSavedView(auth, view) {
  if (!view) return false
  if (view.owner_user_id === auth.user?.id) return true
  return auth.user?.active_tenant?.role_code === 'admin'
}

export function groupSavedViews(views, userId) {
  const mine = []
  const team = []
  for (const view of views || []) {
    if (view.owner_user_id === userId) {
      mine.push(view)
    } else if (view.is_public) {
      team.push(view)
    }
  }
  return { mine, team }
}

export async function deleteSavedView(view, { confirm = true } = {}) {
  if (!view?.id) return false
  if (confirm) {
    await ElMessageBox.confirm(`确定删除视图「${view.name}」？`, '删除视图', { type: 'warning' })
  }
  await crmApi.deleteView(view.id)
  if (view.is_pinned) notifyPinnedViewsChanged()
  ElMessage.success('视图已删除')
  return true
}

export async function pinSavedView(view) {
  if (!view?.id || view.is_pinned) return false
  await crmApi.updateView(view.id, { is_pinned: true })
  notifyPinnedViewsChanged()
  ElMessage.success('已钉选到侧栏')
  return true
}

export async function unpinSavedView(view) {
  if (!view?.id || !view.is_pinned) return false
  await crmApi.updateView(view.id, { is_pinned: false })
  notifyPinnedViewsChanged()
  ElMessage.success('已取消钉选')
  return true
}

export async function togglePinSavedView(view) {
  if (!view?.id) return false
  if (view.is_pinned) return unpinSavedView(view)
  return pinSavedView(view)
}

export async function setDefaultSavedView(view) {
  if (!view?.id) return false
  await crmApi.updateView(view.id, { is_default: true })
  ElMessage.success('已设为默认视图')
  return true
}

export function navigateToView(router, listPath, viewId) {
  if (viewId) {
    router.replace({ path: listPath, query: { view_id: String(viewId) } })
  } else {
    router.replace({ path: listPath })
  }
}

export function clearViewFromRoute(router, listPath, activeViewId, viewId) {
  if (String(activeViewId) !== String(viewId)) return
  navigateToView(router, listPath, '')
}
