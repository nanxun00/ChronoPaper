<template>
  <div class="graph-container" ref="container"></div>
</template>

<script setup>
import { Graph } from '@antv/g6'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { createGraphOptions, formatGraphPayload } from '@/utils/graphViz'

const props = defineProps({
  graphData: {
    type: Object,
    required: true,
    default: () => ({ nodes: [], edges: [] }),
  },
  showEdgeLabels: {
    type: Boolean,
    default: false,
  },
})

const container = ref(null)
let graphInstance = null

const destroyGraph = () => {
  if (graphInstance) {
    graphInstance.destroy()
    graphInstance = null
  }
}

const renderGraph = () => {
  if (!container.value) return
  if (!props.graphData?.nodes?.length) {
    destroyGraph()
    return
  }

  destroyGraph()
  graphInstance = new Graph(
    createGraphOptions(container.value, {
      showEdgeLabels: props.showEdgeLabels,
      maxLabelLen: 16,
    }),
  )
  graphInstance.setData(
    formatGraphPayload(props.graphData, { showEdgeLabels: props.showEdgeLabels }),
  )
  graphInstance.render()
}

const handleResize = () => {
  if (!graphInstance || !container.value) return
  graphInstance.setSize(
    container.value.offsetWidth || container.value.clientWidth,
    container.value.offsetHeight || container.value.clientHeight,
  )
  graphInstance.fitView()
}

onMounted(() => {
  nextTick(() => renderGraph())
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  destroyGraph()
})

watch(
  () => [props.graphData, props.showEdgeLabels],
  () => nextTick(renderGraph),
  { deep: true },
)
</script>

<style scoped>
.graph-container {
  background: #f7f7f7;
  border-radius: 16px;
  width: 100%;
  height: 600px;
  overflow: hidden;
}
</style>
