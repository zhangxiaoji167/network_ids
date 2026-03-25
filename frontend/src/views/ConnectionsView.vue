<template>
  <div>
    <!-- 过滤器 -->
    <el-card shadow="never" style="margin-bottom:16px">
      <el-form :model="filters" inline>
        <el-form-item label="数据集">
          <el-select v-model="filters.dataset" clearable placeholder="全部" style="width:140px">
            <el-option label="NSL-KDD 测试集" value="nsl-test" />
            <el-option label="NSL-KDD 训练集" value="nsl-train" />
            <el-option label="UNSW 测试集" value="unsw-test" />
            <el-option label="UNSW 训练集" value="unsw-train" />
          </el-select>
        </el-form-item>
        <el-form-item label="攻击类别">
          <el-input v-model="filters.attack_category" clearable placeholder="如 DoS" style="width:140px" />
        </el-form-item>
        <el-form-item label="协议">
          <el-input v-model="filters.protocol_type" clearable placeholder="如 tcp" style="width:100px" />
        </el-form-item>
        <el-form-item label="服务">
          <el-input v-model="filters.service" clearable placeholder="如 http" style="width:100px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 数据表格 -->
    <el-card shadow="never">
      <el-table :data="tableData" v-loading="loading" stripe border style="width:100%"
        row-key="id">
        <el-table-column type="expand">
          <template #default="{ row }">
            <ConnectionDetail :conn-id="row.id" />
          </template>
        </el-table-column>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="dataset" label="数据集" width="120" />
        <el-table-column prop="protocol_type" label="协议" width="80" />
        <el-table-column prop="service" label="服务" width="100" />
        <el-table-column prop="attack_category" label="攻击类别" width="120">
          <template #default="{ row }">
            <el-tag :type="row.attack_category === 'Normal' ? 'success' : 'danger'" size="small">
              {{ row.attack_category }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="label" label="标签" width="120" show-overflow-tooltip />
        <el-table-column label="src_bytes" width="100">
          <template #default="{ row }">{{ row.src_bytes ?? row.sbytes ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="dst_bytes" width="100">
          <template #default="{ row }">{{ row.dst_bytes ?? row.dbytes ?? '—' }}</template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="size"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        style="margin-top:16px;justify-content:flex-end;display:flex"
        @size-change="loadData"
        @current-change="loadData"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getConnections } from '../utils/api.js'
import ConnectionDetail from '../components/ConnectionDetail.vue'

const filters = reactive({ dataset: '', attack_category: '', protocol_type: '', service: '' })
const page = ref(1)
const size = ref(20)
const total = ref(0)
const tableData = ref([])
const loading = ref(false)

async function loadData() {
  loading.value = true
  try {
    const params = { page: page.value, size: size.value }
    if (filters.dataset) params.dataset = filters.dataset
    if (filters.attack_category) params.attack_category = filters.attack_category
    if (filters.protocol_type) params.protocol_type = filters.protocol_type
    if (filters.service) params.service = filters.service
    const res = await getConnections(params)
    tableData.value = res.items
    total.value = res.total
  } catch {
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadData()
}

function handleReset() {
  Object.assign(filters, { dataset: '', attack_category: '', protocol_type: '', service: '' })
  page.value = 1
  loadData()
}

onMounted(loadData)
</script>
