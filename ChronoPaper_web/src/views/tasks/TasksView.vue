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
          <template v-else-if="column.key === 'visibility'">
            <a-tag :color="record.visibility === 'public' ? 'green' : 'orange'">
              {{ record.visibility_label }}
            </a-tag>
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
                v-if="canCancelTask(record)"
                type="link"
                size="small"
                danger
                @click="cancelTask(record)"
              >
                取消
              </a-button>
              <a-button
                v-if="record.type === 'crawl' && canRunCrawl(record)"
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
      title="新建抓取任务"
      ok-text="创建"
      cancel-text="取消"
      :confirm-loading="creating"
      :width="720"
      @ok="handleCreate"
    >
      <a-form layout="vertical">
        <a-form-item label="智能规划">
          <a-switch
            v-model:checked="createForm.enable_smart_planning"
            checked-children="开启"
            un-checked-children="关闭"
          />
          <span class="field-hint">开启后由大模型从 arXiv / OpenReview / OpenAlex 中自动选择数据源并规划参数</span>
        </a-form-item>
        <a-form-item label="任务名称" required>
          <a-input v-model:value="createForm.name" placeholder="例如：多模态医疗影像每日抓取" />
        </a-form-item>
        <a-form-item :label="createForm.enable_smart_planning ? '研究领域描述' : '研究兴趣描述'" required>
          <a-textarea
            v-model:value="createForm.intent_text"
            :rows="4"
            :placeholder="
              createForm.enable_smart_planning
                ? '用自然语言描述你想跟踪的研究领域，例如：大模型 Agent 的长期记忆与检索增强'
                : '用一段话描述你希望抓取的文章领域、方向与细节，例如：关注多模态大模型在医疗影像诊断中的应用'
            "
            @blur="!createForm.enable_smart_planning && refreshCrawlTranslationPreview()"
          />
        </a-form-item>
        <template v-if="!createForm.enable_smart_planning">
        <a-alert
          v-if="crawlTranslatePreview.translated"
          type="info"
          show-icon
          class="translate-preview-alert"
          message="已检测到中文，执行时将使用以下英文进行匹配"
        >
          <template #description>
            <p v-if="crawlTranslatePreview.intent_text">
              <strong>兴趣译文：</strong>{{ crawlTranslatePreview.intent_text }}
            </p>
            <p v-if="crawlTranslatePreview.keywords">
              <strong>关键词译文：</strong>{{ crawlTranslatePreview.keywords }}
            </p>
          </template>
        </a-alert>
        <a-form-item label="抓取数据源" required>
          <a-checkbox-group v-model:value="createForm.sources" style="width: 100%">
            <a-row :gutter="[8, 8]">
              <a-col v-for="opt in CRAWL_SOURCE_OPTIONS" :key="opt.value" :span="24">
                <a-checkbox :value="opt.value">
                  <span>{{ opt.label }}</span>
                  <span class="source-hint"> — {{ opt.description }}</span>
                </a-checkbox>
              </a-col>
            </a-row>
          </a-checkbox-group>
        </a-form-item>
        <a-form-item v-if="createForm.sources.includes('arxiv')" label="arXiv 分类" required>
          <a-select
            v-model:value="createForm.categories"
            mode="multiple"
            placeholder="请选择 arXiv 分类（可多选）"
            style="width: 100%"
            show-search
            :filter-option="filterArxivCategory"
            :max-tag-count="4"
          >
            <a-select-opt-group
              v-for="group in ARXIV_CATEGORY_GROUPS"
              :key="group.label"
              :label="group.label"
            >
              <a-select-option
                v-for="opt in group.options"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </a-select-option>
            </a-select-opt-group>
          </a-select>
        </a-form-item>
        <a-form-item v-if="createForm.sources.includes('openreview')" label="OpenReview 会议" required>
          <a-select
            v-model:value="createForm.openreview_venues"
            mode="multiple"
            placeholder="请选择会议（可多选）"
            style="width: 100%"
            show-search
            :filter-option="filterOpenReviewVenue"
            :max-tag-count="3"
          >
            <a-select-opt-group
              v-for="group in OPENREVIEW_VENUE_GROUPS"
              :key="group.label"
              :label="group.label"
            >
              <a-select-option
                v-for="opt in group.options"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </a-select-option>
            </a-select-opt-group>
          </a-select>
        </a-form-item>
        <a-form-item v-if="createForm.sources.includes('openalex')" label="OpenAlex 综合抓取" required>
          <a-form-item label="文献类型" :style="{ marginBottom: '12px' }">
            <a-checkbox-group v-model:value="createForm.openalex_venue_types">
              <a-checkbox v-for="opt in OPENALEX_VENUE_TYPE_OPTIONS" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </a-checkbox>
            </a-checkbox-group>
          </a-form-item>
          <a-form-item label="CCF 分级" :style="{ marginBottom: '12px' }">
            <a-checkbox-group v-model:value="createForm.openalex_ccf_ranks">
              <a-checkbox v-for="opt in OPENALEX_CCF_RANK_OPTIONS" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </a-checkbox>
            </a-checkbox-group>
          </a-form-item>
          <a-row :gutter="12">
            <a-col :span="12">
              <a-form-item label="起始年份">
                <a-input-number v-model:value="createForm.openalex_year_from" :min="1990" :max="CURRENT_YEAR" style="width: 100%" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="结束年份">
                <a-input-number v-model:value="createForm.openalex_year_to" :min="1990" :max="CURRENT_YEAR" style="width: 100%" />
              </a-form-item>
            </a-col>
          </a-row>
          <a-form-item label="会议/期刊名称（可选）">
            <a-input
              v-model:value="createForm.openalex_venue_names"
              placeholder="逗号分隔，如 NeurIPS, IEEE TPAMI"
            />
          </a-form-item>
          <p class="field-hint">按兴趣描述+关键词检索 OpenAlex，自动匹配 CCF 分级与期刊指标参与质量打分</p>
        </a-form-item>
        <a-form-item label="关键词（可选）">
          <a-input
            v-model:value="createForm.keywords"
            placeholder="逗号分隔，用于加强匹配"
            @blur="refreshCrawlTranslationPreview"
          />
        </a-form-item>
        </template>
        <a-form-item label="入库位置" required>
          <a-radio-group v-model:value="createForm.visibility">
            <a-radio value="public">公开文献列表（全员可见）</a-radio>
            <a-radio value="private">私有文献列表（仅自己可见）</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item label="语义相关分阈值">
          <a-slider v-model:value="createForm.min_semantic_score" :min="0" :max="100" />
          <span class="field-hint">Embedding 余弦相似度映射，建议 55–65</span>
        </a-form-item>
        <a-form-item label="质量分过滤">
          <a-switch v-model:checked="createForm.enable_quality_filter" checked-children="开启" un-checked-children="关闭" />
          <span class="field-hint">关闭时仅按语义相关排序（适合追最新预印本）</span>
        </a-form-item>
        <a-form-item v-if="createForm.enable_quality_filter" label="质量分阈值">
          <a-slider v-model:value="createForm.min_quality_score" :min="0" :max="100" />
        </a-form-item>
        <a-form-item label="单次最多入选">
          <a-input-number v-model:value="createForm.max_papers_per_run" :min="1" :max="200" style="width: 100%" />
        </a-form-item>
        <a-form-item label="每日定时执行（可选）">
          <a-time-picker v-model:value="createForm.schedule" format="HH:mm" style="width: 100%" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-drawer v-model:open="detailOpen" title="任务详情" width="560" placement="right">
      <template v-if="detailItem">
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="任务 ID">{{ detailItem.id }}</a-descriptions-item>
          <a-descriptions-item label="类型">{{ typeLabel(detailItem.type) }}</a-descriptions-item>
          <a-descriptions-item label="入库位置">{{ detailItem.visibility_label }}</a-descriptions-item>
          <a-descriptions-item label="状态">{{ statusLabel(detailItem.status) }}</a-descriptions-item>
          <a-descriptions-item label="进度">{{ detailItem.progress }}%</a-descriptions-item>
          <a-descriptions-item v-if="detailItem.enable_smart_planning" label="规划模式">
            {{ planningStatusLabel(detailItem.planning_status) }}
          </a-descriptions-item>
          <a-descriptions-item
            v-if="detailItem.enable_smart_planning && detailItem.planning_status === 'failed'"
            label="规划失败原因"
          >
            {{ detailItem.planning_error || '—' }}
          </a-descriptions-item>
          <template v-if="!detailItem.enable_smart_planning">
          <a-descriptions-item label="数据源">{{ detailItem.sources || 'arxiv' }}</a-descriptions-item>
          <a-descriptions-item label="兴趣描述">{{ detailItem.intent_text || '—' }}</a-descriptions-item>
          <a-descriptions-item label="arXiv 分类">{{ detailItem.categories || '—' }}</a-descriptions-item>
          <a-descriptions-item label="OpenReview">{{ detailItem.openreview_venues || '—' }}</a-descriptions-item>
          <a-descriptions-item v-if="(detailItem.sources || '').includes('openalex')" label="OpenAlex CCF">
            {{ detailItem.openalex_ccf_ranks || '—' }}
          </a-descriptions-item>
          <a-descriptions-item v-if="(detailItem.sources || '').includes('openalex')" label="OpenAlex 年份">
            {{ detailItem.openalex_year_from || '—' }} — {{ detailItem.openalex_year_to || '—' }}
          </a-descriptions-item>
          </template>
          <a-descriptions-item v-else label="领域描述">{{ detailItem.intent_text || '—' }}</a-descriptions-item>
          <a-descriptions-item label="创建时间">{{ detailItem.created_at }}</a-descriptions-item>
          <a-descriptions-item label="最近执行">{{ detailItem.last_run || '—' }}</a-descriptions-item>
        </a-descriptions>
        <a-divider />
        <template v-if="latestRunStats">
          <h4>最近执行统计</h4>
          <a-descriptions :column="2" size="small" bordered class="run-stats">
            <a-descriptions-item label="候选论文">{{ latestRunStats.candidates ?? '—' }}</a-descriptions-item>
            <a-descriptions-item label="匹配入选">{{ latestRunStats.matched ?? '—' }}</a-descriptions-item>
            <a-descriptions-item label="新增入库">
              <span class="stat-highlight">{{ latestRunStats.new_entries ?? 0 }}</span>
            </a-descriptions-item>
            <a-descriptions-item label="跳过重复">{{ latestRunStats.skipped_dup ?? 0 }}</a-descriptions-item>
            <a-descriptions-item label="新论文元数据">{{ latestRunStats.new_papers ?? 0 }}</a-descriptions-item>
            <a-descriptions-item label="PDF 下载失败">{{ latestRunStats.download_failed ?? 0 }}</a-descriptions-item>
          </a-descriptions>
          <p class="run-stats-hint">
            日志中的「已下载 PDF」包含补下历史论文，不等于新增入库数；请到「文献管理」对应入库位置查看。
          </p>
          <a-divider />
        </template>
        <h4>执行日志</h4>
        <pre class="task-log">{{ detailItem.log || '暂无日志' }}</pre>
      </template>
    </a-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import dayjs from 'dayjs'
