<template>
  <a-popover
    v-model:open="open"
    trigger="click"
    placement="topLeft"
    overlay-class-name="translate-toggle-popover"
    :arrow="false"
  >
    <template #content>
      <div class="translate-panel">
        <div
          class="translate-option"
          :class="{ 'translate-option--active': !modelValue }"
          @click="selectOff"
        >
          <span class="translate-option__title">关闭</span>
          <span class="translate-option__hint">恢复普通对话</span>
        </div>
        <div class="translate-panel__divider" />
        <div
          v-for="opt in langOptions"
          :key="opt.value"
          class="translate-option"
          :class="{ 'translate-option--active': modelValue && targetLang === opt.value }"
          @click="selectLang(opt.value)"
        >
          <span class="translate-option__title">{{ opt.label }}</span>
          <span class="translate-option__hint">发送内容译为{{ opt.short }}</span>
        </div>
      </div>
    </template>

    <button
      type="button"
      class="tool-chip"
      :class="{ 'tool-chip--active': modelValue }"
      @click.prevent
    >
      <TranslationOutlined />
      <span>{{ displayLabel }}</span>
      <DownOutlined class="tool-chip__caret" />
    </button>
  </a-popover>
</template>

<script setup>
import { computed, ref } from 'vue'
import { TranslationOutlined, DownOutlined } from '@ant-design/icons-vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  targetLang: { type: String, default: 'zh' },
})

const emit = defineEmits(['update:modelValue', 'update:targetLang'])

const open = ref(false)

const langOptions = [
  { value: 'zh', label: '简体中文', short: '中文' },
  { value: 'en', label: 'English', short: '英文' },
  { value: 'ja', label: '日本語', short: '日文' },
]

const displayLabel = computed(() => {
  if (!props.modelValue) return '翻译'
  const opt = langOptions.find((item) => item.value === props.targetLang)
  return opt ? `翻译 · ${opt.short}` : '翻译'
})

const selectOff = () => {
  emit('update:modelValue', false)
  open.value = false
}

const selectLang = (lang) => {
  emit('update:targetLang', lang)
  emit('update:modelValue', true)
  open.value = false
}
</script>

<style scoped lang="less">
.tool-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: #555;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.tool-chip:hover {
  background: #f3f5f7;
  color: #222;
}

.tool-chip--active {
  background: #eef5ff;
  color: var(--main-700, #1677ff);
}

.tool-chip__caret {
  font-size: 10px;
  opacity: 0.55;
}

.translate-panel {
  min-width: 200px;
}

.translate-panel__divider {
  height: 1px;
  margin: 6px 0;
  background: #f0f0f0;
}

.translate-option {
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.translate-option:hover {
  background: #f5f7fa;
}

.translate-option--active {
  background: #eef5ff;
}

.translate-option__title {
  display: block;
  font-size: 13px;
  color: #222;
}

.translate-option__hint {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: #888;
}
</style>
