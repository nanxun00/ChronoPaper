<template>
  <div class="database-empty" v-if="!showPage">
    <a-empty>
      <template #description>
        <span>
          前往 <router-link to="/setting" style="color: var(--main-color); font-weight: bold;">设置</router-link> 页面配置图数据库。
        </span>
      </template>
    </a-empty>
  </div>
  <div class="graph-container layout-container" v-else>
    <HeaderComponent title="图数据库"
      :description="`${graphInfo?.database_name || ''} - 共 ${graphInfo?.entity_count || 0} 实体，${graphInfo?.relationship_count || 0} 个关系`">
      <template #actions>
        <div class="status-wrapper">
          <div class="status-indicator" :class="graphStatusClass"></div>
        </div>
        <!-- <input v-model="state.fileNameInput" placeholder="输入要删除的文件名" style="width: 200px" @keydown.enter="deleteFile"
          class="inputFile" />
        <a-button type="primary" danger @click="deleteFile">删除文件</a-button> -->
        <a-button type="primary" danger @click="deleteFiles">删除所有文件</a-button>
        <a-button type="primary" @click="state.showModal = true">
          <UploadOutlined /> 上传文件
        </a-button>
      </template>
    </HeaderComponent>

    <div class="actions">
      <div class="actions-left">
        <input v-model="state.searchInput" placeholder="输入要查询的实体" style="width: 200px" @keydown.enter="onSearch" />
        <a-button type="primary" :loading="state.searchLoading" @click="onSearch">
          检索实体
        </a-button>
        <a-button type="primary" danger @click="deleteofFile">删除实体</a-button>
      </div>
      <div class="actions-right">
        <a-select
          v-model:value="state.selectedDomain"
          allow-clear
          placeholder="按领域筛选"
          style="width: 160px"
          :options="domainOptions"
        />
        <input
          v-model="state.highlightQuery"
          placeholder="关键词高亮"
          style="width: 140px"
          @keydown.enter="onHighlightChange"
        />
        <a-checkbox v-model:checked="state.colorByDomain">领域配色</a-checkbox>
        <a-checkbox v-model:checked="state.includeCite">显示引用边</a-checkbox>
        <a-checkbox v-model:checked="state.showEdgeLabels">关系标签</a-checkbox>
        <input v-model.number="sampleNodeCount" type="number" min="10" max="200" step="10">
        <a-button @click="loadSampleNodes" :loading="state.fetching">获取节点</a-button>
      </div>
    </div>
    <div class="main" id="container" ref="container" v-show="graphData.nodes.length > 0"></div>
    <a-empty v-show="graphData.nodes.length === 0" style="padding: 4rem 0;" />

    <GraphNodeDrawer v-model:open="state.drawerOpen" :node="state.drawerNode" />

    <a-modal :open="state.showModal" title="上传文件" @ok="addDocumentByFile" @cancel="() => state.showModal = false"
      ok-text="确定" cancel-text="取消" :confirm-loading="state.precessing">
      <div class="upload">
        <a-upload-dragger class="upload-dragger" v-model:fileList="fileList" name="file" :fileList="fileList"
          :max-count="1" :disabled="state.precessing" action="/api/data/graph/multi/upload/" @change="handleFileUpload"
          @drop="handleDrop">
          <p class="ant-upload-text">点击或者把文件拖拽到这里上传</p>
          <p class="ant-upload-hint">
            同名文件无法重复添加。
          </p>
        </a-upload-dragger>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { Graph } from "@antv/g6";
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue';
import { message, Modal, Button as AButton } from 'ant-design-vue';
import { useConfigStore } from '@/stores'
import { UploadOutlined } from '@ant-design/icons-vue';
import HeaderComponent from '@/components/common/HeaderComponent.vue';
import GraphNodeDrawer from '@/components/graph/GraphNodeDrawer.vue';
import {
  applyGraphViewFilters,
  bindPaperNodeClick,
  createGraphOptions,
  DEFAULT_SAMPLE_COUNT,
  formatGraphPayload,
} from '@/utils/graphViz';

