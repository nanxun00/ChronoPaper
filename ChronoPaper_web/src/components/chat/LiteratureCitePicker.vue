<template>
  <a-popover
    v-model:open="open"
    trigger="click"
    placement="topLeft"
    overlay-class-name="literature-cite-popover"
    :arrow="false"
  >
    <template #content>
      <div class="cite-panel">
        <div class="cite-panel__header">
          <a-input-search
            v-model:value="keyword"
            placeholder="搜索标题、作者、摘要、ID"
            allow-clear
            :loading="loading"
            @search="doSearch"
            @change="onKeywordChange"
          />
        </div>
        <a-tabs v-model:activeKey="activeTab" size="small" @change="doSearch">
          <a-tab-pane key="public" tab="存量论文" />
          <a-tab-pane key="private" tab="私有文献" />
        </a-tabs>
        <div class="cite-panel__list">
          <a-spin :spinning="loading">
            <div v-if="!loading && papers.length === 0" class="cite-panel__empty">
              {{ keyword ? '未找到相关文献' : '输入关键词搜索文献' }}
            </div>
            <div
              v-for="paper in papers"
              :key="paper.arxiv_id"
              class="cite-item"
              :class="{ 'cite-item--selected': isSelected(paper.arxiv_id) }"
              @click="togglePaper(paper)"
            >
              <div class="cite-item__check">
                <CheckOutlined v-if="isSelected(paper.arxiv_id)" />
              </div>
              <div class="cite-item__body">
                <div class="cite-item__title">{{ paper.title }}</div>
                <div class="cite-item__meta">
                  <span v-if="paper.authors">{{ truncate(paper.authors, 60) }}</span>
                  <span v-if="paper.published_at"> · {{ paper.published_at }}</span>
                </div>
              </div>
            </div>
          </a-spin>
        </div>
        <div v-if="modelValue.length" class="cite-panel__footer">
          已选 {{ modelValue.length }} 篇，点击文献可取消
        </div>
      </div>
    </template>
    <slot />
  </a-popover>
</template>

<script setup>
import { ref, watch } from 'vue'
import { CheckOutlined } from '@ant-design/icons-vue'
import { listPublicPapers, listPrivatePapers, getPaperDetail } from '@/api/literature'

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['update:modelValue'])

const open = ref(false)
const keyword = ref('')
const activeTab = ref('public')
const papers = ref([])
const loading = ref(false)
let searchTimer = null

const truncate = (text, max) => {
  if (!text || text.length <= max) return text
  return `${text.slice(0, max)}…`
}

const isSelected = (arxivId) => props.modelValue.some((p) => p.arxiv_id === arxivId)

const toCiteItem = (paper) => ({
  arxiv_id: paper.arxiv_id,
  title: paper.title,
  abstract: paper.abstract || '',
  authors: paper.authors || '',
  source: paper.source || 'arxiv',
  visibility: activeTab.value,
})

const togglePaper = async (paper) => {
  const id = paper.arxiv_id
  if (isSelected(id)) {
    emit(
      'update:modelValue',
      props.modelValue.filter((p) => p.arxiv_id !== id),
    )
    return
  }
  let citeSource = paper
  try {
    const detail = await getPaperDetail(paper.arxiv_id)
    if (detail) citeSource = detail
  } catch {
    // 列表数据兜底
  }
  emit('update:modelValue', [...props.modelValue, toCiteItem(citeSource)])
}

const doSearch = async () => {
  const q = keyword.value.trim()
  if (!q) {
    papers.value = []
    return
  }
  loading.value = true
  try {
    const params = { q, page: 1, page_size: 12 }
    const data =
      activeTab.value === 'public'
        ? await listPublicPapers(params)
        : await listPrivatePapers(params)
    papers.value = data.papers || []
  } catch {
    papers.value = []
  } finally {
    loading.value = false
  }
}

const onKeywordChange = () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(doSearch, 350)
}

watch(open, (val) => {
  if (val && keyword.value.trim()) {
    doSearch()
  }
})
</script>

<style scoped lang="less">
.cite-panel {
  width: 380px;
}

.cite-panel__header {
  margin-bottom: 4px;
}

.cite-panel__list {
  max-height: 280px;
  overflow-y: auto;
  margin: 0 -4px;
}

.cite-panel__empty {
  padding: 24px 8px;
  text-align: center;
  color: #999;
  font-size: 13px;
}

.cite-item {
  display: flex;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;

  &:hover {
    background: #f5f7fa;
  }

  &--selected {
    background: #eef5ff;
  }
}

.cite-item__check {
  width: 16px;
  flex-shrink: 0;
  color: var(--main-600, #1677ff);
  padding-top: 2px;
}

.cite-item__title {
  font-size: 13px;
  line-height: 1.4;
  color: #222;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.cite-item__meta {
  margin-top: 2px;
  font-size: 12px;
  color: #999;
}

.cite-panel__footer {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #f0f0f0;
  font-size: 12px;
  color: #666;
}
</style>
