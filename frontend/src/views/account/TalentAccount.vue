<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <el-input v-model="keyword" placeholder="搜索姓名" clearable style="width:240px" @keyup.enter="load" @clear="load">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon> 新增</el-button>
        <el-button @click="exportExcel"><el-icon><Download /></el-icon> 导出</el-button>
        <span class="tip">账号加密存储，列表脱敏；点「编辑」可查看完整账号</span>
      </div>

      <el-table :data="rows" v-loading="loading" border stripe>
        <el-table-column type="index" label="序号" width="60" />
        <el-table-column prop="name" label="姓名" width="110" />
        <el-table-column prop="digital_bank" label="数币银行" width="140" />
        <el-table-column prop="digital_account_mask" label="数币账号(脱敏)" width="180" />
        <el-table-column prop="bank_name" label="普通开户行" min-width="180" show-overflow-tooltip />
        <el-table-column prop="bank_account_mask" label="普通账号(脱敏)" width="180" />
        <el-table-column label="拿过补贴" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.has_subsidy" type="success" size="small">是</el-tag>
            <el-tag v-else type="info" size="small">否</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="120" show-overflow-tooltip />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑账号' : '新增账号'" width="520px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="姓名" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="数币银行"><el-input v-model="form.digital_bank" /></el-form-item>
        <el-form-item label="数币账号">
          <el-input v-model="form.digital_account" placeholder="完整账号（编辑时可见明文）" />
        </el-form-item>
        <el-form-item label="普通开户行"><el-input v-model="form.bank_name" /></el-form-item>
        <el-form-item label="普通账号">
          <el-input v-model="form.bank_account" placeholder="完整账号（编辑时可见明文）" />
        </el-form-item>
        <el-form-item label="拿过补贴">
          <el-switch v-model="form.has_subsidy" />
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api'

const rows = ref([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const keyword = ref('')

const form = reactive({
  name: '', digital_bank: '', digital_account: '', bank_name: '', bank_account: '', has_subsidy: true, remark: ''
})

async function load() {
  loading.value = true
  try {
    const params = keyword.value ? { keyword: keyword.value } : {}
    rows.value = await api.get('/account/list', { params })
  } finally { loading.value = false }
}

function openCreate() {
  isEdit.value = false
  editId.value = null
  Object.assign(form, { name: '', digital_bank: '', digital_account: '', bank_name: '', bank_account: '', has_subsidy: true, remark: '' })
  dialogVisible.value = true
}

async function openEdit(row) {
  isEdit.value = true
  editId.value = row.id
  // 拉取完整账号（解密）填入表单
  const full = await api.get(`/account/${row.id}/full`)
  Object.assign(form, {
    name: full.name,
    digital_bank: full.digital_bank,
    digital_account: full.digital_account,
    bank_name: full.bank_name,
    bank_account: full.bank_account,
    has_subsidy: row.has_subsidy,
    remark: row.remark
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.name) { ElMessage.warning('请填写姓名'); return }
  saving.value = true
  try {
    if (isEdit.value) await api.put(`/account/${editId.value}`, form)
    else await api.post('/account', form)
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } finally { saving.value = false }
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除 ${row.name} 的账号？`, '提示', { type: 'warning' })
  await api.delete(`/account/${row.id}`)
  ElMessage.success('删除成功')
  load()
}

async function exportExcel() {
  const res = await api.get('/export/accounts', { responseType: 'blob' })
  const url = URL.createObjectURL(res)
  const a = document.createElement('a')
  a.href = url
  a.download = '个人数币账号总明细_导出.xlsx'
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(load)
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; }
.tip { color: #999; font-size: 12px; }
</style>