const configStore = useConfigStore()

const showPage = computed(
  () => configStore.config.enable_knowledge_base && configStore.config.enable_knowledge_graph,
)

let graphInstance
let unbindPaperClick = null
let resizeListenerAdded = false
const taskDomains = ref([])
const graphInfo = ref(null)
const container = ref(null);
const fileList = ref([]);
const sampleNodeCount = ref(DEFAULT_SAMPLE_COUNT);
const rawGraphData = reactive({
  nodes: [],
  edges: [],
});
const graphData = reactive({
  nodes: [],
  edges: [],
});

const state = reactive({
  fetching: false,
  loadingGraphInfo: false,
  searchInput: '',
  searchLoading: false,
  showModal: false,
  precessing: false,
  fileNameInput: '',
  includeCite: false,
  showEdgeLabels: false,
  selectedDomain: undefined,
  highlightQuery: '',
  colorByDomain: false,
  drawerOpen: false,
  drawerNode: null,
})

const domainOptions = computed(() =>
  taskDomains.value.map((d) => ({ label: d, value: d })),
)

const applyGraphFilters = () => {
  const filtered = applyGraphViewFilters(rawGraphData, {
    includeCite: state.includeCite,
    domain: state.selectedDomain || '',
    highlightQuery: state.highlightQuery,
  })
  graphData.nodes = filtered.nodes
  graphData.edges = filtered.edges
}

const setGraphResult = (result) => {
  rawGraphData.nodes = result?.nodes || []
  rawGraphData.edges = result?.edges || []
  applyGraphFilters()
}


const loadGraphInfo = () => {
  state.loadingGraphInfo = true
  fetch('/api/data/graph', {
    method: "GET",
  })
    .then(response => response.json())
    .then(data => {
      console.log(data)
      graphInfo.value = data.graph
      state.loadingGraphInfo = false
    })
    .catch(error => {
      console.error(error)
      message.error(error.message)
      state.loadingGraphInfo = false
    })
}

const getGraphData = () => {
  return formatGraphPayload(graphData, {
    showEdgeLabels: state.showEdgeLabels,
    maxLabelLen: 14,
    colorByDomain: state.colorByDomain,
    highlightQuery: state.highlightQuery,
  })
}

const loadTaskDomains = () => {
  fetch('/api/data/graph/task-domains?limit=50')
    .then((res) => (res.ok ? res.json() : Promise.reject(new Error('加载领域失败'))))
    .then((data) => {
      taskDomains.value = data.domains || []
    })
    .catch((error) => console.warn('task domains:', error))
}

const onPaperNodeClick = (data) => {
  state.drawerNode = data
  state.drawerOpen = true
}

const onHighlightChange = () => {
  applyGraphFilters()
  nextTick(() => randerGraph())
}


const addDocumentByFile = () => {
  state.precessing = true; 
  setTimeout(() => { 
    state.precessing = false; 
    state.showModal = false; 
    loadGraphInfo();
    loadSampleNodes();
    randerGraph(); 
    message.success("添加到图数据库成功");
  }, 500); 
};
const loadSampleNodes = () => {
  state.fetching = true
  const num = Math.max(10, Math.min(200, Number(sampleNodeCount.value) || DEFAULT_SAMPLE_COUNT))
  // 始终拉取核心边 + 引用边，由前端 includeCite 开关控制展示
  fetch(`/api/data/graph/nodes?kgdb_name=neo4j&num=${num}&include_cite=true`)
    .then((res) => {
      console.log(res)
      if (res.ok) {
        return res.json();
      } else {
        throw new Error("加载失败");
      }
    })
    .then(async (data) => {
      console.log(data)
      setGraphResult(data.result)
      console.log(graphData)
      await nextTick()
      randerGraph()
    })
    .catch((error) => {
      message.error(error.message);
    })
    .finally(() => state.fetching = false)
}

