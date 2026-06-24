<template>
  <a-popover
    v-model:open="open"
    trigger="click"
    placement="topLeft"
    overlay-class-name="prompt-picker-popover"
    :arrow="false"
    @open-change="onOpenChange"
  >
    <template #content>
      <div class="prompt-panel">
        <a-input
          v-model:value="keyword"
          placeholder="搜索提示词标题或内容"
          allow-clear
          size="small"
          class="prompt-panel__search"
        >
          <template #prefix>
            <SearchOutlined class="prompt-panel__search-icon" />
          </template>
        </a-input>

        <div v-if="!filteredPrompts.length" class="prompt-panel__empty">
          {{ keyword.trim() ? '未找到匹配的提示词' : '暂无提示词' }}
          <RouterLink to="/setting?section=prompts" class="prompt-panel__link" @click="open = false">去设置添加</RouterLink>
        </div>

        <div v-else class="prompt-panel__list">
          <button
            v-for="item in filteredPrompts"
            :key="item.id"
            type="button"
            class="prompt-option"
            @click="selectPrompt(item)"
          >
            <span class="prompt-option__title">{{ item.title }}</span>
            <span class="prompt-option__preview">{{ previewText(item.content) }}</span>
          </button>
        </div>
      </div>
    </template>

    <button type="button" class="tool-chip" @click.prevent>
      <BulbOutlined />
      <span>提示词</span>
      <DownOutlined class="tool-chip__caret" />
    </button>
  </a-popover>
</template>

<script setup>
import { computed, ref } from 'vue'
import { BulbOutlined, DownOutlined, SearchOutlined } from '@ant-design/icons-vue'
import { useConfigStore } from '@/stores'

const emit = defineEmits(['select'])

const configStore = useConfigStore()
const open = ref(false)
const keyword = ref('')

const prompts = computed(() => {
  const raw = configStore.config?.custom_prompts
  if (!Array.isArray(raw)) return []
  return raw.filter((item) => item?.title && item?.content)
})

const filteredPrompts = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return prompts.value
  return prompts.value.filter((item) => {
    const title = String(item.title || '').toLowerCase()
    const content = String(item.content || '').toLowerCase()
    return title.includes(q) || content.includes(q)
  })
})

const previewText = (text) => {
  const trimmed = String(text || '').trim()
  if (!trimmed) return ''
  return trimmed.length > 80 ? `${trimmed.slice(0, 80)}…` : trimmed
}

const onOpenChange = (visible) => {
  if (visible) {
    keyword.value = ''
    configStore.refreshConfig()
  }
}

const selectPrompt = (item) => {
  emit('select', item.content)
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

.tool-chip__caret {
  font-size: 10px;
  opacity: 0.55;
}

.prompt-panel {
  width: 320px;
}

.prompt-panel__search {
  margin-bottom: 8px;
}

.prompt-panel__search-icon {
  color: #999;
}

.prompt-panel__empty {
  padding: 16px 4px;
  font-size: 13px;
  color: #888;
  text-align: center;
}

.prompt-panel__link {
  display: inline-block;
  margin-left: 6px;
}

.prompt-panel__list {
  max-height: 280px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.prompt-option {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  width: 100%;
  padding: 8px 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s;
}

.prompt-option:hover {
  background: #f5f7fa;
}

.prompt-option__title {
  font-size: 13px;
  font-weight: 600;
  color: #222;
}

.prompt-option__preview {
  font-size: 12px;
  line-height: 1.5;
  color: #888;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
