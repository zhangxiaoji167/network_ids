<template>
  <v-chart :option="option" style="height:320px" autoresize />
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { HeatmapChart } from 'echarts/charts'
import { TooltipComponent, GridComponent, VisualMapComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getConfusionMatrix } from '../utils/api.js'

use([HeatmapChart, TooltipComponent, GridComponent, VisualMapComponent, CanvasRenderer])

const props = defineProps({ source: { type: String, default: 'nsl-kdd' } })
const option = ref({})

async function load() {
  try {
    const data = await getConfusionMatrix(props.source)
    const cats = data.categories || []
    const matrix = data.matrix || []
    const heatData = []
    let maxVal = 0
    matrix.forEach((row, i) => {
      row.forEach((v, j) => {
        heatData.push([j, i, v])
        if (v > maxVal) maxVal = v
      })
    })
    option.value = {
      tooltip: { formatter: (p) => `实际: ${cats[p.data[1]]}<br>预测: ${cats[p.data[0]]}<br>数量: ${p.data[2]}` },
      grid: { left: 100, right: 20, top: 20, bottom: 80 },
      xAxis: { type: 'category', data: cats, name: '预测', axisLabel: { rotate: 30, fontSize: 11 } },
      yAxis: { type: 'category', data: cats, name: '实际', axisLabel: { fontSize: 11 } },
      visualMap: { min: 0, max: maxVal, calculable: true, orient: 'horizontal', left: 'center', bottom: 0 },
      series: [{ type: 'heatmap', data: heatData, label: { show: cats.length <= 6, formatter: (p) => p.data[2] } }],
    }
  } catch {}
}

function reload() { load() }
defineExpose({ reload })
watch(() => props.source, load)
onMounted(load)
</script>
