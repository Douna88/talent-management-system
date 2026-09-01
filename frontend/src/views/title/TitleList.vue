<template>
  <div>
    <el-card shadow="never">
      <!-- 工具栏 -->
      <div class="toolbar">
        <el-radio-group v-model="series" @change="load">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="engineering">工程类</el-radio-button>
          <el-radio-button value="technician">技能类</el-radio-button>
        </el-radio-group>
        <el-select v-model="education" placeholder="学历" clearable style="width:150px" @change="load">
          <el-option v-for="e in educations" :key="e" :label="e" :value="e" />
        </el-select>
        <el-date-picker v-model="year" type="year" placeholder="认定年份" value-format="YYYY" clearable style="width:130px" @change="load" />
        <el-select v-model="level" placeholder="职称等级" clearable style="width:150px" @change="load">
          <el-option v-for="lv in levelOptions" :key="lv.value" :label="lv.label" :value="lv.value" />
        </el-select>
        <el-input v-model="keyword" placeholder="搜索姓名/专业/学科" clearable style="width:200px" @keyup.enter="load" @clear="load">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon> 新增</el-button>
        <el-button @click="exportExcel"><el-icon><Download /></el-icon> 导出</el-button>
      </div>

      <!-- 表格 -->
      <el-table :data="rows" v-loading="loading" border stripe>
        <el-table-column prop="seq_no" label="序号" width="60" />
        <el-table-column prop="name" label="姓名" width="100" />
        <el-table-column prop="education" label="学历" width="110" />
        <el-table-column prop="title_name" label="职称类型" width="130" />
        <el-table-column prop="title_date" label="认定时间" width="110" />
        <el-table-column prop="major_field" label="专业" min-width="130" show-overflow-tooltip />
        <el-table-column prop="discipline" label="学科" min-width="130" show-overflow-tooltip />
        <el-table-column prop="next_stage_apply" label="下一阶段申请" width="130" />
        <el-table-column prop="remark" label="备注" min-width="130" show-overflow-tooltip />
        <el-table-column label="证书" width="80">
          <template #default="{ row }">
            <el-button link type="primary" @click="openCerts(row)">查看</el-button>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑职称' : '新增职称'" width="560px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="姓名" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="学历">
          <el-select v-model="form.education" clearable style="width:100%">
            <el-option v-for="e in educations" :key="e" :label="e" :value="e" />
          </el-select>
        </el-form-item>
        <el-form-item label="序列" required>
          <el-radio-group v-model="form.title_series">
            <el-radio value="engineering">工程类</el-radio>
            <el-radio value="technician">技能类</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="职称类型" required>
          <el-select v-model="form.title_level" style="width:100%" @change="onLevelChange">
            <el-option v-for="lv in currentLevels" :key="lv.value" :label="lv.label" :value="lv.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="认定时间">
          <el-date-picker v-model="form.title_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
        </el-form-item>
        <el-form-item label="专业">
          <el-input v-model="form.major_field" />
        </el-form-item>
        <el-form-item label="学科">
          <el-input v-model="form.discipline" />
        </el-form-item>
        <el-form-item label="下一阶段申请">
          <el-input v-model="form.next_stage_apply" placeholder="如：2027年申请副高" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 证书弹窗 -->
    <el-dialog v-model="certDialogVisible" :title="`证书管理 - ${certName}`" width="640px">
      <el-upload
        :show-file-list="false"
        :http-request="uploadCert"
        accept=".pdf,.jpg,.jpeg,.png"
      >
        <el-button type="primary"><el-icon><Upload /></el-icon> 上传证书</el-button>
      </el-upload>
      <el-table :data="certs" border stripe style="margin-top:12px">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="original_name" label="文件名" min-width="220" show-overflow-tooltip />
        <el-table-column prop="cert_type" label="类型" width="120" />
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button link type="primary" @click="previewCert(row)">预览</el-button>
            <el-button link type="danger" @click="delCert(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api'

const rows = ref([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)

const series = ref('')
const level = ref('')
const education = ref('')
const year = ref('')
const keyword = ref('')

const options = ref({})
const educations = ['Bachelor', 'Master', 'PhD', 'Vocational College']

// 证书相关
const certDialogVisible = ref(false)
const certTitleId = ref(null)
const certName = ref('')
const certs = ref([])

const form = reactive({
  name: '', education: '', title_series: 'engineering', title_level: '',
  title_date: '', major_field: '', discipline: '', next_stage_apply: '', remark: ''
})

const levelOptions = computed(() => {
  const list = []
  Object.values(options.value).forEach(s => (s.levels || []).forEach(lv => list.push(lv)))
  return list
})

const currentLevels = computed(() => {
  const s = options.value[form.title_series]
  return s ? s.levels : []
})

function onLevelChange(val) {
  const lv = currentLevels.value.find(l => l.value === val)
  if (lv) form.title_name = lv.label
}

async function load() {
  loading.value = true
  try {
    const params = {}
    if (series.value) params.series = series.value
    if (level.value) params.level = level.value
    if (education.value) params.education = education.value
    if (year.value) params.year = year.value
    if (keyword.value) params.keyword = keyword.value
    rows.value = await api.get('/title/list', { params })
  } catch (e) { /* 拦截器已提示 */ } finally {
    loading.value = false
  }
}

function resetForm() {
  Object.assign(form, {
    name: '', education: '', title_series: 'engineering', title_level: '',
    title_date: '', major_field: '', discipline: '', next_stage_apply: '', remark: ''
  })
}

function openCreate() {
  isEdit.value = false
  editId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row) {
  isEdit.value = true
  editId.value = row.id
  Object.assign(form, {
    name: row.name, education: row.education, title_series: row.title_series,
    title_level: row.title_level, title_date: row.title_date,
    major_field: row.major_field, discipline: row.discipline,
    next_stage_apply: row.next_stage_apply, remark: row.remark,
    title_name: row.title_name
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.name || !form.title_series || !form.title_level) {
    ElMessage.warning('请填写姓名、序列、职称类型')
    return
  }
  saving.value = true
  try {
    const payload = { ...form }
    if (isEdit.value) {
      await api.put(`/title/${editId.value}`, payload)
    } else {
      await api.post('/title', payload)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } catch (e) { /* 拦截器已提示 */ } finally {
    saving.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除 ${row.name} 的职称记录？`, '提示', { type: 'warning' })
  await api.delete(`/title/${row.id}`)
  ElMessage.success('删除成功')
  load()
}

// ===== 证书 =====
async function openCerts(row) {
  certTitleId.value = row.id
  certName.value = row.name
  certDialogVisible.value = true
  await loadCerts()
}

async function loadCerts() {
  certs.value = await api.get(`/title/certificates/${certTitleId.value}`)
}

async function uploadCert({ file }) {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('cert_type', '职称证书')
  await api.post(`/title/certificates/${certTitleId.value}`, fd)
  ElMessage.success('证书上传成功')
  loadCerts()
}

function previewCert(row) {
  window.open(row.url, '_blank')
}

async function delCert(row) {
  await ElMessageBox.confirm('确认删除该证书？', '提示', { type: 'warning' })
  await api.delete(`/title/certificates/${row.id}`)
  ElMessage.success('已删除')
  loadCerts()
}

// ===== 导出 =====
async function exportExcel() {
  const res = await api.get('/export/titles', { responseType: 'blob' })
  downloadBlob(res, '职称汇总表_导出.xlsx')
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(async () => {
  options.value = await api.get('/title/options')
  load()
})
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; flex-wrap: wrap; }
</style>
