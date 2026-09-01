<template>
  <div class="ai-assistant">
    <!-- 悬浮按钮 -->
    <div class="fab" @click="toggle" :title="open ? '收起 AI 助手' : '打开 AI 助手'">
      <el-icon :size="22"><ChatDotRound v-if="!open" /><Close v-else /></el-icon>
      <span v-if="!open" class="fab-tip">AI</span>
    </div>

    <!-- 聊天面板 -->
    <transition name="slide">
      <div v-if="open" class="panel" :class="{ wide: wide }">
        <div class="panel-header">
          <div class="ph-left">
            <span class="ph-title">🤖 AI 助手</span>
            <el-tag size="small" :type="aiOk ? 'success' : 'info'" effect="dark">
              {{ aiOk ? '已连接 · 可查可改' : '未连接' }}
            </el-tag>
          </div>
          <div class="ph-right">
            <el-tooltip content="清空对话" placement="bottom">
              <el-icon class="ph-icon" @click="clearAll"><Delete /></el-icon>
            </el-tooltip>
            <el-tooltip :content="wide ? '恢复宽度' : '加宽'" placement="bottom">
              <el-icon class="ph-icon" @click="wide = !wide"><FullScreen /></el-icon>
            </el-tooltip>
            <el-icon class="ph-icon" @click="open = false"><Close /></el-icon>
          </div>
        </div>

        <div class="panel-body" ref="bodyRef">
          <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
            <!-- 附件（图片直接预览） -->
            <div v-if="m.files && m.files.length" class="msg-files" :class="{ right: m.role === 'user' }">
              <div v-for="(f, fi) in m.files" :key="fi" class="file-chip">
                <img v-if="f.preview" :src="f.preview" class="thumb" alt="" />
                <el-icon v-else><Document /></el-icon>
                <span class="fname">{{ f.name }}</span>
              </div>
            </div>

            <div class="bubble">
              <!-- 思考中 -->
              <span v-if="m.pending" class="typing">
                <i></i><i></i><i></i> 正在思考{{ m.elapsed ? `（${m.elapsed}s）` : '' }}
              </span>
              <div v-else-if="m.role === 'user'" class="plain">{{ m.content }}</div>
              <div v-else class="md" v-html="renderMd(m.content)"></div>
            </div>

            <!-- 查询结果表 -->
            <div v-if="m.rows && m.rows.length" class="result-box">
              <div class="result-head">
                <span>📊 查询结果（{{ m.total || m.rows.length }} 行）</span>
                <el-button link size="small" type="primary" @click="copyTable(m)">复制</el-button>
              </div>
              <el-table :data="m.rows" size="small" border stripe max-height="240" class="result-table">
                <el-table-column v-for="c in m.columns" :key="c" :prop="c" :label="c" min-width="110" show-overflow-tooltip>
                  <template #default="{ row }">
                    <span>{{ fmtCell(row[c]) }}</span>
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <!-- 写操作确认卡片 -->
            <div v-if="m.plan" class="action-card">
              <div class="ac-title">
                <el-icon><EditPen /></el-icon>
                需要你确认后才会执行
              </div>
              <div class="ac-desc">{{ m.plan.explain }}</div>
              <div class="ac-kv">
                <div><span>操作</span><b>{{ actionLabel(m.plan.action) }} · {{ entityLabel(m.plan.entity) }}</b></div>
                <div v-if="m.plan.match && Object.keys(m.plan.match).length">
                  <span>定位</span><b>{{ kvText(m.plan.match) }}</b>
                </div>
                <div v-if="m.plan.data && Object.keys(m.plan.data).length">
                  <span>内容</span><b>{{ kvText(m.plan.data) }}</b>
                </div>
              </div>
              <div class="ac-btns" v-if="!m.planDone">
                <el-button size="small" type="primary" :loading="m.executing" @click="execPlan(m)">确认执行</el-button>
                <el-button size="small" @click="cancelPlan(m)">取消</el-button>
              </div>
              <div class="ac-done" v-else>{{ m.planResult }}</div>
            </div>
          </div>
        </div>

        <!-- 快捷问题 -->
        <div v-if="messages.length <= 1" class="chips">
          <el-tag v-for="q in quickQuestions" :key="q" class="chip" @click="useQuick(q)">{{ q }}</el-tag>
        </div>

        <div class="panel-footer">
          <el-tooltip content="上传图片 / PDF / Word / Excel 让我一起看" placement="top">
            <el-icon class="attach-btn" @click="pickFile"><Paperclip /></el-icon>
          </el-tooltip>
          <input ref="fileRef" type="file" multiple hidden
                 accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv"
                 @change="onPickFile" />
          <el-input
            v-model="input"
            type="textarea"
            :rows="2"
            :autosize="{ minRows: 1, maxRows: 4 }"
            resize="none"
            placeholder="问我任何问题，也可以上传图片/文件…（Enter 发送，Shift+Enter 换行）"
            @keydown.enter.exact.prevent="send"
          />
          <el-button type="primary" :loading="loading" :disabled="!canSend" @click="send">
            <el-icon><Promotion /></el-icon>
          </el-button>
        </div>

        <div v-if="pendingFiles.length" class="pending-files">
          <div v-for="(f, i) in pendingFiles" :key="i" class="pf">
            <img v-if="f.preview" :src="f.preview" class="thumb sm" alt="" />
            <el-icon v-else><Document /></el-icon>
            <span>{{ f.raw.name }}</span>
            <el-icon class="pf-del" @click="removePending(i)"><Close /></el-icon>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { aiApi } from '../api'

