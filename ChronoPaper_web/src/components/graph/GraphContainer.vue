<template>
  <div class="graph-container" ref="container"></div>
</template>

<script setup>
import { Graph } from '@antv/g6'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  graphData: {
    type: Object,
    required: true,
    default: () => ({ nodes: [], edges: [] }),
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

const initGraph = () => {
  if (!container.value) return false

  graphInstance = new Graph({
    container: container.value,
    width: container.value.offsetWidth || container.value.clientWidth,
    height: container.value.offsetHeight || container.value.clientHeight,
    autoFit: true,
    autoResize: true,
    layout: {
      type: 'd3-force',
      preventOverlap: true,
      kr: 20,
      collide: {
        strength: 1.0,
      },
    },
    node: {
      type: 'circle',
      style: {
        labelText: (d) => d.data.label,
        size: 70,
      },
      palette: {
        field: 'label',
        color: 'tableau',
      },
    },
    edge: {
      type: 'line',
      style: {
        labelText: (d) => d.data.label,
        labelBackground: '#fff',
        endArrow: true,
      },
    },
    behaviors: ['drag-element', 'zoom-canvas', 'drag-canvas'],
  })
  return true
}

const renderGraph = () => {
  if (!container.value) return
  if (!props.graphData?.nodes?.length) {
    destroyGraph()
    return
  }

  if (!graphInstance && !initGraph()) return

  const formattedData = {
    nodes: props.graphData.nodes.map((node) => ({
      id: node.id,
      data: { label: node.name },
    })),
    edges: props.graphData.edges.map((edge) => ({
      source: edge.source_id,
      target: edge.target_id,
      data: { label: edge.type },
    })),
  }

  graphInstance.setData(formattedData)
  graphInstance.render()
}

const handleResize = () => {
  renderGraph()
}

onMounted(() => {
  nextTick(() => renderGraph())
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  destroyGraph()
})

watch(() => props.graphData, () => nextTick(renderGraph), { deep: true })
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
