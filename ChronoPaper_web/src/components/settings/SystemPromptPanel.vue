<template>
  <div class="system-prompt-panel">
    <p class="system-prompt-panel__hint">
      此处配置的内容会作为<strong>全局系统提示词</strong>注入每次对话（与技能专用提示词叠加）。
      修改后即时保存到 <code>saves/config/config.yaml</code>，无需重启服务。
    </p>
    <a-textarea
      v-model:value="draft"
      :rows="14"
      :maxlength="8000"
      show-count
      placeholder="例如：你是 ChronoPaper 科研助手，回答应简洁准确……"
      class="system-prompt-panel__textarea"
    />
    <div class="system-prompt-panel__actions">
      <a-button :loading="saving" type="primary" @click="savePrompt">保存</a-button>
      <a-button :disabled="!isDirty" @click="resetDraft">撤销修改</a-button>
      <a-button danger @click="confirmResetDefault">恢复默认</a-button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Modal, message } from 'ant-design-vue'
import { useConfigStore } from '@/stores'

const DEFAULT_PROMPT =
  '你是 ChronoPaper 科研助手，帮助用户进行文献检索、论文阅读、知识库问答与学术写作。回答应准确、结构化；引用资料时注明来源，不确定时请明确说明。'

const configStore = useConfigStore()
const draft = ref('')
const saving = ref(false)

const storedPrompt = computed(() => configStore.config?.chat_system_prompt ?? DEFAULT_PROMPT)

const isDirty = computed(() => draft.value !== storedPrompt.value)

const syncFromStore = () => {
  draft.value = storedPrompt.value
}

watch(
  () => configStore.config?.chat_system_prompt,
  () => {
    if (!isDirty.value) {
      syncFromStore()
    }
  },
  { immediate: true },
)

const savePrompt = async () => {
  const text = draft.value.trim()
  if (!text) {
    message.warning('系统提示词不能为空')
    return
  }
  saving.value = true
  try {
    await configStore.setConfigValue('chat_system_prompt', text)
    message.success('系统提示词已保存')
  } catch (err) {
    message.error(err.message || '保存失败')
  } finally {
    saving.value = false
  }
}

const resetDraft = () => {
  syncFromStore()
}

const confirmResetDefault = () => {
  Modal.confirm({
    title: '恢复默认系统提示词？',
    content: '将覆盖当前编辑内容并立即保存。',
    okText: '恢复',
    cancelText: '取消',
    onOk: async () => {
      draft.value = DEFAULT_PROMPT
      saving.value = true
      try {
        await configStore.setConfigValue('chat_system_prompt', DEFAULT_PROMPT)
        message.success('已恢复默认提示词')
      } catch (err) {
        message.error(err.message || '保存失败')
      } finally {
        saving.value = false
      }
    },
  })
}

defineExpose({ syncFromStore })
</script>

<style scoped>
.system-prompt-panel__hint {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--gray-700);
  line-height: 1.6;
}

.system-prompt-panel__textarea {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
}

.system-prompt-panel__actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
</style>
