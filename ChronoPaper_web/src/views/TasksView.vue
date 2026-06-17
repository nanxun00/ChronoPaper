<template>
  <div class="tasks-container layout-container">
    <HeaderComponent
      title="任务中心"
      description="统一管理所有后台异步任务：论文抓取、推送、LaTeX 编译、TimeRAG 时序分析等。"
    >
      <template #actions>
        <a-button type="primary" @click="openCreateModal">新建任务</a-button>
      </template>
    </HeaderComponent>

    <div class="tasks-body">
      <div class="stats-row">
        <a-card v-for="item in taskStats" :key="item.key" class="stat-card" :bordered="false">
          <div class="stat-value">{{ item.value }}</div>
          <div class="stat-label">{{ item.label }}</div>
        </a-card>
      </div>

      <a-tabs v-model:activeKey="activeTab" class="tasks-tabs">
        <a-tab-pane key="all" tab="全部任务" />
        <a-tab-pane key="crawl" tab="抓取任务" />
        <a-tab-pane key="push" tab="推送任务" />
        <a-tab-pane key="compile" tab="编译任务" />
        <a-tab-pane key="timerag" tab="时序分析" />
      </a-tabs>

      <a-table
        :columns="columns"
        :data-source="filteredTasks"
        :loading="loading"
        row-key="id"
        :pagination="{ pageSize: 10 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'type'">
            <a-tag :color="typeColor(record.type)">{{ typeLabel(record.type) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-badge :status="statusBadge(record.status)" :text="statusLabel(record.status)" />
          </template>
          <template v-else-if="column.key === 'progress'">
            <a-progress
              :percent="record.progress"
              :status="record.status === 'failed' ? 'exception' : record.status === 'done' ? 'success' : 'active'"
              size="small"
            />
          </template>
          <template v-else-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" @click="viewDetail(record)">详情</a-button>
              <a-button
                v-if="record.status === 'running' || record.status === 'waiting'"
                type="link"
                size="small"
                danger
                @click="cancelTask(record)"
              >
                取消
              </a-button>
              <a-button
                v-if="record.type === 'crawl' && record.status !== 'running'"
                type="link"
                size="small"
                @click="runNow(record)"
              >
                立即执行
              </a-button>
            </a-space>
          </template>
        </template>
        <template #emptyText>
          <a-empty description="暂无任务，点击右上角新建任务" />
        </template>
      </a-table>
    </div>

    <a-modal
      v-model:open="createOpen"
      title="新建任务"
      ok-text="创建"
      cancel-text="取消"
      @ok="handleCreate"
    >
      <a-form layout="vertical">
        <a-form-item label="任务类型" required>
          <a-select v-model:value="createForm.type" placeholder="选择任务类型">
            <a-select-option value="crawl">抓取任务</a-select-option>
            <a-select-option value="push">推送任务</a-select-option>
            <a-select-option value="compile" disabled>编译任务（即将支持）</a-select-option>
            <a-select-option value="timerag" disabled>时序分析（即将支持）</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item v-if="createForm.type === 'crawl'" label="arXiv 分类">
          <a-input v-model:value="createForm.categories" placeholder="如 cs.AI, cs.CL" />
        </a-form-item>
        <a-form-item v-if="createForm.type === 'crawl'" label="关键词">
          <a-input v-model:value="createForm.keywords" placeholder="可选" />
        </a-form-item>
        <a-form-item v-if="createForm.type === 'crawl'" label="定时执行">
          <a-time-picker v-model:value="createForm.schedule" format="HH:mm" style="width: 100%" />
        </a-form-item>
        <a-form-item v-if="createForm.type === 'push'" label="推送说明">
          <a-textarea v-model:value="createForm.note" :rows="3" placeholder="论文更新推送配置（开发中）" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-drawer v-model:open="detailOpen" title="任务详情" width="560" placement="right">
      <template v-if="detailItem">
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="任务 ID">{{ detailItem.id }}</a-descriptions-item>
          <a-descriptions-item label="类型">{{ typeLabel(detailItem.type) }}</a-descriptions-item>
          <a-descriptions-item label="状态">{{ statusLabel(detailItem.status) }}</a-descriptions-item>
          <a-descriptions-item label="进度">{{ detailItem.progress }}%</a-descriptions-item>
          <a-descriptions-item label="创建时间">{{ detailItem.created_at }}</a-descriptions-item>
          <a-descriptions-item label="最近执行">{{ detailItem.last_run || '—' }}</a-descriptions-item>
        </a-descriptions>
        <a-divider />
        <h4>执行日志</h4>
        <pre class="task-log">{{ detailItem.log || '暂无日志' }}</pre>
      </template>
    </a-drawer>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'
import HeaderComponent from '@/components/HeaderComponent.vue'

const activeTab = ref('all')
const loading = ref(false)
const createOpen = ref(false)
const detailOpen = ref(false)
const detailItem = ref(null)

const createForm = ref({
  type: 'crawl',
  categories: '',
  keywords: '',
  schedule: null,
  note: '',
})

const tasks = ref([])

const taskStats = computed(() => [
  { key: 'total', label: '全部任务', value: tasks.value.length },
  { key: 'running', label: '运行中', value: tasks.value.filter((t) => t.status === 'running').length },
  { key: 'done', label: '已完成', value: tasks.value.filter((t) => t.status === 'done').length },
  { key: 'failed', label: '失败', value: tasks.value.filter((t) => t.status === 'failed').length },
])

const filteredTasks = computed(() => {
  if (activeTab.value === 'all') return tasks.value
  return tasks.value.filter((t) => t.type === activeTab.value)
})

const columns = [
  { title: '任务名称', dataIndex: 'name', ellipsis: true },
  { title: '类型', key: 'type', width: 110 },
  { title: '状态', key: 'status', width: 110 },
  { title: '进度', key: 'progress', width: 160 },
  { title: '创建时间', dataIndex: 'created_at', width: 170 },
  { title: '操作', key: 'action', width: 200 },
]

const typeLabel = (type) => {
  const map = { crawl: '抓取', push: '推送', compile: '编译', timerag: '时序分析' }
  return map[type] || type
}

const typeColor = (type) => {
  const map = { crawl: 'blue', push: 'green', compile: 'purple', timerag: 'orange' }
  return map[type] || 'default'
}

const statusLabel = (status) => {
  const map = {
    waiting: '等待中',
    running: '运行中',
    done: '已完成',
    failed: '失败',
    cancelled: '已取消',
  }
  return map[status] || status
}

const statusBadge = (status) => {
  const map = {
    waiting: 'default',
    running: 'processing',
    done: 'success',
    failed: 'error',
    cancelled: 'warning',
  }
  return map[status] || 'default'
}

const openCreateModal = () => {
  createOpen.value = true
}

const handleCreate = () => {
  createOpen.value = false
  message.info('任务创建接口开发中，将在后端异步任务模块接入后启用')
}

const viewDetail = (record) => {
  detailItem.value = record
  detailOpen.value = true
}

const cancelTask = (record) => {
  record.status = 'cancelled'
  message.success('任务已取消')
}

const runNow = (record) => {
  record.status = 'running'
  record.progress = 10
  message.success('已触发立即执行')
}
</script>

<style scoped lang="less">
.tasks-container {
  padding: 0;
}

.tasks-body {
  padding: 0 24px 24px;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.stat-card {
  background: #fff;
  border: 1px solid var(--gray-300);
  border-radius: 8px;

  .stat-value {
    font-size: 28px;
    font-weight: 600;
    color: var(--main-600);
  }

  .stat-label {
    margin-top: 4px;
    color: var(--gray-700);
    font-size: 13px;
  }
}

.tasks-tabs {
  margin-bottom: 16px;
}

.task-log {
  background: var(--gray-100);
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  max-height: 320px;
  overflow: auto;
}

@media (max-width: 900px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
