<template>
  <div v-if="visible" class="translate-float">
    <div class="translate-float__header">
      <span class="translate-float__title">
        <TranslationOutlined /> 划词翻译
        <a-tag size="small" color="blue">{{ modelName }}</a-tag>
      </span>
      <a-space>
        <a-select v-model:value="targetLang" size="small" style="width: 100px" :disabled="loading">
          <a-select-option value="zh">译成中文</a-select-option>
          <a-select-option value="en">译成英文</a-select-option>
        </a-select>
        <a-button type="text" size="small" @click="retranslate" :disabled="!sourceText || loading">重译</a-button>
        <a-button type="text" size="small" @click="hidePanel"><CloseOutlined /></a-button>
      </a-space>
    </div>

    <div class="translate-float__body">
      <div v-if="sourceText" class="translate-block">
        <div class="translate-label">原文</div>
        <p class="translate-source">{{ sourceText }}</p>
      </div>
      <div class="translate-block">
        <div class="translate-label">译文</div>
        <a-spin :spinning="loading && !result">
          <p v-if="result" class="translate-result">{{ result }}<span v-if="loading" class="cursor">▍</span></p>
          <p v-else-if="error" class="translate-error">{{ error }}</p>
          <p v-else class="translate-placeholder">翻译中…</p>
        </a-spin>
      </div>
    </div>

    <div class="translate-float__footer">
      <RouterLink to="/tools/translate">打开翻译页</RouterLink>
    </div>
  </div>
</template>

<script setup>
import { onMounted, watch } from 'vue'
import { CloseOutlined, TranslationOutlined } from '@ant-design/icons-vue'
import { storeToRefs } from 'pinia'
import { getTranslateConfig } from '@/api/translate'
import { useTranslateStore } from '@/stores'

const translateStore = useTranslateStore()
const { visible, sourceText, result, loading, error, targetLang, modelName } = storeToRefs(translateStore)

onMounted(async () => {
  try {
    const cfg = await getTranslateConfig()
    translateStore.modelName = cfg.model || 'deepseek-chat'
  } catch {
    // ignore
  }
})

const hidePanel = () => translateStore.hidePanel()

const retranslate = () => {
  if (sourceText.value) {
    translateStore.translateText(sourceText.value, { targetLang: targetLang.value })
  }
}

watch(targetLang, (lang, prev) => {
  if (lang !== prev && sourceText.value && visible.value) {
    translateStore.translateText(sourceText.value, { targetLang: lang })
  }
})
</script>

<style scoped lang="less">
.translate-float {
  position: fixed;
  z-index: 1100;
  width: min(420px, calc(100vw - 32px));
  max-height: min(480px, calc(100vh - 100px));
  background: #fff;
  border: 1px solid var(--gray-300);
  border-radius: 12px;
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.translate-float__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--gray-200);
  background: #fafafa;
}

.translate-float__title {
  font-weight: 600;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.translate-float__body {
  padding: 12px;
  overflow-y: auto;
  flex: 1;
}

.translate-block + .translate-block {
  margin-top: 12px;
}

.translate-label {
  font-size: 12px;
  color: var(--gray-700);
  margin-bottom: 4px;
}

.translate-source {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--gray-800);
  max-height: 96px;
  overflow-y: auto;
  background: #f5f5f5;
  padding: 8px;
  border-radius: 6px;
}

.translate-result {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: var(--gray-900);
  white-space: pre-wrap;
}

.translate-error {
  margin: 0;
  color: #cf1322;
  font-size: 13px;
}

.translate-placeholder {
  margin: 0;
  color: var(--gray-600);
  font-size: 13px;
}

.cursor {
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

.translate-float__footer {
  padding: 8px 12px;
  border-top: 1px solid var(--gray-200);
  font-size: 12px;
}
</style>
