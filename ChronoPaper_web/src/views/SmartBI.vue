<template>
  <div class="smartbi-layout">
    <!-- 顶部Header -->
    <HeaderComponent
      title="智能分析"
      description="这里提供了智能分析并生成可视化图表的功能。"
    />
    <div class="main-content">
      <!-- 左侧表单卡片 -->
      <div class="card form-card">
        <div class="card-title">智能分析</div>
        <a-form :model="form" layout="vertical">
          <a-form-item label="分析目标：" required>
            <a-textarea v-model:value="form.target" placeholder="请输入分析目标" :rows="2" />
          </a-form-item>
          <a-form-item label="图表名称：" required>
            <a-input v-model:value="form.chartName" placeholder="请输入图表名称" />
          </a-form-item>
          <a-form-item label="图表类型：" required>
            <a-select v-model:value="form.chartType" placeholder="选择图表类型，如柱状图、折线图等">
              <a-select-option value="柱状图">柱状图</a-select-option>
              <a-select-option value="饼状图">饼状图</a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="知识库选择：" required>
            <a-select v-model:value="form.dataset" placeholder="请选择知识库">
              <a-select-option
                v-for="option in datasetOptions"
                :key="option.value"
                :value="option.value">
                {{ option.label }}
              </a-select-option>
            </a-select>
          </a-form-item>
          <div class="form-btns">
            <a-button type="primary" @click="onSubmit">分析</a-button>
            <a-button style="margin-left: 16px" @click="onReset">重置</a-button>
          </div>
        </a-form>
      </div>
      <!-- 右侧卡片区 -->
      <div class="right-cards">
        <!-- 上：可视化图表 -->
        <div class="card chart-card">
          <div class="card-title">可视化图表</div>
          <el-empty v-if="!chartData" description="暂无数据"></el-empty>
          <div v-else ref="chartRef" class="chart-box">
            
          </div>
        </div>
        <!-- 下：分析结论 -->
        <div class="card conclusion-card">
          <div class="card-title">分析结论</div>
          <div class="conclusion-text">
            <el-empty v-if="!conclusion" description="暂无结论"></el-empty>
            <p v-else>{{ conclusion }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import HeaderComponent from '@/components/HeaderComponent.vue'
import { ElEmpty } from 'element-plus'

const form = reactive({
  target: '',
  chartName: '',
  chartType: '柱状图',
  dataset: null
})

const chartRef = ref(null)
const chartTitle = ref('网站用户增长情况')
const conclusion = ref('') // 初始化为空字符串
const chartData = ref(null) // 用于存储图表数据

const datasetOptions = ref([
  { value: null, label: '请选择知识库' } 
]);

const renderChart = () => {
  nextTick(() => {
    if (!chartRef.value) return
    const chart = echarts.init(chartRef.value)
    if (chartData.value && chartData.value.option) {
      chart.setOption(chartData.value.option, true)
    } else {
      chart.clear()
    }
  })
}

// 上传数据给后端进行分析返回可视化图标和分析结论
const onSubmit = async () => {
  if (!form.dataset) {
    alert('请选择知识库');
    return;
  }

  const formData = {
    query: form.target,
    title: form.chartName,
    type: form.chartType, 
    meta: { db_name: form.dataset } // 假设后端需要的数据格式
  };

  try {
    const response = await fetch('/api/smartbi/generate-graph', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(formData)
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const result = await response.json();
    console.log('Backend response:', result);

    // 更新图表标题
    chartTitle.value = result.chartName || form.chartName || '可视化图表';

    // 更新分析结论
    conclusion.value = result.analysis || '暂无分析结论';

    // 根据后端返回的数据重新渲染图表
    chartData.value = result;
    renderChart();
  } catch (error) {
    console.error('Error submitting form:', error);
    alert('提交失败，请稍后再试');
  }
};

const onReset = () => {
  form.target = ''
  form.chartName = ''
  form.chartType = 'bar'    
  form.dataset = null  
  chartData.value = null // 重置图表数据
  conclusion.value = '' // 重置分析结论
}

// 获取知识库
const getsmart =async ()=>{
  const response = await fetch('/api/smartbi/', {
      method: 'GET',
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const result = await response.json();
  console.log('Backend response:', result);

  // 假设返回的数据结构中包含一个名为 databases 的数组
  datasetOptions.value = result.databases.map(db => ({
    value: db.metadata.collection_name,  // 下拉框的值使用数据库ID
    label: db.name    // 下拉框的显示文本使用数据库名称
  }));
}

onMounted(() => {
  renderChart()
  window.addEventListener('resize', resizeChart)
  getsmart()
})

const resizeChart = () => {
  if (chartRef.value) {
    const chart = echarts.getInstanceByDom(chartRef.value)
    chart && chart.resize()
  }
}

watch([() => form.chartType, () => form.dataset], renderChart)
</script>

<style scoped lang="less">
.smartbi-layout {
  min-height: 100vh;
  background: #f7fbfa;
  display: flex;
  flex-direction: column;
}
.main-content {
  display: flex;
  flex-direction: row;
  justify-content: flex-start;
  align-items: flex-start;
  margin: 20px 0 0 0;
  gap: 40px;
  width: 100%;
  max-width: 1570px;
  margin-left: 20px;
  margin-right: auto;
}
.card {
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.06);
  padding: 20px 40px 32px 40px;
  margin-bottom: 20px;
}
.form-card {
  width: 640px;
  min-width: 400px;
  .form-btns {
    display: flex;
    justify-content: flex-start;
    margin-top: 16px;
    .ant-btn {
      font-size: 16px;
      height: 40px;
      min-width: 80px;
    }
  }
}
.right-cards {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.chart-card {
  min-height: 420px;
  .chart-box {
    width: 100%;
    height: 340px;
    position: relative;
    
  }
}
.conclusion-card {
  min-height: 160px;
  .conclusion-text {
    color: #444;
    font-size: 17px;
    line-height: 1.8;
    margin-top: 12px;
    white-space: pre-line;
  }
}
.card-title {
  font-size: 21px;
  font-weight: 700;
  margin-bottom: 10px;
  color: #222;
  padding-bottom: 16px;  
  border-bottom: 1px solid #e8e8e8; 
  margin-bottom: 20px; 
}
</style>