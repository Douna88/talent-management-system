<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">
        <el-icon><UserFilled /></el-icon>
        <span>人才管理系统</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        background-color="#001529"
        text-color="#a6adb4"
        active-text-color="#ffffff"
      >
        <el-menu-item index="/dashboard">
          <el-icon><Odometer /></el-icon>
          <span>工作台</span>
        </el-menu-item>
        <el-menu-item index="/title">
          <el-icon><Collection /></el-icon>
          <span>职称管理</span>
        </el-menu-item>
        <el-menu-item index="/account">
          <el-icon><CreditCard /></el-icon>
          <span>人才账号</span>
        </el-menu-item>
        <el-sub-menu index="subsidy">
          <template #title>
            <el-icon><Wallet /></el-icon>
            <span>个人补贴</span>
          </template>
          <el-menu-item index="/subsidy/policies">政策管理</el-menu-item>
          <el-menu-item index="/subsidy/list">补贴明细</el-menu-item>
          <el-menu-item index="/subsidy/confirm">发放确认</el-menu-item>
        </el-sub-menu>
        <el-menu-item index="/io">
          <el-icon><TrendCharts /></el-icon>
          <span>数据大屏 / 报表</span>
        </el-menu-item>
        <el-menu-item index="/files">
          <el-icon><FolderOpened /></el-icon>
          <span>文件中心</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>系统设置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-title">{{ $route.meta.title || '人才管理系统' }}</div>
        <div class="header-right">
          <span class="user-name">{{ user?.display_name || '管理员' }}</span>
          <el-button text @click="logout">退出登录</el-button>
        </div>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>

  <!-- AI 助手浮窗 -->
  <AiAssistant />
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AiAssistant from '../components/AiAssistant.vue'

const route = useRoute()
const router = useRouter()

const user = computed(() => {
  try { return JSON.parse(localStorage.getItem('user') || 'null') } catch { return null }
})

const activeMenu = computed(() => route.path)

function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  router.push('/login')
}
</script>

<style scoped>
.layout { height: 100%; }
.aside { background-color: #001529; }
.logo {
  height: 56px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 20px;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}
.aside :deep(.el-menu) { border-right: none; }
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e8e8e8;
  background: #fff;
}
.header-title { font-size: 16px; font-weight: 600; }
.header-right { display: flex; align-items: center; gap: 12px; }
.user-name { color: #666; }
.main { background: #f5f6f8; padding: 16px; }
</style>
