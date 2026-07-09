<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../../stores/auth'
import {
  canEditSavedView,
  deleteSavedView,
  groupSavedViews,
  navigateToView,
  setDefaultSavedView,
  togglePinSavedView,
} from '../../composables/useCrmSavedViews'

const props = defineProps({
  modelValue: { type: String, default: '' },
  views: { type: Array, default: () => [] },
  allLabel: { type: String, required: true },
  listPath: { type: String, required: true },
  canSave: { type: Boolean, default: false },
  hasDraftFilters: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'change', 'save', 'refresh'])

const router = useRouter()
const auth = useAuthStore()
const open = ref(false)

const activeView = computed(
  () => props.views.find((v) => String(v.id) === String(props.modelValue)) || null,
)
const currentLabel = computed(() => activeView.value?.name || props.allLabel)
const canEditActive = computed(() => canEditSavedView(auth, activeView.value))
const grouped = computed(() => groupSavedViews(props.views, auth.user?.id))
const hasSavedViews = computed(() => grouped.value.mine.length + grouped.value.team.length > 0)

function canEdit(view) {
  return canEditSavedView(auth, view)
}

function selectView(viewId) {
  emit('update:modelValue', viewId ? String(viewId) : '')
  navigateToView(router, props.listPath, viewId)
  open.value = false
  emit('change')
}

async function handleTogglePin(view, event) {
  event?.stopPropagation?.()
  if (!canEdit(view)) return
  try {
    await togglePinSavedView(view)
    emit('refresh')
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  }
}

async function handleSetDefault(view) {
  if (!canEdit(view)) return
  try {
    await setDefaultSavedView(view)
    emit('refresh')
  } catch (e) {
    ElMessage.error(e.message || '设置失败')
  }
}

