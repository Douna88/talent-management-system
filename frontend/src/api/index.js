import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000
})

/**
 * AI 专用实例：本地 27B 模型复杂问题可能要 20~60 秒，
 * 用默认的 30s 超时会被前端误判成"网络错误"（这正是之前 AI 答不上问题的根因）。
 */
export const aiApi = axios.create({
  baseURL: '/api',
  timeout: 300000 // 5 分钟
})

/**
 * 慢操作实例：汇报导出（PPT/PDF 生成 + 数据聚合）、Excel 导入（Python 解析）耗时较长，
 * 用独立 5 分钟超时，避免被前端误判为网络错误。
 */
export const slowApi = axios.create({
  baseURL: '/api',
  timeout: 300000 // 5 分钟
})

function attachAuth(instance) {
  instance.interceptors.request.use(config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  })

  instance.interceptors.response.use(
    response => response.data,
    error => {
      if (error.response) {
        if (error.response.status === 401) {
          localStorage.removeItem('token')
          localStorage.removeItem('user')
          window.location.href = '/login'
          return Promise.reject(error)
        }
        const msg = error.response.data?.detail || error.response.data?.message || '请求失败'
        ElMessage.error(msg)
      } else if (error.code === 'ECONNABORTED') {
        ElMessage.error('模型响应超时，请换个简单点的问法再试')
      } else {
        ElMessage.error('网络错误')
      }
      return Promise.reject(error)
    }
  )
}

attachAuth(api)
attachAuth(aiApi)
attachAuth(slowApi)

/**
 * 下载二进制文件并触发浏览器保存（用于 Excel/PDF/PPT/HTML 导出）。
 */
export async function downloadBlob(url, filename, instance = slowApi) {
  const resp = await instance.get(url, { responseType: 'blob' })
  const blob = resp instanceof Blob ? resp : resp.data
  const urlObj = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = urlObj
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(urlObj)
}

export default api