import HeaderComponent from '@/components/common/HeaderComponent.vue'
import { apiJson } from '@/api'
import { ARXIV_CATEGORY_GROUPS, ARXIV_CATEGORY_OPTIONS } from '@/constants/arxivCategories'
import { CRAWL_SOURCE_OPTIONS } from '@/constants/crawlSources'
import { OPENREVIEW_VENUE_GROUPS, OPENREVIEW_VENUE_OPTIONS } from '@/constants/openreviewVenues'
import {
  CURRENT_YEAR,
  OPENALEX_CCF_RANK_OPTIONS,
  OPENALEX_VENUE_TYPE_OPTIONS,
} from '@/constants/openalexVenues'
import { previewCrawlQueryTranslation } from '@/api/translate'

const CJK_RE = /[\u4e00-\u9fff\u3400-\u4dbf]/

const activeTab = ref('all')
const loading = ref(false)
const creating = ref(false)
const createOpen = ref(false)
const detailOpen = ref(false)
const detailItem = ref(null)

const latestRunStats = computed(() => detailItem.value?.runs?.[0]?.stats || null)
let pollTimer = null

const defaultCreateForm = () => ({
  name: '',
  intent_text: '',
  sources: ['arxiv'],
  categories: [],
  openreview_venues: [],
  openalex_venue_types: ['conference', 'journal'],
  openalex_ccf_ranks: ['A', 'B', 'C'],
  openalex_year_from: CURRENT_YEAR - 2,
  openalex_year_to: CURRENT_YEAR,
  openalex_venue_names: '',
  keywords: '',
  visibility: 'public',
  min_semantic_score: 55,
  min_quality_score: 70,
  enable_quality_filter: false,
  enable_smart_planning: false,
  max_papers_per_run: 50,
  schedule: null,
})

