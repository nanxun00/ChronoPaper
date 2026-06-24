<template>
  <a-modal
    v-model:open="modalVisible"
    title="文档生成"
    :width="600"
    @ok="handleGenerate"
    @cancel="handleCancel"
  >
    <div class="mcp-document-generator">
      <a-form :model="formState" layout="vertical">
        <a-form-item label="文档标题" name="title">
          <a-input v-model:value="formState.title" placeholder="请输入文档标题" />
        </a-form-item>

        <a-form-item label="文档内容" name="content">
          <a-textarea
            v-model:value="formState.content"
            placeholder="请输入或粘贴文档内容"
            :rows="8"
          />
        </a-form-item>

        <a-form-item label="输出格式" name="format">
          <a-radio-group v-model:value="formState.format">
            <a-radio value="docx">DOCX</a-radio>
            <a-radio value="pdf">PDF</a-radio>
          </a-radio-group>
        </a-form-item>

        <a-form-item label="文档模板" name="template">
          <a-select v-model:value="formState.template">
            <a-select-option value="academic">学术论文</a-select-option>
            <a-select-option value="report">技术报告</a-select-option>
            <a-select-option value="memo">备忘录</a-select-option>
            <a-select-option value="letter">正式信函</a-select-option>
            <a-select-option value="thesis">学位论文</a-select-option>
            <a-select-option value="presentation">演示文稿</a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="字体设置" name="fontFamily">
          <a-select v-model:value="formState.fontFamily">
            <a-select-option value="Times New Roman">Times New Roman</a-select-option>
            <a-select-option value="Arial">Arial</a-select-option>
            <a-select-option value="Calibri">Calibri</a-select-option>
            <a-select-option value="SimSun">宋体</a-select-option>
            <a-select-option value="Microsoft YaHei">微软雅黑</a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="字号" name="fontSize">
          <a-input-number v-model:value="formState.fontSize" :min="8" :max="24" />
        </a-form-item>

        <a-form-item label="行距" name="lineSpacing">
          <a-select v-model:value="formState.lineSpacing">
            <a-select-option :value="1.0">单倍行距</a-select-option>
            <a-select-option :value="1.5">1.5倍行距</a-select-option>
            <a-select-option :value="2.0">双倍行距</a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item name="includeToc">
          <a-checkbox v-model:checked="formState.includeToc">包含目录</a-checkbox>
        </a-form-item>

        <a-form-item name="includePageNumbers">
          <a-checkbox v-model:checked="formState.includePageNumbers">包含页码</a-checkbox>
        </a-form-item>
      </a-form>
    </div>
  </a-modal>
</template>

<script setup>
import { reactive, computed } from 'vue'
import { message } from 'ant-design-vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:visible', 'generate-document'])

const modalVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const formState = reactive({
  title: '',
  content: '',
  format: 'docx',
  template: 'academic',
  fontFamily: 'Times New Roman',
  fontSize: 12,
  lineSpacing: 1.5,
  includeToc: false,
  includePageNumbers: true
})

const handleGenerate = () => {
  if (!formState.title.trim()) {
    message.error('请输入文档标题')
    return
  }
  if (!formState.content.trim()) {
    message.error('请输入文档内容')
    return
  }

  emit('generate-document', { ...formState })
  modalVisible.value = false
  
  // 重置表单
  formState.title = ''
  formState.content = ''
}

const handleCancel = () => {
  modalVisible.value = false
}
</script>

<style scoped>
.mcp-document-generator {
  max-height: 70vh;
  overflow-y: auto;
}
</style>
