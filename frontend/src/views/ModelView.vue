<template>
  <div>
    <div class="toolbar">
      <el-select v-model="source" size="default" style="width:160px" @change="loadAll">
        <el-option label="NSL-KDD" value="nsl-kdd" />
        <el-option label="UNSW-NB15" value="unsw-nb15" />
      </el-select>
    </div>

    <!-- 指标卡片 -->
    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="8">
        <el-card shadow="never">
          <el-statistic title="验证集准确率" :value="valAcc" suffix="%" :precision="2" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never">
          <el-statistic title="外部测试集准确率" :value="extAcc" suffix="%" :precision="2" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never">
          <el-statistic title="训练耗时" :value="trainTime" suffix=" 秒" :precision="1" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 混淆矩阵 + 特征重要性 -->
    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="12">
        <el-card shadow="never" header="混淆矩阵">
          <ConfusionMatrix :source="source" ref="cmRef" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" header="特征重要性 Top 15">
          <FeatureImportance :source="source" ref="fiRef" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 分类报告 -->
    <el-card shadow="never" header="各类别 Precision / Recall / F1-Score" style="margin-bottom:16px">
      <ClassificationReport :source="source" ref="crRef" />
    </el-card>

    <!-- ROC + 检测方式对比 -->
    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="12">
        <el-card shadow="never" header="ROC 曲线">
          <RocCurve :source="source" ref="rocRef" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" header="检测方式对比">
          <MethodComparison :source="source" ref="mcRef" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 检测方式分布饼图 -->
    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="never" header="检测方式分布">
          <MethodPieChart :source="source" ref="mpRef" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getModelMetrics } from '../utils/api.js'
import ConfusionMatrix from '../components/ConfusionMatrix.vue'
import FeatureImportance from '../components/FeatureImportance.vue'
import ClassificationReport from '../components/ClassificationReport.vue'
import RocCurve from '../components/RocCurve.vue'
import MethodComparison from '../components/MethodComparison.vue'
import MethodPieChart from '../components/MethodPieChart.vue'

const source = ref('nsl-kdd')
const valAcc = ref(0)
const extAcc = ref(0)
const trainTime = ref(0)

const cmRef = ref(null)
const fiRef = ref(null)
const crRef = ref(null)
const rocRef = ref(null)
const mcRef = ref(null)
const mpRef = ref(null)

async function loadMetrics() {
  try {
    const m = await getModelMetrics(source.value)
    valAcc.value = ((m.accuracy ?? 0) * 100)
    extAcc.value = ((m.external_test_accuracy ?? 0) * 100)
    trainTime.value = m.train_time_seconds ?? 0
  } catch {}
}

async function loadAll() {
  await loadMetrics()
  cmRef.value?.reload()
  fiRef.value?.reload()
  crRef.value?.reload()
  rocRef.value?.reload()
  mcRef.value?.reload()
  mpRef.value?.reload()
}

onMounted(loadAll)
</script>

<style scoped>
.toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
</style>
