<template>
  <v-chart :option="option" style="height:280px" autoresize />
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getMethodComparisonByDataset } from '../utils/api.js'

const props = defineProps({ source: { type: String, default: null }, dataset: { type: String, default: null } })

use([PieChart, TooltipComponent, LegendComponent, CanvasRenderer])

const option = ref({})

async function load() {
  try {
    const params = {}
    if (props.source) params.source = props.source
    if (props.dataset) params.dataset = props.dataset
    const data = await getMethodComparisonByDataset(params)
    if (data.message) {
      option.value = { title: { text: data.message, left: 'center', top: 'center', textStyle: { fontSize: 14, color: '#8c8c8c' } } }
      return
    }
    const bySource = data.by_source || {}
    const items = Object.entries(bySource).map(([name, v]) => ({ name, value: v.count }))
    option.value = {
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      legend: { orient: 'vertical', right: 10, top: 'center', textStyle: { fontSize: 12 } },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['40%', '50%'],
        data: items,
        label: { show: false },
      }],
    }
  } catch {}
}

function reload() { load() }
defineExpose({ reload })
watch(() => [props.source, props.dataset], load)
onMounted(load)
</script>
