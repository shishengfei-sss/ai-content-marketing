import { ref } from 'vue'
import { teamApi } from '../api/client'
import { useAuthStore } from '../stores/auth'

let cachedMembers = null
let loadingPromise = null

/** 成员增删改后调用，避免 CRM 各页仍显示旧名单/旧姓名 */
export function invalidateTeamMembersCache() {
  cachedMembers = null
  loadingPromise = null
}

export function useTeamMembers() {
  const auth = useAuthStore()
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
      .then(({ data }) => {
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

  function sameUserId(a, b) {
    if (a == null || b == null) return false
    return String(a).replace(/-/g, '').toLowerCase() === String(b).replace(/-/g, '').toLowerCase()
  }

  function findMember(userId) {
    if (!userId) return null
    return (cachedMembers || members.value).find((m) => sameUserId(m.user_id, userId)) || null
  }

  function resolveMemberName(userId, { withSelfTag = true } = {}) {
    if (!userId) return '未分配'
    const member = findMember(userId)
    const isSelf = sameUserId(userId, auth.user?.id)
    let name = member?.display_name || member?.phone || ''
    // 无 team.member.view 时成员列表为空：本人回退到登录用户资料
    if (!name && isSelf) {
      name = auth.user?.display_name || auth.user?.phone || ''
    }
    if (!name) name = '未知成员'
    // 单字昵称易被误认为空值，附带手机号便于辨认
    if (member?.phone && [...String(name)].length <= 1) {
      name = `${name}（${member.phone}）`
    }
    if (withSelfTag && isSelf) return `${name}（我）`
    return name
  }

  return {
    members,
    loadMembers,
    findMember,
    resolveMemberName,
    invalidateTeamMembersCache,
  }
}