const createForm = ref(defaultCreateForm())

const crawlTranslatePreview = ref({
  translated: false,
  intent_text: '',
  keywords: '',
})

const hasChinese = (text) => CJK_RE.test(text || '')

const resetCrawlTranslatePreview = () => {
  crawlTranslatePreview.value = { translated: false, intent_text: '', keywords: '' }
}

const refreshCrawlTranslationPreview = async () => {
  const intent = createForm.value.intent_text?.trim() || ''
  const keywords = createForm.value.keywords?.trim() || ''
  if (!hasChinese(intent) && !hasChinese(keywords)) {
    resetCrawlTranslatePreview()
    return
  }
  try {
    const data = await previewCrawlQueryTranslation({ intent_text: intent, keywords })
    crawlTranslatePreview.value = {
      translated: !!data.translated,
      intent_text: data.intent_text || '',
      keywords: data.keywords || '',
    }
  } catch {
    resetCrawlTranslatePreview()
  }
}

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
  { title: '类型', key: 'type', width: 90 },
  { title: '入库', key: 'visibility', width: 110 },
  { title: '状态', key: 'status', width: 100 },
  { title: '进度', key: 'progress', width: 140 },
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
    idle: '空闲',
    waiting: '等待中',
    running: '运行中',
    done: '已完成',
    failed: '失败',
    cancelled: '已取消',
    planning: '规划中',
    planning_failed: '规划失败',
  }
  return map[status] || status
}

