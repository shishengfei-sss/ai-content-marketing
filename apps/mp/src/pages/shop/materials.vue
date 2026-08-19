<script setup>
/**
 * M09 资料领取/下载。对照 PRD #m09
 */
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { ensureShopBuyerSession, getShopBuyerTenantId, setShopBuyerTenantId, shopBuyerApi } from '@/utils/shopApi'

const entitlementId = ref('')
const loading = ref(true)
const data = ref(null)
const previewUrl = ref('')
const previewName = ref('')
const openidHint = ref('')

const revoked = computed(() => data.value && data.value.entitlement_status !== 'active')

function fmtSize(n) {
  if (!n) return '—'
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)}KB`
  return `${(n / (1024 * 1024)).toFixed(1)}MB`
}

async function load() {
  loading.value = true
  try {
    await ensureShopBuyerSession(getShopBuyerTenantId(), openidHint.value || undefined)
    data.value = await shopBuyerApi.getMaterials(entitlementId.value)
    if (data.value.entitlement_status === 'revoked') {
      uni.showToast({ title: '权限已关闭', icon: 'none' })
    }
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function download(file) {
  if (revoked.value) {
    uni.showToast({ title: '权限已关闭', icon: 'none' })
    return
  }
  if (file.download_disabled) {
    uni.showToast({ title: '已达下载上限', icon: 'none' })
    return
  }
  try {
    const res = await shopBuyerApi.downloadMaterial(entitlementId.value, file.id)
    uni.setClipboardData({
      data: res.download_url,
      success: () => uni.showToast({ title: '下载链接已复制', icon: 'success' }),
    })
    await load()
  } catch (e) {
    uni.showToast({ title: e.message || '下载失败，请重试', icon: 'none' })
  }
}

function preview(file) {
  if (revoked.value) {
    uni.showToast({ title: '权限已关闭', icon: 'none' })
    return
  }
  if (!file.can_preview) {
    uni.showToast({ title: '该文件不支持预览', icon: 'none' })
    return
  }
  previewName.value = file.name
  previewUrl.value = `preview://${file.id}`
}

function closePreview() {
  previewUrl.value = ''
  previewName.value = ''
}

onLoad((q) => {
  entitlementId.value = (q?.entitlement_id || '').trim()
  const tid = (q?.tenant_id || '').trim()
  if (tid) setShopBuyerTenantId(tid)
  openidHint.value = (q?.openid || '').trim()
  if (entitlementId.value) load()
})
</script>

<template>
  <view class="page">
    <view class="head">
      <text class="title">资料领取</text>
      <text class="sub">数字权益</text>
    </view>
    <view v-if="loading" class="empty">加载中…</view>
    <template v-else-if="data">
      <view v-if="revoked" class="revoked">
        <text class="revoked-title">权限已关闭</text>
        <text class="revoked-sub">退款后资料不可再下载</text>
      </view>
      <text class="meta">
        {{ data.product_name }} · {{ data.deliver_mode === 'online_view' ? '在线查看' : '仅下载' }} ·
        {{ data.files.length }} 个文件
      </text>
      <view v-for="f in data.files" :key="f.id" class="card">
        <view>
          <text class="name">{{ f.name }}</text>
          <text class="size">
            {{ fmtSize(f.size_bytes) }}
            <text v-if="!f.can_preview"> · 仅下载</text>
            <text v-if="f.remaining_downloads === 0" class="danger"> · 已达上限</text>
          </text>
        </view>
        <view class="ops">
          <button
            v-if="f.can_preview"
            class="btn"
            size="mini"
            :disabled="revoked"
            @click="preview(f)"
          >
            预览
          </button>
          <button
            class="btn primary"
            size="mini"
            :disabled="revoked || f.download_disabled"
            @click="download(f)"
          >
            下载
          </button>
        </view>
      </view>
      <text class="hint">
        已下载 {{ data.total_download_count }} 次
        <text v-if="data.max_downloads != null"> · 上限 {{ data.max_downloads }} 次/文件</text>
        <text v-else> · 不限次数</text>
      </text>
    </template>

    <view v-if="previewUrl" class="mask" @click="closePreview">
      <view class="preview" @click.stop>
        <text class="preview-title">{{ previewName }} · 在线预览</text>
        <view class="preview-box">PDF 预览区（Mock）</view>
        <button class="btn" @click="closePreview">关闭预览</button>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f3f5f9;
  padding: 16px;
}
.head {
  margin-bottom: 10px;
}
.title {
  display: block;
  font-size: 20px;
  font-weight: 800;
}
.sub {
  display: block;
  font-size: 12px;
  color: #64748b;
}
.meta {
  display: block;
  font-size: 12px;
  margin-bottom: 10px;
  color: #475569;
}
.card {
  background: #fff;
  border-radius: 16px;
  padding: 12px;
  margin-bottom: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
}
.name {
  display: block;
  font-weight: 700;
  font-size: 13px;
}
.size {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  color: #64748b;
}
.danger {
  color: #991b1b;
}
.ops {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
.btn {
  margin: 0;
  background: #fff;
  border: 1px solid #cbd5e1;
  color: #334155;
  border-radius: 999px;
}
.btn.primary {
  background: #1677ff;
  color: #fff;
  border: none;
}
.hint {
  display: block;
  margin-top: 10px;
  font-size: 11px;
  color: #64748b;
}
.revoked {
  text-align: center;
  padding: 20px;
  margin-bottom: 12px;
  background: #fff;
  border-radius: 12px;
  opacity: 0.85;
}
.revoked-title {
  display: block;
  color: #991b1b;
  font-weight: 700;
  margin-bottom: 6px;
}
.revoked-sub {
  display: block;
  font-size: 12px;
  color: #64748b;
}
.mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
.preview {
  width: 100%;
  background: #fff;
  border-radius: 12px;
  padding: 14px;
}
.preview-title {
  display: block;
  font-size: 12px;
  margin-bottom: 8px;
  font-weight: 600;
}
.preview-box {
  height: 160px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 12px;
  margin-bottom: 10px;
}
.empty {
  text-align: center;
  color: #94a3b8;
  margin-top: 40px;
}
</style>
