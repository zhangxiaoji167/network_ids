<template>
  <v-chart :option="option" style="height:320px" autoresize />
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getRocData } from '../utils/api.js'

use([LineChart, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

const props = defineProps({ source: { type: String, default: 'nsl-kdd' } })
const option = ref({})

async function load() {
  try {
    const data = await getRocData(props.source)
    const series = []
    // data 结构: { ClassName: { fpr: [...], tpr: [...], auc: 0.xx }, ... }
    for (const [cls, val] of Object.entries(data)) {
      if (!val.fpr) continue
      const points = val.fpr.map((x, i) => [x, val.tpr[i]])
      series.push({
        name: `${cls} (AUC=${val.auc?.toFixed(3) ?? '?'})`,
        type: 'line',
        data: points,
        showSymbol: false,
        smooth: false,
        lineStyle: { width: 1.5 },
      })
    }
    // 对角线
    series.push({ name: 'Random', type: 'line', data: [[0,0],[1,1]], showSymbol: false, lineStyle: { type: 'dashed', color: '#ccc', width: 1 }, tooltip: { show: false } })

    option.value = {
      tooltip: { trigger: 'axis', formatter: (params) => params.map(p => `${p.seriesName}: (${p.data[0].toFixed(3)}, ${p.data[1].toFixed(3)})`).join('<br>') },
      legend: { type: 'scroll', bottom: 0, textStyle: { fontSize: 11 } },
      grid: { left: 50, right: 20, top: 10, bottom: 60 },
      xAxis: { type: 'value', name: 'FPR', min: 0, max: 1 },
      yAxis: { type: 'value', name: 'TPR', min: 0, max: 1 },
      series,
    }
  } catch {}
}

function reload() { load() }
defineExpose({ reload })
watch(() => props.source, load)
onMounted(load)
</script>
