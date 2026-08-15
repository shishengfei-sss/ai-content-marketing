/**
 * 商家端当前店铺。对照 PRD 01-管理端UI.html #a01-select-spec · C13
 * 顶栏切换 = 店铺管理「进入」；落点 localStorage shop.current_shop_id。
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import api from '../api/client'

export const CURRENT_SHOP_KEY = 'shop.current_shop_id'
export const CURRENT_SHOP_EVENT = 'shop:current-shop-changed'

const stores = ref([])
const currentId = ref(readStoredId())
const planLabel = ref('')
const roleLabel = ref('')
const storeScope = ref('all')
const loaded = ref(false)

function readStoredId() {
  try {
    return localStorage.getItem(CURRENT_SHOP_KEY) || ''
  } catch {
    return ''
  }
}

function persist(id) {
  try {
    if (id) localStorage.setItem(CURRENT_SHOP_KEY, String(id))
    else localStorage.removeItem(CURRENT_SHOP_KEY)
  } catch {
    /* ignore */
  }
}

export function getCurrentShopId() {
  return currentId.value || readStoredId()
}

export function setCurrentShopId(id) {
  const val = id ? String(id) : ''
  const changed = String(currentId.value || '') !== val
  currentId.value = val
  persist(val)
  if (changed) {
    window.dispatchEvent(new CustomEvent(CURRENT_SHOP_EVENT, { detail: { shopId: val } }))
  }
}

export function clearCurrentShopId() {
  setCurrentShopId('')
}

function preferDefaultStore(list) {
  return list.find((s) => s.status === 'active') || list[0] || null
}

function ensureValidId() {
  const list = stores.value
  if (!list.length) return
  const ok = list.some((s) => String(s.id) === String(currentId.value))
  if (!ok) {
    const pick = preferDefaultStore(list)
    if (pick) setCurrentShopId(pick.id)
  }
}

export async function loadCurrentShopStores() {
  try {
    const { data } = await api.get('/api/v1/shop/stores/options')
    stores.value = data.items || []
    planLabel.value = data.plan_label || ''
    roleLabel.value = data.role_label || ''
    storeScope.value = data.store_scope || 'all'
    loaded.value = true
    ensureValidId()
    return data
  } catch {
    stores.value = []
    loaded.value = true
    return { items: [] }
  }
}

export function useCurrentShop() {
  const currentStore = computed(
    () => stores.value.find((s) => String(s.id) === String(currentId.value)) || null,
  )

  function onExternalChange(e) {
    const id = e?.detail?.shopId ?? readStoredId()
    if (String(currentId.value || '') !== String(id || '')) {
      currentId.value = id || ''
    }
  }

  onMounted(() => {
    window.addEventListener(CURRENT_SHOP_EVENT, onExternalChange)
  })
  onUnmounted(() => {
    window.removeEventListener(CURRENT_SHOP_EVENT, onExternalChange)
  })

  return {
    stores,
    currentId,
    currentStore,
    planLabel,
    roleLabel,
    storeScope,
    loaded,
    loadStores: loadCurrentShopStores,
    setCurrent: setCurrentShopId,
  }
}
