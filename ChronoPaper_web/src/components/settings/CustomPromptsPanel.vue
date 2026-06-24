<template>
  <div class="custom-prompts-panel">
    <p class="custom-prompts-panel__hint">
      在此维护常用输入提示词，可在聊天输入框工具栏中检索并一键填入。
      修改后即时保存到 <code>saves/config/config.yaml</code>，无需重启服务。
    </p>

    <div class="custom-prompts-panel__toolbar">
      <a-button type="primary" @click="openCreate">
        <PlusOutlined /> 新建提示词
      </a-button>
      <a-button :loading="saving" @click="saveAll" :disabled="!isDirty">保存全部</a-button>
    </div>

    <a-spin :spinning="loading">
      <a-empty v-if="!prompts.length && !loading" description="暂无提示词，点击「新建提示词」添加" />

      <div v-else class="prompt-list">
        <div v-for="item in prompts" :key="item.id" class="prompt-row">
          <div class="prompt-row__main">
            <div class="prompt-row__title">{{ item.title }}</div>
            <p class="prompt-row__preview">{{ previewText(item.content) }}</p>
          </div>
          <div class="prompt-row__actions">
            <a-button type="text" @click="openEdit(item)"><EditOutlined /></a-button>
            <a-popconfirm title="确认删除该提示词？" ok-text="删除" cancel-text="取消" @confirm="removePrompt(item.id)">
              <a-button type="text" danger><DeleteOutlined /></a-button>
            </a-popconfirm>
          </div>
        </div>
      </div>
    </a-spin>

    <a-modal
      v-model:open="editor.visible"
      :title="editor.mode === 'edit' ? '编辑提示词' : '新建提示词'"
      ok-text="确定"
      cancel-text="取消"
      :ok-button-props="{ disabled: !editor.title.trim() || !editor.content.trim() }"
      @ok="confirmEditor"
      @cancel="closeEditor"
    >
      <a-form layout="vertical">
        <a-form-item label="标题" required>
          <a-input v-model:value="editor.title" placeholder="例如：论文总结、创新点分析" :maxlength="80" show-count />
        </a-form-item>
        <a-form-item label="提示词内容" required>
          <a-textarea
            v-model:value="editor.content"
            :rows="8"
            :maxlength="4000"
            show-count
            placeholder="输入后会填入聊天框，可继续编辑再发送"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import { useConfigStore } from '@/stores'

const configStore = useConfigStore()
const loading = ref(false)
const saving = ref(false)
const prompts = ref([])
const snapshot = ref('')

const editor = ref({
  visible: false,
  mode: 'create',
  id: '',
  title: '',
  content: '',
})

const isDirty = computed(() => JSON.stringify(prompts.value) !== snapshot.value)

const previewText = (text) => {
  const trimmed = (text || '').trim()
  if (!trimmed) return '（空内容）'
  return trimmed.length > 120 ? `${trimmed.slice(0, 120)}…` : trimmed
}

const generateId = () => {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
  let id = 'prompt-'
  for (let i = 0; i < 8; i += 1) {
    id += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return id
}

const normalizePrompts = (raw) => {
  if (!Array.isArray(raw)) return []
  return raw
    .filter((item) => item && typeof item === 'object')
    .map((item) => ({
      id: String(item.id || generateId()),
      title: String(item.title || '').trim(),
      content: String(item.content || '').trim(),
    }))
    .filter((item) => item.title && item.content)
}

const syncFromStore = () => {
  const list = normalizePrompts(configStore.config?.custom_prompts)
  prompts.value = list
  snapshot.value = JSON.stringify(list)
}

const persist = async () => {
  saving.value = true
  try {
    await configStore.setConfigValue('custom_prompts', prompts.value)
    snapshot.value = JSON.stringify(prompts.value)
    message.success('提示词已保存')
  } catch (err) {
    message.error(err.message || '保存失败')
  } finally {
    saving.value = false
  }
}

const saveAll = () => persist()

const openCreate = () => {
  editor.value = {
    visible: true,
    mode: 'create',
    id: '',
    title: '',
    content: '',
  }
}

const openEdit = (item) => {
  editor.value = {
    visible: true,
    mode: 'edit',
    id: item.id,
    title: item.title,
    content: item.content,
  }
}

const closeEditor = () => {
  editor.value.visible = false
}

const confirmEditor = async () => {
  const title = editor.value.title.trim()
  const content = editor.value.content.trim()
  if (!title || !content) {
    message.warning('请填写标题和内容')
    return
  }

  if (editor.value.mode === 'edit') {
    prompts.value = prompts.value.map((item) =>
      item.id === editor.value.id ? { ...item, title, content } : item,
    )
  } else {
    prompts.value = [...prompts.value, { id: generateId(), title, content }]
  }

  editor.value.visible = false
  await persist()
}

const removePrompt = async (id) => {
  prompts.value = prompts.value.filter((item) => item.id !== id)
  await persist()
}

defineExpose({ syncFromStore })
</script>

<style scoped lang="less">
.custom-prompts-panel__hint {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--gray-700);
  line-height: 1.6;
}

.custom-prompts-panel__toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.prompt-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.prompt-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid var(--gray-300);
  border-radius: 8px;
  background: #fff;
}

.prompt-row__main {
  flex: 1;
  min-width: 0;
}

.prompt-row__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-900);
}

.prompt-row__preview {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--gray-600);
  white-space: pre-wrap;
  word-break: break-word;
}

.prompt-row__actions {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}
</style>
