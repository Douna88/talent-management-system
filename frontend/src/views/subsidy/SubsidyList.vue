<template>
  <div>
    <el-card shadow="never">
      <!-- 筛选栏 -->
      <div class="toolbar">
        <el-select v-model="policyId" placeholder="选择政策" clearable filterable style="width:260px" @change="load">
          <el-option v-for="p in policies" :key="p.id" :label="p.policy_name" :value="p.id" />
        </el-select>
        <el-select v-model="status" placeholder="状态" clearable style="width:120px" @change="load">
          <el-option label="进行中" value="ongoing" />
          <el-option label="已满期" value="completed" />
          <el-option label="已结束" value="ended" />
          <el-option label="停发" value="stopped" />
          <el-option label="离职" value="resigned" />
        </el-select>
        <el-input v-model="keyword" placeholder="搜索姓名/BU/部门" clearable style="width:200px" @keyup.enter="load" @clear="load">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button @click="exportExcel"><el-icon><Download /></el-icon> 导出</el-button>
      </div>

      <!-- 主表 -->
      <el-table :data="rows" v-loading="loading" border stripe>
        <el-table-column type="index" label="序号" width="60" />
        <el-table-column prop="name" label="姓名" width="90" />
        <el-table-column prop="policy_name" label="政策" min-width="200" show-overflow-tooltip />
        <el-table-column prop="bu" label="BU" width="110" show-overflow-tooltip />
        <el-table-column prop="department" label="部门" width="120" show-overflow-tooltip />
        <el-table-column label="累计到账(万元)" width="130" align="right">
          <template #default="{ row }">
            <b>{{ fmt(row.total_received) }}</b>
          </template>
        </el-table-column>
        <el-table-column label="发放" width="80" align="center">
          <template #default="{ row }">{{ row.payment_count }} 笔</template>
        </el-table-column>
        <el-table-column label="批注" width="70" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.comment_count" type="warning" size="small">💬{{ row.comment_count }}</el-tag>
            <span v-else style="color:#BFBFBF">—</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">明细</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 明细抽屉 -->
    <el-drawer v-model="drawerVisible" :title="drawerTitle" size="720px">
      <div v-if="currentApp" class="detail-wrap">
        <el-descriptions :column="2" border size="small" style="margin-bottom:16px">
          <el-descriptions-item label="姓名">{{ currentApp.name }}</el-descriptions-item>
          <el-descriptions-item label="政策">{{ currentApp.policy_name }}</el-descriptions-item>
          <el-descriptions-item label="BU">{{ currentApp.bu || '—' }}</el-descriptions-item>
          <el-descriptions-item label="部门">{{ currentApp.department || '—' }}</el-descriptions-item>
          <el-descriptions-item label="预计总额(万元)">{{ fmt(currentApp.total_expected) }}</el-descriptions-item>
          <el-descriptions-item label="累计到账(万元)">{{ fmt(currentApp.total_received) }}</el-descriptions-item>
        </el-descriptions>

        <el-table :data="payments" border size="small" v-loading="detailLoading">
          <el-table-column prop="payment_index" label="期次" width="60" />
          <el-table-column prop="expected_date" label="应发日期" width="105" />
          <el-table-column prop="actual_date" label="实发日期" width="105" />
          <el-table-column label="金额(万元)" width="130" align="right">
            <template #default="{ row }">{{ fmt(row.amount) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="remark" label="备注" min-width="140" show-overflow-tooltip />
          <el-table-column label="批注" min-width="200">
            <template #default="{ row }">
              <template v-for="(c, i) in row.comments" :key="i">
                <el-popover trigger="hover" width="320">
                  <template #reference>
                    <el-tag type="warning" size="small" style="margin-right:4px;cursor:pointer">💬 {{ c.author }}</el-tag>
                  </template>
                  <div style="white-space:pre-line">{{ c.content }}</div>
                </el-popover>
              </template>
              <span v-if="!row.comments.length" style="color:#BFBFBF">—</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="70" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-drawer>

    <!-- 编辑发放明细 -->
    <el-dialog v-model="editVisible" :title="`编辑明细 - ${currentApp?.name || ''}`" width="480px">
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="期次">
          <el-input-number v-model="editForm.payment_index" :min="1" :max="99" />
        </el-form-item>
        <el-form-item label="金额(元)">
          <el-input-number v-model="editForm.amount" :min="0" :precision="2" :step="100" style="width:200px" />
          <span class="hint">（当前显示 {{ fmt(editForm.amount) }}）</span>
        </el-form-item>
        <el-form-item label="实发日期">
          <el-date-picker v-model="editForm.actual_date" type="date"
                          :value-format="'YYYY.MM.DD'" placeholder="选择日期" style="width:100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.remark" type="textarea" :rows="3"
                    placeholder="可修改或删除备注（留空 = 清空备注）" />
        </el-form-item>
        <el-form-item label="">
          <el-alert type="info" :closable="false" show-icon
                    title="保存后若该笔为已确认/已发放，系统会自动重算此人的「累计到账」。" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSaving" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const rows = ref([])
