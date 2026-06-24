<template>
  <div class="tools-container layout-container">
    <HeaderComponent
      title="工具箱"
      description="文档处理、翻译、智能分析等实用工具集合。"
    />

    <div class="tools-grid">
      <div
        v-for="tool in allTools"
        :key="tool.id"
        class="tool-card"
        @click="navigateToTool(tool)"
      >
        <div class="tool-header">
          <h3>{{ tool.title }}</h3>
        </div>
        <div class="tool-info">
          <p>{{ tool.description }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import HeaderComponent from '@/components/common/HeaderComponent.vue'

const BUILTIN_TOOLS = [
  {
    id: 'builtin-translate',
    name: 'translate',
    title: '智能翻译',
    description: '基于 DeepSeek 的学术文献翻译，支持流式输出与划词翻译。',
    builtin: true,
  },
  {
    id: 'builtin-smartbi',
    name: 'smartbi',
    title: '智能分析',
    description: '智能分析数据并生成可视化图表。',
    builtin: true,
  },
  {
    id: 'builtin-text-chunking',
    name: 'text-chunking',
    title: '文本分块',
    description: '将文本分块以更好地理解。可以输入文本或者上传文件。',
    builtin: true,
  },
  {
    id: 'builtin-pdf2txt',
    name: 'pdf2txt',
    title: 'PDF转文本',
    description: '将 PDF 文件转换为文本。',
    builtin: true,
  },
]

const router = useRouter()

const allTools = computed(() => BUILTIN_TOOLS)
const navigateToTool = (tool) => {
  router.push(`/tools/${tool.name}`)
}
</script>

<style scoped lang="less">
.tools-container {
  padding: 0;
}

.tools-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 20px;
  padding: 20px;

  .tool-card {
    display: flex;
    flex-direction: column;
    background-color: white;
    border: 1px solid var(--gray-300);
    border-radius: 8px;
    padding: 20px;
    transition: transform 0.3s ease, box-shadow 0.3s ease;
    cursor: pointer;

    &:hover {
      transform: translateY(-1px);
      box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
    }

    .tool-header {
      display: flex;
      align-items: center;
      margin-bottom: 15px;
      font-size: 1rem;

      h3 {
        margin: 0;
      }
    }

    .tool-info {
      flex-grow: 1;

      p {
        margin: 0;
        color: var(--gray-800);
      }
    }
  }
}
</style>
