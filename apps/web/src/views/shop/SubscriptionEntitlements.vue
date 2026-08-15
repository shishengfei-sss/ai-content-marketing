<script setup>
/**
 * A18 套餐信息。对照 PRD 01-管理端UI.html #a18
 * 只读：合并权益、生效订阅、用量进度、升级引导
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api/client'
import ShopSettingsNav from '../../components/shop/ShopSettingsNav.vue'

const router = useRouter()
const loading = ref(false)
const data = ref(null)

const summary = computed(() => data.value?.summary || {})
const alerts = computed(() => summary.value.alerts || [])
const groups = computed(() => data.value?.usage_groups || [])
const subscriptions = computed(() => data.value?.subscriptions || [])

async function load() {
  loading.value = true
  try {
    const { data: res } = await api.get('/api/v1/shop/subscription/overview')
    data.value = res
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function barColor(item) {
  if (item.over_limit || item.at_limit) return '#ff4d4f'
  if ((item.percent || 0) >= 80) return '#faad14'
  return '#52c41a'
}

function go(path) {
  if (path) router.push(path)
}

function contactUpgrade() {
  ElMessage.info(data.value?.upgrade_hint || '请联系平台运营申请升级')
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="page-card a18">
    <div class="hd">
      <div>
        <div class="crumb">设置 / <b>套餐信息</b></div>
        <h3>套餐信息</h3>
      </div>
      <el-tag v-if="data?.plan_label" type="success" effect="plain">
        {{ data.plan_label }}
        <template v-if="data.benefits_until"> · 权益至 {{ data.benefits_until }}</template>
      </el-tag>
    </div>

    <ShopSettingsNav current="subscription" />

    <el-alert
      v-if="data?.state === 'not_onboarded'"
      type="warning"
      :closable="false"
      title="尚未入驻商城，暂无套餐权益"
    />

    <template v-else-if="data">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="怎么用您的套餐？"
        description="以下为平台为您开通的全部生效套餐合并后的实际额度。做业务时系统会自动校验；额度不足时相关按钮会禁用并提示联系升级。"
        style="margin-bottom: 14px"
      />

      <div class="cards">
        <div class="card">
          <div class="k">主套餐</div>
          <div class="v">{{ summary.main_plan_name || data.plan_label || '—' }}</div>
          <div class="s">至 {{ summary.benefits_until || data.benefits_until || '—' }}</div>
        </div>
        <div class="card">
          <div class="k">生效订阅</div>
          <div class="v">
            {{ summary.active_count ?? 0 }}
            <span class="unit">条叠加</span>
          </div>
          <div class="s">含 {{ summary.addon_count ?? 0 }} 条加购包</div>
        </div>
        <div class="card" :class="{ warn: alerts.length }">
          <div class="k">{{ alerts.length ? '需关注' : '状态' }}</div>
          <div class="v" :class="{ danger: alerts.length }">
            {{ alerts[0]?.title || '额度正常' }}
          </div>
          <div class="s">{{ alerts[0]?.detail || '未触达店铺/商品上限' }}</div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-title">生效中订阅</div>
        <el-table :data="subscriptions" size="small" border empty-text="暂无订阅（按免费版权益）">
          <el-table-column prop="plan_name" label="套餐" min-width="140" />
          <el-table-column prop="plan_type_label" label="类型" width="100" />
          <el-table-column label="有效期" min-width="200">
            <template #default="{ row }">
              {{ row.effective_at || '—' }} ～ {{ row.expires_at_inclusive || '—' }}
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
                {{ row.status_label }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="panel">
        <div class="panel-title">合并后可用额度</div>
        <p class="sub">以下为各业务页实际校验的上限；点击「去哪用」跳转对应功能。</p>

        <div v-for="g in groups" :key="g.group" class="group">
          <div class="group-title">{{ g.group }}</div>

          <template v-for="item in g.items" :key="item.code">
            <div v-if="item.kind === 'feature'" class="feat">
              <div class="feat-k">{{ item.label }}</div>
              <div>
                <el-tag :type="item.enabled ? 'success' : 'info'" size="small">
                  {{ item.enabled ? '已开通' : '未开通' }}
                </el-tag>
                <el-button
                  v-if="item.enabled && item.link_path"
                  link
                  type="primary"
                  @click="go(item.link_path)"
                >
                  {{ item.link_label }}
                </el-button>
              </div>
            </div>
            <div v-else class="meter">
              <div class="meter-row">
                <span>{{ item.label }}</span>
                <span :class="{ danger: item.over_limit || item.at_limit }">
                  {{ item.used }} / {{ item.limit_label ?? '—' }}
                </span>
              </div>
              <div class="bar">
                <div
                  class="fill"
                  :style="{
                    width: `${item.percent == null ? 0 : Math.min(100, item.percent)}%`,
                    background: barColor(item),
                  }"
                />
              </div>
              <div class="hint">
                <span v-if="item.hint">{{ item.hint }} · </span>
                <el-button v-if="item.link_path" link type="primary" @click="go(item.link_path)">
                  → {{ item.link_label }}
                </el-button>
              </div>
            </div>
          </template>
        </div>
      </div>

      <div class="actions">
        <el-button type="primary" @click="contactUpgrade">申请升级 / 加购</el-button>
        <el-button @click="contactUpgrade">联系管家</el-button>
      </div>
      <p class="foot">{{ data.upgrade_hint }}</p>
    </template>
  </div>
</template>

<style scoped>
.page-card {
  background: #fff;
  padding: 16px 20px;
  border-radius: 8px;
}
.hd {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.crumb {
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 2px;
}
.crumb b {
  color: #1677ff;
}
.hd h3 {
  margin: 0;
  font-size: 16px;
}
.cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 14px;
}
@media (max-width: 900px) {
  .cards {
    grid-template-columns: 1fr;
  }
}
.card {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 12px;
  background: #fff;
  font-size: 12px;
}
.card.warn {
  border-color: #ffd591;
  background: #fffbe6;
}
.card .k {
  color: #666;
  margin-bottom: 4px;
}
.card .v {
  font-size: 16px;
  font-weight: 700;
}
.card .v.danger {
  color: #d46b08;
  font-size: 14px;
}
.card .unit {
  font-size: 12px;
  font-weight: 400;
  color: #666;
}
.card .s {
  color: #666;
  margin-top: 4px;
}
.panel {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 14px;
  margin-bottom: 12px;
  background: #fff;
}
.panel-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 10px;
}
.sub {
  font-size: 12px;
  color: #666;
  margin: 0 0 12px;
}
.group-title {
  font-size: 12px;
  font-weight: 600;
  color: #666;
  margin: 16px 0 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid #f0f0f0;
}
.group:first-of-type .group-title {
  margin-top: 0;
}
.meter {
  margin-bottom: 12px;
}
.meter-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  margin-bottom: 4px;
}
.meter-row .danger {
  color: #cf1322;
  font-weight: 600;
}
.bar {
  height: 6px;
  background: #f0f0f0;
  border-radius: 3px;
  overflow: hidden;
}
.fill {
  height: 100%;
}
.hint {
  font-size: 11px;
  color: #666;
  margin-top: 4px;
}
.feat {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 8px;
  font-size: 12px;
  background: #fafafa;
}
.feat-k {
  color: #666;
}
.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 8px;
}
.foot {
  margin-top: 10px;
  font-size: 12px;
  color: #64748b;
}
</style>