async function handleDelete(view) {
  if (!canEdit(view)) return
  try {
    await deleteSavedView(view)
    if (String(props.modelValue) === String(view.id)) {
      selectView('')
    }
    emit('refresh')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

function onMoreCommand(command) {
  const view = activeView.value
  if (!view) return
  if (command === 'default') handleSetDefault(view)
  if (command === 'delete') handleDelete(view)
}

function openSave() {
  open.value = false
  emit('save')
}
</script>

<template>
  <div class="crm-view-switcher" :class="{ 'has-active-view': !!activeView }">
    <div class="crm-view-switcher__segment">
      <el-dropdown
        v-model:visible="open"
        trigger="click"
        :hide-on-click="false"
        popper-class="crm-view-switcher__popper"
      >
        <button type="button" class="crm-view-switcher__trigger">
          <el-icon class="crm-view-switcher__trigger-icon"><Menu /></el-icon>
          <span class="crm-view-switcher__trigger-label">{{ currentLabel }}</span>
          <el-icon class="crm-view-switcher__trigger-caret"><ArrowDown /></el-icon>
        </button>
        <template #dropdown>
          <div class="crm-view-switcher__panel">
            <div class="crm-view-switcher__panel-head">切换视图</div>

            <div
              class="crm-view-switcher__row crm-view-switcher__row--selectable"
              :class="{ 'is-active': !modelValue }"
              @click="selectView('')"
            >
              <span class="crm-view-switcher__name">{{ allLabel }}</span>
              <el-icon v-if="!modelValue" class="crm-view-switcher__check"><Check /></el-icon>
            </div>

            <template v-if="grouped.mine.length">
              <div class="crm-view-switcher__group">我的视图</div>
              <div
                v-for="view in grouped.mine"
                :key="view.id"
                class="crm-view-switcher__row"
                :class="{ 'is-active': String(modelValue) === String(view.id) }"
              >
                <span class="crm-view-switcher__name" @click="selectView(view.id)">{{ view.name }}</span>
                <span class="crm-view-switcher__meta">
                  <el-tag v-if="view.is_default" size="small" type="info" effect="plain">默认</el-tag>
                  <el-tooltip :content="view.is_pinned ? '取消钉选' : '钉选到侧栏'" placement="top">
                    <button
                      type="button"
                      class="crm-view-switcher__pin"
                      :class="{ 'is-pinned': view.is_pinned }"
                      @click="handleTogglePin(view, $event)"
                    >
                      <el-icon><StarFilled v-if="view.is_pinned" /><Star v-else /></el-icon>
                    </button>
                  </el-tooltip>
                  <el-dropdown v-if="canEdit(view)" trigger="click" @click.stop>
                    <button type="button" class="crm-view-switcher__more" @click.stop>
                      <el-icon><MoreFilled /></el-icon>
                    </button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item @click="handleSetDefault(view)">设为默认</el-dropdown-item>
                        <el-dropdown-item divided @click="handleDelete(view)">
                          <span class="crm-view-switcher__danger">删除</span>
                        </el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                  <el-icon v-if="String(modelValue) === String(view.id)" class="crm-view-switcher__check">
                    <Check />
                  </el-icon>
                </span>
              </div>
            </template>

            <template v-if="grouped.team.length">
              <div class="crm-view-switcher__group">团队视图</div>
              <div
                v-for="view in grouped.team"
                :key="view.id"
                class="crm-view-switcher__row"
                :class="{ 'is-active': String(modelValue) === String(view.id) }"
              >
                <span class="crm-view-switcher__name" @click="selectView(view.id)">{{ view.name }}</span>
                <span class="crm-view-switcher__meta">
                  <el-tag v-if="view.is_pinned" size="small" effect="plain">已钉选</el-tag>
                  <el-dropdown v-if="canEdit(view)" trigger="click" @click.stop>
                    <button type="button" class="crm-view-switcher__more" @click.stop>
                      <el-icon><MoreFilled /></el-icon>
                    </button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item @click="handleTogglePin(view)">
                          {{ view.is_pinned ? '取消钉选' : '钉选到侧栏' }}
                        </el-dropdown-item>
                        <el-dropdown-item divided @click="handleDelete(view)">
                          <span class="crm-view-switcher__danger">删除</span>
                        </el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                  <el-icon v-if="String(modelValue) === String(view.id)" class="crm-view-switcher__check">
                    <Check />
                  </el-icon>
                </span>
              </div>
            </template>

            <div v-if="!hasSavedViews" class="crm-view-switcher__empty">暂无保存的视图</div>

            <div v-if="canSave && hasDraftFilters" class="crm-view-switcher__footer">
              <el-button link type="primary" @click="openSave">
                <el-icon><Plus /></el-icon>
                保存当前筛选为视图
              </el-button>
            </div>
          </div>
        </template>
      </el-dropdown>

      <template v-if="activeView && canEditActive">
        <el-tooltip :content="activeView.is_pinned ? '取消钉选' : '钉选到侧栏'" placement="top">
          <button
            type="button"
            class="crm-view-switcher__seg-btn"
            :class="{ 'is-pinned': activeView.is_pinned }"
            @click="handleTogglePin(activeView)"
          >
            <el-icon><StarFilled v-if="activeView.is_pinned" /><Star v-else /></el-icon>
          </button>
        </el-tooltip>
        <el-dropdown trigger="click" @command="onMoreCommand">
          <button type="button" class="crm-view-switcher__seg-btn">
            <el-icon><MoreFilled /></el-icon>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="default">设为默认视图</el-dropdown-item>
              <el-dropdown-item command="delete" divided>
                <span class="crm-view-switcher__danger">删除视图</span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
    </div>
  </div>
</template>

<style scoped>
.crm-view-switcher__segment {
  display: inline-flex;
  align-items: stretch;
  background: #fff;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.crm-view-switcher.has-active-view .crm-view-switcher__segment {
  border-color: rgba(64, 150, 255, 0.45);
  box-shadow: 0 0 0 1px rgba(64, 150, 255, 0.08);
}

.crm-view-switcher__trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 12px;
  border: none;
  background: transparent;
  color: var(--el-text-color-primary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  max-width: 220px;
}

.crm-view-switcher__trigger:hover {
  background: var(--el-fill-color-light);
}

.crm-view-switcher__trigger-icon {
  color: var(--el-color-primary);
  font-size: 15px;
  flex-shrink: 0;
}

.crm-view-switcher__trigger-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.crm-view-switcher__trigger-caret {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}

.crm-view-switcher__seg-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: none;
  border-left: 1px solid var(--el-border-color-lighter);
  background: transparent;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.crm-view-switcher__seg-btn:hover {
  background: var(--el-fill-color-light);
  color: var(--el-text-color-primary);
}

.crm-view-switcher__seg-btn.is-pinned {
  color: #e6a23c;
  background: rgba(230, 162, 60, 0.08);
}

.crm-view-switcher__panel {
  width: 320px;
  padding: 6px 0 8px;
}

.crm-view-switcher__panel-head {
  padding: 4px 14px 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
  letter-spacing: 0.02em;
}

.crm-view-switcher__group {
  padding: 8px 14px 4px;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.crm-view-switcher__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 14px;
  min-height: 38px;
}

.crm-view-switcher__row--selectable,
.crm-view-switcher__row .crm-view-switcher__name {
  cursor: pointer;
}

.crm-view-switcher__row:hover {
  background: var(--el-fill-color-light);
}

.crm-view-switcher__row.is-active {
  background: rgba(64, 150, 255, 0.08);
}

.crm-view-switcher__row.is-active .crm-view-switcher__name {
  color: var(--el-color-primary);
  font-weight: 500;
}

.crm-view-switcher__name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.crm-view-switcher__meta {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.crm-view-switcher__check {
  color: var(--el-color-primary);
  font-size: 14px;
}

.crm-view-switcher__pin,
.crm-view-switcher__more {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s, background 0.15s, color 0.15s;
}

.crm-view-switcher__row:hover .crm-view-switcher__pin,
.crm-view-switcher__row:hover .crm-view-switcher__more,
.crm-view-switcher__pin.is-pinned {
  opacity: 1;
}

.crm-view-switcher__pin:hover,
.crm-view-switcher__more:hover {
  background: var(--el-fill-color);
  color: var(--el-text-color-primary);
}

.crm-view-switcher__pin.is-pinned {
  color: #e6a23c;
}

.crm-view-switcher__empty {
  padding: 16px 14px;
  text-align: center;
  color: var(--el-text-color-placeholder);
  font-size: 13px;
}

.crm-view-switcher__footer {
  margin-top: 4px;
  padding: 8px 14px 2px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.crm-view-switcher__danger {
  color: var(--el-color-danger);
}
</style>

<style>
.crm-view-switcher__popper.el-popper {
  padding: 0;
  border-radius: 10px;
  overflow: hidden;
}
</style>