const onSearch = () => {
  const cur_embed_model = configStore.config.embed_model;
  if (cur_embed_model !== 'zhipu-embedding-3') {
    message.error('当前不支持实体检索，请在设置中选择向量模型为 zhipu-embedding-3');
    return;
  }

  // 如果检索参数为空，调用 loadSampleNodes 方法
  if (!state.searchInput.trim()) {
    loadSampleNodes();
    return;
  }

  state.searchLoading = true;
  let apiUrl = `/api/data/graph/node/?entity_name=${state.searchInput}`;

  fetch(apiUrl)
    .then((res) => {
      if (!res.ok) {
        return res.json().then(errorData => {
          throw new Error(errorData.message || `查询失败：${res.status} ${res.statusText}`);
        });
      }
      return res.json();
    })
    .then(async (data) => {
      console.log(data);
      if (!data.result || !data.result.nodes || !data.result.edges) {
        throw new Error('返回数据格式不正确');
      }
      setGraphResult(data.result);
      if (graphData.nodes.length === 0) {
        message.info('未找到相关实体');
      }
      console.log(data);
      console.log(graphData);
      await nextTick();
      randerGraph();
    })
    .catch((error) => {
      console.error('查询错误:', error);
      message.error(`查询出错：${error.message}`);
    })
    .finally(() => state.searchLoading = false);
};

const destroyGraph = () => {
  if (unbindPaperClick) {
    unbindPaperClick()
    unbindPaperClick = null
  }
  if (graphInstance) {
    graphInstance.destroy()
    graphInstance = null
  }
}

const handleResize = () => {
  if (!graphInstance || !container.value) return
  graphInstance.setSize(
    container.value.offsetWidth || container.value.clientWidth,
    container.value.offsetHeight || container.value.clientHeight,
  )
  graphInstance.fitView()
}

const ensureResizeListener = () => {
  if (!resizeListenerAdded) {
    window.addEventListener('resize', handleResize)
    resizeListenerAdded = true
  }
}

const cleanupGraph = () => {
  destroyGraph()
  if (resizeListenerAdded) {
    window.removeEventListener('resize', handleResize)
    resizeListenerAdded = false
  }
}

const randerGraph = () => {
  if (!showPage.value || !container.value) return
  if (graphData.nodes.length === 0) {
    destroyGraph()
    return
  }

  destroyGraph()
  graphInstance = new Graph(
    createGraphOptions(container.value, {
      showEdgeLabels: state.showEdgeLabels,
      maxLabelLen: 14,
      colorByDomain: state.colorByDomain,
    }),
  )
  ensureResizeListener()
  graphInstance.setData(getGraphData())
  graphInstance.render()
  unbindPaperClick = bindPaperNodeClick(graphInstance, onPaperNodeClick, container.value)
}

watch(
  () => state.includeCite,
  async () => {
    applyGraphFilters()
    await nextTick()
    randerGraph()
  },
)

watch(
  () => state.showEdgeLabels,
  async () => {
    await nextTick()
    randerGraph()
  },
)

watch(
  () => state.selectedDomain,
  async () => {
    applyGraphFilters()
    await nextTick()
    randerGraph()
  },
)

watch(
  () => state.colorByDomain,
  async () => {
    await nextTick()
    randerGraph()
  },
)

watch(
  () => state.highlightQuery,
  async () => {
    applyGraphFilters()
    await nextTick()
    randerGraph()
  },
)

const bootstrapGraphPage = () => {
  if (!showPage.value) return
  loadGraphInfo()
  loadTaskDomains()
  loadSampleNodes()
}

watch(showPage, (ready, prev) => {
  if (ready) {
    bootstrapGraphPage()
  } else if (prev) {
    cleanupGraph()
  }
}, { immediate: true })

