<template>
  <div class="pie-panel">
    <v-chart :option="option" class="pie-chart" autoresize />
    <div class="legend-panel">
      <div class="legend-grid">
        <div v-for="item in legendItems" :key="item.name" class="legend-item">
          <span class="legend-dot" :style="{ backgroundColor: item.color }"></span>
          <span>{{ item.name }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getProtocolDistribution } from '../utils/api.js'

use([PieChart, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps({ dataset: { type: String, default: null } })

const option = ref({})
const legendItems = ref([])
const COLORS = ['#1677ff', '#52c41a', '#faad14', '#ff4d4f', '#722ed1', '#13c2c2', '#eb2f96', '#2f54eb']

async function load() {
  try {
    const data = await getProtocolDistribution(props.dataset)
    const items = Array.isArray(data)
      ? data.map(d => ({ name: d.name, value: d.count }))
      : Object.entries(data).map(([name, value]) => ({ name, value }))

    legendItems.value = items.map((item, index) => ({
      ...item,
      color: COLORS[index % COLORS.length],
    }))

    option.value = {
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      legend: { show: false },
      color: COLORS,
      series: [{
        type: 'pie',
        radius: ['42%', '70%'],
        center: ['50%', '52%'],
        data: items,
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
      }],
    }
  } catch {}
}

function reload() { load() }
defineExpose({ reload })

watch(() => props.dataset, load)
onMounted(load)
</script>

<style scoped>
.pie-panel {
  min-height: 420px;
  display: flex;
  flex-direction: column;
}

.pie-chart {
  height: 260px;
}

.legend-panel {
  min-height: 140px;
  padding: 10px 8px 0;
}

.legend-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  align-content: flex-start;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  color: #595959;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
  flex-shrink: 0;
}
</style>
