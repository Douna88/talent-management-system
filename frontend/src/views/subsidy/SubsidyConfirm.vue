<template>
  <div>
    <!-- 页面用途说明 -->
    <el-alert type="info" :closable="false" class="guide">
      <template #title>发放确认 · 这个页面是做什么的？</template>
      <div class="guide-body">
        本页面是你<b>审核补贴金额对不对</b>的地方，<b>不需要财务批准</b>。工作流很简单：
        <br />① 在「政策管理」上传红头文件 → AI 解析出「分几期 / 共多少钱」规则 → 你确认规则；
        <br />② 点上方「按规则自动计算并导入」，系统按规则为每条申领算出<b>应发计划</b>（第几期、多少钱、哪天发），状态为「待确认」；
        <br />③ 你逐笔（或批量）点「确认」即表示<b>核对无误</b>；如金额与政策不符点「有异议」并写明原因；
        <br />④ 弹窗里会自动展示该政策的 <b>AI 解析规则作为发放依据</b>，方便你核对。确认后若财务已实际打款，可勾选「同时标记为已发放」。
      </div>
    </el-alert>

    <!-- 顶部汇总卡片 -->
    <el-row :gutter="12" class="cards">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card pending">
          <div class="sc-label">待部门员工确认</div>
          <div class="sc-value">{{ summary.pending_count }} <span class="sc-unit">笔</span></div>
          <div class="sc-sub">{{ fmt(summary.pending_amount) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card rejected">
          <div class="sc-label">有异议待处理</div>
          <div class="sc-value">{{ summary.rejected_count }} <span class="sc-unit">笔</span></div>
          <div class="sc-sub">{{ fmt(summary.rejected_amount) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card done">
          <div class="sc-label">{{ thisYear }} 年已确认</div>
          <div class="sc-value">{{ summary.confirmed_year_count }} <span class="sc-unit">笔</span></div>
          <div class="sc-sub">{{ fmt(summary.confirmed_year_amount) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card total">
          <div class="sc-label">历史已发放</div>
          <div class="sc-value">{{ summary.by_status?.paid || 0 }} <span class="sc-unit">笔</span></div>
          <div class="sc-sub">迁移自历史台账</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <!-- 筛选栏 -->
      <div class="toolbar">
        <el-select v-model="status" placeholder="状态" style="width:150px" @change="load">
          <el-option label="待确认" value="pending_confirm" />
          <el-option label="已确认" value="confirmed" />
          <el-option label="有异议" value="rejected" />
          <el-option label="已发放" value="paid" />
          <el-option label="全部" value="pending_confirm,confirmed,rejected,paid,pending,completed" />
        </el-select>
        <el-select v-model="policyId" placeholder="选择政策" clearable filterable style="width:250px" @change="load">
          <el-option v-for="p in policies" :key="p.id" :label="p.policy_name" :value="p.id" />
        </el-select>
        <el-input v-model="keyword" placeholder="搜索姓名" clearable style="width:180px"
                  @keyup.enter="load" @clear="load">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button @click="load"><el-icon><Refresh /></el-icon> 刷新</el-button>
        <div class="spacer" />
        <el-button type="warning" @click="autoCalcAll" :loading="autoCalculating">
          <el-icon><Cpu /></el-icon> 按规则自动计算并导入
        </el-button>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon> 登记一笔发放
        </el-button>
        <el-button type="success" :disabled="!selection.length" @click="batchConfirm">
          批量确认（{{ selection.length }}）
        </el-button>
      </div>

      <!-- 主表 -->
      <el-table :data="rows" v-loading="loading" border stripe
                @selection-change="sel => selection = sel" ref="tableRef">
        <el-table-column type="selection" width="46" :selectable="r => r.status === 'pending_confirm' || r.status === 'rejected'" />
        <el-table-column type="index" label="序号" width="60" />
        <el-table-column prop="name" label="姓名" width="90" />
        <el-table-column prop="policy_name" label="政策" min-width="200" show-overflow-tooltip />
        <el-table-column prop="bu" label="BU" width="110" show-overflow-tooltip>
          <template #default="{ row }">{{ row.bu || '—' }}</template>
        </el-table-column>
        <el-table-column prop="department" label="部门" width="110" show-overflow-tooltip>
          <template #default="{ row }">{{ row.department || '—' }}</template>
        </el-table-column>
        <el-table-column label="期次" width="70" align="center">
          <template #default="{ row }">第 {{ row.payment_index }} 期</template>
        </el-table-column>
        <el-table-column prop="expected_date" label="应发日期" width="105" />
        <el-table-column prop="actual_date" label="实发日期" width="105">
          <template #default="{ row }">{{ row.actual_date || '—' }}</template>
        </el-table-column>
        <el-table-column label="金额(万元)" width="130" align="right">
          <template #default="{ row }"><b>{{ fmt(row.amount) }}</b></template>
        </el-table-column>
        <el-table-column label="批注" width="70" align="center">
          <template #default="{ row }">
            <el-tooltip v-if="row.comments?.length" placement="top">
              <template #content>
                <div v-for="(c, i) in row.comments" :key="i" style="max-width:320px">
                  {{ c.author }}：{{ c.content }}
                </div>
              </template>
              <el-tag type="warning" size="small">💬{{ row.comments.length }}</el-tag>
            </el-tooltip>
            <span v-else style="color:#ccc">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.remark || '—' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ row.status_label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="success" :disabled="row.status === 'paid'"
                       @click="openConfirm(row)">确认</el-button>
            <el-button link type="danger" :disabled="row.status === 'paid'"
                       @click="openReject(row)">有异议</el-button>
            <el-button link type="primary" @click="openComment(row)">批注</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="没有待确认的发放记录。点右上角「登记一笔发放」录入新发放。" />
        </template>
      </el-table>
    </el-card>

    <!-- 确认 / 有异议 对话框 -->
    <el-dialog v-model="dlgVisible" :title="dlgTitle" width="480px">
      <el-descriptions :column="2" border size="small" v-if="current">
        <el-descriptions-item label="姓名">{{ current.name }}</el-descriptions-item>
        <el-descriptions-item label="期次">第 {{ current.payment_index }} 期</el-descriptions-item>
        <el-descriptions-item label="政策" :span="2">{{ current.policy_name }}</el-descriptions-item>
        <el-descriptions-item label="金额(万元)">{{ fmt(current.amount) }}</el-descriptions-item>
        <el-descriptions-item label="应发日期">{{ current.expected_date || '—' }}</el-descriptions-item>
      </el-descriptions>

      <el-divider content-position="left" v-if="policyRules.length">
        <span class="rule-title">该政策 AI 解析规则（发放依据）</span>
      </el-divider>
      <el-alert v-else-if="current" type="info" :closable="false" class="rule-empty">
        该政策尚未完成 AI 规则解析（可在「政策管理」中上传文档并解析），本次确认无系统规则依据。
      </el-alert>
      <div v-if="policyRules.length" class="rule-list">
        <div v-for="(r, i) in policyRules" :key="i" class="rule-item">
          <el-tag size="small" :type="ruleTagType(r.rule_type)">{{ ruleLabel(r.rule_type) }}</el-tag>
          <span class="rule-text">{{ r.rule_desc || r.rule_value }}</span>
        </div>
      </div>

      <el-form :model="form" label-width="90px" style="margin-top:14px">
        <el-form-item v-if="mode === 'confirm'" label="实发日期">
          <el-date-picker v-model="form.actual_date" type="date" value-format="YYYY-MM-DD"
                          placeholder="选择日期" style="width:100%" />
        </el-form-item>
        <el-form-item :label="mode === 'confirm' ? '确认备注' : '异议原因'" required>
          <el-input v-model="form.remark" type="textarea" :rows="3"
                    :placeholder="mode === 'confirm' ? '例如：已与本人核对，金额无误（可留空）' : '请写明异议原因，例如：金额与政策不符，需复核'" />
        </el-form-item>
        <el-form-item v-if="mode === 'confirm'" label="">
          <el-checkbox v-model="form.set_paid">同时标记为「已发放」（财务实际打款后再勾）</el-checkbox>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dlgVisible = false">取消</el-button>
        <el-button :type="mode === 'confirm' ? 'success' : 'danger'"
                   :loading="submitting" @click="submit">
          {{ mode === 'confirm' ? '确认无误' : '提交异议' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 追加批注 -->
    <el-dialog v-model="cmtVisible" title="追加批注" width="440px">
      <el-form label-width="70px">
        <el-form-item label="对象">
          <span v-if="current">{{ current.name }} · {{ current.policy_name }} · 第 {{ current.payment_index }} 期</span>
        </el-form-item>
        <el-form-item label="批注内容" required>
          <el-input v-model="cmtText" type="textarea" :rows="3" placeholder="填写需要留痕说明的内容" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cmtVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitComment">保存</el-button>
      </template>
    </el-dialog>

    <!-- 登记新发放 -->
    <el-dialog v-model="createVisible" title="登记一笔发放" width="520px">
      <el-form :model="newPay" label-width="100px">
        <el-form-item label="申领记录" required>
          <el-select v-model="newPay.application_id" filterable placeholder="选择姓名 + 政策" style="width:100%">
            <el-option v-for="a in applications" :key="a.id"
                       :label="`${a.name} · ${a.policy_name}`" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="期次" required>
          <el-input-number v-model="newPay.payment_index" :min="1" :max="99" />
        </el-form-item>
        <el-form-item label="金额(元)" required>
          <el-input-number v-model="newPay.amount" :min="0" :precision="2" :step="100" />
        </el-form-item>
        <el-form-item label="应发日期">
          <el-date-picker v-model="newPay.expected_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="newPay.remark" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
        <el-form-item label="">
          <el-alert type="info" :closable="false" show-icon
                    title="保存后状态为「待确认」，需部门员工确认后才会计入累计到账。" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreate">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api, { slowApi } from '../../api'

const thisYear = new Date().getFullYear()

const rows = ref([])
const policies = ref([])
const applications = ref([])
const selection = ref([])
const loading = ref(false)
const submitting = ref(false)
const summary = ref({ pending_count: 0, pending_amount: 0, rejected_count: 0, rejected_amount: 0, confirmed_year_count: 0, confirmed_year_amount: 0, by_status: {} })

const status = ref('pending_confirm')
const policyId = ref(null)
const keyword = ref('')

const dlgVisible = ref(false)
const dlgTitle = ref('')
const mode = ref('confirm')
const current = ref(null)
const policyRules = ref([])
const form = reactive({ remark: '', actual_date: '', set_paid: false })

const cmtVisible = ref(false)
const cmtText = ref('')

const createVisible = ref(false)
const newPay = reactive({ application_id: null, payment_index: 1, amount: 0, expected_date: '', remark: '' })

const fmt = v => (v === null || v === undefined || v === '') ? '0.0000 万元'
  : (Number(v) / 10000).toLocaleString('zh-CN', { minimumFractionDigits: 4, maximumFractionDigits: 4 }) + ' 万元'

function statusTagType(s) {
  return { pending_confirm: 'warning', confirmed: 'success', paid: 'info', rejected: 'danger',
           pending: '', stopped: 'info', unpaid: 'danger', completed: 'success' }[s] || 'info'
}

const RULE_LABELS = { period: '有效期', target: '适用对象', amount: '补贴总额', installment: '发放期次', eligibility: '申领条件', conflict: '互斥/扣减', special: '特殊条款' }
const RULE_TAGS = { period: 'primary', target: 'info', amount: 'success', installment: 'warning', eligibility: 'warning', conflict: 'danger', special: '' }
function ruleLabel(t) { return RULE_LABELS[t] || t }
function ruleTagType(t) { return RULE_TAGS[t] || 'info' }

async function loadSummary() {
  try { summary.value = await api.get('/subsidy/payments/summary') } catch { /* 忽略 */ }
}

const autoCalculating = ref(false)
async function autoCalcAll() {
  try {
    await ElMessageBox.confirm(
      '将扫描所有申领记录，按政策 AI 解析的「分 N 期 / 总额」规则自动生成各期应发计划（每期 = 总额 / N）。已存在发放记录的申领不会重复生成。',
      '按规则自动计算并导入', { type: 'warning' })
  } catch { return }
  autoCalculating.value = true
  try {
    const r = await slowApi.post('/subsidy/settle-all')
    ElMessage.success(`已为 ${r.settled_apps} 条申领自动结算，生成 ${r.generated} 笔应发计划`)
    await Promise.all([load(), loadSummary()])
  } catch (e) {
    ElMessage.error('自动计算失败：' + (e?.response?.data?.detail || '请求失败'))
  } finally { autoCalculating.value = false }
}

async function load() {
  loading.value = true
  try {
    const params = { status: status.value, limit: 500 }
    if (policyId.value) params.policy_id = policyId.value
    if (keyword.value) params.keyword = keyword.value
    rows.value = await api.get('/subsidy/payments', { params })
  } catch { rows.value = [] }
  loading.value = false
}

async function loadPolicyRules(policyId) {
  policyRules.value = []
  if (!policyId) return
  try { policyRules.value = await api.get(`/subsidy/policies/${policyId}/rules`) } catch { policyRules.value = [] }
}

function openConfirm(row) {
  mode.value = 'confirm'
  current.value = row
  dlgTitle.value = `确认发放 — ${row.name}`
  form.remark = ''
  form.actual_date = row.actual_date || new Date().toISOString().slice(0, 10)
  form.set_paid = false
  loadPolicyRules(row.policy_id)
  dlgVisible.value = true
}

function openReject(row) {
  mode.value = 'reject'
  current.value = row
  dlgTitle.value = `标记有异议 — ${row.name}`
  form.remark = ''
  loadPolicyRules(row.policy_id)
  dlgVisible.value = true
}

async function submit() {
  if (mode.value === 'reject' && !form.remark.trim()) {
    ElMessage.warning('请填写异议原因')
    return
  }
  submitting.value = true
  try {
    if (mode.value === 'confirm') {
      await api.post(`/subsidy/payments/${current.value.id}/confirm`, {
        remark: form.remark, actual_date: form.actual_date, set_paid: form.set_paid,
      })
      ElMessage.success('已确认')
    } else {
      await api.post(`/subsidy/payments/${current.value.id}/reject`, { reason: form.remark })
      ElMessage.success('已标记有异议')
    }
    dlgVisible.value = false
    await Promise.all([load(), loadSummary()])
  } catch { /* 拦截器已提示 */ }
  submitting.value = false
}

function openComment(row) {
  current.value = row
  cmtText.value = ''
  cmtVisible.value = true
}

async function submitComment() {
  if (!cmtText.value.trim()) { ElMessage.warning('请填写批注内容'); return }
  submitting.value = true
  try {
    await api.post(`/subsidy/payments/${current.value.id}/comments`, { content: cmtText.value })
    ElMessage.success('批注已保存')
    cmtVisible.value = false
    await load()
  } catch { /* ignored */ }
  submitting.value = false
}

async function batchConfirm() {
  const ids = selection.value.map(r => r.id)
  if (!ids.length) return
  try {
    await ElMessageBox.confirm(
      `将把选中的 ${ids.length} 笔标记为「已确认」，确认后会计入累计到账。`, '批量确认',
      { type: 'warning' })
  } catch { return }
  submitting.value = true
  try {
    const res = await api.post('/subsidy/payments/batch-confirm', { ids, remark: '批量确认' })
    ElMessage.success(res.message || '已确认')
    await Promise.all([load(), loadSummary()])
  } catch { /* ignored */ }
  submitting.value = false
}

async function openCreate() {
  if (!applications.value.length) {
    try { applications.value = await api.get('/subsidy/applications') } catch { applications.value = [] }
  }
  Object.assign(newPay, { application_id: null, payment_index: 1, amount: 0, expected_date: '', remark: '' })
  createVisible.value = true
}

async function submitCreate() {
  if (!newPay.application_id) { ElMessage.warning('请选择申领记录'); return }
  if (!newPay.amount) { ElMessage.warning('请填写金额'); return }
  submitting.value = true
  try {
    await api.post('/subsidy/payments', newPay)
    ElMessage.success('已登记，状态为「待确认」')
    createVisible.value = false
    status.value = 'pending_confirm'
    await Promise.all([load(), loadSummary()])
  } catch { /* ignored */ }
  submitting.value = false
}

onMounted(async () => {
  try { policies.value = await api.get('/subsidy/policies') } catch { policies.value = [] }
  await Promise.all([load(), loadSummary()])
})
</script>

<style scoped>
.cards { margin-bottom: 12px; }
.stat-card { border-left: 4px solid #dcdfe6; }
.guide { margin-bottom: 14px; }
.guide-body { font-size: 13px; line-height: 1.9; color: #455; }
.stat-card.pending { border-left-color: #e6a23c; }
.stat-card.rejected { border-left-color: #f56c6c; }
.stat-card.done { border-left-color: #67c23a; }
.stat-card.total { border-left-color: #409eff; }
.sc-label { font-size: 13px; color: #909399; }
.sc-value { font-size: 26px; font-weight: 600; color: #303133; margin: 4px 0 2px; }
.sc-unit { font-size: 13px; font-weight: 400; color: #909399; }
.sc-sub { font-size: 12.5px; color: #909399; }

.toolbar { display: flex; gap: 10px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
.spacer { flex: 1; }

.rule-title { font-size: 13px; font-weight: 600; color: #409eff; }
.rule-empty { margin-bottom: 4px; }
.rule-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 6px; }
.rule-item { display: flex; gap: 8px; align-items: flex-start; background: #f7f9fc; border-radius: 8px; padding: 8px 10px; }
.rule-item .rule-text { font-size: 13px; color: #455; line-height: 1.5; }
</style>
