<template>
  <div class="graph-filter-panel" @mousedown.stop @click.stop>
    <div class="panel-title">图谱过滤</div>

    <div class="panel-section">
      <div class="section-label">节点</div>
      <div
        v-for="item in GRAPH_NODE_TYPE_TOGGLES"
        :key="item.key"
        class="filter-row"
      >
        <span class="filter-label">{{ item.label }}</span>
        <a-switch
          :checked="nodeTypes[item.key]"
          size="small"
          @change="(checked) => onNodeTypeChange(item.key, checked)"
        />
      </div>
    </div>

    <div class="panel-section">
      <div class="section-label">关系</div>
      <div
        v-for="item in GRAPH_REL_TYPE_TOGGLES"
        :key="item.key"
        class="filter-row"
      >
        <span class="filter-label">{{ item.label }}</span>
        <a-switch
          :checked="relTypes[item.key]"
          size="small"
          @change="(checked) => onRelTypeChange(item.key, checked)"
        />
      </div>
      <div class="filter-row">
        <span class="filter-label">引用</span>
        <a-switch
          :checked="includeCite"
          size="small"
          @change="onIncludeCiteChange"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import {
  GRAPH_NODE_TYPE_TOGGLES,
  GRAPH_REL_TYPE_TOGGLES,
} from '@/utils/graphViz'

const nodeTypes = defineModel('nodeTypes', { type: Object, required: true })
const relTypes = defineModel('relTypes', { type: Object, required: true })
const includeCite = defineModel('includeCite', { type: Boolean, default: false })

const onNodeTypeChange = (key, checked) => {
  nodeTypes.value = { ...nodeTypes.value, [key]: checked }
}

const onRelTypeChange = (key, checked) => {
  relTypes.value = { ...relTypes.value, [key]: checked }
}

const onIncludeCiteChange = (checked) => {
  includeCite.value = checked
}
</script>

<style scoped>
.graph-filter-panel {
  position: absolute;
  left: 16px;
  bottom: 16px;
  z-index: 10;
  min-width: 168px;
  max-width: 220px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 10px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  backdrop-filter: blur(6px);
  user-select: none;
}

.panel-title {
  font-size: 12px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.75);
  margin-bottom: 8px;
}

.panel-section + .panel-section {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.section-label {
  font-size: 11px;
  color: rgba(0, 0, 0, 0.45);
  margin-bottom: 4px;
}

.filter-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 26px;
}

.filter-label {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.72);
  line-height: 1.2;
}
</style>
