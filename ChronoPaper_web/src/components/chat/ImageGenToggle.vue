<template>
  <button
    type="button"
    class="tool-chip"
    :class="{ 'tool-chip--active': modelValue }"
    @click="toggle"
  >
    <PictureOutlined />
    <span>{{ modelValue ? '图像生成' : '图像生成' }}</span>
  </button>
</template>

<script setup>
import { PictureOutlined } from '@ant-design/icons-vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const toggle = () => {
  emit('update:modelValue', !props.modelValue)
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
  background: #f6ffed;
  color: #389e0d;
}
</style>
