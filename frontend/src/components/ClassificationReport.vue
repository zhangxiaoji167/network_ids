<template>
  <v-chart :option="option" style="height:360px" autoresize />
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getModelMetrics } from '../utils/api.js'

use([BarChart, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

const props = defineProps({ source: { type: String, default: 'nsl-kdd' } })
const option = ref({})

async function load() {
  try {
    const m = await getModelMetrics(props.source)
    const report = m.classification_report || {}
    // 过滤掉聚合行，只保留各攻击类别
    const skipKeys = new Set(['accuracy', 'macro avg', 'weighted avg'])
    const categories = []
    const precisionData = []
    const recallData = []
    const f1Data = []

    for (const [label, metrics] of Object.entries(report)) {
      if (skipKeys.has(label)) continue
      categories.push(label)
      precisionData.push(+(metrics.precision * 100).toFixed(2))
      recallData.push(+(metrics.recall * 100).toFixed(2))
      f1Data.push(+(metrics['f1-score'] * 100).toFixed(2))
    }

    option.value = {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params) =>
          params[0].name + '<br>' +
          params.map((p) => `${p.marker}${p.seriesName}: ${p.value}%`).join('<br>'),
      },
      legend: { data: ['Precision', 'Recall', 'F1-Score'], bottom: 0 },
      grid: { left: 80, right: 20, top: 10, bottom: 40 },
      yAxis: {
        type: 'category',
        data: categories,
        axisLabel: { fontSize: 11 },
      },
      xAxis: {
        type: 'value',
        max: 100,
        axisLabel: { formatter: '{value}%' },
      },
      series: [
        { name: 'Precision', type: 'bar', data: precisionData, itemStyle: { color: '#1677ff' } },
        { name: 'Recall', type: 'bar', data: recallData, itemStyle: { color: '#52c41a' } },
        { name: 'F1-Score', type: 'bar', data: f1Data, itemStyle: { color: '#faad14' } },
      ],
    }
  } catch {}
}

function reload() { load() }
defineExpose({ reload })
watch(() => props.source, load)
onMounted(load)
</script>
