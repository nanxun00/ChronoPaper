<template>
  <div class="copyable-block">
    <button
      type="button"
      class="copyable-block__btn"
      :title="copyTitle"
      @click="onCopy"
    >
      复制
    </button>
    <pre><slot /></pre>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { blockCopyLabel, copyTextToClipboard } from '@/utils/copyBlock'

const props = defineProps({
  text: { type: String, default: '' },
  lang: { type: String, default: 'code' },
})

const copyTitle = computed(() => `复制${blockCopyLabel(props.lang)}`)

const onCopy = () => {
  void copyTextToClipboard(props.text)
}
</script>

<style scoped>
.copyable-block {
  position: relative;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  background: #f6f8fa;
  overflow: hidden;
}

.copyable-block__btn {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 2;
  padding: 2px 10px;
  border: 1px solid #d0d7de;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.92);
  color: #57606a;
  font-size: 12px;
  line-height: 20px;
  cursor: pointer;
}

.copyable-block__btn:hover {
  background: #fff;
  color: var(--main-700, #1677ff);
  border-color: var(--main-300, #91caff);
}

.copyable-block pre {
  margin: 0;
  max-height: 480px;
  overflow: auto;
  padding: 2.5rem 10px 10px;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  background: transparent;
  border: none;
}
</style>
