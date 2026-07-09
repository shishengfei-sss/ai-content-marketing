import { ref } from 'vue'
import { teamApi } from '@/utils/api'

let cachedMembers = null
let loadingPromise = null

export function invalidateTeamMembersCache() {
  cachedMembers = null
  loadingPromise = null
}

export function useTeamMembers() {
  const members = ref(cachedMembers || [])

  async function loadMembers(force = false) {
    if (force) {
      invalidateTeamMembersCache()
    }
    if (cachedMembers && !force) {
      members.value = cachedMembers
      return cachedMembers
    }
    if (loadingPromise && !force) {
      await loadingPromise
      members.value = cachedMembers || []
      return cachedMembers || []
    }
    loadingPromise = teamApi
      .listMembers()
      .then((data) => {
        cachedMembers = Array.isArray(data) ? data : []
        members.value = cachedMembers
        return cachedMembers
      })
      .catch(() => {
        cachedMembers = []
        members.value = []
        return []
      })
      .finally(() => {
        loadingPromise = null
      })
    return loadingPromise
  }

  function resolveMemberName(userId, { empty = '—' } = {}) {
    if (!userId) return empty
    const list = members.value.length ? members.value : cachedMembers || []
    const m = list.find((x) => String(x.user_id) === String(userId))
    return m?.display_name || m?.phone || empty
  }

  return { members, loadMembers, resolveMemberName, invalidateTeamMembersCache }
}

export function resolveMemberNameSync(userId, { empty = '—' } = {}) {
  if (!userId) return empty
  const m = (cachedMembers || []).find((x) => String(x.user_id) === String(userId))
  return m?.display_name || m?.phone || empty
}
