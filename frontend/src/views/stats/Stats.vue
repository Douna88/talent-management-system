<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="24">
        <el-card shadow="never">
          <template #header>年度补贴发放趋势（已发，单位：元）</template>
          <div ref="trendRef" class="chart" style="height:320px"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>各政策补贴占比</template>
          <div ref="policyRef" class="chart" style="height:360px"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>BU 补贴汇总 TOP15</template>
          <div ref="buRef" class="chart" style="height:360px"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>个人补贴 TOP20</template>
          <div ref="personRef" class="chart" style="height:420px"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>职称等级分布 / 学历分布</template>
          <div ref="titleRef" class="chart" style="height:220px"></div>
          <div style="height:8px;border-top:1px dashed #E8E8E8;margin:4px 16px"></div>
          <div ref="eduRef" class="chart" style="height:220px"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import api from '../../api'

const trendRef = ref()
const policyRef = ref()
const buRef = ref()
const personRef = ref()
const titleRef = ref()
const eduRef = ref()

const charts = []

function makePie(data, nameField = 'name', valueField = 'value') {
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { type: 'scroll', orient: 'vertical', right: 10, top: 'middle' },
    series: [{
      type: 'pie',
      radius: ['35%', '65%'],
      center: ['38%', '50%'],
      label: { show: false },
      data: data.map(d => ({ name: d[nameField], value: d[valueField] }))
    }]
  }
}

function makeBar(data, nameField = 'name', valueField = 'value') {
  const names = data.map(d => d[nameField])
  const values = data.map(d => d[valueField])
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 10, right: 30, bottom: 10, top: 10, containLabel: true },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: names, inverse: true, axisLabel: { width: 120, overflow: 'truncate' } },
    series: [{ type: 'bar', data: values, barMaxWidth: 18, itemStyle: { color: '#2F6FED' } }]
  }
}

function renderChart(elRef, option) {
  if (!elRef.value) return
  const chart = echarts.init(elRef.value)
  chart.setOption(option)
  charts.push(chart)
}

async function load() {
  const d = await api.get('/stats/charts')

  renderChart(trendRef, {
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 20, bottom: 30, top: 20 },
    xAxis: { type: 'category', data: d.trend.years },
    yAxis: { type: 'value', name: '元' },
    series: [{
      type: 'line',
      data: d.trend.amounts,
      smooth: true,
      areaStyle: { opacity: 0.15 },
      itemStyle: { color: '#409eff' },
      label: { show: true, formatter: p => (p.value / 10000).toFixed(1) + '万' }
    }]
  })

  renderChart(policyRef, makePie(d.policy_pie))
  renderChart(buRef, makeBar(d.bu_top))
  renderChart(personRef, makeBar(d.person_top))
  renderChart(titleRef, makePie(d.title_pie))
  renderChart(eduRef, makePie(d.edu_pie))
}

function resizeAll() {
  charts.forEach(c => c.resize())
}

onMounted(async () => {
  await load()
  window.addEventListener('resize', resizeAll)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeAll)
  charts.forEach(c => c.dispose())
})
</script>

<style scoped>
.chart { width: 100%; }
</style>
