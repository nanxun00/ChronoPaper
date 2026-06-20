<template>
  <div v-if="images.length" class="message-images">
    <button
      v-for="(imageUrl, index) in images"
      :key="`${imageUrl}-${index}`"
      type="button"
      class="message-image-btn"
      @click="openPreview(imageUrl, index)"
    >
      <img :src="imageUrl" :alt="imageAlt(index)" class="message-image" />
      <span class="message-image-btn__hint">点击预览</span>
    </button>

    <a-modal
      v-model:open="previewOpen"
      :title="previewTitle"
      :width="920"
      centered
      destroy-on-close
      class="message-image-modal"
    >
      <div class="message-image-preview">
        <img :src="previewUrl" :alt="previewTitle" />
      </div>
      <template #footer>
        <a-button @click="previewOpen = false">关闭</a-button>
        <a-button type="primary" :loading="downloading" @click="downloadCurrent">
          <DownloadOutlined /> 下载图片
        </a-button>
      </template>
    </a-modal>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { DownloadOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'

const props = defineProps({
  images: { type: Array, default: () => [] },
  namePrefix: { type: String, default: 'generated-image' },
})

const previewOpen = ref(false)
const previewUrl = ref('')
const previewIndex = ref(0)
const downloading = ref(false)

const previewTitle = computed(() => `${props.namePrefix}-${previewIndex.value + 1}`)

const imageAlt = (index) => `消息图片 ${index + 1}`

const guessExt = (url) => {
  const clean = String(url || '').split('?')[0].split('#')[0]
  const ext = clean.slice(clean.lastIndexOf('.')).toLowerCase()
  if (['.png', '.jpg', '.jpeg', '.webp', '.gif'].includes(ext)) return ext
  return '.png'
}

const openPreview = (url, index) => {
  previewUrl.value = url
  previewIndex.value = index
  previewOpen.value = true
}

const downloadCurrent = async () => {
  const url = previewUrl.value
  if (!url) return

  downloading.value = true
  const filename = `${previewTitle.value}${guessExt(url)}`

  try {
    const response = await fetch(url)
    if (!response.ok) {
      throw new Error(`下载失败 (${response.status})`)
    }
    const blob = await response.blob()
    const objectUrl = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = objectUrl
    anchor.download = filename
    anchor.click()
    URL.revokeObjectURL(objectUrl)
    message.success('图片已开始下载')
  } catch (err) {
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    anchor.target = '_blank'
    anchor.rel = 'noopener'
    anchor.click()
    message.info('已尝试下载，若未成功请在新页面中另存')
  } finally {
    downloading.value = false
  }
}
</script>

<style scoped lang="less">
.message-images {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 4px 0 8px;
}

.message-image-btn {
  position: relative;
  padding: 0;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  background: #fafafa;
  cursor: zoom-in;
  overflow: hidden;
  transition: border-color 0.15s, box-shadow 0.15s;

  &:hover {
    border-color: var(--main-400, #69b1ff);
    box-shadow: 0 2px 8px rgba(22, 119, 255, 0.12);

    .message-image-btn__hint {
      opacity: 1;
    }
  }
}

.message-image {
  display: block;
  max-width: 220px;
  max-height: 220px;
  width: auto;
  height: auto;
  object-fit: contain;
}

.message-image-btn__hint {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 4px 8px;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.55));
  color: #fff;
  font-size: 11px;
  text-align: center;
  opacity: 0;
  transition: opacity 0.15s;
}

.message-image-preview {
  display: flex;
  justify-content: center;
  align-items: center;
  max-height: 70vh;
  overflow: auto;
  background: #f5f5f5;
  border-radius: 8px;

  img {
    display: block;
    max-width: 100%;
    max-height: 70vh;
    object-fit: contain;
  }
}
</style>