const open = ref(false)
const wide = ref(false)
const input = ref('')
const messages = ref([])
const loading = ref(false)
const aiOk = ref(false)
const bodyRef = ref()
const fileRef = ref()
const pendingFiles = ref([])

const quickQuestions = [
  '张三一共拿了多少补贴',
  '2025年每个BU发放了多少',
  '哪些政策还在发',
  '博士学历有多少人',
  '补贴批注里提到哪些特殊情况',
]

const welcome = `你好，我是这个系统的 AI 助手，权限已全开：

• **查数据**——"某人拿了多少补贴""今年每个 BU 发了多少"
• **改数据**——说"把 XX 的备注改成…"，我会先给你确认再执行
• **看文件**——直接上传截图 / PDF / Word / Excel，我一起看
• **问政策**——补贴条款、申报条件、系统怎么用

用大白话问就行，我会用人话回答。`

const canSend = computed(() => (input.value.trim() || pendingFiles.value.length) && !loading.value)

let timer = null

function toggle() {
  open.value = !open.value
  if (open.value && messages.value.length === 0) {
    messages.value.push({ role: 'assistant', content: welcome })
  }
  scrollBottom()
}

function clearAll() {
  messages.value = [{ role: 'assistant', content: welcome }]
}

function scrollBottom() {
  nextTick(() => {
    if (bodyRef.value) bodyRef.value.scrollTop = bodyRef.value.scrollHeight
  })
}

function useQuick(q) {
  input.value = q
  send()
}

// ===== 文件 =====
function pickFile() { fileRef.value?.click() }

function onPickFile(e) {
  const files = Array.from(e.target.files || [])
  for (const f of files) {
    const isImg = /^image\//.test(f.type)
    pendingFiles.value.push({ raw: f, preview: isImg ? URL.createObjectURL(f) : '' })
  }
  e.target.value = ''
}

function removePending(i) {
  const f = pendingFiles.value[i]
  if (f?.preview) URL.revokeObjectURL(f.preview)
  pendingFiles.value.splice(i, 1)
}

