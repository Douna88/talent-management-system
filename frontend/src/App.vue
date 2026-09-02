<template>
  <router-view />
</template>

<script setup>
</script>

<style>
/* ============================================================
   全局 CSS 变量 — 统一设计系统
   ============================================================ */
:root {
  /* 主色 */
  --color-primary: #2F6FED;
  --color-primary-light: #EBF2FF;
  --color-success: #52C41A;
  --color-success-light: #F6FFED;
  --color-warning: #FAAD14;
  --color-warning-light: #FFFBE6;
  --color-danger: #FF4D4F;
  --color-danger-light: #FFF2F0;
  --color-info: #8C8C8C;

  /* 文字 */
  --color-text-primary: #262626;
  --color-text-secondary: #595959;
  --color-text-muted: #8C8C8C;
  --color-text-placeholder: #BFBFBF;

  /* 边框与背景 */
  --color-border: #E8E8E8;
  --color-border-light: #F0F0F0;
  --color-bg-page: #F5F7FA;
  --color-bg-card: #FFFFFF;
  --color-bg-table-header: #F8FAFC;
  --color-bg-hover: #F5F7FA;
  --color-bg-sidebar: #141F33;

  /* 间距 */
  --space-page: 20px;
  --space-card-gap: 16px;
  --space-section: 20px;

  /* 圆角 */
  --radius-card: 8px;
  --radius-btn: 4px;
  --radius-tag: 4px;

  /* 阴影 — 页面级不用阴影，保持干净 */
  --shadow-none: none;
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 2px 8px rgba(0,0,0,0.06);
}

/* 全局重置 */
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body, #app { height: 100%; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  color: var(--color-text-primary);
  background: var(--color-bg-page);
  -webkit-font-smoothing: antialiased;
}

/* ============================================================
   Element Plus 主题覆盖 — 统一到底
   ============================================================ */

/* 主按钮 */
.el-button--primary {
  --el-button-bg-color: var(--color-primary);
  --el-button-border-color: var(--color-primary);
}

/* 表格表头 */
.el-table thead th {
  background: var(--color-bg-table-header) !important;
  color: var(--color-text-secondary) !important;
  font-weight: 500 !important;
}

/* 卡片统一 */
.el-card {
  border: 1px solid var(--color-border) !important;
  border-radius: var(--radius-card) !important;
}
.el-card__header {
  padding: 14px 20px;
  border-bottom: 1px solid var(--color-border-light);
  font-weight: 600;
  color: var(--color-text-primary);
  font-size: 15px;
}

/* 分页器 */
.el-pagination.is-background .el-pager li:not(.is-disabled).is-active {
  background-color: var(--color-primary) !important;
}

/* 输入框聚焦 */
.el-input__wrapper.is-focus {
  box-shadow: 0 0 0 1px var(--color-primary) inset !important;
}

/* 侧边栏菜单覆盖 */
.el-menu--vertical {
  border-right: none !important;
}

/* Tag 字体大小统一 */
.el-tag { font-weight: 500; }
</style>