const planningStatusLabel = (status) => {
  const map = {
    none: '—',
    planning: '后台规划中',
    ready: '已完成',
    failed: '失败',
    cancelled: '已取消',
  }
  return map[status] || status
}

const canRunCrawl = (record) =>
  record.type === 'crawl'
  && record.status !== 'running'
  && record.status !== 'planning'
  && record.status !== 'planning_failed'

const canCancelTask = (record) =>
  record.status === 'running' || record.status === 'waiting' || record.status === 'planning'

const statusBadge = (status) => {
  const map = {
    idle: 'default',
    waiting: 'default',
    running: 'processing',
    done: 'success',
    failed: 'error',
    cancelled: 'warning',
    planning: 'processing',
    planning_failed: 'error',
  }
  return map[status] || 'default'
}

const fetchTasks = async () => {
  loading.value = true
  try {
    const data = await apiJson('/api/tasks')
    tasks.value = data.tasks || []
  } catch (err) {
    message.error(err.message || '加载任务失败')
  } finally {
    loading.value = false
  }
}

const openCreateModal = () => {
  createForm.value = defaultCreateForm()
  resetCrawlTranslatePreview()
  createOpen.value = true
}

const filterArxivCategory = (input, option) => {
  const q = input.toLowerCase()
  const value = String(option?.value ?? '').toLowerCase()
  const meta = ARXIV_CATEGORY_OPTIONS.find((o) => o.value === option?.value)
  const label = (meta?.label ?? '').toLowerCase()
  return value.includes(q) || label.includes(q)
}

const filterOpenReviewVenue = (input, option) => {
  const q = input.toLowerCase()
  const value = String(option?.value ?? '').toLowerCase()
  const meta = OPENREVIEW_VENUE_OPTIONS.find((o) => o.value === option?.value)
  const label = (meta?.label ?? '').toLowerCase()
  return value.includes(q) || label.includes(q)
}

