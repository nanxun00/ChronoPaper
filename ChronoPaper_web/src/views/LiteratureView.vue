<template>
  <div class="literature-container layout-container">
    <HeaderComponent
      title="文献管理"
      description="管理公共 arXiv 论文、私有文档，支持预览、图文检索与收藏。"
    />

    <div class="literature-body">
      <a-tabs v-model:activeKey="activeTab" class="literature-tabs">
        <a-tab-pane key="public" tab="存量论文">
          <div class="tab-toolbar">
            <a-input-search
              v-model:value="publicQuery"
              placeholder="搜索标题、作者、摘要、arXiv ID"
              style="max-width: 420px"
              allow-clear
            />
            <a-select v-model:value="publicCategory" style="width: 160px" placeholder="分类筛选">
              <a-select-option value="">全部分类</a-select-option>
              <a-select-option value="cs.AI">cs.AI</a-select-option>
              <a-select-option value="cs.CL">cs.CL</a-select-option>
              <a-select-option value="cs.CV">cs.CV</a-select-option>
            </a-select>
          </div>
          <a-table
            :columns="paperColumns"
            :data-source="publicPapers"
            :loading="loading"
            row-key="arxiv_id"
            :pagination="{ pageSize: 10 }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'title'">
                <a @click="openPreview(record)">{{ record.title }}</a>
              </template>
              <template v-else-if="column.key === 'action'">
                <a-space>
                  <a-button type="link" size="small" @click="openPreview(record)">预览</a-button>
                  <a-button type="link" size="small" @click="toggleFavorite(record)">
                    {{ record.favorited ? '取消收藏' : '收藏' }}
                  </a-button>
                </a-space>
              </template>
            </template>
            <template #emptyText>
              <a-empty description="暂无公共论文，请先在任务中心创建抓取任务" />
            </template>
          </a-table>
        </a-tab-pane>

        <a-tab-pane key="private" tab="私有文档">
          <div class="tab-toolbar">
            <a-upload :show-upload-list="false" :before-upload="beforePrivateUpload">
              <a-button type="primary">上传 PDF</a-button>
            </a-upload>
            <a-input-search
              v-model:value="privateQuery"
              placeholder="搜索私有文档"
              style="max-width: 320px"
              allow-clear
            />
          </div>
          <a-table
            :columns="privateColumns"
            :data-source="privateDocs"
            :loading="loading"
            row-key="id"
            :pagination="{ pageSize: 10 }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'status'">
                <a-tag :color="statusColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
              </template>
              <template v-else-if="column.key === 'action'">
                <a-space>
                  <a-button type="link" size="small" @click="openPreview(record)">预览</a-button>
                  <a-button type="link" size="small" danger>删除</a-button>
                </a-space>
              </template>
            </template>
            <template #emptyText>
              <a-empty description="暂无私有文档，可上传 PDF 或等待 LaTeX 编译生成" />
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
      width="720"
      placement="right"
    >
      <template v-if="previewItem">
        <h3>{{ previewItem.title }}</h3>
        <p class="preview-meta">
          <span v-if="previewItem.arxiv_id">{{ previewItem.arxiv_id }}</span>
          <span v-if="previewItem.authors">{{ previewItem.authors }}</span>
          <span v-if="previewItem.year">{{ previewItem.year }}</span>
        </p>
        <a-divider />
        <p class="preview-abstract">{{ previewItem.abstract || previewItem.summary || '摘要加载中…' }}</p>
        <a-alert
          type="info"
          show-icon
          message="PDF 全文预览与溯源区块定位将在后端解析接口接入后启用"
        />
      </template>
    </a-drawer>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { PictureOutlined } from '@ant-design/icons-vue'
import HeaderComponent from '@/components/HeaderComponent.vue'

const activeTab = ref('public')
const loading = ref(false)
const searchLoading = ref(false)
const previewOpen = ref(false)
const previewItem = ref(null)

const publicQuery = ref('')
const publicCategory = ref('')
const privateQuery = ref('')
const searchMode = ref('text')
const imageTextQuery = ref('')
const searchResults = ref([])

const searchModeOptions = [
  { label: '文字搜图', value: 'text' },
  { label: '以图搜图', value: 'image' },
]

const paperColumns = [
  { title: '标题', key: 'title', dataIndex: 'title', ellipsis: true },
  { title: '作者', dataIndex: 'authors', width: 180, ellipsis: true },
  { title: '年份', dataIndex: 'year', width: 80 },
  { title: 'arXiv ID', dataIndex: 'arxiv_id', width: 140 },
  { title: '操作', key: 'action', width: 140 },
]

const privateColumns = [
  { title: '文件名', dataIndex: 'filename', ellipsis: true },
  { title: '来源', dataIndex: 'source', width: 120 },
  { title: '状态', key: 'status', width: 100 },
  { title: '上传时间', dataIndex: 'created_at', width: 180 },
  { title: '操作', key: 'action', width: 140 },
]

const favoriteColumns = [
  { title: '标题', key: 'title', dataIndex: 'title', ellipsis: true },
  { title: 'arXiv ID', dataIndex: 'arxiv_id', width: 140 },
  { title: '收藏时间', dataIndex: 'favorited_at', width: 180 },
  { title: '操作', key: 'action', width: 140 },
]

const publicPapers = ref([])
const privateDocs = ref([])
const favoritePapers = ref([])

const statusColor = (status) => {
  const map = { done: 'green', processing: 'blue', waiting: 'default', failed: 'red' }
  return map[status] || 'default'
}

const statusLabel = (status) => {
  const map = { done: '已解析', processing: '解析中', waiting: '等待中', failed: '失败' }
  return map[status] || status
}

const openPreview = (record) => {
  previewItem.value = record
  previewOpen.value = true
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
</style>
