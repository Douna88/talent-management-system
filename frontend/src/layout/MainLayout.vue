<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">
        <el-icon size="22"><UserFilled /></el-icon>
        <span>人才管理系统</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        background-color="#141F33"
        text-color="#A3AAB8"
        active-text-color="#FFFFFF"
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
        <div class="header-left">
          <span class="page-title">{{ $route.meta.title || '人才管理系统' }}</span>
        </div>
        <div class="header-right">
          <el-avatar :size="28" :icon="UserFilled" class="avatar" />
          <span class="user-name">{{ user?.display_name || '管理员' }}</span>
          <el-divider direction="vertical" />
          <el-button text size="small" class="logout-btn" @click="logout">
            <el-icon size="14"><SwitchButton /></el-icon> 退出
          </el-button>
        </div>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>

  <AiAssistant />
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { UserFilled, SwitchButton } from '@element-plus/icons-vue'
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

/* 侧边栏 */
.aside {
  background: #141F33;
  display: flex;
  flex-direction: column;
}
.logo {
  height: 56px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 20px;
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  flex-shrink: 0;
}
.aside :deep(.el-menu) {
  border-right: none;
  background: transparent;
}
.aside :deep(.el-menu-item),
.aside :deep(.el-sub-menu__title) {
  height: 44px;
  line-height: 44px;
  font-size: 13.5px;
  border-radius: 6px;
  margin: 2px 8px;
}
.aside :deep(.el-menu-item.is-active) {
  background: rgba(47,111,237,0.15) !important;
  color: #fff !important;
  font-weight: 500;
}
.aside :deep(.el-menu-item:hover) {
  background: rgba(255,255,255,0.06) !important;
}
.aside :deep(.el-sub-menu__title:hover) {
  background: rgba(255,255,255,0.06) !important;
}

/* 顶栏 */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 52px;
  padding: 0 24px;
  border-bottom: 1px solid #E8E8E8;
  background: #fff;
}
.page-title {
  font-size: 16px;
  font-weight: 600;
  color: #262626;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.avatar {
  background: #E8E8E8;
  color: #8C8C8C;
}
.user-name {
  font-size: 13px;
  color: #595959;
}
.logout-btn {
  color: #8C8C8C;
}
.logout-btn:hover {
  color: #FF4D4F;
}

/* 主内容区 */
.main {
  background: #F5F7FA;
  padding: 20px;
}
</style>