const handleCreate = async () => {
  if (!createForm.value.name?.trim()) {
    message.warning('请填写任务名称')
    return Promise.reject()
  }
  if (!createForm.value.intent_text?.trim()) {
    message.warning(createForm.value.enable_smart_planning ? '请填写研究领域描述' : '请填写研究兴趣描述')
    return Promise.reject()
  }
  if (!createForm.value.enable_smart_planning) {
    if (!createForm.value.sources?.length) {
      message.warning('请至少选择一种抓取数据源')
      return Promise.reject()
    }
    if (createForm.value.sources.includes('arxiv') && !createForm.value.categories?.length) {
      message.warning('请选择至少一个 arXiv 分类')
      return Promise.reject()
    }
    if (createForm.value.sources.includes('openreview') && !createForm.value.openreview_venues?.length) {
      message.warning('请选择至少一个 OpenReview 会议')
      return Promise.reject()
    }
    if (createForm.value.sources.includes('openalex')) {
      if (!createForm.value.openalex_venue_types?.length) {
        message.warning('OpenAlex 请至少选择一种文献类型')
        return Promise.reject()
      }
      if (!createForm.value.openalex_ccf_ranks?.length) {
        message.warning('OpenAlex 请至少选择一种 CCF 分级')
        return Promise.reject()
      }
    }
  }

  creating.value = true
  const schedule_time = createForm.value.schedule
    ? dayjs(createForm.value.schedule).format('HH:mm')
    : null

  try {
    const payload = {
      name: createForm.value.name.trim(),
      intent_text: createForm.value.intent_text.trim(),
      visibility: createForm.value.visibility,
      min_semantic_score: createForm.value.min_semantic_score,
      min_quality_score: createForm.value.min_quality_score,
      enable_quality_filter: createForm.value.enable_quality_filter,
      enable_smart_planning: createForm.value.enable_smart_planning,
      max_papers_per_run: createForm.value.max_papers_per_run,
      schedule_time,
    }
    if (!createForm.value.enable_smart_planning) {
      Object.assign(payload, {
        sources: createForm.value.sources.join(','),
        categories: createForm.value.categories.join(', '),
        openreview_venues: createForm.value.openreview_venues.join(','),
        openalex_venue_types: createForm.value.openalex_venue_types.join(','),
        openalex_ccf_ranks: createForm.value.openalex_ccf_ranks.join(','),
        openalex_year_from: createForm.value.openalex_year_from,
        openalex_year_to: createForm.value.openalex_year_to,
        openalex_venue_names: createForm.value.openalex_venue_names?.trim() || '',
        keywords: createForm.value.keywords.trim(),
      })
    }
    await apiJson('/api/tasks/crawl', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    const wasSmartPlan = createForm.value.enable_smart_planning
    createOpen.value = false
    createForm.value = defaultCreateForm()
    resetCrawlTranslatePreview()
    message.success(wasSmartPlan ? '任务已创建，智能规划在后台进行' : '任务创建成功')
    await fetchTasks()
    if (wasSmartPlan) {
      startPolling()
    }
  } catch (err) {
    message.error(err.message || '创建失败')
    return Promise.reject(err)
  } finally {
    creating.value = false
  }
}

const viewDetail = async (record) => {
  try {
    const data = await apiJson(`/api/tasks/${record.id}`)
    detailItem.value = data
    detailOpen.value = true
  } catch (err) {
    message.error(err.message || '加载详情失败')
  }
}

const cancelTask = async (record) => {
  try {
    const data = await apiJson(`/api/tasks/${record.id}/cancel`, { method: 'POST' })
    message.success(data.message || '已取消')
    await fetchTasks()
    if (record.status === 'planning' || record.status === 'running') {
      startPolling()
    }
  } catch (err) {
    message.error(err.message || '取消失败')
  }
}

const runNow = async (record) => {
  try {
    await apiJson(`/api/tasks/${record.id}/run`, { method: 'POST' })
    message.success('已触发立即执行，请稍后刷新查看结果')
    record.status = 'running'
    record.progress = 5
    startPolling()
    setTimeout(fetchTasks, 1500)
  } catch (err) {
    message.error(err.message || '执行失败')
  }
}

const startPolling = () => {
  if (pollTimer) return
  pollTimer = setInterval(async () => {
    await fetchTasks()
    const needsPoll = tasks.value.some(
      (t) => t.status === 'running' || t.status === 'planning',
    )
    if (!needsPoll) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }, 3000)
}

onMounted(() => {
  fetchTasks().then(() => {
    if (tasks.value.some((t) => t.status === 'running' || t.status === 'planning')) {
      startPolling()
    }
  })
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
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

.source-hint {
  color: var(--gray-700);
  font-size: 12px;
}

.translate-preview-alert {
  margin-bottom: 16px;

  p {
    margin: 4px 0 0;
    line-height: 1.6;
  }
}

.field-hint {
  display: block;
  margin-top: 4px;
  color: var(--gray-700);
  font-size: 12px;
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

.run-stats {
  margin-bottom: 8px;
}

.run-stats-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--gray-700);
}

.stat-highlight {
  color: var(--main-600);
  font-weight: 600;
}

@media (max-width: 900px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
