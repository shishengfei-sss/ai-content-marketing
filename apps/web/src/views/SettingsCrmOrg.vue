<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crmApi } from '../api/client'

const loading = ref(false)
const territories = ref([])
const profiles = ref([])

const territoryDialog = ref(false)
const editingTerritory = ref(null)
const territoryForm = ref({ name: '', code: '', parent_id: null })

const profileDialog = ref(false)
const editingProfile = ref(null)
const profileForm = ref({ primary_territory_id: null, reports_to_membership_id: null })

function territoryName(id) {
  if (!id) return '—'
  return territories.value.find((t) => t.id === id)?.name || id
}

function memberName(membershipId) {
  if (!membershipId) return '—'
  const row = profiles.value.find((p) => p.membership_id === membershipId)
  return row ? row.display_name || row.phone : membershipId
}

async function loadAll() {
  loading.value = true
  try {
    const [{ data: terr }, { data: prof }] = await Promise.all([
      crmApi.listTerritories(),
      crmApi.listSalesProfiles(),
    ])
    territories.value = Array.isArray(terr) ? terr : []
    profiles.value = Array.isArray(prof) ? prof : []
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function openTerritory(row = null) {
  editingTerritory.value = row
  territoryForm.value = row
    ? { name: row.name, code: row.code, parent_id: row.parent_id }
    : { name: '', code: '', parent_id: null }
  territoryDialog.value = true
}

async function saveTerritory() {
  if (!territoryForm.value.name.trim()) {
    ElMessage.warning('请填写地区名称')
    return
  }
  try {
    if (editingTerritory.value) {
      await crmApi.updateTerritory(editingTerritory.value.id, territoryForm.value)
    } else {
      await crmApi.createTerritory(territoryForm.value)
    }
    ElMessage.success('已保存')
    territoryDialog.value = false
    loadAll()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  }
}

async function removeTerritory(row) {
  try {
    await ElMessageBox.confirm(`删除地区「${row.name}」？`, '确认')
    await crmApi.deleteTerritory(row.id)
    ElMessage.success('已删除')
    loadAll()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

function openProfile(row) {
  editingProfile.value = row
  profileForm.value = {
    primary_territory_id: row.primary_territory_id,
    reports_to_membership_id: row.reports_to_membership_id,
  }
  profileDialog.value = true
}

async function saveProfile() {
  try {
    await crmApi.updateSalesProfile(editingProfile.value.membership_id, profileForm.value)
    ElMessage.success('已保存')
    profileDialog.value = false
    loadAll()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  }
}

onMounted(loadAll)
</script>

<template>
  <div v-loading="loading" class="page-card">
    <div class="section">
      <div class="section-head">
        <div class="page-title">销售地区</div>
        <el-button type="primary" @click="openTerritory()">新建地区</el-button>
      </div>
      <el-table :data="territories" stripe>
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column label="上级地区" width="140">
          <template #default="{ row }">{{ territoryName(row.parent_id) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button link type="primary" @click="openTerritory(row)">编辑</el-button>
            <el-button link type="danger" @click="removeTerritory(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="section">
      <div class="section-head">
        <div class="page-title">成员销售档案</div>
      </div>
      <el-table :data="profiles" stripe>
        <el-table-column label="成员" min-width="140">
          <template #default="{ row }">{{ row.display_name || row.phone }}</template>
        </el-table-column>
        <el-table-column prop="role_name" label="角色" width="120" />
        <el-table-column label="主地区" width="140">
          <template #default="{ row }">{{ territoryName(row.primary_territory_id) }}</template>
        </el-table-column>
        <el-table-column label="汇报上级" width="140">
          <template #default="{ row }">{{ memberName(row.reports_to_membership_id) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="primary" @click="openProfile(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="territoryDialog" :title="editingTerritory ? '编辑地区' : '新建地区'" width="480px">
      <el-form label-width="88px">
        <el-form-item label="名称" required>
          <el-input v-model="territoryForm.name" />
        </el-form-item>
        <el-form-item label="编码">
          <el-input v-model="territoryForm.code" />
        </el-form-item>
        <el-form-item label="上级">
          <el-select v-model="territoryForm.parent_id" clearable placeholder="无" style="width: 100%">
            <el-option
              v-for="t in territories.filter((x) => !editingTerritory || x.id !== editingTerritory.id)"
              :key="t.id"
              :label="t.name"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="territoryDialog = false">取消</el-button>
        <el-button type="primary" @click="saveTerritory">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="profileDialog" title="编辑销售档案" width="480px">
      <el-form label-width="88px">
        <el-form-item label="主地区">
          <el-select v-model="profileForm.primary_territory_id" clearable placeholder="无" style="width: 100%">
            <el-option v-for="t in territories" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="汇报上级">
          <el-select
            v-model="profileForm.reports_to_membership_id"
            clearable
            placeholder="无"
            style="width: 100%"
          >
            <el-option
              v-for="p in profiles.filter((x) => x.membership_id !== editingProfile?.membership_id)"
              :key="p.membership_id"
              :label="p.display_name || p.phone"
              :value="p.membership_id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="profileDialog = false">取消</el-button>
        <el-button type="primary" @click="saveProfile">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.section {
  margin-bottom: 28px;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
}
</style>
