<template>
  <div class="settings">
    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="never" header="AI 助手状态">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="启用状态">
              <el-tag :type="ai.enabled ? 'success' : 'danger'">{{ ai.enabled ? '已启用' : '未启用' }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="模型提供方">{{ ai.provider || 'local' }}</el-descriptions-item>
            <el-descriptions-item label="模型名称">{{ ai.model }}</el-descriptions-item>
            <el-descriptions-item label="视觉/多模态">
              <el-tag :type="ai.vision ? 'success' : 'info'">{{ ai.vision ? '支持' : '不支持' }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="写操作权限">
              <el-tag :type="ai.can_write ? 'success' : 'info'">{{ ai.can_write ? '已开放' : '仅只读' }}</el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" header="当前账户">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="用户名">{{ user?.username }}</el-descriptions-item>
            <el-descriptions-item label="显示名">{{ user?.display_name }}</el-descriptions-item>
            <el-descriptions-item label="角色">
              <el-tag size="small">{{ user?.role === 'admin' ? '管理员' : user?.role }}</el-tag>
            </el-descriptions-item>
          </el-descriptions>
          <el-alert type="info" :closable="false" class="mt" title="本系统仅部门内 2 人使用，不做跨部门权限隔离；AI 助手已开放全部数据权限，改数据需人工确认后执行。" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" header="数据概览" class="mt">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="职称人数">{{ stats.title_count }}</el-descriptions-item>
        <el-descriptions-item label="人才账号">{{ stats.account_count }}</el-descriptions-item>
        <el-descriptions-item label="补贴政策">{{ stats.policy_count }}</el-descriptions-item>
        <el-descriptions-item label="补贴申领">{{ stats.application_count }}</el-descriptions-item>
        <el-descriptions-item label="发放笔数">{{ stats.payment_count }}</el-descriptions-item>
        <el-descriptions-item label="累计已发(元)">{{ fmt(stats.total_paid) }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '../../api'

const user = computed(() => {
  try { return JSON.parse(localStorage.getItem('user') || 'null') } catch { return null }
})
const ai = ref({})
const stats = ref({})

function fmt(v) {
  if (v == null) return '-'
  return Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

onMounted(async () => {
  try {
    ai.value = await api.get('/ai/status')
    stats.value = await api.get('/stats/dashboard')
  } catch (e) {}
})
</script>

<style scoped>
.mt { margin-top: 16px; }
</style>
