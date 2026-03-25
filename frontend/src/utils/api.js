import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// 运行检测用独立 axios 实例，超时延长到 10 分钟（大数据集全量检测耗时较长）
const apiLong = axios.create({
  baseURL: '/api',
  timeout: 600000,
})
apiLong.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const msg = err.response?.data?.detail || err.message || '请求失败'
    ElMessage.error(msg)
    return Promise.reject(err)
  }
)

api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const msg = err.response?.data?.detail || err.message || '请求失败'
    ElMessage.error(msg)
    return Promise.reject(err)
  }
)

// 仪表盘
export const getDashboardStats = (params = {}) =>
  api.get('/dashboard/stats', { params })

// 检测
export const runDetection = (source = 'nsl-kdd', dataset = 'test', limit = 0) =>
  apiLong.post('/detection/run', null, { params: { source, dataset, limit } })

export const getDetectionResults = (params) => api.get('/detection/results', { params })

export const getAlerts = (params) => api.get('/alerts', { params })

export const markAlertRead = (alertId) => api.put(`/alerts/${alertId}/read`)

// 连接记录
export const getConnections = (params) => api.get('/connections', { params })

export const getConnectionDetail = (id) => api.get(`/connections/${id}`)

// 模型
export const getModelMetrics = (source = 'nsl-kdd') =>
  api.get('/model/metrics', { params: { source } })

export const getFeatureImportance = (source = 'nsl-kdd') =>
  api.get('/model/feature-importance', { params: { source } })

export const getConfusionMatrix = (source = 'nsl-kdd') =>
  api.get('/model/confusion-matrix', { params: { source } })

export const getRocData = (source = 'nsl-kdd') =>
  api.get('/model/roc-data', { params: { source } })

export const getMethodComparison = () => api.get('/model/comparison')
export const getMethodComparisonByDataset = (params = {}) =>
  api.get('/model/comparison', { params })

// 分析（dataset 传 null/undefined 时后端返回全量）
export const getProtocolDistribution = (dataset = null) =>
  api.get('/analysis/protocol-distribution', { params: dataset ? { dataset } : {} })

export const getAttackDistribution = (dataset = null) =>
  api.get('/analysis/attack-distribution', { params: dataset ? { dataset } : {} })

// 系统
export const getDatasetInfo = () => api.get('/system/dataset-info')

export const triggerTraining = (source = 'nsl-kdd') =>
  api.post('/system/train', null, { params: { source } })

export const loadDataset = (source = 'nsl-kdd', dataset = 'test') =>
  api.post('/system/load-data', null, { params: { source, dataset } })
