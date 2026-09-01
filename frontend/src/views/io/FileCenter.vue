<template>
  <div class="files">
    <el-card shadow="never">
      <div class="toolbar">
        <el-select v-model="filterType" clearable placeholder="按类型筛选" style="width:180px" @change="load">
          <el-option label="全部" value="" />
          <el-option label="职称证书" value="title_certificate" />
          <el-option label="政策文档" value="subsidy_policy" />
          <el-option label="发放凭证" value="subsidy_voucher" />
          <el-option label="AI 对话附件" value="ai_chat" />
          <el-option label="其他文档" value="other" />
        </el-select>
        <el-input v-model="kw" placeholder="搜索文件名" clearable style="width:220px" @keyup.enter="load" @clear="load" />
        <el-button type="primary" @click="load"><el-icon><Search /></el-icon> 查询</el-button>
        <div class="spacer" />
        <el-button type="success" @click="openUpload"><el-icon><UploadFilled /></el-icon> 上传文档</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" border stripe>
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="name" label="文件名" min-width="260" show-overflow-tooltip />
        <el-table-column label="类型" width="120">
          <template #default="{ row }"><el-tag size="small">{{ row.business_label }}</el-tag></template>
        </el-table-column>
        <el-table-column label="大小" width="110">
          <template #default="{ row }">{{ fmtSize(row.size) }}</template>
        </el-table-column>
        <el-table-column prop="uploaded_at" label="上传时间" width="160" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="download(row)">下载</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 上传文档 -->
    <el-dialog v-model="uploadVisible" title="上传文档到文件中心" width="480px">
      <el-form label-width="90px">
        <el-form-item label="文档分类">
          <el-select v-model="uploadForm.business_type" style="width:100%">
            <el-option label="政策文档" value="subsidy_policy" />
            <el-option label="职称证书" value="title_certificate" />
            <el-option label="发放凭证" value="subsidy_voucher" />
            <el-option label="其他文档" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="选择文件">
          <el-upload
            drag
            :auto-upload="false"
            :limit="1"
            accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.png,.jpg,.jpeg"
            :on-change="onChange"
            :on-remove="onRemove"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div>将文件拖到此处，或点击选择（支持 PDF/Word/Excel/PPT/图片）</div>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!uploadFileObj" :loading="uploading" @click="submitUpload">上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api, { slowApi } from '../../api'

const rows = ref([])
const loading = ref(false)
const filterType = ref('')
const kw = ref('')

const uploadVisible = ref(false)
const uploading = ref(false)
const uploadFileObj = ref(null)
const uploadForm = ref({ business_type: 'subsidy_policy' })

async function load() {
  loading.value = true
  try {
    const params = {}
    if (filterType.value) params.business_type = filterType.value
    if (kw.value) params.keyword = kw.value
    rows.value = await api.get('/files', { params })
  } finally { loading.value = false }
}

async function download(row) {
  try {
    const resp = await api.get(`/files/download/${row.id}`, { responseType: 'blob' })
    const blob = resp instanceof Blob ? resp : resp.data
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = row.name
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {}
}

function openUpload() {
  uploadFileObj.value = null
  uploadForm.value = { business_type: 'subsidy_policy' }
  uploadVisible.value = true
}
function onChange(file) { uploadFileObj.value = file.raw; return false }
function onRemove() { uploadFileObj.value = null }

async function submitUpload() {
  if (!uploadFileObj.value) return
  uploading.value = true
  const fd = new FormData()
  fd.append('file', uploadFileObj.value)
  fd.append('business_type', uploadForm.value.business_type)
  try {
    await slowApi.post('/files/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    ElMessage.success('上传成功')
    uploadVisible.value = false
    await load()
  } finally { uploading.value = false }
}

function fmtSize(n) {
  if (!n) return '-'
  if (n < 1024) return n + ' B'
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB'
  return (n / 1024 / 1024).toFixed(2) + ' MB'
}

onMounted(load)
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; }
.spacer { flex: 1; }
</style>
