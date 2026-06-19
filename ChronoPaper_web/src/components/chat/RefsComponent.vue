<template>
  <div class="refs" v-if="showRefs">
    <div class="tags">
      <span class="item btn" @click="copyText(msg.text)"><CopyOutlined /></span>
      <span class="item btn" @click="likeThisResponse(msg)"><LikeOutlined /></span>
      <span class="item btn" @click="dislikeThisResponse(msg)"><DislikeOutlined /></span>
      <span class="item btn delete-btn" @click="deleteThisTurn(msg)">
        <DeleteOutlined />
      </span>
      <span class="item"><GlobalOutlined /> {{ msg.model_name }}</span>
      <span
        class="item btn"
        @click="openSubGraph(msg)"
        v-if="hasSubGraphData(msg)"
      >
        <GlobalOutlined /> 关系图
      </span>
      <span
        class="item btn skill-artifact-tag"
        v-for="artifact in skillArtifacts"
        :key="artifact.url"
        @click="openArtifact(artifact)"
      >
        <FileTextOutlined v-if="artifact.kind !== 'image'" />
        <PictureOutlined v-else />
        {{ artifact.name }}
      </span>
      <span class="filetag item btn"
        v-for="(results, filename) in groupedResults"
        :key="filename"
        @click="toggleDrawer(filename)"
      >
        <FileTextOutlined /> {{ filename }}
        <a-drawer
          v-model:open="openDetail[filename]"
          :title="filename"
          width="800"
          :contentWrapperStyle="{ maxWidth: '100%'}"
          placement="right"
          class="retrieval-detail"
          rootClassName="root"
        >
          <div class="fileinfo">
            <p><FileOutlined /> {{ results[0].file.type }}</p>
            <p><ClockCircleOutlined /> {{ formatDate(results[0].file.created_at) }}</p>
          </div>
          <div class="results-list">
            <div v-for="res in results" :key="res.id" class="result-item">
              <div class="result-meta">
                <div class="score-info">
                  <span>
                    <strong>相似度：</strong>
                    <a-progress :percent="getPercent(res.distance)"/>
                  </span>
                  <span v-if="res.rerank_score">
                    <strong>重排序：</strong>
                    <a-progress :percent="getPercent(res.rerank_score)"/>
                  </span>
                </div>
                <div class="result-id">
                  ID: #{{ res.id }}
                  <span v-if="res.entity?.page_num"> · 第 {{ res.entity.page_num }} 页</span>
                </div>
              </div>
              <div class="result-text">{{ res.entity.text }}</div>
            </div>
          </div>
        </a-drawer>
      </span>
    </div>
    <a-modal
      v-model:open="artifactPreviewOpen"
      :title="artifactPreview?.name || '技能产物'"
      :width="900"
      :footer="null"
    >
      <div v-if="artifactPreview?.kind === 'image'" class="artifact-preview">
        <img :src="artifactPreview.url" :alt="artifactPreview.name" />
      </div>
      <div v-else-if="artifactPreview?.kind === 'file' && isMarkdown(artifactPreview)" class="artifact-md">
        <a-spin :spinning="artifactLoading" />
        <pre v-if="artifactText">{{ artifactText }}</pre>
      </div>
      <div v-else class="artifact-download">
        <p>文件已生成，点击下载：</p>
        <a :href="artifactPreview?.url" :download="artifactPreview?.name" target="_blank" rel="noopener">
          {{ artifactPreview?.name }}
        </a>
      </div>
    </a-modal>
    <a-modal
      v-model:open="subGraphVisible"
      title="相关实体与关系"
      :width="800"
      :footer="null"
    >
      <GraphContainer
        :graphData="subGraphData"
        :color-by-domain="true"
        @paper-click="onPaperNodeClick"
      />
    </a-modal>
    <GraphNodeDrawer v-model:open="drawerOpen" :node="drawerNode" />
  </div>
</template>

<script setup>
import { ref, computed, reactive, watch } from 'vue'
import { useClipboard } from '@vueuse/core'
import { message } from 'ant-design-vue'
import {
  GlobalOutlined,
  FileTextOutlined,
  CopyOutlined,
  LikeOutlined,
  DislikeOutlined,
  DeleteOutlined,
  FileOutlined,
  ClockCircleOutlined,
  PictureOutlined,
} from '@ant-design/icons-vue'
import GraphContainer from '@/components/graph/GraphContainer.vue'
import GraphNodeDrawer from '@/components/graph/GraphNodeDrawer.vue'

