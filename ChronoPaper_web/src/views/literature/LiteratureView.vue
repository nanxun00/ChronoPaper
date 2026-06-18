<template>
  <div class="literature-container layout-container">
    <HeaderComponent
      title="文献管理"
      description="管理公共论文、私有文档，支持 arXiv / OpenReview 多源抓取、预览与收藏。"
    />

    <div class="literature-body">
      <a-tabs v-model:activeKey="activeTab" class="literature-tabs">
        <a-tab-pane key="public" tab="公共空间">
          <div class="tab-toolbar">
            <a-input-search
              v-model:value="publicQuery"
              placeholder="搜索标题、作者、摘要、arXiv ID"
              style="max-width: 420px"
              allow-clear
              @search="searchPublicPapers"
            />
            <a-select v-model:value="publicCategory" style="width: 160px" placeholder="分类筛选" @change="searchPublicPapers">
              <a-select-option value="">全部分类</a-select-option>
              <a-select-option value="cs.AI">cs.AI</a-select-option>
              <a-select-option value="cs.CL">cs.CL</a-select-option>
              <a-select-option value="cs.CV">cs.CV</a-select-option>
            </a-select>
            <a-select
              v-model:value="publicSource"
              style="width: 140px"
              placeholder="数据源"
              allow-clear
              @change="searchPublicPapers"
            >
              <a-select-option value="">全部来源</a-select-option>
              <a-select-option value="arxiv">预印本池</a-select-option>
              <a-select-option value="openreview">顶会池</a-select-option>
              <a-select-option value="openalex">综合期刊/会议</a-select-option>
            </a-select>
            <span class="filter-label">语义≥</span>
            <a-input-number
              v-model:value="publicMinSemantic"
              :min="0"
              :max="100"
              style="width: 72px"
              placeholder="—"
            />
            <span class="filter-label">质量≥</span>
            <a-input-number
              v-model:value="publicMinQuality"
              :min="0"
              :max="100"
              style="width: 72px"
              placeholder="—"
            />
            <a-button @click="searchPublicPapers">应用筛选</a-button>
            <a-button
              danger
              :disabled="!publicSelectedKeys.length"
              :loading="deleting"
              @click="confirmBatchDelete('public')"
            >
              批量删除 ({{ publicSelectedKeys.length }})
            </a-button>
          </div>
          <a-table
            :columns="literatureColumns"
            :data-source="publicPapers"
            :loading="loading"
            row-key="arxiv_id"
            :row-selection="publicRowSelection"
            :pagination="publicPagination"
            @change="onPublicTableChange"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'title'">
                <a @click="openPreview(record)">{{ record.title }}</a>
              </template>
              <template v-else-if="column.key === 'source'">
                <a-tag :color="sourceColor(record.source)">
                  {{ sourceLabel(record.source) }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'action'">
                <a-space>
                  <a-button type="link" size="small" @click="openPreview(record)">预览</a-button>
                  <a-button type="link" size="small" @click="toggleFavorite(record)">
                    {{ record.favorited ? '取消收藏' : '收藏' }}
                  </a-button>
                  <a-button type="link" size="small" danger @click="confirmDeleteOne(record, 'public')">
                    删除
                  </a-button>
                </a-space>
              </template>
            </template>
            <template #emptyText>
              <a-empty description="暂无公共论文，请先在任务中心创建抓取任务" />
            </template>
          </a-table>
        </a-tab-pane>

        <a-tab-pane key="private" tab="私有文献">
          <div class="tab-toolbar">
            <a-upload :show-upload-list="false" :before-upload="beforePrivateUpload">
              <a-button>上传 PDF</a-button>
            </a-upload>
            <a-input-search
              v-model:value="privateQuery"
              placeholder="搜索私有文献"
              style="max-width: 320px"
              allow-clear
              @search="searchPrivatePapers"
            />
            <a-select
              v-model:value="privateSource"
              style="width: 140px"
              placeholder="数据源"
              allow-clear
              @change="searchPrivatePapers"
            >
              <a-select-option value="">全部来源</a-select-option>
              <a-select-option value="arxiv">预印本池</a-select-option>
              <a-select-option value="openreview">顶会池</a-select-option>
              <a-select-option value="openalex">综合期刊/会议</a-select-option>
            </a-select>
            <span class="filter-label">语义≥</span>
            <a-input-number v-model:value="privateMinSemantic" :min="0" :max="100" style="width: 72px" />
            <span class="filter-label">质量≥</span>
            <a-input-number v-model:value="privateMinQuality" :min="0" :max="100" style="width: 72px" />
            <a-button @click="searchPrivatePapers">应用筛选</a-button>
            <a-button
              danger
              :disabled="!privateSelectedKeys.length"
              :loading="deleting"
              @click="confirmBatchDelete('private')"
            >
              批量删除 ({{ privateSelectedKeys.length }})
            </a-button>
          </div>
          <a-table
            :columns="literatureColumns"
            :data-source="privateDocs"
            :loading="loading"
            row-key="arxiv_id"
            :row-selection="privateRowSelection"
            :pagination="privatePagination"
            @change="onPrivateTableChange"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'title'">
                <a @click="openPreview(record)">{{ record.title }}</a>
              </template>
              <template v-else-if="column.key === 'source'">
                <a-tag :color="sourceColor(record.source)">
                  {{ sourceLabel(record.source) }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'action'">
                <a-space>
                  <a-button type="link" size="small" @click="openPreview(record)">预览</a-button>
                  <a-button type="link" size="small" danger @click="confirmDeleteOne(record, 'private')">
                    删除
                  </a-button>
                </a-space>
              </template>
            </template>
            <template #emptyText>
              <a-empty description="暂无私有文献，可在任务中心创建「入库到私有文献」的抓取任务" />
            </template>
          </a-table>
        </a-tab-pane>

        <a-tab-pane key="search" tab="图文检索">
          <div class="search-panel">
            <a-segmented v-model:value="searchMode" :options="searchModeOptions" />
            <a-textarea
              v-if="searchMode === 'text'"
              v-model:value="imageTextQuery"
              placeholder="用文字描述你想找的图表，例如：Transformer 架构图"
              :rows="3"
            />
            <a-upload-dragger
              v-else
              :show-upload-list="false"
              :before-upload="beforeImageSearchUpload"
            >
              <p class="ant-upload-drag-icon">
                <PictureOutlined />
              </p>
              <p class="ant-upload-text">上传图片进行以图搜图</p>
            </a-upload-dragger>
            <a-button type="primary" :loading="searchLoading" @click="runImageSearch">
              {{ searchMode === 'text' ? '文字搜图' : '以图搜图' }}
            </a-button>
          </div>
          <a-list
            v-if="searchResults.length"
            :data-source="searchResults"
            item-layout="vertical"
            class="search-results"
          >
            <template #renderItem="{ item }">
              <a-list-item>
                <a-list-item-meta :title="item.title" :description="item.caption" />
                <div class="search-meta">
                  <span>{{ item.arxiv_id }}</span>
                  <span>第 {{ item.page_num }} 页</span>
                  <a-button type="link" size="small" @click="openPreview(item)">查看原文</a-button>
                </div>
              </a-list-item>
            </template>
          </a-list>
          <a-empty v-else description="输入检索条件后查看匹配图表" />
        </a-tab-pane>

        <a-tab-pane key="favorites" tab="收藏">
          <a-table
            :columns="favoriteColumns"
            :data-source="favoritePapers"
            row-key="arxiv_id"
            :pagination="{ pageSize: 10 }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'title'">
                <a @click="openPreview(record)">{{ record.title }}</a>
              </template>
              <template v-else-if="column.key === 'source'">
                <a-tag :color="sourceColor(record.source)">
                  {{ sourceLabel(record.source) }}
                </a-tag>
              </template>
              <template v-else-if="column.key === 'action'">
                <a-space>
                  <a-button type="link" size="small" @click="openPreview(record)">预览</a-button>
                  <a-button type="link" size="small" danger @click="toggleFavorite(record)">移除</a-button>
                </a-space>
              </template>
            </template>
            <template #emptyText>
              <a-empty description="暂无收藏论文" />
            </template>
          </a-table>
        </a-tab-pane>
      </a-tabs>
    </div>

    <a-drawer
      v-model:open="previewOpen"
      title="文献预览"
      width="min(960px, 92vw)"
      placement="right"
      :destroy-on-close="true"
    >
      <template v-if="previewItem">
        <h3>{{ previewItem.title }}</h3>
        <p class="preview-meta">
          <a-tag v-if="previewItem.source" :color="sourceColor(previewItem.source)">
            {{ sourceLabel(previewItem.source) }}
          </a-tag>
          <span v-if="previewItem.venue">会议/期刊：{{ previewItem.venue }}</span>
          <span v-if="previewItem.venue_rank">CCF：{{ previewItem.venue_rank }}</span>
          <span v-if="previewItem.journal_if != null"> · IF/citedness：{{ previewItem.journal_if }}</span>
          <span v-if="previewItem.jcr_quartile"> · 分区：{{ previewItem.jcr_quartile }}</span>
          <span v-if="previewItem.doi"> · DOI：{{ previewItem.doi }}</span>
          <span v-if="previewItem.review_rating != null">评审均分：{{ previewItem.review_rating }}</span>
          <span v-if="previewItem.citation_count != null">引用：{{ previewItem.citation_count }}</span>
          <span v-if="previewItem.arxiv_id">ID：{{ previewItem.arxiv_id }}</span>
          <span v-if="previewItem.authors">{{ previewItem.authors }}</span>
          <span v-if="previewItem.published_at">发布时间：{{ previewItem.published_at }}</span>
          <span v-else-if="previewItem.year">年份：{{ previewItem.year }}</span>
        </p>
        <a-divider />
        <p class="preview-abstract selectable-text" @mouseup="handleTextSelection">
          {{ previewItem.abstract || previewItem.summary || '暂无摘要' }}
        </p>
        <a-divider orientation="left">PDF 预览</a-divider>
        <PdfPreview
          :arxiv-id="previewItem.arxiv_id"
          :external-url="previewExternalUrl"
        />
      </template>
    </a-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { Modal, message } from 'ant-design-vue'
import { PictureOutlined } from '@ant-design/icons-vue'
import HeaderComponent from '@/components/common/HeaderComponent.vue'
import PdfPreview from '@/components/literature/PdfPreview.vue'
import { deleteLiteratureEntries, getPaperDetail, listPublicPapers, listPrivatePapers } from '@/api/literature'
import { SOURCE_LABELS } from '@/constants/openreviewVenues'
import { useSelectionTranslate } from '@/composables/useSelectionTranslate'

const { handleTextSelection } = useSelectionTranslate()

const activeTab = ref('public')
const loading = ref(false)
const deleting = ref(false)
const searchLoading = ref(false)
const previewOpen = ref(false)
const previewItem = ref(null)

const publicQuery = ref('')
const publicCategory = ref('')
const publicSource = ref('')
const publicMinSemantic = ref(null)
const publicMinQuality = ref(null)
const privateQuery = ref('')
const privateSource = ref('')
const privateMinSemantic = ref(null)
const privateMinQuality = ref(null)
const publicSelectedKeys = ref([])
const privateSelectedKeys = ref([])
const searchMode = ref('text')
const imageTextQuery = ref('')
const searchResults = ref([])

const searchModeOptions = [
  { label: '文字搜图', value: 'text' },
  { label: '以图搜图', value: 'image' },
]

const literatureColumns = [
  { title: '标题', key: 'title', dataIndex: 'title', ellipsis: true },
  { title: '来源', key: 'source', width: 100 },
  { title: '会议/期刊', dataIndex: 'venue', width: 140, ellipsis: true },
  { title: 'CCF', dataIndex: 'venue_rank', width: 60 },
  { title: 'IF/citedness', dataIndex: 'journal_if', width: 100 },
  { title: '引用', dataIndex: 'citation_count', width: 70 },
  { title: '作者', dataIndex: 'authors', width: 150, ellipsis: true },
  { title: '发布时间', dataIndex: 'published_at', width: 120 },
  { title: '操作', key: 'action', width: 180 },
]

const publicRowSelection = computed(() => ({
  selectedRowKeys: publicSelectedKeys.value,
  onChange: (keys) => {
    publicSelectedKeys.value = keys
  },
}))

const privateRowSelection = computed(() => ({
  selectedRowKeys: privateSelectedKeys.value,
  onChange: (keys) => {
    privateSelectedKeys.value = keys
  },
}))

const favoriteColumns = [
  { title: '标题', key: 'title', dataIndex: 'title', ellipsis: true },
  { title: '来源', key: 'source', width: 90 },
  { title: '会议/期刊', dataIndex: 'venue', width: 130, ellipsis: true },
  { title: '引用', dataIndex: 'citation_count', width: 70 },
  { title: 'ID', dataIndex: 'arxiv_id', width: 120, ellipsis: true },
  { title: '收藏时间', dataIndex: 'favorited_at', width: 180 },
  { title: '操作', key: 'action', width: 140 },
]

const publicPapers = ref([])
const privateDocs = ref([])
const favoritePapers = ref([])

const publicPagination = ref({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showTotal: (total) => `共 ${total} 篇`,
})

const privatePagination = ref({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showTotal: (total) => `共 ${total} 篇`,
})

const sourceLabel = (source) => SOURCE_LABELS[source] || source || 'arXiv'

const sourceColor = (source) => {
  const map = { arxiv: 'blue', openreview: 'purple', openalex: 'green' }
  return map[source] || 'default'
}

const previewExternalUrl = computed(() => {
  const item = previewItem.value
  if (!item?.pdf_url) return ''
  const url = String(item.pdf_url)
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  if (url.startsWith('/')) return `https://openreview.net${url}`
  return url
})

const loadPublicPapers = async (page = publicPagination.value.current, pageSize = publicPagination.value.pageSize) => {
  loading.value = true
  try {
    const data = await listPublicPapers({
      q: publicQuery.value || undefined,
      category: publicCategory.value || undefined,
      source: publicSource.value || undefined,
      min_semantic: publicMinSemantic.value ?? undefined,
      min_quality: publicMinQuality.value ?? undefined,
      page,
      page_size: pageSize,
    })
    publicPapers.value = data.papers || []
    publicPagination.value = {
      ...publicPagination.value,
      current: data.page || page,
      pageSize: data.page_size || pageSize,
      total: data.total || 0,
    }
  } catch (err) {
    message.error(err.message || '加载公开文献失败')
  } finally {
    loading.value = false
  }
}

const loadPrivatePapers = async (page = privatePagination.value.current, pageSize = privatePagination.value.pageSize) => {
  loading.value = true
  try {
    const data = await listPrivatePapers({
      q: privateQuery.value || undefined,
      source: privateSource.value || undefined,
      min_semantic: privateMinSemantic.value ?? undefined,
      min_quality: privateMinQuality.value ?? undefined,
      page,
      page_size: pageSize,
    })
    privateDocs.value = (data.papers || []).map((p) => ({
      ...p,
      title: p.title,
      status: p.parse_status || p.status,
    }))
    privatePagination.value = {
      ...privatePagination.value,
      current: data.page || page,
      pageSize: data.page_size || pageSize,
      total: data.total || 0,
    }
  } catch (err) {
    message.error(err.message || '加载私有文献失败')
  } finally {
    loading.value = false
  }
}

const onPublicTableChange = (pag) => {
  loadPublicPapers(pag.current, pag.pageSize)
}

const onPrivateTableChange = (pag) => {
  loadPrivatePapers(pag.current, pag.pageSize)
}

const searchPublicPapers = () => {
  publicPagination.value.current = 1
  loadPublicPapers(1)
}

const searchPrivatePapers = () => {
  privatePagination.value.current = 1
  loadPrivatePapers(1)
}

onMounted(() => {
  loadPublicPapers()
  loadPrivatePapers()
})

watch(activeTab, (tab) => {
  if (tab === 'public') {
    publicPagination.value.current = 1
    loadPublicPapers(1)
  }
  if (tab === 'private') {
    privatePagination.value.current = 1
    loadPrivatePapers(1)
  }
})

const openPreview = async (record) => {
  previewItem.value = { ...record }
  previewOpen.value = true
  try {
    const detail = await getPaperDetail(record.arxiv_id)
    previewItem.value = { ...record, ...detail }
  } catch {
    // 列表数据已足够展示，详情失败时保留基础信息
  }
}

const toggleFavorite = (record) => {
  record.favorited = !record.favorited
  if (record.favorited) {
    favoritePapers.value = [...favoritePapers.value, { ...record, favorited_at: new Date().toLocaleString() }]
    message.success('已加入收藏')
  } else {
    favoritePapers.value = favoritePapers.value.filter((p) => p.arxiv_id !== record.arxiv_id)
    message.success('已取消收藏')
  }
}

const removeFromFavorites = (arxivIds) => {
  if (!arxivIds.length) return
  const idSet = new Set(arxivIds)
  favoritePapers.value = favoritePapers.value.filter((p) => !idSet.has(p.arxiv_id))
}

const runDelete = async (arxivIds, visibility) => {
  if (!arxivIds.length) return
  deleting.value = true
  try {
    const result = await deleteLiteratureEntries({ arxiv_ids: arxivIds, visibility })
    const parts = [`已删除 ${result.deleted} 条文献`]
    if (result.files_removed) parts.push(`清理 PDF ${result.files_removed} 个`)
    if (result.papers_removed) parts.push(`移除论文记录 ${result.papers_removed} 条`)
    message.success(parts.join('，'))
    removeFromFavorites(arxivIds)
    if (visibility === 'public') {
      publicSelectedKeys.value = publicSelectedKeys.value.filter((k) => !arxivIds.includes(k))
      await loadPublicPapers()
    } else {
      privateSelectedKeys.value = privateSelectedKeys.value.filter((k) => !arxivIds.includes(k))
      await loadPrivatePapers()
    }
    if (previewItem.value && arxivIds.includes(previewItem.value.arxiv_id)) {
      previewOpen.value = false
      previewItem.value = null
    }
  } catch (err) {
    message.error(err.message || '删除失败')
  } finally {
    deleting.value = false
  }
}

const confirmDeleteOne = (record, visibility) => {
  Modal.confirm({
    title: '确认删除文献？',
    content: `将删除「${record.title}」及其关联 PDF 文件（若无其他列表引用）。`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: () => runDelete([record.arxiv_id], visibility),
  })
}

const confirmBatchDelete = (visibility) => {
  const keys = visibility === 'public' ? publicSelectedKeys.value : privateSelectedKeys.value
  if (!keys.length) return
  Modal.confirm({
    title: `确认批量删除 ${keys.length} 篇文献？`,
    content: '删除后将从列表移除，并清理不再被引用的 PDF 文件与论文记录。',
    okText: '批量删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: () => runDelete([...keys], visibility),
  })
}

const beforePrivateUpload = () => {
  message.info('私有文档上传接口开发中')
  return false
}

const beforeImageSearchUpload = () => {
  message.info('以图搜图接口开发中')
  return false
}

const runImageSearch = () => {
  searchLoading.value = true
  setTimeout(() => {
    searchResults.value = []
    searchLoading.value = false
    message.info('图文检索接口开发中')
  }, 400)
}
</script>

<style scoped lang="less">
.literature-container {
  padding: 0;
}

.literature-body {
  padding: 0 24px 24px;
}

.literature-tabs {
  background: #fff;
  padding: 16px;
  border-radius: 8px;
  border: 1px solid var(--gray-300);
}

.tab-toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
  align-items: center;
}

.filter-label {
  font-size: 13px;
  color: var(--gray-700);
}

.search-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 640px;
  margin-bottom: 24px;
}

.search-results {
  margin-top: 8px;
}

.search-meta {
  display: flex;
  gap: 16px;
  color: var(--gray-700);
  font-size: 13px;
}

.preview-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: var(--gray-700);
  font-size: 13px;
}

.preview-abstract {
  line-height: 1.7;
  color: var(--gray-900);
  margin-bottom: 16px;
}

.selectable-text {
  user-select: text;
  -webkit-user-select: text;
  cursor: text;
}
</style>