// ===== 发送 =====
async function send() {
  const q = input.value.trim()
  if (!canSend.value) return
  const files = pendingFiles.value.slice()

  messages.value.push({
    role: 'user',
    content: q || (files.length ? `（上传了 ${files.length} 个文件）${q}` : ''),
    files: files.map(f => ({ name: f.raw.name, preview: f.preview })),
  })

  input.value = ''
  pendingFiles.value = []
  loading.value = true

  const pending = { role: 'assistant', pending: true, content: '', elapsed: 0 }
  messages.value.push(pending)
  scrollBottom()

  const startAt = Date.now()
  timer = setInterval(() => {
    pending.elapsed = Math.round((Date.now() - startAt) / 1000)
  }, 1000)

  try {
    const history = messages.value
      .filter(m => !m.pending && !m.plan && m.role !== 'system')
      .slice(-9)
      .map(m => ({ role: m.role, content: typeof m.content === 'string' ? m.content : '' }))

    let res
    if (files.length) {
      const fd = new FormData()
      fd.append('question', q)
      fd.append('history', JSON.stringify(history))
      files.forEach(f => fd.append('files', f.raw))
      res = await aiApi.post('/ai/chat', fd)
    } else {
      res = await aiApi.post('/ai/query', { question: q, history })
    }
    applyResult(pending, res)
  } catch (e) {
    pending.pending = false
    pending.content = '⚠️ 这次没答上来。可能是模型忙，换个说法或稍等一下再试。'
  } finally {
    clearInterval(timer)
    loading.value = false
    scrollBottom()
  }
}

function applyResult(pending, res) {
  pending.pending = false
  if (res?.ok === false) {
    pending.content = '⚠️ ' + (res.message || '没能理解这个问题，换个说法试试？')
    return
  }
  pending.content = res?.answer || '（没有拿到回答）'
  if (res?.rows?.length) {
    pending.rows = res.rows
    pending.columns = res.columns
    pending.total = res.total
  }
  if (res?.mode === 'action' && res?.plan) {
    pending.plan = res.plan
    pending.executing = false
    pending.planDone = false
  }
}

// ===== 写操作确认 =====
async function execPlan(m) {
  m.executing = true
  try {
    const res = await aiApi.post('/ai/action', { plan: m.plan })
    m.planDone = true
    m.planResult = res?.ok
      ? `✅ ${res.answer || '已完成'}`
      : `⚠️ ${res?.answer || res?.detail || '执行失败'}`
    if (res?.ok) ElMessage.success('操作已执行')
  } catch (e) {
    m.planDone = true
    m.planResult = '⚠️ 执行失败，请到对应页面手动处理。'
  } finally {
    m.executing = false
    scrollBottom()
  }
}

function cancelPlan(m) {
  m.planDone = true
  m.planResult = '已取消，没有做任何改动。'
}

// ===== 展示辅助 =====
const ENTITY_LABELS = {
  talent_account: '人才账号', employee_title: '职称', subsidy_policy: '补贴政策',
  subsidy_application: '补贴申领', subsidy_payment: '发放明细', payment_comment: '批注',
}
const ACTION_LABELS = { create: '新增', update: '修改', delete: '删除' }
const FIELD_LABELS = {
  name: '姓名', remark: '备注', status: '状态', bu: 'BU', department: '部门',
  education: '学历', title_name: '职称', title_level: '等级', title_date: '认定时间',
  policy_name: '政策名称', policy_id: '政策编号', amount: '金额', actual_date: '实发日期',
  expected_date: '应发日期', payment_index: '期次', content: '批注内容', author: '批注人',
  application_id: '申领编号', payment_id: '发放编号', total_received: '累计到账',
  total_expected: '预计总额', digital_bank: '数币银行', bank_name: '开户行',
  major_field: '专业', discipline: '学科', next_stage_apply: '下一阶段申请',
  has_subsidy: '是否拿过补贴', title_series: '序列', award_level: '获评等级',
  awarded_date: '获评日期', hire_date: '入职日期', region: '区域', region_level: '级别',
  policy_category: '政策类别', seq_no: '序号', source: '来源',
}

const entityLabel = e => ENTITY_LABELS[e] || e
const actionLabel = a => ACTION_LABELS[a] || a

function kvText(obj) {
  return Object.entries(obj || {})
    .map(([k, v]) => `${FIELD_LABELS[k] || k}：${v === null || v === '' ? '（清空）' : v}`)
    .join('　|　')
}

function fmtCell(v) {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'number') {
    // 金额类：保留两位小数
    return Number.isInteger(v) ? String(v) : v.toFixed(2)
  }
  return String(v)
}

async function copyTable(m) {
  const cols = m.columns || []
  const text = [cols.join('\t')]
    .concat(m.rows.map(r => cols.map(c => r[c] ?? '').join('\t')))
    .join('\n')
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败，可手动选中表格')
  }
}