const policies = ref([])
const loading = ref(false)
const policyId = ref(null)
const status = ref('')
const keyword = ref('')

const drawerVisible = ref(false)
const drawerTitle = ref('')
const currentApp = ref(null)
const payments = ref([])
const detailLoading = ref(false)

// 编辑明细（金额/备注/实发日期/期次）
const editVisible = ref(false)
const editSaving = ref(false)
const editForm = reactive({ amount: 0, remark: '', actual_date: '', payment_index: 1 })
const editingId = ref(null)

const statusMap = {
  ongoing: '进行中', completed: '已满期', ended: '已结束', stopped: '停发', resigned: '离职',
  pending: '待发', pending_confirm: '待确认', confirmed: '已确认', paid: '已发', unpaid: '未发'
}
function statusLabel(s) { return statusMap[s] || s }
function statusTagType(s) {
  if (['paid', 'confirmed', 'completed'].includes(s)) return 'success'
  if (s === 'pending_confirm') return 'warning'
  if (['stopped', 'resigned'].includes(s)) return 'danger'
  return 'info'
}
function fmt(n) {
  if (n === null || n === undefined) return '—'
  // 后端/DB 存元，展示统一为万元
  return (Number(n) / 10000).toLocaleString('zh-CN', { minimumFractionDigits: 4, maximumFractionDigits: 4 }) + ' 万元'
}

async function load() {
  loading.value = true
  try {
    const params = {}
    if (policyId.value) params.policy_id = policyId.value
    if (status.value) params.status = status.value
    if (keyword.value) params.keyword = keyword.value
    rows.value = await api.get('/subsidy/applications', { params })
  } finally { loading.value = false }
}

async function openDetail(row) {
  currentApp.value = row
  drawerTitle.value = `发放明细 - ${row.name}`
  drawerVisible.value = true
  detailLoading.value = true
  try {
    payments.value = await api.get(`/subsidy/applications/${row.id}/payments`)
  } finally { detailLoading.value = false }
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(editForm, {
    payment_index: row.payment_index,
    amount: row.amount,
    remark: row.remark || '',
    actual_date: row.actual_date || '',
  })
  editVisible.value = true
}

async function submitEdit() {
  if (editForm.amount === null || editForm.amount === undefined || editForm.amount < 0) {
    ElMessage.warning('金额不能为负数'); return
  }
  editSaving.value = true
  try {
    await api.put(`/subsidy/payments/${editingId.value}`, {
      payment_index: editForm.payment_index,
      amount: editForm.amount,
      remark: editForm.remark,
      actual_date: editForm.actual_date || null,
    })
    ElMessage.success('已保存')
    editVisible.value = false
    // 刷新明细 + 主表（累计到账可能变化）
    await Promise.all([
      (async () => { payments.value = await api.get(`/subsidy/applications/${currentApp.value.id}/payments`) })(),
      load(),
    ])
  } catch { /* 拦截器已提示 */ }
  editSaving.value = false
}

async function exportExcel() {
  const res = await api.get('/export/subsidy', { responseType: 'blob' })
  const url = URL.createObjectURL(res)
  const a = document.createElement('a')
  a.href = url
  a.download = '个人补贴总表_导出.xlsx'
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(async () => {
  policies.value = await api.get('/subsidy/policies')
  load()
})
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; }
.detail-wrap { padding: 0 8px; }
.hint { margin-left: 8px; color: #8C8C8C; font-size: 12px; }
</style>
