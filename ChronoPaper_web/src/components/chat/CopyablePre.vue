<template>
  <div class="copyable-block">
    <div class="copyable-block__toolbar">
      <span class="copyable-block__lang">{{ langLabel }}</span>
      <div class="copyable-block__actions">
        <button
          type="button"
          class="copyable-block__btn"
          :title="copyTitle"
          :aria-label="copyTitle"
          @click="onCopy"
        >
          <svg
            class="copyable-block__icon"
            viewBox="0 0 24 24"
            width="16"
            height="16"
            fill="none"
            stroke="currentColor"
            stroke-width="1.5"
            aria-hidden="true"
          >
            <rect x="9" y="9" width="11" height="11" rx="1.5" />
            <path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1" />
          </svg>
          <span class="copyable-block__tooltip">复制</span>
        </button>
      </div>
    </div>
    <div class="copyable-block__body">
      <pre><slot /></pre>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { blockCopyLabel, copyTextToClipboard, langDisplayLabel } from '@/utils/copyBlock'

const props = defineProps({
  text: { type: String, default: '' },
  lang: { type: String, default: 'code' },
})

const langLabel = computed(() => langDisplayLabel(props.lang))
const copyTitle = computed(() => `复制${blockCopyLabel(props.lang)}`)

const onCopy = () => {
  void copyTextToClipboard(props.text)
}
</script>
