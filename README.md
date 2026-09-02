# 人才补贴管理系统 · Talent Subsidy Management System

> 一个面向 HR / 人才管理场景的一体化台账系统（**个人作品集项目**）。
> 这是从真实项目中提炼的**脱敏版**：代码完整可运行，但**不含任何公司真实数据、内部地址或商业资产**，所有演示数据均由脚本随机生成。

技术栈：FastAPI + SQLAlchemy + SQLite（后端） · Vue 3 + Vite + Element Plus + ECharts（前端） · 可选接入任意 OpenAI 兼容大模型做 AI 助手。

---

## 一、在你自己的电脑上「直接打开」（最简单，无需 Node）

前端已经预编译好放在 `backend/static/`，所以**只要装了 Python 就能跑**，不用装 Node：

```bash
cd backend
python -m venv venv && venv\Scripts\activate      # 可选，建议用虚拟环境
pip install -r requirements.txt

# 生成一套虚构演示数据（账号 admin / admin123）
python seed_demo.py

# 启动（单进程，后端顺带托管前端）
python -m uvicorn app.main:app --host 0.0.0.0 --port 8002
```

浏览器打开 **http://localhost:8002** ，用 `admin / admin123` 登录即可。
同事/同局域网其他机器访问 **http://你的IP:8002**（记得放行防火墙 8002 入站端口）。

---

## 二、用 WorkBuddy 二次开发

把整个 `talent-system-personal/` 文件夹用 WorkBuddy 打开即可作为项目。

**改后端**：编辑 `backend/app/` 下的 Python，重启 uvicorn 生效。

**改前端**（需要 Node 18+）：

```bash
cd frontend
npm install
npm run dev        # 开发服务器 http://localhost:5175，已代理 /api 到 8002
# 改完发布：
npm run build      # 输出到 backend/static/，被后端直接托管
```

> 前端开发用 5175，生产用 8002（由后端托管构建产物），二者共用同一套后端 API。

---

## 三、AI 助手（可选）

默认**关闭**，不影响任何基础功能。想接自己的大模型，设环境变量即可（任意 OpenAI 兼容接口）：

```bash
AI_ENABLED=true
AI_PROVIDER=local
AI_BASE_URL=http://你的llm-host:8000/v1
AI_API_KEY=
AI_MODEL=你的模型名
```

---

## 四、功能一览

- **职称台账**：工程/技师双体系，证书归档、多维筛选
- **人才账号**：银行卡/数币账号 AES 字段级加密 + 列表脱敏
- **补贴政策 + AI 规则解析**：上传政策 PDF/Word → 解析为结构化规则（需配 AI）
- **补贴申领与发放确认**：分期计划、逐笔确认、自动回算累计到账、可改金额/备注
- **数据可视化大屏**：KPI + 6 张图表，支持按年份筛选
- **汇报材料导出**：PPT / PDF / HTML（PPT 需自备公司模板，见下方说明）
- **Excel 导入导出**
- **AI 对话助手**：中文 NL2SQL 查数、改数据（先计划后确认）、多模态问答

---

## 五、关于数据与资产

- `seed_demo.py` 生成的数据**全部虚构**：姓名/账号/金额随机生成（固定种子，结果可复现），政策名称沿用各地公开发布的人才补贴政策（公开信息）。
- 本包**不含**任何真实业务数据、员工个人信息、企业内部文档。
- **PPT 导出模板未包含**（属公司资产）。如需使用 PPT 导出功能，把自己公司的 `PPT模板.pptx` 放到 `backend/` 目录下即可；没有模板时系统会给出明确提示而不报错。

---

## 六、目录结构

```
talent-system-personal/
├── backend/
│   ├── app/              # FastAPI 后端（main/config/models/routers...）
│   ├── static/           # 已构建的前端（开箱即用）
│   ├── uploads/          # 上传文件目录（运行期生成）
│   ├── seed_demo.py      # 虚构演示数据生成
│   ├── init_db.py
│   └── requirements.txt
├── frontend/             # Vue3 源码（二次开发用）
└── README.md
```
