import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue') },
  {
    path: '/',
    component: () => import('../layout/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '工作台' } },
      { path: 'title', name: 'TitleList', component: () => import('../views/title/TitleList.vue'), meta: { title: '职称管理' } },
      { path: 'account', name: 'TalentAccount', component: () => import('../views/account/TalentAccount.vue'), meta: { title: '人才账号' } },
      { path: 'subsidy/policies', name: 'PolicyList', component: () => import('../views/subsidy/PolicyList.vue'), meta: { title: '政策管理' } },
      { path: 'subsidy/list', name: 'SubsidyList', component: () => import('../views/subsidy/SubsidyList.vue'), meta: { title: '补贴明细' } },
      { path: 'subsidy/confirm', name: 'SubsidyConfirm', component: () => import('../views/subsidy/SubsidyConfirm.vue'), meta: { title: '发放确认' } },
      { path: 'stats', name: 'Stats', component: () => import('../views/io/DataCenter.vue'), meta: { title: '数据大屏 / 报表' } },
      { path: 'io', name: 'ImportExport', component: () => import('../views/io/DataCenter.vue'), meta: { title: '数据大屏 / 报表' } },
      { path: 'files', name: 'FileCenter', component: () => import('../views/io/FileCenter.vue'), meta: { title: '文件中心' } },
      { path: 'settings', name: 'Settings', component: () => import('../views/io/Settings.vue'), meta: { title: '系统设置' } },
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.path !== '/login' && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/')
  } else {
    next()
  }
})

export default router
