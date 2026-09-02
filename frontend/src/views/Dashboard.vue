<template>
  <div class="dashboard">
    <!-- 统计卡 — 数字统一深色，仅待确认用红色强调 -->
    <el-row :gutter="16">
      <el-col :span="3" v-for="card in cards" :key="card.label">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value" :class="{ danger: card.isDanger }">{{ card.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mt16">
      <!-- 快捷入口 -->
      <el-col :span="14">
        <el-card shadow="never" class="panel">
          <template #header><span class="panel-title">快捷入口</span></template>
          <div class="quick">
            <div class="q-item" @click="go('/title')">
              <div class="q-icon"><el-icon><Collection /></el-icon></div>
              <span class="q-label">职称管理</span>
            </div>
            <div class="q-item" @click="go('/account')">
              <div class="q-icon"><el-icon><CreditCard /></el-icon></div>
              <span class="q-label">人才账号</span>
            </div>
            <div class="q-item" @click="go('/subsidy/policies')">
              <div class="q-icon"><el-icon><Files /></el-icon></div>
              <span class="q-label">政策管理</span>
            </div>
            <div class="q-item" @click="go('/subsidy/confirm')">
              <div class="q-icon"><el-icon><Wallet /></el-icon></div>
              <span class="q-label">发放确认</span>
            </div>
            <div class="q-item" @click="go('/io')">
              <div class="q-icon"><el-icon><TrendCharts /></el-icon></div>
              <span class="q-label">数据大屏</span>
            </div>
            <div class="q-item" @click="go('/files')">
              <div class="q-icon"><el-icon><FolderOpened /></el-icon></div>
              <span class="q-label">文件中心</span>
            </div>
            <div class="q-item" @click="go('/settings')">
              <div class="q-icon"><el-icon><Setting /></el-icon></div>
              <span class="q-label">系统设置</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <!-- 待办 -->
      <el-col :span="10">
        <el-card shadow="never" class="panel">
          <template #header><span class="panel-title">待办提醒</span></template>
          <ul class="todo">
            <li>
              <el-tag v-if="stats.pending_confirm" type="danger" size="small" effect="light">{{ stats.pending_confirm }}</el-tag>
              <el-tag v-else type="info" size="small" effect="light">0</el-tag>
              <span class="todo-text">笔发放待部门员工确认</span>
              <el-link type="primary" :underline="false" @click="go('/subsidy/confirm')">去处理</el-link>
            </li>
            <li>
              <el-tag v-if="stats.parsed_policy" type="warning" size="small" effect="light">{{ stats.parsed_policy }}</el-tag>
              <el-tag v-else type="info" size="small" effect="light">0</el-tag>
              <span class="todo-text">项政策 AI 已解析，待人工确认生效</span>
              <el-link type="primary" :underline="false" @click="go('/subsidy/policies')">去确认</el-link>
            </li>
            <li>
              <el-tag type="success" size="small" effect="light">{{ stats.confirmed_policy ?? 0 }}</el-tag>
              <span class="todo-text">项政策规则已确认生效</span>
            </li>
            <li v-if="stats.pending_policy">
              <el-tag type="info" size="small" effect="light">{{ stats.pending_policy }}</el-tag>
              <span class="todo-text">项政策尚未上传文档并解析</span>
              <el-link type="primary" :underline="false" @click="go('/subsidy/policies')">去处理</el-link>
            </li>
            <li class="summary">
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
  { label: '职称人数', value: stats.value.title_count ?? '-' },
  { label: '人才账号', value: stats.value.account_count ?? '-' },
  { label: '补贴政策', value: stats.value.policy_count ?? '-' },
  { label: '待确认', value: stats.value.pending_confirm ?? '-', isDanger: true },
  { label: '补贴申领', value: stats.value.application_count ?? '-' },
  { label: '发放笔数', value: stats.value.payment_count ?? '-' },
  { label: '在发政策', value: stats.value.active_policy_count ?? '-' },
  { label: '累计已发(万元)', value: fmt(stats.value.total_paid) },
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
.stat-card {
  text-align: center;
  padding: 12px 0;
  margin-bottom: 16px;
}
.stat-label {
  font-size: 12px;
  color: #8C8C8C;
  margin-bottom: 6px;
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #262626;
  line-height: 1.2;
}
.stat-value.danger {
  color: #FF4D4F;
}
.mt16 { margin-top: 16px; }
.panel-title {
  font-weight: 600;
  font-size: 15px;
  color: #262626;
}

/* 快捷入口 */
.quick {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.q-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px 8px;
  border-radius: 8px;
  cursor: pointer;
  background: #F8FAFC;
  border: 1px solid transparent;
  transition: all .15s;
}
.q-item:hover {
  background: #EBF2FF;
  border-color: #D6E4FF;
}
.q-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  color: #2F6FED;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.q-label {
  font-size: 13px;
  color: #595959;
  font-weight: 500;
}

/* 待办 */
.todo {
  list-style: none;
  padding: 0;
  margin: 0;
}
.todo li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid #F0F0F0;
  font-size: 14px;
}
.todo li:last-child { border-bottom: none; }
.todo-text { flex: 1; color: #595959; }
.todo .summary {
  padding-top: 12px;
  color: #8C8C8C;
  font-size: 13px;
}
.todo .summary b { color: #262626; font-weight: 600; }
</style>
