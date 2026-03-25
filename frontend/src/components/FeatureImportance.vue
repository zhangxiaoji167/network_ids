<template>
  <v-chart :option="option" style="height:320px" autoresize />
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { TooltipComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getFeatureImportance } from '../utils/api.js'

use([BarChart, TooltipComponent, GridComponent, CanvasRenderer])

const props = defineProps({ source: { type: String, default: 'nsl-kdd' } })
const option = ref({})

async function load() {
  try {
    const data = await getFeatureImportance(props.source)
    const top15 = data.slice(0, 15).reverse()
    option.value = {
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: 120, right: 20, top: 10, bottom: 20 },
      xAxis: { type: 'value' },
      yAxis: { type: 'category', data: top15.map((d) => d.feature), axisLabel: { fontSize: 11 } },
      series: [{
        type: 'bar',
        data: top15.map((d) => d.importance),
        itemStyle: { color: '#1677ff' },
        label: { show: true, position: 'right', formatter: (p) => p.value.toFixed(4), fontSize: 10 },
      }],
    }
  } catch {}
}

function reload() { load() }
defineExpose({ reload })
watch(() => props.source, load)
onMounted(load)
</script>
