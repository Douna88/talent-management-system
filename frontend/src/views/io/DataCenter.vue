<template>
  <div class="dc">
    <!-- 大屏头部 -->
    <div class="screen-head">
      <div class="sh-left">
        <span class="sh-title">人才补贴数据大屏</span>
        <span class="sh-sub">数据看板 · 统计对账</span>
      </div>
      <div class="sh-right">
        <span class="yr-label">统计年份</span>
        <el-select v-model="year" @change="loadCharts" style="width:140px" placeholder="全部">
          <el-option label="全部（累计）" value="all" />
          <el-option v-for="y in availableYears" :key="y" :label="`${y} 年`" :value="y" />
        </el-select>
      </div>
    </div>

    <!-- KPI 卡片 -->
    <el-row :gutter="14" class="kpi-row">
      <el-col :span="4" v-for="k in kpis" :key="k.label">
        <div class="kpi" :style="{ '--c': k.color }">
          <div class="kpi-v">{{ k.value }}</div>
          <div class="kpi-l">{{ k.label }}</div>
        </div>
      </el-col>
    </el-row>

    <!-- 图表区 -->
    <el-row :gutter="14" class="chart-row">
      <el-col :span="24">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="ct">年度发放趋势（万元）</span></template>
          <div ref="trendRef" class="chart" style="height:300px"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="14" class="chart-row">
      <el-col :span="8">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="ct">各政策累计到账占比</span></template>
          <div ref="policyRef" class="chart" style="height:340px"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="ct">各 BU 补贴汇总 TOP15</span></template>
          <div ref="buRef" class="chart" style="height:340px"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="ct">个人补贴 TOP20</span></template>
          <div ref="personRef" class="chart" style="height:340px"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="14" class="chart-row">
      <el-col :span="12">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="ct">职称等级分布</span></template>
          <div ref="titleRef" class="chart" style="height:260px"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="ct">学历分布</span></template>
          <div ref="eduRef" class="chart" style="height:260px"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 报表与导出 -->
    <el-card shadow="never" class="export-card">
      <template #header>
        <span class="ct">报表与导出 / 导入</span>
        <span class="hint">基于当前系统数据一键生成汇报材料，或导入同结构 Excel 回写。</span>
      </template>
      <el-tabs v-model="tab">
        <el-tab-pane label="汇报材料" name="report">
          <div class="actions">
            <el-button type="primary" :loading="busy==='ppt'" @click="exportReport('ppt')"><el-icon><Picture /></el-icon> 导出 PPT（公司模板）</el-button>
            <el-button :loading="busy==='pdf'" @click="exportReport('pdf')"><el-icon><Document /></el-icon> 导出 PDF</el-button>
            <el-button :loading="busy==='html'" @click="exportReport('html')"><el-icon><Memo /></el-icon> 导出 HTML</el-button>
          </div>
        </el-tab-pane>
        <el-tab-pane label="Excel 导出" name="export">
          <div class="actions">
            <el-button @click="exportExcel('titles','职称汇总表_导出.xlsx')"><el-icon><Collection /></el-icon> 职称表</el-button>
            <el-button @click="exportExcel('accounts','个人数币账号总明细_导出.xlsx')"><el-icon><CreditCard /></el-icon> 人才账号</el-button>
            <el-button @click="exportExcel('policies','人才补贴政策清单_导出.xlsx')"><el-icon><Files /></el-icon> 政策清单</el-button>
            <el-button @click="exportExcel('subsidy','个人补贴总表_导出.xlsx')"><el-icon><Wallet /></el-icon> 补贴明细</el-button>
          </div>
        </el-tab-pane>
        <el-tab-pane label="Excel 导入" name="import">
          <el-form label-width="110px">
            <el-form-item label="导入类型">
              <el-radio-group v-model="importType">
                <el-radio value="titles">职称表</el-radio>
                <el-radio value="accounts">人才账号</el-radio>
                <el-radio value="subsidy">补贴明细</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="选择文件">
              <el-upload :auto-upload="false" :show-file-list="true" :limit="1" accept=".xlsx,.xls" :on-change="onFileChange" :on-remove="onFileRemove">
                <el-button><el-icon><UploadFilled /></el-icon> 选择 Excel</el-button>
              </el-upload>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :disabled="!importFile" :loading="importing" @click="doImport">开始导入</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import api, { slowApi, downloadBlob } from '../../api'

