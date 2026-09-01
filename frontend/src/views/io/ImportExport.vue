<template>
  <div class="io">
    <el-card shadow="never">
      <el-tabs v-model="tab">
        <el-tab-pane label="汇报材料" name="report">
          <p class="desc">基于当前系统数据，一键生成向领导汇报的材料，支持 PPT / PDF / HTML 三种格式（PPT 套用公司固定模板）。</p>
          <div class="actions">
            <el-button type="primary" :loading="busy==='ppt'" @click="exportReport('ppt')">
              <el-icon><Picture /></el-icon> 导出 PPT（公司模板）
            </el-button>
            <el-button :loading="busy==='pdf'" @click="exportReport('pdf')">
              <el-icon><Document /></el-icon> 导出 PDF
            </el-button>
            <el-button :loading="busy==='html'" @click="exportReport('html')">
              <el-icon><Memo /></el-icon> 导出 HTML
            </el-button>
            <el-button @click="go('/stats')">
              <el-icon><TrendCharts /></el-icon> 查看数据看板
            </el-button>
          </div>
        </el-tab-pane>

        <el-tab-pane label="Excel 导出" name="export">
          <p class="desc">按系统现有结构实时导出 Excel，可直接二次编辑后回传导入。</p>
          <div class="actions">
            <el-button @click="exportExcel('titles','职称汇总表_导出.xlsx')"><el-icon><Collection /></el-icon> 职称表</el-button>
            <el-button @click="exportExcel('accounts','个人数币账号总明细_导出.xlsx')"><el-icon><CreditCard /></el-icon> 人才账号</el-button>
            <el-button @click="exportExcel('policies','人才补贴政策清单_导出.xlsx')"><el-icon><Files /></el-icon> 政策清单</el-button>
            <el-button @click="exportExcel('subsidy','个人补贴总表_导出.xlsx')"><el-icon><Wallet /></el-icon> 补贴明细</el-button>
          </div>
        </el-tab-pane>

        <el-tab-pane label="Excel 导入" name="import">
          <p class="desc">上传与导出同结构的 xlsx，按表头自动解析并写入（已存在的记录自动跳过/补全）。</p>
          <el-form label-width="110px">
            <el-form-item label="导入类型">
              <el-radio-group v-model="importType">
                <el-radio value="titles">职称表</el-radio>
                <el-radio value="accounts">人才账号</el-radio>
                <el-radio value="subsidy">补贴明细</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="选择文件">
              <el-upload
                :auto-upload="false"
                :show-file-list="true"
                :limit="1"
                accept=".xlsx,.xls"
                :on-change="onFileChange"
                :on-remove="onFileRemove"
              >
                <el-button><el-icon><UploadFilled /></el-icon> 选择 Excel</el-button>
              </el-upload>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :disabled="!importFile" :loading="importing" @click="doImport">
                开始导入
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api, { slowApi, downloadBlob } from '../../api'

const router = useRouter()
const tab = ref('report')
const busy = ref('')
const importType = ref('titles')
const importFile = ref(null)
const importing = ref(false)

function go(p) { router.push(p) }

async function exportReport(fmt) {
  busy.value = fmt
  try {
    const name = { ppt: '人才补贴管理汇报.pptx', pdf: '人才补贴管理汇报.pdf', html: '人才补贴管理汇报.html' }[fmt]
    await downloadBlob(`/export/report/${fmt}`, name, slowApi)
    ElMessage.success('导出成功')
  } catch (e) { /* 拦截器已提示 */ }
  finally { busy.value = '' }
}

async function exportExcel(kind, name) {
  try {
    await downloadBlob(`/export/${kind}`, name, slowApi)
    ElMessage.success('导出成功')
  } catch (e) {}
}

function onFileChange(file) { importFile.value = file.raw; return false }
function onFileRemove() { importFile.value = null }

async function doImport() {
  if (!importFile.value) return
  importing.value = true
  const form = new FormData()
  form.append('file', importFile.value)
  try {
    const res = await slowApi.post(`/import/${importType.value}`, form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    ElMessage.success(res.message || '导入完成')
    importFile.value = null
  } catch (e) {}
  finally { importing.value = false }
}
</script>

<style scoped>
.desc { color: #888; font-size: 13px; margin: 4px 0 16px; }
.actions { display: flex; flex-wrap: wrap; gap: 12px; }
.actions .el-button { margin: 0; }
</style>
