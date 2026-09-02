<template>
  <div class="dc">
    <!-- 大屏头部 — 统一为白色卡片风格 -->
    <el-card shadow="never" class="screen-head">
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
    </el-card>

    <!-- KPI 卡片 — 统一风格，无边框色差异 -->
    <el-row :gutter="14" class="kpi-row">
      <el-col :span="4" v-for="k in kpis" :key="k.label">
        <div class="kpi">
          <div class="kpi-v">{{ k.value }}</div>
          <div class="kpi-l">{{ k.label }}</div>
        </div>
      </el-col>
    </el-row>

    <!-- 图表区 -->
    <el-row :gutter="14" class="chart-row">
      <el-col :span="24">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <span class="ct">补贴金额趋势（万元）</span>
            <span class="hint">按实发日期汇总，多年趋势始终全量展示</span>
          </template>
          <v-chart :option="trendOpt" style="height:280px" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="14" class="chart-row">
      <el-col :span="8">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="ct">政策分布</span></template>
          <v-chart :option="policyPie" style="height:280px" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="ct">BU 分布</span></template>
          <v-chart :option="buPie" style="height:280px" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="ct">人员 Top10</span></template>
          <v-chart :option="personBar" style="height:280px" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="14" class="chart-row">
      <el-col :span="12">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <span class="ct">职称等级分布</span>
            <span class="hint">按职称级别聚合</span>
          </template>
          <v-chart :option="titlePie" style="height:280px" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <span class="ct">学历分布</span>
            <span class="hint">按学历聚合</span>
          </template>
          <v-chart :option="seriesPie" style="height:280px" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 汇报导出 -->
    <el-card shadow="never" class="export-card">
      <template #header>
        <span class="ct">汇报材料导出</span>
        <span class="hint">按当前选中年份生成</span>
      </template>
      <div class="actions">
        <el-button type="primary" @click="exportPPT">导出 PPT 汇报</el-button>
        <el-button @click="exportPDF">导出 PDF 简报</el-button>
        <el-button @click="exportHTML">导出 HTML 简报</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import api, { slowApi } from '../../api'
import { downloadBlob } from '../../api'

use([CanvasRenderer, BarChart, PieChart, LineChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent])

const year = ref('all')
const availableYears = ref([])
const chartData = ref({ trend: { years: [], amounts: [] }, policy: [], bu: [], person: [], title_level: [], title_series: [] })
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
    { label: `累计已发(万元)`, value: f(kpiData.value.total_paid) },
    { label: `${cur}已发(万元)`, value: f(yv) },
    { label: '补贴政策', value: kpiData.value.policy_count },
    { label: '补贴申领', value: kpiData.value.application_count },
    { label: '待确认发放', value: kpiData.value.pending_confirm },
    { label: '人才账号', value: kpiData.value.account_count },
  ]
})

function makePie(data) {
  return {
    color: ['#2F6FED', '#52C41A', '#FAAD14', '#FF4D4F', '#36CFC9', '#9254DE', '#FADB14', '#F759AB'],
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { type: 'scroll', orient: 'horizontal', bottom: 4, left: 'center',
      itemWidth: 12, itemHeight: 8, textStyle: { fontSize: 11 } },
    series: [{
      type: 'pie', radius: ['28%', '52%'], center: ['50%', '42%'],
      avoidLabelOverlap: true,
      label: { show: false }, labelLine: { show: false },
      data: data.map(d => ({ name: d.name, value: d.value })),
    }]
  }
}

const policyPie = computed(() => makePie(chartData.value.policy || []))
const buPie = computed(() => makePie(chartData.value.bu || []))
const titlePie = computed(() => makePie(chartData.value.title_level || []))
const seriesPie = computed(() => makePie(chartData.value.title_series || []))

const personBar = computed(() => {
  const data = chartData.value.person || []
  const names = data.map(d => d.name)
  const values = data.map(d => d.value)
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 80, right: 20, top: 20, bottom: 20 },
    xAxis: { type: 'value', axisLabel: { formatter: '{value} 万', fontSize: 11 } },
    yAxis: { type: 'category', data: names, axisLabel: { fontSize: 11 } },
    series: [{ type: 'bar', data: values, barMaxWidth: 16,
      itemStyle: { color: '#2F6FED', borderRadius: [0, 4, 4, 0] } }]
  }
})

const trendOpt = computed(() => {
  const t = chartData.value.trend || { years: [], amounts: [] }
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 30, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: t.years || [],
      axisLabel: { fontSize: 12 } },
    yAxis: { type: 'value', axisLabel: { fontSize: 12 } },
    series: [{ type: 'line', smooth: true, data: t.amounts || [],
      areaStyle: { opacity: 0.12, color: '#2F6FED' },
      itemStyle: { color: '#2F6FED' },
      lineStyle: { width: 2 },
    }]
  }
})

async function loadCharts() {
  const params = year.value === 'all' ? {} : { year: year.value }
  const [chartsRes, dashRes] = await Promise.all([
    api.get('/stats/charts', { params }),
    api.get('/stats/dashboard'),
  ])
  const d = chartsRes || {}
  chartData.value = {
    trend: d.trend || { years: [], amounts: [] },
    policy: d.policy_pie || [],
    bu: d.bu_top || [],
    person: d.person_top || [],
    title_level: d.title_pie || [],
    title_series: d.edu_pie || [],
  }
  availableYears.value = d.available_years || []
  kpiData.value = dashRes || kpiData.value
  const t = chartData.value.trend
  const idx = (t.years || []).indexOf(String(year.value))
  selectedYearTotal.value = idx >= 0 && t.amounts ? (t.amounts[idx] || 0) : 0
}

async function exportPPT() { await downloadBlob(`/export/report/ppt?year=${year.value}`, `人才补贴管理汇报_${year.value}.pptx`) }
async function exportPDF() { await downloadBlob(`/export/report/pdf?year=${year.value}`, `人才补贴管理简报_${year.value}.pdf`) }
async function exportHTML() { await downloadBlob(`/export/report/html?year=${year.value}`, `人才补贴管理简报_${year.value}.html`) }

onMounted(loadCharts)
</script>

<style scoped>
.dc { padding: 0; }

/* 大屏头部 — 白色卡片 */
.screen-head :deep(.el-card__body) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
}
.sh-title { font-size: 18px; font-weight: 700; color: #262626; }
.sh-sub { margin-left: 12px; font-size: 13px; color: #8C8C8C; }
.sh-right { display: flex; align-items: center; gap: 10px; }
.yr-label { font-size: 13px; color: #8C8C8C; }

/* KPI 卡片 — 统一风格 */
.kpi-row { margin-bottom: 4px; }
.kpi {
  background: #fff;
  border-radius: 8px;
  padding: 14px 10px;
  text-align: center;
  border: 1px solid #E8E8E8;
}
.kpi-v { font-size: 20px; font-weight: 700; color: #262626; }
.kpi-l { font-size: 12px; color: #8C8C8C; margin-top: 4px; }

/* 图表区 */
.chart-row { margin-top: 14px; }
.chart-card { border-radius: 8px; }
.ct { font-weight: 600; font-size: 15px; color: #262626; }
.chart-card :deep(.el-card__header) { padding: 10px 16px; background: #F8FAFC; }
.hint { font-size: 12px; color: #8C8C8C; margin-left: 10px; font-weight: 400; }

/* 导出区 */
.export-card { margin-top: 14px; border-radius: 8px; }
.actions { display: flex; flex-wrap: wrap; gap: 12px; }
.actions .el-button { margin: 0; }
</style>
