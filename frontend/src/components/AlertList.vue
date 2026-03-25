<template>
  <el-table :data="alerts" v-loading="loading" stripe border style="width:100%" max-height="320">
    <el-table-column prop="alert_id" label="告警ID" width="220" show-overflow-tooltip />
    <el-table-column prop="severity" label="级别" width="90">
      <template #default="{ row }">
        <el-tag :type="severityType(row.severity)" size="small">{{ row.severity }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="attack_category" label="攻击类别" width="120" />
    <el-table-column prop="source" label="检测来源" width="90" />
    <el-table-column prop="description" label="描述" show-overflow-tooltip />
    <el-table-column prop="is_read" label="状态" width="80">
      <template #default="{ row }">
        <el-tag :type="row.is_read ? 'info' : 'warning'" size="small">
          {{ row.is_read ? '已读' : '未读' }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="80">
      <template #default="{ row }">
        <el-button v-if="!row.is_read" link type="primary" size="small" @click="markRead(row)">已读</el-button>
      </template>
    </el-table-column>
  </el-table>
  <el-pagination
    v-model:current-page="page"
    :page-size="size"
    :total="total"
    layout="total, prev, pager, next"
    style="margin-top:12px;justify-content:flex-end;display:flex"
    @current-change="load"
  />
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { getAlerts, markAlertRead } from '../utils/api.js'
import { ElMessage } from 'element-plus'

const props = defineProps({ source: { type: String, default: null }, dataset: { type: String, default: null } })

const alerts = ref([])
const loading = ref(false)
const page = ref(1)
const size = 10
const total = ref(0)

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, size }
    if (props.source) params.source = props.source
    if (props.dataset) params.dataset = props.dataset
    const res = await getAlerts(params)
    alerts.value = res.items
    total.value = res.total
  } catch {
  } finally {
    loading.value = false
  }
}

async function markRead(row) {
  try {
    await markAlertRead(row.alert_id)
    row.is_read = 1
    ElMessage.success('已标记为已读')
  } catch {}
}

function severityType(s) {
  return { CRITICAL: 'danger', HIGH: 'warning', MEDIUM: '', LOW: 'info' }[s] ?? ''
}

function reload() { page.value = 1; load() }
defineExpose({ reload })
watch(() => [props.source, props.dataset], () => {
  page.value = 1
  load()
})
onMounted(load)
</script>
