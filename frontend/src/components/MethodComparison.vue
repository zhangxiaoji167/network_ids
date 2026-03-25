<template>
  <div v-if="!data" class="empty-tip">暂无检测结果，请先运行检测</div>
  <div v-else>
    <el-descriptions :column="2" border size="small" style="margin-bottom:16px">
      <el-descriptions-item label="总检测数">{{ data.total?.toLocaleString() }}</el-descriptions-item>
      <el-descriptions-item label="综合准确率">{{ (data.overall_accuracy * 100).toFixed(2) }}%</el-descriptions-item>
    </el-descriptions>
    <el-table :data="sourceRows" border stripe size="small" style="width:100%">
      <el-table-column prop="source" label="检测来源" />
      <el-table-column prop="count" label="数量" />
      <el-table-column prop="correct" label="正确" />
      <el-table-column prop="accuracy" label="准确率">
        <template #default="{ row }">{{ (row.accuracy * 100).toFixed(2) }}%</template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { getMethodComparisonByDataset } from '../utils/api.js'

const props = defineProps({ source: { type: String, default: null }, dataset: { type: String, default: null } })

const data = ref(null)
const sourceRows = ref([])

async function load() {
  try {
    const params = {}
    if (props.source) params.source = props.source
    if (props.dataset) params.dataset = props.dataset
    const res = await getMethodComparisonByDataset(params)
    if (res.message) { data.value = null; return }
    data.value = res
    sourceRows.value = Object.entries(res.by_source || {}).map(([source, v]) => ({ source, ...v }))
  } catch {}
}

function reload() { load() }
defineExpose({ reload })
watch(() => [props.source, props.dataset], load)
onMounted(load)
</script>

<style scoped>
.empty-tip { color: #8c8c8c; text-align: center; padding: 60px 0; font-size: 14px; }
</style>
