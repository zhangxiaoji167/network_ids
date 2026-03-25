<template>
  <div v-loading="loading" style="padding:16px">
    <div v-if="detail">
      <el-descriptions title="连接特征" :column="4" border size="small" style="margin-bottom:16px">
        <el-descriptions-item
          v-for="(val, key) in featureFields"
          :key="key"
          :label="key"
        >{{ val ?? '—' }}</el-descriptions-item>
      </el-descriptions>

      <template v-if="detail.detection">
        <el-descriptions title="检测结果" :column="3" border size="small">
          <el-descriptions-item label="最终判断">
            <el-tag :type="detail.detection.final_verdict === 'Normal' ? 'success' : 'danger'" size="small">
              {{ detail.detection.final_verdict }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="检测来源">{{ detail.detection.final_source }}</el-descriptions-item>
          <el-descriptions-item label="结果正确">
            <el-tag :type="detail.detection.is_correct ? 'success' : 'danger'" size="small">
              {{ detail.detection.is_correct ? '是' : '否' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="ML预测">{{ detail.detection.ml_predicted ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="ML置信度">
            {{ detail.detection.ml_confidence ? (detail.detection.ml_confidence * 100).toFixed(2) + '%' : '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="实际标签">{{ detail.detection.actual_label }}</el-descriptions-item>
        </el-descriptions>
      </template>
      <el-empty v-else description="该连接暂无检测结果" :image-size="60" />
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { getConnectionDetail } from '../utils/api.js'

const props = defineProps({ connId: { type: Number, required: true } })
const loading = ref(false)
const detail = ref(null)

// 过滤掉元数据字段，只展示特征
const META_FIELDS = new Set(['id', 'dataset', 'attack_category', 'label', 'detection'])
const featureFields = computed(() => {
  if (!detail.value) return {}
  return Object.fromEntries(
    Object.entries(detail.value).filter(([k]) => !META_FIELDS.has(k))
  )
})

async function load() {
  loading.value = true
  try {
    detail.value = await getConnectionDetail(props.connId)
  } catch {
  } finally {
    loading.value = false
  }
}

watch(() => props.connId, load, { immediate: true })
</script>