/** 极简 Markdown 渲染：标题、加粗、行内代码、代码块、列表、分隔线、换行 */
function renderMd(src) {
  if (!src) return ''
  let s = String(src)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

  // 代码块
  s = s.replace(/```[\w]*\n?([\s\S]*?)```/g, (_m, code) => `<pre class="md-code">${code.trim()}</pre>`)

  const lines = s.split('\n')
  const out = []
  let inList = false
  const closeList = () => { if (inList) { out.push('</ul>'); inList = false } }

  for (const raw of lines) {
    const line = raw.trimEnd()
    if (/^\s*(-|\*)\s+/.test(line)) {
      if (!inList) { out.push('<ul>'); inList = true }
      out.push(`<li>${inline(line.replace(/^\s*(-|\*)\s+/, ''))}</li>`)
      continue
    }
    closeList()
    if (/^\s*(\d+)[.)]\s+/.test(line)) {
      out.push(`<div class="md-li">${inline(line)}</div>`)
      continue
    }
    if (/^(#{1,4})\s+/.test(line)) {
      const lv = line.match(/^(#{1,4})/)[1].length
      out.push(`<div class="md-h md-h${lv}">${inline(line.replace(/^#{1,4}\s+/, ''))}</div>`)
      continue
    }
    if (/^(-{3,}|\*{3,})$/.test(line)) { out.push('<hr class="md-hr"/>'); continue }
    if (!line.trim()) { out.push('<div class="md-gap"></div>'); continue }
    out.push(`<div>${inline(line)}</div>`)
  }
  closeList()
  return out.join('')
}

function inline(t) {
  return t
    .replace(/`([^`]+)`/g, '<code class="md-inline">$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
}

onMounted(async () => {
  try {
    const s = await aiApi.get('/ai/status')
    aiOk.value = !!s.enabled
  } catch { aiOk.value = false }
})

onUnmounted(() => {
  clearInterval(timer)
  pendingFiles.value.forEach(f => f.preview && URL.revokeObjectURL(f.preview))
})
</script>

<style scoped>
.ai-assistant { position: fixed; right: 24px; bottom: 24px; z-index: 2000; }

.fab {
  width: 54px; height: 54px; border-radius: 50%;
  background: linear-gradient(135deg, #409eff, #2f7fe0);
  color: #fff; display: flex; align-items: center; justify-content: center;
  cursor: pointer; box-shadow: 0 6px 20px rgba(64, 158, 255, 0.45);
  transition: transform 0.18s;
}
.fab:hover { transform: scale(1.06); }
.fab-tip { display: none; }

.panel {
  position: absolute; right: 0; bottom: 66px;
  width: 440px; height: 620px;
  background: #fff; border-radius: 14px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.28);
  display: flex; flex-direction: column; overflow: hidden;
}
.panel.wide { width: 720px; height: 720px; }

.panel-header {
  padding: 11px 14px; background: linear-gradient(135deg, #409eff, #2f7fe0);
  color: #fff; display: flex; justify-content: space-between; align-items: center;
}
.ph-left { display: flex; align-items: center; gap: 8px; }
.ph-title { font-weight: 600; font-size: 15px; }
.ph-right { display: flex; align-items: center; gap: 10px; }
.ph-icon { cursor: pointer; font-size: 17px; opacity: 0.85; }
.ph-icon:hover { opacity: 1; }

.panel-body { flex: 1; padding: 12px; overflow-y: auto; background: #f5f6f8; }

.msg { margin-bottom: 14px; display: flex; flex-direction: column; }
.msg.user { align-items: flex-end; }

.bubble {
  max-width: 92%; padding: 9px 13px; border-radius: 12px;
  font-size: 14px; line-height: 1.65; word-break: break-word;
}
.msg.user .bubble { background: #409eff; color: #fff; }
.msg.assistant .bubble { background: #fff; color: #2c3e50; border: 1px solid #e6e8eb; }
.plain { white-space: pre-wrap; }

/* markdown */
.md :deep(.md-h) { font-weight: 600; margin: 6px 0 2px; }
.md :deep(.md-h1) { font-size: 16px; }
.md :deep(.md-h2) { font-size: 15px; }
.md :deep(.md-h3) { font-size: 14px; }
.md :deep(ul) { margin: 4px 0; padding-left: 20px; }
.md :deep(li) { margin: 2px 0; }
.md :deep(.md-li) { margin: 2px 0; }
.md :deep(.md-gap) { height: 6px; }
.md :deep(.md-hr) { border: none; border-top: 1px solid #e6e8eb; margin: 8px 0; }
.md :deep(.md-code) {
  background: #f4f5f7; border: 1px solid #e6e8eb; border-radius: 6px;
  padding: 8px 10px; font-size: 12px; overflow-x: auto; margin: 6px 0;
  font-family: Consolas, Menlo, monospace;
}
.md :deep(.md-inline) {
  background: #f0f2f5; padding: 1px 5px; border-radius: 4px;
  font-family: Consolas, Menlo, monospace; font-size: 12.5px;
}

.typing { color: #909399; }
.typing i {
  display: inline-block; width: 5px; height: 5px; margin-right: 3px;
  border-radius: 50%; background: #c0c4cc; animation: blink 1.2s infinite;
}
.typing i:nth-child(2) { animation-delay: 0.2s; }
.typing i:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0%, 60%, 100% { opacity: 0.25 } 30% { opacity: 1 } }

/* 结果表 */
.result-box {
  max-width: 96%; margin-top: 7px; background: #fff;
  border: 1px solid #e6e8eb; border-radius: 10px; overflow: hidden;
}
.result-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 5px 10px; background: #fafbfc; border-bottom: 1px solid #eee;
  font-size: 12.5px; color: #606266;
}
.result-table { font-size: 12.5px; }

/* 操作确认 */
.action-card {
  max-width: 94%; margin-top: 7px; padding: 10px 12px;
  background: #fff8ec; border: 1px solid #f3d19e; border-radius: 10px;
}
.ac-title { display: flex; align-items: center; gap: 6px; font-weight: 600; font-size: 13px; color: #b88230; }
.ac-desc { margin: 5px 0 8px; font-size: 13.5px; color: #303133; }
.ac-kv { font-size: 12.5px; color: #606266; margin-bottom: 9px; }
.ac-kv div { display: flex; gap: 8px; margin: 3px 0; }
.ac-kv span { flex: 0 0 34px; color: #909399; }
.ac-kv b { font-weight: 600; color: #303133; word-break: break-all; }
.ac-btns { display: flex; gap: 8px; }
.ac-done { font-size: 13px; color: #67c23a; }

/* 附件 */
.msg-files { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 5px; }
.msg-files.right { justify-content: flex-end; }
.file-chip {
  display: flex; align-items: center; gap: 5px; padding: 3px 8px;
  background: #fff; border: 1px solid #e0e3e8; border-radius: 14px; font-size: 12px; color: #606266;
}
.thumb { width: 26px; height: 26px; object-fit: cover; border-radius: 4px; }
.thumb.sm { width: 20px; height: 20px; }
.fname { max-width: 130px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.chips { padding: 6px 12px 0; display: flex; flex-wrap: wrap; gap: 6px; background: #f5f6f8; }
.chip { cursor: pointer; font-size: 12px; }
.chip:hover { border-color: #409eff; color: #409eff; }

.panel-footer {
  padding: 8px; display: flex; gap: 6px; align-items: flex-end;
  border-top: 1px solid #eee; background: #fff;
}
.attach-btn { font-size: 19px; color: #909399; cursor: pointer; margin-bottom: 6px; }
.attach-btn:hover { color: #409eff; }

.pending-files {
  display: flex; flex-wrap: wrap; gap: 6px; padding: 6px 10px;
  background: #fff; border-top: 1px solid #f0f0f0;
}
.pf {
  display: flex; align-items: center; gap: 5px; padding: 2px 8px;
  background: #f4f5f7; border-radius: 12px; font-size: 12px; color: #606266;
}
.pf-del { cursor: pointer; color: #c0c4cc; }
.pf-del:hover { color: #f56c6c; }

.slide-enter-active, .slide-leave-active { transition: all 0.22s ease; }
.slide-enter-from, .slide-leave-to { opacity: 0; transform: translateY(12px) scale(0.98); }
</style>
