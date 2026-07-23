import { ref } from 'vue'
import { crmApi } from '../api/client'

const leadPinnedViews = ref([])
const customerPinnedViews = ref([])
const dealPinnedViews = ref([])
let loadingPromise = null

const ENTITY_BY_PATH = {
  '/crm/leads': 'lead',
  '/crm/customers': 'customer',
  '/crm/deals': 'deal',
}

function filterPinned(views) {
  return (views || []).filter((v) => v.is_pinned)
}

function pinnedRefFor(entityType) {
  if (entityType === 'lead') return leadPinnedViews
  if (entityType === 'customer') return customerPinnedViews
  if (entityType === 'deal') return dealPinnedViews
  return null
}

export function usePinnedViews() {
  async function loadPinnedViews(force = false) {
    if (loadingPromise && !force) {
      await loadingPromise
      return {
        lead: leadPinnedViews.value,
        customer: customerPinnedViews.value,
        deal: dealPinnedViews.value,
      }
    }

    loadingPromise = Promise.all(
      Object.values(ENTITY_BY_PATH).map((entityType) =>
        crmApi.listViews(entityType).then(({ data }) => {
          const target = pinnedRefFor(entityType)
          if (target) target.value = filterPinned(Array.isArray(data) ? data : [])
          return target?.value || []
        }),
      ),
    )
      .catch(() => {
        leadPinnedViews.value = []
        customerPinnedViews.value = []
        dealPinnedViews.value = []
      })
      .finally(() => {
        loadingPromise = null
      })

    await loadingPromise
    return {
      lead: leadPinnedViews.value,
      customer: customerPinnedViews.value,
      deal: dealPinnedViews.value,
    }
  }

  function pinnedForPath(path) {
    const entityType = ENTITY_BY_PATH[path]
    return pinnedRefFor(entityType)?.value || []
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
    dealPinnedViews,
    loadPinnedViews,
    pinnedForPath,
    viewRoute,
    viewIndex,
  }
}

export function notifyPinnedViewsChanged() {
  window.dispatchEvent(new CustomEvent('crm:pinned-views-changed'))
}