const router = useRouter()
const tab = ref('report')
const busy = ref('')
const importType = ref('titles')
const importFile = ref(null)
const importing = ref(false)

const year = ref('all')
const availableYears = ref([])

const trendRef = ref(); const policyRef = ref(); const buRef = ref()
const personRef = ref(); const titleRef = ref(); const eduRef = ref()

const kpiData = ref({
  total_paid: 0, year_paid: 0, policy_count: 0, application_count: 0,
  pending_confirm: 0, account_count: 0, title_count: 0,
})
const selectedYearTotal = ref(0)
const kpis = computed(() => {
  const f = v => Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  const cur = year.value === 'all' ? '本年' : `${year.value}年`
  const yv = year.value === 'all' ? kpiData.value.year_paid : selectedYearTotal.value
  return [
    { label: `累计已发(万元)`, value: f(kpiData.value.total_paid), color: '#ff6b6b' },
    { label: `${cur}已发(万元)`, value: f(yv), color: '#ffa940' },
    { label: '补贴政策', value: kpiData.value.policy_count, color: '#36cfc9' },
    { label: '补贴申领', value: kpiData.value.application_count, color: '#4096ff' },
    { label: '待确认发放', value: kpiData.value.pending_confirm, color: '#fadb14' },
    { label: '人才账号', value: kpiData.value.account_count, color: '#9254de' },
  ]
})

function makePie(data) {
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    // 图例放到饼图下方避免与图体重叠；饼体居中并稍微缩小
    legend: { type: 'scroll', orient: 'horizontal', bottom: 4, left: 'center',
      itemWidth: 12, itemHeight: 8, textStyle: { fontSize: 11 } },
    series: [{
      type: 'pie', radius: ['28%', '52%'], center: ['50%', '42%'],
      avoidLabelOverlap: true,
      label: { show: false }, labelLine: { show: false },
      data: data.map(d => ({ name: d.name, value: d.value }))
    }]
  }
}
function makeBarH(data, name = 'name', value = 'value') {
  const names = data.map(d => d[name]); const values = data.map(d => d[value])
  return {
    tooltip: { trigger: 'axis' }, grid: { left: 8, right: 24, bottom: 8, top: 10, containLabel: true },
    xAxis: { type: 'value' }, yAxis: { type: 'category', data: names, inverse: true, axisLabel: { width: 120, overflow: 'truncate', fontSize: 11 } },
    series: [{ type: 'bar', data: values, barMaxWidth: 16, itemStyle: { color: '#4096ff', borderRadius: [0, 4, 4, 0] } }]
  }
}
// 复用图表实例：切换年份时只重设 option，避免重复 init 报错与内存泄漏
const charts = {}
function draw(key, elRef, option) {
  if (!elRef.value) return
  if (!charts[key]) charts[key] = echarts.init(elRef.value)
  charts[key].setOption(option, true) // notMerge：彻底替换旧数据
}

