<template>
  <button 
    type="button" 
    class="tool-chip" 
    :class="{ 'tool-chip--active': mcpEnabled }"
    @click="toggleMCP"
  >
    <FileTextOutlined />
    <span>文档生成</span>
  </button>
</template>

<script setup>
import { computed } from 'vue'
import { FileTextOutlined } from '@ant-design/icons-vue'

const props = defineProps({
  mcpEnabled: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:mcpEnabled'])

const toggleMCP = () => {
  emit('update:mcpEnabled', !props.mcpEnabled)
}
</script>

<style scoped>
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
</style>
