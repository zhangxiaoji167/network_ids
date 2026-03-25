<template>
  <div>
    <!-- 顶部操作栏 -->
    <div class="toolbar">
      <el-select v-model="source" size="default" style="width:160px">
        <el-option label="NSL-KDD" value="nsl-kdd" />
        <el-option label="UNSW-NB15" value="unsw-nb15" />
      </el-select>
      <el-button type="primary" :loading="detecting" @click="handleRunDetection">
        <el-icon><VideoPlay /></el-icon> 运行检测
      </el-button>
      <el-select v-model="detectDataset" size="default" style="width:120px">
        <el-option label="测试集" value="test" />
        <el-option label="训练集" value="train" />
      </el-select>
      <el-input-number v-model="detectLimit" :min="0" :max="10000" :step="100" size="default"
        placeholder="记录数(0=全部)" style="width:150px" />
      <el-tag v-if="activeDataset" closable @close="resetToOverview" type="info" size="large" style="margin-left:8px">
        当前: {{ activeDataset }}
      </el-tag>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6" v-for="card in statCards" :key="card.label">
        <el-card shadow="never" class="stat-card">
          <div class="stat-icon" :style="{ background: card.color }">
            <el-icon size="22"><component :is="card.icon" /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ card.value }}</div>
            <div class="stat-label">{{ card.label }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :span="12">
        <el-card shadow="never" header="攻击类型分布">
          <AttackPieChart :dataset="activeDataset" ref="attackChart" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" header="协议类型分布">
          <ProtocolPieChart :dataset="activeDataset" ref="protocolChart" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 告警列表 -->
    <el-card shadow="never" header="最新告警" class="alert-card">
      <AlertList :source="source" :dataset="activeDataset" ref="alertList" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getDashboardStats, runDetection } from '../utils/api.js'
import AttackPieChart from '../components/AttackPieChart.vue'
import ProtocolPieChart from '../components/ProtocolPieChart.vue'
import AlertList from '../components/AlertList.vue'

const source = ref('nsl-kdd')
const detectDataset = ref('test')
const detectLimit = ref(0)
const detecting = ref(false)

// null = 全量总览，'nsl-test' / 'unsw-train' 等 = 按数据集过滤
const activeDataset = ref(null)

const stats = ref({ total_connections: 0, attack_connections: 0, detection_accuracy: null, alert_high: 0 })

const attackChart = ref(null)
const protocolChart = ref(null)
const alertList = ref(null)

const statCards = computed(() => [
  { label: '总连接数', value: stats.value.total_connections?.toLocaleString() ?? 0, icon: 'Connection', color: '#1677ff' },
  { label: '攻击连接', value: stats.value.attack_connections?.toLocaleString() ?? 0, icon: 'Warning', color: '#ff4d4f' },
  { label: '检测准确率', value: stats.value.detection_accuracy != null ? (stats.value.detection_accuracy * 100).toFixed(2) + '%' : '—', icon: 'CircleCheck', color: '#52c41a' },
  { label: '高危告警', value: stats.value.alert_high?.toLocaleString() ?? 0, icon: 'Bell', color: '#faad14' },
])

async function loadStats() {
  try {
    // 始终传入 source，保证统计基于该数据集的实际检测结果
    const params = { source: source.value }
    if (activeDataset.value) params.dataset = activeDataset.value
    stats.value = await getDashboardStats(params)
  } catch {}
}

// source 变化时刷新统计与图表
watch(source, () => {
  loadStats()
  attackChart.value?.reload()
  protocolChart.value?.reload()
  alertList.value?.reload()
})

async function handleRunDetection() {
  detecting.value = true
  try {
    const res = await runDetection(source.value, detectDataset.value, detectLimit.value)
    ElMessage.success(`检测完成：共 ${res.total_records} 条，准确率 ${(res.accuracy * 100).toFixed(2)}%`)
    // 切换为按数据集过滤显示
    const prefix = source.value === 'nsl-kdd' ? 'nsl' : 'unsw'
    activeDataset.value = `${prefix}-${detectDataset.value}`
    await loadStats()
    attackChart.value?.reload()
    protocolChart.value?.reload()
    alertList.value?.reload()
  } catch {
  } finally {
    detecting.value = false
  }
}

function resetToOverview() {
  activeDataset.value = null
  loadStats()
  attackChart.value?.reload()
  protocolChart.value?.reload()
  alertList.value?.reload()
}

onMounted(loadStats)
</script>

<style scoped>
.toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }
.stats-row { margin-bottom: 16px; }
.stat-card .el-card__body { display: flex; align-items: center; gap: 16px; padding: 20px; }
.stat-icon { width: 48px; height: 48px; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: #fff; flex-shrink: 0; }
.stat-value { font-size: 24px; font-weight: 700; color: #262626; line-height: 1.2; }
.stat-label { font-size: 13px; color: #8c8c8c; margin-top: 4px; }
.chart-row { margin-bottom: 16px; }
.alert-card {}
</style>