async function loadKpis() {
  try { kpiData.value = await api.get('/stats/dashboard') } catch {}
}
async function loadCharts() {
  const d = await api.get('/stats/charts', { params: { year: year.value } })
  availableYears.value = d.available_years || []
  // 选中年份的发放额（趋势里取），供 KPI 展示
  if (year.value === 'all') {
    selectedYearTotal.value = 0
  } else {
    const idx = (d.trend.years || []).indexOf(year.value)
    selectedYearTotal.value = idx >= 0 ? (d.trend.amounts[idx] || 0) : 0
  }
  draw('trend', trendRef, {
    tooltip: { trigger: 'axis', formatter: p => `${p[0].axisValue} 年<br/>${Number(p[0].value).toFixed(1)} 万元` },
    grid: { left: 60, right: 24, bottom: 28, top: 20 },
    xAxis: { type: 'category', data: d.trend.years },
    yAxis: { type: 'value', name: '万元', axisLabel: { formatter: v => Number(v).toFixed(0) } },
    series: [{ type: 'line', smooth: true, areaStyle: { opacity: 0.18 }, itemStyle: { color: '#36cfc9' },
      data: d.trend.amounts, label: { show: true, formatter: p => Number(p.value).toFixed(1) } }]
  })
  draw('policy', policyRef, makePie(d.policy_pie))
  draw('bu', buRef, makeBarH(d.bu_top))
  draw('person', personRef, makeBarH(d.person_top))
  draw('title', titleRef, makePie(d.title_pie))
  draw('edu', eduRef, makePie(d.edu_pie))
}

function exportReport(fmt) {
  busy.value = fmt
  const y = year.value === 'all' ? '' : year.value
  const yearLabel = y || '累计'
  const name = { ppt: `人才补贴管理汇报_${yearLabel}.pptx`, pdf: `人才补贴管理汇报_${yearLabel}.pdf`, html: `人才补贴管理汇报_${yearLabel}.html` }[fmt]
  const q = y ? `?year=${y}` : ''
  downloadBlob(`/export/report/${fmt}${q}`, name, slowApi).then(() => ElMessage.success(`已导出 ${yearLabel} 报告`)).catch(() => {}).finally(() => busy.value = '')
}
function exportExcel(kind, name) {
  downloadBlob(`/export/${kind}`, name, slowApi).then(() => ElMessage.success('导出成功')).catch(() => {})
}
function onFileChange(file) { importFile.value = file.raw; return false }
function onFileRemove() { importFile.value = null }
async function doImport() {
  if (!importFile.value) return
  importing.value = true
  const form = new FormData(); form.append('file', importFile.value)
  try {
    const res = await slowApi.post(`/import/${importType.value}`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
    ElMessage.success(res.message || '导入完成'); importFile.value = null
  } catch (e) {} finally { importing.value = false }
}

function resizeAll() { Object.values(charts).forEach(c => c.resize()) }
onMounted(async () => { await Promise.all([loadKpis(), loadCharts()]); window.addEventListener('resize', resizeAll) })
onBeforeUnmount(() => { window.removeEventListener('resize', resizeAll); Object.values(charts).forEach(c => c.dispose()) })
</script>

<style scoped>
.dc { padding: 4px; }
.screen-head { display: flex; justify-content: space-between; align-items: center;
  background: linear-gradient(90deg, #0b2545, #13315c); border-radius: 10px; padding: 14px 20px; color: #fff; margin-bottom: 14px; }
.sh-title { font-size: 20px; font-weight: 700; letter-spacing: 1px; }
.sh-sub { margin-left: 12px; font-size: 13px; color: #9ec5ff; }
.sh-right { display: flex; align-items: center; gap: 10px; }
.yr-label { font-size: 13px; color: #cfe3ff; }
.kpi-row { margin-bottom: 4px; }
.kpi { background: #fff; border-radius: 10px; padding: 14px 10px; text-align: center; border-top: 3px solid var(--c); box-shadow: 0 2px 8px rgba(0,0,0,.05); }
.kpi-v { font-size: 22px; font-weight: 700; color: var(--c); }
.kpi-l { font-size: 12px; color: #888; margin-top: 4px; }
.chart-row { margin-top: 14px; }
.chart-card { border-radius: 10px; }
.ct { font-weight: 600; }
.chart-card :deep(.el-card__header) { padding: 10px 16px; background: #fafbfc; }
.export-card { margin-top: 14px; border-radius: 10px; }
.hint { font-size: 12px; color: #999; margin-left: 10px; font-weight: 400; }
.actions { display: flex; flex-wrap: wrap; gap: 12px; }
.actions .el-button { margin: 0; }
</style>
