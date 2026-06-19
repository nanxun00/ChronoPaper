<template>
  <a-drawer
    :open="open"
    :title="title"
    width="480"
    placement="right"
    @close="emit('update:open', false)"
  >
    <template v-if="node">
      <a-tag v-if="node.taskDomain" color="blue" class="domain-tag">
        {{ node.taskDomain }}
      </a-tag>
      <p v-if="metaLine" class="meta-line">{{ metaLine }}</p>

      <template v-if="node.nodeType === 'Paper'">
        <h4 class="section-title">创新点</h4>
        <p class="innovation-text">{{ node.innovationSummary || '暂无创新点摘要' }}</p>
        <p v-if="node.paperId" class="paper-id">论文 ID：{{ node.paperId }}</p>
      </template>

      <template v-else-if="node.nodeType === 'Venue'">
        <p class="innovation-text">
          {{ venueDesc }}
        </p>
      </template>

      <template v-else>
        <h4 class="section-title">领域</h4>
        <p class="innovation-text">{{ node.taskDomain || '暂无' }}</p>
        <template v-if="node.description">
          <h4 class="section-title">描述</h4>
          <p class="innovation-text">{{ node.description }}</p>
        </template>
      </template>
    </template>
  </a-drawer>
</template>

<script setup>
import { computed } from 'vue'
import { buildMetaLine } from '@/utils/graphViz'

const props = defineProps({
  open: { type: Boolean, default: false },
  node: { type: Object, default: null },
})

const emit = defineEmits(['update:open'])

const title = computed(() => props.node?.label || '节点详情')

const metaLine = computed(() => {
  if (!props.node) return ''
  return buildMetaLine({
    venue: props.node.venue,
    year: props.node.year,
    type: props.node.nodeType,
    ccf_rank: props.node.ccfRank,
  })
})

const venueDesc = computed(() => {
  const bits = []
  if (props.node?.ccfRank && props.node.ccfRank !== 'None') {
    bits.push(`等级：${props.node.ccfRank}`)
  }
  if (props.node?.venueType) bits.push(props.node.venueType)
  return bits.join(' · ') || '会议/期刊节点'
})
</script>

<style scoped>
.domain-tag {
  margin-bottom: 12px;
}

.meta-line {
  color: #8c8c8c;
  margin-bottom: 16px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 8px;
}

.innovation-text {
  white-space: pre-wrap;
  line-height: 1.6;
  color: #333;
}

.paper-id {
  margin-top: 16px;
  font-size: 12px;
  color: #8c8c8c;
}
</style>