onBeforeUnmount(() => {
  cleanupGraph()
})


const handleFileUpload = (event) => {
  console.log(event)
  console.log(fileList.value)
}

const handleDrop = (event) => {
  console.log(event)
  console.log(fileList.value)
}

const graphStatusClass = computed(() => {
  if (state.loadingGraphInfo) return 'loading';
  return graphInfo.value?.status === 'open' ? 'open' : 'closed';
});

const graphStatusText = computed(() => {
  if (state.loadingGraphInfo) return '加载中';
  return graphInfo.value?.status === 'open' ? '已连接' : '已关闭';
});

const deleteFiles = () => {
  Modal.confirm({
    title: '确认删除',
    content: '确定要删除所有文件吗？此操作不可恢复。',
    onOk() {
      fetch('/api/data/delete/all_graph', {
        method: 'DELETE',
      })
        .then(response => response.json())
        .then(data => {
          message.success(data.message);
          loadGraphInfo();
          loadSampleNodes();
          randerGraph(); 
          console.log('删除成功');
        })
        .catch(error => {
          console.error('删除失败:', error);
          message.error(error.message);
        });
    },
    onCancel() {
      message.info('取消删除');
    },
  });
};
const deleteofFile = () => {
  const nodeId = state.searchInput.trim();
  if (!nodeId) {
    message.error("请输入要删除的实体标识");
    return;
  }
  const apiUrl = `/api/data/graph/delete/node/?entity=${encodeURIComponent(nodeId)}`;

  fetch(apiUrl, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
    }
  })
    .then(response => {
      console.log(response)
      if (!response.ok) {
        throw new Error(`HTTP错误 ${response.status}`);
      }
      return response.json();
    })
    .then(data => {
      if (data.message) {
        message.success(data.message);
        state.searchInput = ''
        loadGraphInfo();
        loadSampleNodes();
        randerGraph()
      } else {
        throw new Error(data.message || '删除失败（业务逻辑错误）');
      }
    })
    .catch(error => {
      console.error('删除失败:', error);
      message.error(error.message);
    });
};
</script>

<style lang="less" scoped>
.graph-container {
  padding: 0;
}

.status-wrapper {
  display: flex;
  align-items: center;
  margin-right: 16px;
  font-size: 14px;
  color: rgba(0, 0, 0, 0.65);
}

.status-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;

  &.loading {
    background-color: #faad14;
    animation: pulse 1.5s infinite ease-in-out;
  }

  &.open {
    background-color: #52c41a;
  }

  &.closed {
    background-color: #f5222d;
  }
}

@keyframes pulse {
  0% {
    transform: scale(0.8);
    opacity: 0.5;
  }

  50% {
    transform: scale(1.2);
    opacity: 1;
  }

  100% {
    transform: scale(0.8);
    opacity: 0.5;
  }
}

.actions {
  display: flex;
  justify-content: space-between;
  margin: 20px 0;
  padding: 0 24px;

  .actions-left,
  .actions-right {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  input {
    width: 100px;
    border-radius: 8px;
    padding: 4px 12px;
    border: 2px solid var(--main-300);
    outline: none;
    height: 42px;

    &:focus {
      border-color: var(--main-color);
    }
  }

  button {
    border-width: 2px;
    height: 40px;
    box-shadow: none;
  }
}


.upload {
  margin-bottom: 20px;

  .upload-dragger {
    margin: 0px;
  }
}

#container {
  background: #F7F7F7;
  margin: 20px 24px;
  border-radius: 16px;
  width: calc(100% - 48px);
  height: calc(100vh - 200px);
  resize: horizontal;
  overflow: hidden;
}

.database-empty {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  height: 100%;
  flex-direction: column;
  color: var(--gray-900);
}

.inputFile {
  border-radius: 8px;
  padding: 8px 12px;
  border: 2px solid #d9d9d9;
  outline: none;
  height: 38px;
  font-size: 14px;
}
</style>