const props = defineProps({
  message: Object,
  disabled: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['delete-turn'])

const msg = computed(() => props.message || {})

const groupedResults = computed(() => msg.value.groupedResults || {})

const skillArtifacts = computed(() => {
  const list = msg.value?.refs?.skill?.artifacts
  return Array.isArray(list) ? list : []
})

const artifactPreviewOpen = ref(false)
const artifactPreview = ref(null)
const artifactText = ref('')
const artifactLoading = ref(false)

const isMarkdown = (artifact) => {
  const name = (artifact?.name || '').toLowerCase()
  return name.endsWith('.md') || name.endsWith('.txt')
}

const openArtifact = async (artifact) => {
  if (!artifact) return
  if (artifact.kind === 'file' && !isMarkdown(artifact)) {
    window.open(artifact.url, '_blank', 'noopener')
    return
  }
  artifactPreview.value = artifact
  artifactPreviewOpen.value = true
  artifactText.value = ''
  if (artifact.kind === 'file' && isMarkdown(artifact)) {
    artifactLoading.value = true
    try {
      const res = await fetch(artifact.url)
      artifactText.value = await res.text()
    } catch (e) {
      artifactText.value = '预览失败，请尝试下载文件。'
    } finally {
      artifactLoading.value = false
    }
  }
}

// 使用 reactive 创建一个响应式对象来存储每个文件的抽屉状态
const openDetail = reactive({})

watch(
  groupedResults,
  (groups) => {
    for (const filename of Object.keys(groups)) {
      if (!(filename in openDetail)) {
        openDetail[filename] = false
      }
    }
  },
  { immediate: true, deep: true },
)
const { copy, isSupported } = useClipboard()

// 定义 copy 方法
const copyText = async (text) => {
  if (isSupported) {
    try {
      await copy(text)
      message.success('文本已复制到剪贴板')
    } catch (error) {
      console.error('复制失败:', error)
      message.error('复制失败，请手动复制')
    }
  } else {
    console.warn('浏览器不支持自动复制')
    message.warning('浏览器不支持自动复制，请手动复制')
  }
}

// 其他方法
const likeThisResponse = (msg) => {
  console.log('Like this response:', msg)
}

const dislikeThisResponse = (msg) => {
  console.log('Dislike this response:', msg)
}

const deleteThisTurn = (msg) => {
  if (props.disabled) return
  emit('delete-turn', msg.id)
}

const toggleDrawer = (filename) => {
  openDetail[filename] = !openDetail[filename]
}

const showRefs = computed(() => msg.value.role === 'received' && msg.value.status === 'finished')

const subGraphVisible = ref(false)
const subGraphData = ref(null)
const drawerOpen = ref(false)
const drawerNode = ref(null)

const onPaperNodeClick = (data) => {
  drawerNode.value = data
  drawerOpen.value = true
}


const openSubGraph = (msg) => {
  if (hasSubGraphData(msg)) {
    subGraphData.value = msg.refs.graph_base.results
    subGraphVisible.value = true
  } else {
    console.error('无法获取子图数据')
  }
}

const closeSubGraph = () => {
  subGraphVisible.value = false
}

const hasSubGraphData = (msg) => {
  return msg.refs &&
         msg.refs.graph_base &&
         msg.refs.graph_base.results.nodes.length > 0;
}

// 添加日期格式化函数
const formatDate = (timestamp) => {
  return new Date(timestamp * 1000).toLocaleString()
}

// 添加百分比计算函数
const getPercent = (value) => {
  return parseFloat((value * 100).toFixed(2))
}
</script>

<style lang="less" scoped>
.refs {
  display: flex;
  margin-bottom: 20px;
  color: var(--gray-500);
  font-size: 14px;
  gap: 10px;

  .item {
    background: var(--gray-100);
    color: var(--gray-800);
    padding: 2px 8px;
    border-radius: 8px;
    font-size: 14px;
    user-select: none;

    &.btn {
      cursor: pointer;
      &:hover {
        background: var(--gray-200);
      }
      &:active {
        background: var(--gray-300);
      }
    }

    &.delete-btn {
      color: #f56c6c;
      &:hover {
        background: #fef0f0;
      }
      &:active {
        background: #fde2e2;
      }
    }
  }

  .tags {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;

    .filetag {
      display: flex;
      align-items: center;
      gap: 5px;
    }

    .skill-artifact-tag {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: #eef8f4;
      color: #0d7a5f;
    }
  }
}

.artifact-preview {
  text-align: center;

  img {
    max-width: 100%;
    max-height: 70vh;
    object-fit: contain;
  }
}

.artifact-md pre {
  max-height: 70vh;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  background: #f9f9f9;
  padding: 12px;
  border-radius: 6px;
}

.artifact-download a {
  color: var(--main-600, #1677ff);
}

.retrieval-detail {
  .fileinfo {
    display: flex;
    justify-content: space-between;
    padding: 12px 16px;
    background-color: #f5f5f5;
    border-radius: 4px;
    margin-bottom: 16px;

    p {
      margin: 0;
      color: #666;
    }
  }

  .score-info {
    display: flex;
    flex-wrap: wrap;
    gap: 2rem;
    margin-bottom: 8px;

    span {
      display: flex;
      align-items: center;

      strong {
        margin-right: 8px;
        white-space: nowrap;
        color: #666;
      }

      .ant-progress {
        width: 170px;
        margin-bottom: 0;
        margin-inline: 10px;

        .ant-progress-bg {
          background-color: #666;
        }
      }
    }
  }

  .result-id {
    font-size: 12px;
    color: #999;
    margin-bottom: 8px;
  }

  .result-text {
    font-size: 14px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
    background-color: #f9f9f9;
    padding: 12px;
    border-radius: 4px;
    border: 1px solid #e8e8e8;
  }
}

.results-list {
  .result-item {
    border-bottom: 1px solid #f0f0f0;
    padding: 16px 0;

    &:last-child {
      border-bottom: none;
    }
  }

  .result-meta {
    margin-bottom: 12px;
  }
}
</style>