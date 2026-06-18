<template>
  <div class="translate-page layout-container">
    <HeaderComponent
      title="智能翻译"
      description="基于 DeepSeek 的学术文献翻译，支持流式输出。在文献预览中划词也会自动弹出翻译面板。"
    />

    <div class="translate-panel card">
      <a-form layout="vertical">
        <a-form-item label="目标语言">
          <a-select v-model:value="targetLang" style="width: 160px">
            <a-select-option value="zh">简体中文</a-select-option>
            <a-select-option value="en">English</a-select-option>
            <a-select-option value="ja">日本語</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="待翻译文本">
          <a-textarea v-model:value="inputText" :rows="6" placeholder="粘贴或输入需要翻译的段落…" />
        </a-form-item>
        <a-space>
          <a-button type="primary" :loading="loading" @click="handleTranslate">开始翻译</a-button>
          <a-button @click="clearAll">清空</a-button>
        </a-space>
      </a-form>

      <a-divider />

      <div v-if="sourceText" class="result-section">
        <h4>原文</h4>
        <p class="source-box">{{ sourceText }}</p>
        <h4>译文 <a-tag color="blue">{{ modelName }}</a-tag></h4>
        <p class="result-box">
          {{ result }}<span v-if="loading" class="cursor">▍</span>
        </p>
        <p v-if="error" class="error-text">{{ error }}</p>
      </div>
      <a-empty v-else description="输入文本后点击「开始翻译」" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import HeaderComponent from '@/components/common/HeaderComponent.vue'
import { getTranslateConfig } from '@/api/translate'
import { useTranslateStore } from '@/stores'

const translateStore = useTranslateStore()
const { sourceText, result, loading, error, targetLang, modelName } = storeToRefs(translateStore)

const inputText = ref('')

onMounted(async () => {
  try {
    const cfg = await getTranslateConfig()
    translateStore.modelName = cfg.model || 'deepseek-chat'
  } catch {
    // ignore
  }
})

const handleTranslate = () => {
  translateStore.translateText(inputText.value, { targetLang: targetLang.value })
}

const clearAll = () => {
  inputText.value = ''
  translateStore.clear()
}
</script>

<style scoped lang="less">
.translate-page {
  padding-bottom: 24px;
}

.translate-panel {
  margin: 0 24px;
  padding: 20px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid var(--gray-300);
}

.result-section h4 {
  margin: 12px 0 8px;
  font-size: 14px;
}

.source-box,
.result-box {
  padding: 12px;
  border-radius: 8px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.source-box {
  background: #f5f5f5;
  color: var(--gray-800);
}

.result-box {
  background: #f6ffed;
  border: 1px solid #b7eb8f;
  min-height: 80px;
}

.error-text {
  color: #cf1322;
}

.cursor {
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}
</style>
