<template>
  <div class="pdf-preview">
    <div v-if="source && pageCount > 0" class="pdf-toolbar">
      <span class="page-indicator">共 {{ pageCount }} 页，下划浏览</span>
    </div>

    <a-spin :spinning="loading" tip="加载 PDF…">
      <div
        v-if="source"
        ref="scrollContainer"
        class="pdf-scroll-wrap"
        @mouseup="handleTextSelection"
      >
        <div
          v-for="pageNum in pageNums"
          :key="pageNum"
          :ref="(el) => setPageRef(el, pageNum - 1)"
          class="pdf-page-slot"
          :data-page="pageNum"
        >
          <VuePdfEmbed
            v-if="pageVisibility[pageNum]"
            :source="source"
            :page="pageNum"
            text-layer
            annotation-layer
            class="pdf-page"
            @internal-link-clicked="scrollToPage"
            @rendering-failed="handleLoadFailed"
          />
          <div v-else class="pdf-page-placeholder">
            <a-spin size="small" />
            <span>第 {{ pageNum }} 页</span>
          </div>
        </div>
      </div>
      <a-empty v-else-if="!loading" :description="emptyText">
        <template v-if="externalUrl" #extra>
          <a :href="externalUrl" target="_blank" rel="noopener noreferrer">在外部打开 PDF</a>
        </template>
      </a-empty>
    </a-spin>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import VuePdfEmbed from 'vue-pdf-embed'
import { GlobalWorkerOptions } from 'vue-pdf-embed/dist/index.essential.mjs'
import 'vue-pdf-embed/dist/styles/annotationLayer.css'
import 'vue-pdf-embed/dist/styles/textLayer.css'
import PdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import * as pdfjsLib from 'pdfjs-dist'
import { authFetch } from '@/api/client'
import { useSelectionTranslate } from '@/composables/useSelectionTranslate'

GlobalWorkerOptions.workerSrc = PdfWorker
pdfjsLib.GlobalWorkerOptions.workerSrc = PdfWorker

const props = defineProps({
  arxivId: {
    type: String,
    default: '',
  },
  externalUrl: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['error', 'loaded'])

const { handleTextSelection } = useSelectionTranslate()

const loading = ref(false)
const source = ref(null)
const pageCount = ref(0)
const emptyText = ref('暂无 PDF 可预览')
const scrollContainer = ref(null)
const pageRefs = ref([])
const pageVisibility = ref({})

const pageNums = computed(() =>
  pageCount.value > 0 ? Array.from({ length: pageCount.value }, (_, i) => i + 1) : [],
)

let blobUrl = ''
let pageIntersectionObserver = null

const setPageRef = (el, index) => {
  if (el) {
    pageRefs.value[index] = el
  }
}

const resetPageIntersectionObserver = () => {
  pageIntersectionObserver?.disconnect()
  if (!scrollContainer.value) return

  pageIntersectionObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return
        const pageNum = Number(entry.target.dataset.page)
        if (pageNum && !pageVisibility.value[pageNum]) {
          pageVisibility.value = { ...pageVisibility.value, [pageNum]: true }
        }
      })
    },
    { root: scrollContainer.value, rootMargin: '320px 0px', threshold: 0.01 },
  )

  pageRefs.value.forEach((element) => {
    if (element) pageIntersectionObserver.observe(element)
  })
}

const scrollToPage = (pageNum) => {
  pageVisibility.value = { ...pageVisibility.value, [pageNum]: true }
  nextTick(() => {
    const el = pageRefs.value[pageNum - 1]
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

const resetSource = () => {
  pageIntersectionObserver?.disconnect()
  pageIntersectionObserver = null
  pageRefs.value = []
  pageVisibility.value = {}

  if (blobUrl) {
    URL.revokeObjectURL(blobUrl)
    blobUrl = ''
  }
  source.value = null
  pageCount.value = 0
}

const loadPdf = async (arxivId) => {
  resetSource()
  if (!arxivId) {
    emptyText.value = '未选择文献'
    return
  }

  loading.value = true
  try {
    const response = await authFetch(`/api/literature/pdf/${encodeURIComponent(arxivId)}`)
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      const detail = data.detail || '加载 PDF 失败'
      emptyText.value =
        response.status === 404
          ? '本地 PDF 未缓存，后端拉取失败。可尝试外部链接，或重新执行抓取任务。'
          : detail
      throw new Error(detail)
    }
    const blob = await response.blob()
    blobUrl = URL.createObjectURL(blob)

    const pdf = await pdfjsLib.getDocument(blobUrl).promise
    pageCount.value = pdf.numPages
    source.value = pdf
    URL.revokeObjectURL(blobUrl)
    blobUrl = ''

    emit('loaded')
  } catch (err) {
    if (!emptyText.value || emptyText.value === '暂无 PDF 可预览') {
      emptyText.value = err.message || 'PDF 加载失败'
    }
    emit('error', err)
  } finally {
    loading.value = false
  }
}

const handleLoadFailed = () => {
  emptyText.value = 'PDF 渲染失败'
  emit('error', new Error('PDF 渲染失败'))
}

watch(
  () => props.arxivId,
  (id) => {
    loadPdf(id)
  },
  { immediate: true },
)

watch(pageNums, (nums) => {
  if (!nums.length) return
  pageVisibility.value = { [nums[0]]: true }
  nextTick(resetPageIntersectionObserver)
})

onBeforeUnmount(() => {
  resetSource()
})
</script>

<style scoped lang="less">
.pdf-preview {
  margin-top: 8px;
}

.pdf-toolbar {
  margin-bottom: 12px;
  position: sticky;
  top: 0;
  z-index: 1;
  background: #fff;
  padding: 8px 0;
}

.page-indicator {
  color: var(--gray-700);
  font-size: 13px;
}

.pdf-scroll-wrap {
  border: 1px solid var(--gray-300);
  border-radius: 8px;
  overflow: auto;
  max-height: calc(100vh - 280px);
  background: #f5f5f5;
  padding: 12px;
}

.pdf-page-slot {
  margin-bottom: 16px;

  &:last-child {
    margin-bottom: 0;
  }
}

.pdf-page {
  display: block;
  margin: 0 auto;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  position: relative;
}

.pdf-page-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  min-height: min(1100px, 140vw);
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  color: var(--gray-600);
  font-size: 13px;
}

.pdf-page :deep(.textLayer) {
  user-select: text;
  -webkit-user-select: text;
}

.pdf-page :deep(.textLayer span) {
  cursor: text;
}
</style>
