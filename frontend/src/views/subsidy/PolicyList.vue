<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon> 新增政策</el-button>
        <el-button type="warning" @click="batchConfirmParsed" :loading="confirming" :disabled="parsedCount === 0">
          <el-icon><CircleCheck /></el-icon> 批量确认已解析政策{{ parsedCount ? `(${parsedCount})` : '' }}
        </el-button>
        <el-button @click="exportExcel"><el-icon><Download /></el-icon> 导出</el-button>
        <span class="tip">政策文档可点击「查看/编辑规则」上传，系统抽取原文后 AI 解析并支持人工订正。</span>
      </div>

      <el-table :data="rows" v-loading="loading" border stripe>
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="policy_name" label="政策名称" min-width="280" show-overflow-tooltip />
        <el-table-column prop="policy_category" label="类别" width="110" />
        <el-table-column prop="region" label="区域" width="100" />
        <el-table-column prop="region_level" label="级别" width="80" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'active'" type="success" size="small">在发</el-tag>
            <el-tag v-else type="info" size="small">已结束</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="AI 规则解析" width="170">
          <template #default="{ row }">
            <el-tag v-if="row.ai_status === 'confirmed'" type="success" size="small">已确认</el-tag>
            <el-tag v-else-if="row.ai_status === 'parsed'" type="warning" size="small">待确认({{ row.rule_count || 0 }})</el-tag>
            <el-tag v-else-if="row.ai_status === 'pending'" type="info" size="small">未解析</el-tag>
            <span v-else>{{ row.ai_status }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="360" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openUpload(row)"><el-icon><UploadFilled /></el-icon>上传文档</el-button>
            <el-button link type="warning" size="small" @click="parsePolicy(row)" :loading="row._parsing">AI解析</el-button>
            <el-button link type="success" size="small" @click="viewRules(row)">查看/编辑规则</el-button>
            <el-button v-if="row.ai_status === 'parsed'" link type="primary" size="small" @click="confirmRules(row)">确认规则</el-button>
            <el-button link type="danger" size="small" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增 / 编辑 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑政策' : '新增政策'" width="520px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="政策名称" required><el-input v-model="form.policy_name" /></el-form-item>
        <el-form-item label="类别">
          <el-select v-model="form.policy_category" clearable style="width:100%">
            <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="区域"><el-input v-model="form.region" /></el-form-item>
        <el-form-item label="级别">
          <el-select v-model="form.region_level" clearable style="width:100%">
            <el-option label="市级" value="市级" />
            <el-option label="区级" value="区级" />
            <el-option label="县级" value="县级" />
          </el-select>
        </el-form-item>
        <el-form-item label="有效起止">
          <el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD" style="width:100%" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio value="active">在发</el-radio>
            <el-radio value="ended">已结束</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 上传文档 -->
    <el-dialog v-model="uploadVisible" title="上传政策文档" width="460px">
      <p class="up-tip">仅支持 PDF / Word（.doc/.docx），上传后系统抽取原文供 AI 解析。</p>
      <el-upload
        drag
        :auto-upload="false"
        :limit="1"
        accept=".pdf,.doc,.docx"
        :on-change="onDocChange"
        :on-remove="onDocRemove"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div>将文件拖到此处，或点击选择</div>
      </el-upload>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!docFile" :loading="uploading" @click="submitUpload">上传并抽取</el-button>
      </template>
    </el-dialog>

    <!-- 规则详情 / 编辑 -->
    <el-dialog v-model="rulesVisible" :title="`政策规则（${currentPolicy?.policy_name || ''}）`" width="760px" top="5vh">
      <div class="dlg-toolbar">
        <el-button size="small" @click="openUpload(currentPolicy)"><el-icon><UploadFilled /></el-icon> 上传政策文档</el-button>
        <span class="dtip">上传 PDF / Word 后系统抽取原文，可触发「AI解析」</span>
      </div>
      <el-alert
        v-if="currentPolicy?.ai_status === 'parsed'"
        type="warning" :closable="false" class="mb"
        title="规则已由 AI 解析，请逐项核对。可修改、删除或新增规则订正错误，订正后点「确认生效」。"
      />
      <el-alert
        v-else-if="currentPolicy?.ai_status === 'confirmed'"
        type="success" :closable="false" class="mb"
        title="规则已确认生效。如需修改，可直接编辑，系统会自动退回为待确认状态。"
      />
      <el-alert
        v-else type="info" :closable="false" class="mb"
        title="该政策尚未解析出规则。可先「上传文档 → AI 解析」，或直接手动新增规则。"
      />

      <div class="rule-toolbar">
        <span class="rcount">共 {{ rules.length }} 条规则</span>
        <el-button size="small" type="primary" @click="startAdd"><el-icon><Plus /></el-icon> 新增规则</el-button>
      </div>

      <!-- 新增表单 -->
      <el-card v-if="adding" shadow="never" class="rule-edit mb">
        <div class="re-title">新增规则</div>
        <el-form label-width="80px" :model="editForm">
          <el-form-item label="类型">
            <el-select v-model="editForm.rule_type" style="width:100%">
              <el-option v-for="(lbl,key) in RULE_LABELS" :key="key" :label="lbl" :value="key" />
            </el-select>
          </el-form-item>
          <el-form-item label="内容">
            <el-input v-model="editForm.rule_desc" type="textarea" :rows="2" placeholder="规则描述，例如：社保需连续缴纳满 24 个月" />
          </el-form-item>
          <el-form-item label="取值">
            <el-input v-model="editForm.rule_value" placeholder="可选，结构化取值，如 24 或 是/否" />
          </el-form-item>
          <el-form-item label="原文">
            <el-input v-model="editForm.source_quote" placeholder="可选，政策原文引用" />
          </el-form-item>
          <div class="re-actions">
            <el-button size="small" @click="cancelEdit">取消</el-button>
            <el-button size="small" type="primary" :loading="savingRule" @click="saveAdd">保存新增</el-button>
          </div>
        </el-form>
      </el-card>

      <el-empty v-if="!rules.length && !adding" description="暂无规则，点击右上角「新增规则」" />

      <div v-for="(r, i) in rules" :key="r.id" class="rule-card">
        <template v-if="editingId !== r.id">
          <div class="rule-head">
            <el-tag size="small">{{ ruleLabel(r.rule_type) }}</el-tag>
            <span class="rule-desc">{{ r.rule_desc || r.rule_value }}</span>
            <span class="rule-ops">
              <el-button link type="primary" size="small" @click="startEdit(r)">编辑</el-button>
              <el-button link type="danger" size="small" @click="delRule(r)">删除</el-button>
            </span>
          </div>
          <div v-if="r.source_quote" class="rule-quote">原文：{{ r.source_quote }}</div>
        </template>
        <el-card v-else shadow="never" class="rule-edit">
          <div class="re-title">编辑规则 #{{ r.id }}</div>
          <el-form label-width="80px" :model="editForm">
            <el-form-item label="类型">
              <el-select v-model="editForm.rule_type" style="width:100%">
                <el-option v-for="(lbl,key) in RULE_LABELS" :key="key" :label="lbl" :value="key" />
              </el-select>
            </el-form-item>
            <el-form-item label="内容">
              <el-input v-model="editForm.rule_desc" type="textarea" :rows="2" />
            </el-form-item>
            <el-form-item label="取值">
              <el-input v-model="editForm.rule_value" />
            </el-form-item>
            <el-form-item label="原文">
              <el-input v-model="editForm.source_quote" />
            </el-form-item>
            <div class="re-actions">
              <el-button size="small" @click="cancelEdit">取消</el-button>
              <el-button size="small" type="primary" :loading="savingRule" @click="saveEdit(r)">保存</el-button>
            </div>
          </el-form>
        </el-card>
      </div>

      <template #footer>
        <el-button @click="rulesVisible = false">关闭</el-button>
        <el-button
          v-if="currentPolicy?.ai_status === 'parsed'"
          type="success"
          :loading="confirmingOne"
          @click="confirmRules(currentPolicy)"
        >确认生效</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api, { slowApi } from '../../api'

const rows = ref([])
const loading = ref(false)
const saving = ref(false)
const uploading = ref(false)
const confirming = ref(false)
const confirmingOne = ref(false)
const savingRule = ref(false)

const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const dateRange = ref([])
const categories = ['薪酬补贴', '紧缺人才', '紧缺专技', '租房', '房票', '奖励', '落户', '乐居', '就业创业', '贡献', '专项', '安家', '其他']

const form = reactive({
  policy_name: '', policy_category: '', region: '', region_level: '', status: 'active', remark: ''
})

const uploadVisible = ref(false)
const docFile = ref(null)
const currentPolicy = ref(null)

const rulesVisible = ref(false)
const rules = ref([])
const editingId = ref(null)
const adding = ref(false)
const editForm = reactive({ rule_type: 'special', rule_desc: '', rule_value: '', source_quote: '' })

const parsedCount = computed(() => rows.value.filter(r => r.ai_status === 'parsed').length)

async function load() {
  loading.value = true
  try {
    rows.value = await api.get('/subsidy/policies')
    await Promise.all(rows.value.map(async r => {
      try { r.rule_count = (await api.get(`/subsidy/policies/${r.id}/rules`)).length } catch { r.rule_count = 0 }
    }))
  } finally { loading.value = false }
}

function openCreate() {
  isEdit.value = false; editId.value = null; dateRange.value = []
  Object.assign(form, { policy_name: '', policy_category: '', region: '', region_level: '', status: 'active', remark: '' })
  dialogVisible.value = true
}

function openEdit(row) {
  isEdit.value = true; editId.value = row.id; dateRange.value = row.valid_from ? [row.valid_from, row.valid_until] : []
  Object.assign(form, { policy_name: row.policy_name, policy_category: row.policy_category, region: row.region, region_level: row.region_level, status: row.status, remark: row.remark })
  dialogVisible.value = true
}

async function save() {
  if (!form.policy_name) { ElMessage.warning('请填写政策名称'); return }
  saving.value = true
  const payload = { ...form }
  payload.valid_from = dateRange.value?.[0] || null
  payload.valid_until = dateRange.value?.[1] || null
  try {
    if (isEdit.value) await api.put(`/subsidy/policies/${editId.value}`, payload)
    else await api.post('/subsidy/policies', payload)
    ElMessage.success('保存成功'); dialogVisible.value = false; load()
  } finally { saving.value = false }
}

async function exportExcel() {
  try {
    const resp = await api.get('/export/policies', { responseType: 'blob' })
    const blob = resp instanceof Blob ? resp : resp.data
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = '人才补贴政策清单_导出.xlsx'; a.click()
    URL.revokeObjectURL(url)
  } catch (e) {}
}

function openUpload(row) { currentPolicy.value = row; docFile.value = null; uploadVisible.value = true }
function onDocChange(file) { docFile.value = file.raw; return false }
function onDocRemove() { docFile.value = null }

async function submitUpload() {
  if (!docFile.value || !currentPolicy.value) return
  uploading.value = true
  const fd = new FormData(); fd.append('file', docFile.value)
  try {
    await slowApi.post(`/subsidy/policies/${currentPolicy.value.id}/upload-doc`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    ElMessage.success('文档已上传并抽取原文，可点击「AI解析」')
    uploadVisible.value = false; load()
  } finally { uploading.value = false }
}

async function parsePolicy(row) {
  row._parsing = true
  try {
    const res = await slowApi.post(`/subsidy/policies/${row.id}/parse?force=false`)
    if (res.skipped) ElMessage.info(res.message)
    else ElMessage.success(`已解析出 ${res.rule_count} 条规则，请核对后确认`)
    load()
  } finally { row._parsing = false }
}

async function viewRules(row) {
  currentPolicy.value = row
  try { rules.value = await api.get(`/subsidy/policies/${row.id}/rules`) } catch { rules.value = [] }
  editingId.value = null; adding.value = false
  rulesVisible.value = true
}

async function confirmRules(row) {
  confirmingOne.value = true
  try {
    await api.post(`/subsidy/policies/${row.id}/confirm-rules`)
    ElMessage.success('规则已确认生效')
    rulesVisible.value = false; load()
  } finally { confirmingOne.value = false }
}

async function batchConfirmParsed() {
  try {
    await ElMessageBox.confirm(
      `将把全部 ${parsedCount.value} 个「待确认」政策一键确认生效，并立即按规则为各申领自动结算生成应发计划。\n请确认已在「查看/编辑规则」中核对并订正 AI 解析结果。`,
      '批量确认并自动结算', { type: 'warning' })
  } catch { return }
  confirming.value = true
  try {
    const res = await api.post('/subsidy/policies/batch-confirm-rules')
    ElMessage.success(`已确认 ${res.confirmed} 个政策，自动结算生成 ${res.auto_settled} 笔应发计划`)
    load()
  } catch (e) {
    ElMessage.error('批量确认失败：' + (e?.response?.data?.detail || '请求失败'))
  } finally { confirming.value = false }
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除政策「${row.policy_name}」？`, '提示', { type: 'warning' })
  await api.delete(`/subsidy/policies/${row.id}`)
  ElMessage.success('删除成功'); load()
}

// ---- 规则 增 / 改 / 删 ----
function startAdd() {
  adding.value = true; editingId.value = null
  Object.assign(editForm, { rule_type: 'special', rule_desc: '', rule_value: '', source_quote: '' })
}
function startEdit(r) {
  editingId.value = r.id; adding.value = false
  Object.assign(editForm, { rule_type: r.rule_type, rule_desc: r.rule_desc || '', rule_value: r.rule_value || '', source_quote: r.source_quote || '' })
}
function cancelEdit() { editingId.value = null; adding.value = false }

async function saveAdd() {
  if (!editForm.rule_desc.trim()) { ElMessage.warning('请填写规则内容'); return }
  savingRule.value = true
  try {
    await api.post(`/subsidy/policies/${currentPolicy.value.id}/rules`, { ...editForm })
    ElMessage.success('已新增规则')
    adding.value = false
    rules.value = await api.get(`/subsidy/policies/${currentPolicy.value.id}/rules`)
    await load()
  } finally { savingRule.value = false }
}

async function saveEdit(r) {
  if (!editForm.rule_desc.trim()) { ElMessage.warning('请填写规则内容'); return }
  savingRule.value = true
  try {
    await api.put(`/subsidy/policies/rules/${r.id}`, { ...editForm })
    ElMessage.success('已保存修改')
    editingId.value = null
    rules.value = await api.get(`/subsidy/policies/${currentPolicy.value.id}/rules`)
    await load()
  } finally { savingRule.value = false }
}

async function delRule(r) {
  await ElMessageBox.confirm('确认删除该规则？', '提示', { type: 'warning' })
  await api.delete(`/subsidy/policies/rules/${r.id}`)
  ElMessage.success('已删除')
  rules.value = await api.get(`/subsidy/policies/${currentPolicy.value.id}/rules`)
  await load()
}

const RULE_LABELS = { period: '有效期', target: '适用对象', amount: '补贴总额', installment: '发放期次', eligibility: '申领条件', conflict: '互斥/扣减', special: '特殊条款' }
function ruleLabel(t) { return RULE_LABELS[t] || t }

onMounted(load)
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; flex-wrap: wrap; }
.tip { color: #999; font-size: 12px; }
.up-tip { color: #888; font-size: 13px; margin-bottom: 12px; }
.mb { margin-bottom: 14px; }
.rule-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.rcount { color: #888; font-size: 13px; }
.rule-card { border: 1px solid #ebeef5; border-radius: 8px; padding: 10px 12px; margin-bottom: 10px; background: #fafbfc; }
.rule-head { display: flex; gap: 8px; align-items: flex-start; }
.rule-desc { font-size: 14px; flex: 1; line-height: 1.5; }
.rule-ops { flex-shrink: 0; }
.rule-quote { margin-top: 6px; font-size: 12px; color: #999; padding-left: 4px; border-left: 2px solid #dcdfe6; }
.rule-edit { margin-bottom: 10px; }
.re-title { font-weight: 600; margin-bottom: 10px; color: #303133; }
.re-actions { text-align: right; }
.dlg-toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.dtip { color: #999; font-size: 12px; }
</style>
