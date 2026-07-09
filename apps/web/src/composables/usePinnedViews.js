import { ref } from 'vue'
import { crmApi } from '../api/client'

const leadPinnedViews = ref([])
const customerPinnedViews = ref([])
let loadingPromise = null

function filterPinned(views) {
  return (views || []).filter((v) => v.is_pinned)
}

export function usePinnedViews() {
  async function loadPinnedViews(force = false) {
    if (loadingPromise && !force) {
      await loadingPromise
      return { lead: leadPinnedViews.value, customer: customerPinnedViews.value }
    }

    loadingPromise = Promise.all([
      crmApi.listViews('lead').then(({ data }) => {
        leadPinnedViews.value = filterPinned(Array.isArray(data) ? data : [])
        return leadPinnedViews.value
      }),
      crmApi.listViews('customer').then(({ data }) => {
        customerPinnedViews.value = filterPinned(Array.isArray(data) ? data : [])
        return customerPinnedViews.value
      }),
    ])
      .catch(() => {
        leadPinnedViews.value = []
        customerPinnedViews.value = []
      })
      .finally(() => {
        loadingPromise = null
      })

    await loadingPromise
    return { lead: leadPinnedViews.value, customer: customerPinnedViews.value }
  }

  function pinnedForPath(path) {
    if (path === '/crm/leads') return leadPinnedViews.value
    if (path === '/crm/customers') return customerPinnedViews.value
    return []
  }

  function viewRoute(path, viewId) {
    return { path, query: { view_id: viewId } }
  }

  function viewIndex(path, viewId) {
    return `${path}?view_id=${viewId}`
  }

  return {
    leadPinnedViews,
    customerPinnedViews,
    loadPinnedViews,
    pinnedForPath,
    viewRoute,
    viewIndex,
  }
}

export function notifyPinnedViewsChanged() {
  window.dispatchEvent(new CustomEvent('crm:pinned-views-changed'))
}
