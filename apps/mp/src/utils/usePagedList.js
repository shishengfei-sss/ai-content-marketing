import { computed, ref } from 'vue'

/** H5 列表分页：首屏加载 + 滚动触底加载更多 */
export function usePagedList(loadPage, pageSize = 20) {
  const loading = ref(false)
  const loadingMore = ref(false)
  const items = ref([])
  const total = ref(0)
  const page = ref(1)

  const hasMore = computed(() => items.value.length < total.value)

  async function fetchPage(pageNum, append = false) {
    const data = await loadPage(pageNum, pageSize)
    total.value = data?.total ?? 0
    const rows = data?.items || []
    items.value = append ? [...items.value, ...rows] : rows
    page.value = pageNum
  }

  async function loadFirst() {
    loading.value = true
    try {
      await fetchPage(1, false)
    } finally {
      loading.value = false
    }
  }

  async function loadMore() {
    if (loading.value || loadingMore.value || !hasMore.value) return
    loadingMore.value = true
    try {
      await fetchPage(page.value + 1, true)
    } finally {
      loadingMore.value = false
    }
  }

  function reset() {
    items.value = []
    total.value = 0
    page.value = 1
  }

  return {
    loading,
    loadingMore,
    items,
    total,
    page,
    hasMore,
    loadFirst,
    loadMore,
    reset,
  }
}
