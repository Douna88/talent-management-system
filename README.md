# 人才补贴管理系统 · Talent Subsidy Management System

> 一个面向 HR / 人才管理场景的一体化台账系统：把散落在 Excel 里的职称、人才账号、政府补贴申领与分期发放记录，收敛成一套结构化、可追溯、带 AI 能力的内部系统。
>
> A full-stack internal tool for HR / talent-management workflows: ingests scattered Excel rosters (titles, accounts, subsidy applications) into a structured, auditable system with built-in AI assistance.

[![Backend](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)](#-技术栈--tech-stack)
[![Frontend](https://img.shields.io/badge/Frontend-Vue_3_+_Element_Plus-4FC08D?logo=vue.js&logoColor=white)](#-技术栈--tech-stack)
[![DB](https://img.shields.io/badge/DB-SQLite_(WAL)-003B57?logo=sqlite&logoColor=white)](#-技术栈--tech-stack)
[![AI](https://img.shields.io/badge/AI-NL2SQL_+_本地大模型-FF6F00?logo=openai&logoColor=white)](#-技术栈--tech-stack)
[![License](https://img.shields.io/badge/License-MIT-blue)](#)

---

## 📖 项目简介 · Overview

为人才与薪酬岗位打造的**一体化台账系统**，覆盖"职称录入"到"补贴发放确认"再到"汇报材料导出"的完整业务流。
系统支持多人协作、数据看板、报表导出（**PPT / PDF / HTML**），并内置一个**自然语言 AI 助手**——用中文提问即可查询数据、自动生成可视化图表。

**核心亮点**：

- **🏗️ 单进程一键部署**：前端（Vue 3）构建后由后端（FastAPI）直接托管，同事访问一个地址即可使用，**无需 Nginx / 独立前端服务器**。
- **🤖 AI 助手**：基于本地大模型（OpenAI 兼容接口）的 **NL2SQL**，断网时自动回退到内置规则引擎，常见问题秒级响应。
- **📊 可视化导出**：看板图表一键导出为 **PDF / PPT（含图表）**，也支持自包含的 **HTML 看板**。
- **🔐 数据安全**：SQLite WAL 模式 + 自动备份脚本；AES 字段级加密敏感账号 + 列表脱敏；`.env` 密钥不入库。

---

## 🛠 技术栈 · Tech Stack

| 层 | 技术 |
| --- | --- |
| 后端 | Python · **FastAPI** · SQLAlchemy · Pydantic · SQLite (WAL) |
| 前端 | Vue 3 · Vite · Element Plus · ECharts (vue-echarts) |
| AI | 本地大模型（OpenAI 兼容 `/chat/completions`） + 正则规则引擎兜底 |
| 导出 | python-pptx · reportlab · openpyxl · 内联 CSS HTML |
| 安全 | bcrypt (密码) · AES (敏感字段) · JWT (鉴权) |
| 部署 | 单进程 uvicorn（静态资源 + SPA 兜底路由） |

---

## ✨ 功能 · Features

### 🧑‍💼 职称台账
工程系列（员级 → 正高级工程师）与技师系列（三级 → 一级）双体系管理，支持证书扫描件归档、按姓名/等级/专业多维筛选，记录"下一阶段申请"计划。

### 💳 人才账号（字段加密）
银行卡号、数字人民币账号 **AES 字段级加密**存储，列表接口**仅展示脱敏掩码**（如 `6222***********6433`），明文需单独接口获取并留审计日志。

### 📑 补贴政策与 AI 规则解析
上传 PDF / Word 政策文件 → 自动抽取正文 → 大模型解析为结构化规则（发放周期、补贴标准、适用对象、享受期限…），每条规则可追溯到**原文引用**。AI 结果**必须经人工确认才生效**；人工增删改后自动退回"待确认"状态。

### 💰 补贴申领与发放确认
按政策规则**一键生成分期发放计划**，逐笔登记与确认，自动回算「累计到账」。
状态流：`待导入 → 待确认 → 已确认/有异议 → 已发放`。

### 📈 数据可视化大屏
6 张 KPI 卡片 + 6 个 ECharts 图表（年度趋势、政策占比、BU 分布、个人 TOP、职称分布、学历分布），支持**按年份筛选**。

### 📤 汇报材料导出
一键生成 **PPT（套用模板 + 原生图表）** / **PDF（中文友好）** / **HTML（自包含）** 三种格式的汇报材料。

### 💬 AI 对话助手
- **NL2SQL 自然语言查数**：用中文提问直接返回结论与中文表格，**永不暴露 SQL**
- **改数据**：先生成执行计划，前端确认后才落地，兼顾自由度与安全
- **多模态**：上传图片走视觉理解，上传 PDF/Word/Excel/PPT 自动抽取文本后作答

### 🔁 Excel 导入导出
按 **导出表结构反向解析** Excel，导入后自动回算累计到账；已存在数据可跳过或补全。

---

## 🚀 快速开始 · Quick Start

### 1. 准备环境
- Python **3.10+**
- Node.js 18+（仅开发模式需要；生产可直接用构建产物）

### 2. 启动后端

```bash
cd backend
pip install -r requirements.txt

# 生成虚构演示数据（30 职称 / 25 加密账号 / 16 政策 / 45 申领 / 109 发放）
python seed_demo.py

# 启动服务（单进程托管前端，无需 Nginx）
python -m uvicorn app.main:app --host 0.0.0.0 --port 8002
```

打开 http://localhost:8002 ，登录账号 **admin / admin123**。

### 3. 启动前端（开发模式）

```bash
cd frontend
npm install
npm run dev      # http://localhost:5175，已配置 /api 代理到 8002
```

生产构建：`npm run build` 会输出到 `backend/static/`，由后端直接托管。

### 4. 配置 AI（可选）

AI 能力默认关闭也能正常跑基础功能。设置环境变量启用：

```bash
AI_ENABLED=true
AI_PROVIDER=local
AI_BASE_URL=http://your-llm-host:8000/v1    # 任意 OpenAI 兼容接口
AI_API_KEY=
AI_MODEL=your-model-name
```

---

## ⚠️ 关于演示数据

仓库内 `seed_demo.py` 生成的数据**全部为虚构**：

- 👤 人员姓名、银行卡号、数币账号均由脚本随机生成（固定种子，结果可复现）
- 💴 补贴金额、发放日期为演示用构造值
- 📜 政策名称沿用各地**公开发布**的人才补贴政策（公开信息），用于还原真实业务场景

> 本仓库**不包含任何真实业务数据、员工个人信息或企业内部文档**。
> 上传至 GitHub 前已完成 4 轮扫描：敏感词 / 真实姓名 / 大文件 / 二进制资产。

---

## 📂 目录结构 · Project Structure

```
talent-system/
├── backend/
│   ├── app/
│   │   ├── main.py            # 应用入口 + 静态资源 + SPA 路由
│   │   ├── config.py          # DB / JWT / 加密 / AI 三档开关
│   │   ├── models.py          # SQLAlchemy 数据模型
│   │   ├── security.py        # JWT 鉴权 + 密码哈希
│   │   ├── encryption.py      # AES 字段加密 + 账号脱敏
│   │   ├── ai_bridge.py       # 大模型桥接（对话 / 视觉 / 文档抽取 / NL2SQL）
│   │   └── routers/           # 业务路由
│   │       ├── title.py           # 职称与证书
│   │       ├── talent_account.py  # 人才账号（加密）
│   │       ├── subsidy.py         # 政策 / 申领 / 发放 / AI 规则
│   │       ├── ai_query.py        # AI 对话助手（含多模态）
│   │       ├── stats.py           # 大屏统计
│   │       ├── report.py          # PPT / PDF / HTML 汇报导出
│   │       ├── export.py / import_router.py  # Excel 双向打通
│   │       └── files.py           # 文件中心
│   ├── seed_demo.py           # 演示数据生成（全部虚构）
│   └── requirements.txt
└── frontend/
    ├── src/views/             # 页面组件
    ├── src/api/               # 接口封装
    └── vite.config.js
```

---

## 📝 说明 · Notice

本仓库为**学习与展示用途的脱敏版本**：

- ✅ 已移除所有真实业务数据、员工个人信息、企业内部文档与资产
- ✅ 代码中的内网地址、硬编码密钥、开发机路径均已替换为占位符
- ✅ 演示数据由 `seed_demo.py` 随机生成

如用于生产环境，请务必：
1. 通过环境变量设置 `SECRET_KEY`，**不要使用默认值**
2. 将 SQLite 切换为 PostgreSQL 等生产级数据库
3. 配置 HTTPS 与正式的备份策略