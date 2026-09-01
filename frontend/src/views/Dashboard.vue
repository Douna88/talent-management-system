<template>
  <div class="dashboard">
    <el-row :gutter="16">
      <el-col :span="6" v-for="card in cards" :key="card.label">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value" :style="{ color: card.color }">{{ card.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mt16">
      <el-col :span="14">
        <el-card shadow="never" class="panel">
          <template #header><span class="panel-title">快捷入口</span></template>
          <div class="quick">
            <div class="q-item" @click="go('/title')"><el-icon><Collection /></el-icon><span>职称管理</span></div>
            <div class="q-item" @click="go('/account')"><el-icon><CreditCard /></el-icon><span>人才账号</span></div>
            <div class="q-item" @click="go('/subsidy/policies')"><el-icon><Files /></el-icon><span>政策管理</span></div>
            <div class="q-item" @click="go('/subsidy/confirm')"><el-icon><Wallet /></el-icon><span>发放确认</span></div>
            <div class="q-item" @click="go('/io')"><el-icon><TrendCharts /></el-icon><span>数据大屏 / 报表</span></div>
            <div class="q-item" @click="go('/files')"><el-icon><FolderOpened /></el-icon><span>文件中心</span></div>
            <div class="q-item" @click="go('/settings')"><el-icon><Setting /></el-icon><span>系统设置</span></div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="never" class="panel">
          <template #header><span class="panel-title">待办提醒</span></template>
          <ul class="todo">
            <li>
              <el-tag type="danger" effect="plain" size="small">{{ stats.pending_confirm ?? 0 }}</el-tag>
              笔发放待部门员工确认
              <el-link type="primary" @click="go('/subsidy/confirm')">去处理</el-link>
            </li>
            <li>
              <el-tag type="warning" effect="plain" size="small">{{ stats.parsed_policy ?? 0 }}</el-tag>
              项政策 AI 已解析，待人工确认生效
              <el-link type="primary" @click="go('/subsidy/policies')">去确认</el-link>
            </li>
            <li>
              <el-tag type="success" effect="plain" size="small">{{ stats.confirmed_policy ?? 0 }}</el-tag>
              项政策规则已确认生效
            </li>
            <li v-if="stats.pending_policy">
              <el-tag type="info" effect="plain" size="small">{{ stats.pending_policy }}</el-tag>
              项政策尚未上传文档并解析
              <el-link type="primary" @click="go('/subsidy/policies')">去处理</el-link>
            </li>
            <li class="muted">
              累计已发放 <b>{{ fmt(stats.total_paid) }}</b> 万元 ·
              {{ stats.year }} 年已发放 <b>{{ fmt(stats.year_paid) }}</b> 万元
            </li>
          </ul>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'

const router = useRouter()
const stats = ref({})

const cards = computed(() => [
  { label: '职称人数', value: stats.value.title_count ?? '-', color: '#409eff' },
  { label: '人才账号', value: stats.value.account_count ?? '-', color: '#67c23a' },
  { label: '补贴政策', value: stats.value.policy_count ?? '-', color: '#e6a23c' },
  { label: '待确认发放', value: stats.value.pending_confirm ?? '-', color: '#f56c6c' },
  { label: '补贴申领', value: stats.value.application_count ?? '-', color: '#909399' },
  { label: '发放笔数', value: stats.value.payment_count ?? '-', color: '#909399' },
  { label: '在发政策', value: stats.value.active_policy_count ?? '-', color: '#409eff' },
  { label: '累计已发(万元)', value: fmt(stats.value.total_paid), color: '#f56c6c' },
])

function fmt(v) {
  if (v == null) return '-'
  return Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
function go(p) { router.push(p) }

onMounted(async () => {
  try { stats.value = await api.get('/stats/dashboard') } catch (e) {}
})
</script>

<style scoped>
.stat-card { text-align: center; margin-bottom: 16px; }
.stat-label { font-size: 13px; color: #909399; }
.stat-value { font-size: 26px; font-weight: 700; margin-top: 6px; }
.mt16 { margin-top: 16px; }
.panel-title { font-weight: 600; }
.quick { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.q-item {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 14px 6px; border-radius: 10px; cursor: pointer;
  background: #f7f9fc; transition: all .15s; font-size: 13px; color: #455;
}
.q-item:hover { background: #eef4ff; color: #1d6cff; transform: translateY(-2px); }
.q-item .el-icon { font-size: 22px; }
.todo { list-style: none; padding: 0; margin: 0; line-height: 2.4; font-size: 14px; }
.todo li { display: flex; align-items: center; gap: 8px; }
.todo .muted { color: #999; gap: 0; }
.todo b { color: #f56c6c; }
</style>
