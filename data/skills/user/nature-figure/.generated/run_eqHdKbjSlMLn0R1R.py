import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import numpy as np

# 设置工作目录
base_dir = Path(__file__).parent
output_dir = base_dir / "output" / "runs" / "eqHdKbjSlMLn0R1R"
output_dir.mkdir(parents=True, exist_ok=True)

# 解析数据
data_str = """BaselineTCN_seed2025,0.916799,0.008083,0.008489,983939,3.753,0.9621,0.9375,0.9496,0.8481,0.9230,0.8840,0.9937,-0.0659,0.0664,1.6153,0.2964,-0.0762,2.0459,0.3608,0.9683,0.9443,0.9562,0.8365,0.9325,0.8819,0.9937,-0.0703,0.0883,1.6628,0.2803,-0.0024,1.8703,0.3066
BaselineInception_seed2024,0.897640,0.006927,0.010762,1323747,5.050,0.9287,0.9464,0.9375,0.8161,0.9040,0.8578,0.9924,-0.0933,0.2533,2.2785,0.4906,0.0730,1.6902,0.4182,0.9395,0.9554,0.9474,0.8065,0.9146,0.8571,0.9925,-0.0895,0.1811,1.7679,0.3401,-0.0725,1.9545,0.4131
PhaseNet_seed2024,0.883974,0.012905,0.012932,235915,0.900,0.9367,0.9207,0.9286,0.8327,0.8461,0.8393,0.9928,-0.1032,0.0872,1.1437,0.1961,-0.0464,1.0000,0.1844,0.9433,0.9314,0.9373,0.8236,0.8314,0.8275,0.9928,-0.1101,0.0876,1.0707,0.1954,-0.0151,1.1448,0.1865
BaselineInception_seed2025,0.903397,0.007186,0.010727,1323747,5.050,0.9616,0.8929,0.9260,0.8244,0.9455,0.8808,0.9929,-0.0852,0.1771,2.4467,0.5410,-0.0604,2.0605,0.4429,0.9589,0.8962,0.9265,0.8042,0.9446,0.8688,0.9927,-0.0993,0.1879,2.2026,0.4810,-0.0283,1.9773,0.3874
PhaseNet_seed2025,0.168855,0.030261,0.030113,235915,0.900,0.0568,0.0615,0.0591,0.2020,0.4490,0.2787,0.0069,-0.8133,2.6234,3.5256,2.7796,0.1184,3.0454,1.2634,0.0644,0.0672,0.0658,0.1921,0.4548,0.2701,0.0070,-0.8150,2.5250,3.4185,2.7312,-0.0529,2.9440,1.2425
PhaseNet_seed2023,0.903913,0.015248,0.015557,235915,0.900,0.9497,0.9566,0.9531,0.8202,0.8922,0.8547,0.9934,-0.0845,0.0565,0.8559,0.1204,0.0285,0.9282,0.1741,0.9543,0.9613,0.9578,0.8220,0.8937,0.8563,0.9935,-0.0817,0.0757,1.5265,0.1785,-0.0192,1.1190,0.1809
EPick_ceed_seed2023,0.903608,0.035677,0.036379,628.2,2.4,0.9609,0.9523,0.9566,0.8290,0.8734,0.8506,0.9934,-0.0900,0.0304,0.4098,0.0763,-0.0490,1.5449,0.2386,0.9616,0.9626,0.9621,0.8285,0.8805,0.8537,0.9935,-0.0820,-0.0129,1.1069,0.1166,-0.0381,1.3747,0.1864
EPick_ceed_seed2024,0.910250,0.035706,0.036184,628.2,2.4,0.9657,0.9353,0.9503,0.8509,0.8904,0.8702,0.9935,-0.0777,0.0040,0.9749,0.1322,-0.0409,0.7476,0.1441,0.9594,0.9594,0.9594,0.8199,0.8876,0.8524,0.9934,-0.0834,-0.0343,1.1206,0.1235,-0.0197,1.3760,0.1947
EPick_ceed_seed2025,0.905570,0.035436,0.036023,628.2,2.4,0.9575,0.9431,0.9503,0.8276,0.8970,0.8609,0.9936,-0.0744,0.0814,0.7266,0.1211,-0.0232,1.2282,0.1681,0.9601,0.9501,0.9551,0.8028,0.8999,0.8486,0.9934,-0.0925,0.0281,0.8038,0.1065,0.0156,1.0607,0.1676
PhaseNet_ceed_seed2024,0.932782,0.006694,0.007493,235.9,0.9,0.9582,0.9754,0.9668,0.8633,0.9373,0.8988,0.9946,-0.0419,0.0019,0.7864,0.0996,-0.0041,0.4510,0.1021,0.9704,0.9804,0.9754,0.8417,0.9318,0.8844,0.9945,-0.0541,0.0185,0.9072,0.1136,0.0429,1.3158,0.1760
PhaseNet_ceed_seed2025,0.938046,0.006648,0.007361,235.9,0.9,0.9649,0.9810,0.9728,0.8695,0.9397,0.9032,0.9947,-0.0249,0.0060,0.5464,0.0735,-0.0157,0.9082,0.1294,0.9645,0.9845,0.9744,0.8517,0.9360,0.8918,0.9945,-0.0501,0.0128,1.2321,0.1391,-0.0150,0.8085,0.1191
PhaseNet_ceed_seed2023,0.929150,0.006617,0.007614,235.9,0.9,0.9552,0.9844,0.9696,0.8490,0.9324,0.8887,0.9946,-0.0623,0.0360,0.8239,0.0829,0.0223,0.6890,0.1245,0.9625,0.9855,0.9738,0.8396,0.9468,0.8900,0.9947,-0.0472,0.0256,1.4409,0.1376,-0.0322,1.0385,0.1269"""

# 读取数据
lines = data_str.strip().split('\n')
columns = lines[0].split(',')
data_lines = [line.split(',') for line in lines[1:]]
df = pd.DataFrame(data_lines, columns=columns)

# 转换数值列
for col in columns[1:]:
    df[col] = pd.to_numeric(df[col], errors='coerce')

# 选择用于比较的关键指标
metrics = ['best_val', 'p_f1', 's_f1', 'time_acc', 'mcc']
metric_labels = ['Best Validation', 'P-wave F1', 'S-wave F1', 'Time Accuracy', 'MCC']

# 设置样式
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")

# 创建图表
fig, axes = plt.subplots(2, 3, figsize=(18, 12))
axes = axes.flatten()

for idx, (metric, label) in enumerate(zip(metrics, metric_labels)):
    if idx >= len(axes):
        break
    
    ax = axes[idx]
    
    # 提取数据并准备绘图
    model_names = df['name'].tolist()
    values = df[metric].tolist()
    
    # 创建颜色映射
    colors = plt.cm.viridis(np.linspace(0, 1, len(model_names)))
    
    # 绘制柱状图
    bars = ax.bar(range(len(model_names)), values, color=colors)
    
    # 设置图表
    ax.set_title(f'{label} Comparison', fontsize=14, fontweight='bold')
    ax.set_ylabel(label, fontsize=12)
    ax.set_xticks(range(len(model_names)))
    
    # 简化模型名称以便显示
    short_names = [name.replace('_seed2023', '').replace('_seed2024', '').replace('_seed2025', '') 
                   for name in model_names]
    ax.set_xticklabels(short_names, rotation=45, ha='right', fontsize=10)
    
    # 添加数值标签
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                f'{value:.3f}', ha='center', va='bottom', fontsize=9, rotation=45)
    
    # 设置网格
    ax.grid(axis='y', alpha=0.3)

# 添加总体标题
fig.suptitle('Model Performance Comparison', fontsize=16, fontweight='bold', y=1.02)

# 调整布局
plt.tight_layout()

# 保存图表
output_path = output_dir / "model_comparison.png"
plt.savefig(output_path, dpi=300, bbox_inches='tight')
print(f"图表已保存到: {output_path}")

# 创建一个单独的综合比较图（包含所有指标）
fig2, ax2 = plt.subplots(figsize=(20, 10))

# 标准化数据用于比较（因为指标范围不同）
df_normalized = df[metrics].copy()
for col in metrics:
    col_min = df_normalized[col].min()
    col_max = df_normalized[col].max()
    if col_max != col_min:
        df_normalized[col] = (df_normalized[col] - col_min) / (col_max - col_min)
    else:
        df_normalized[col] = 0.5

# 设置绘图位置
x = np.arange(len(df))
width = 0.15  # 每个柱子的宽度

# 绘制每个指标的柱状图
colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
for i, (metric, color) in enumerate(zip(metrics, colors)):
    offset = (i - 2) * width
    ax2.bar(x + offset, df_normalized[metric], width, label=metric_labels[i], color=color, alpha=0.8)

# 设置图表
ax2.set_xlabel('Models', fontsize=14)
ax2.set_ylabel('Normalized Performance (0-1)', fontsize=14)
ax2.set_title('Normalized Performance Comparison Across All Metrics', fontsize=16, fontweight='bold')
ax2.set_xticks(x)
short_names = [name.replace('_seed2023', '').replace('_seed2024', '').replace('_seed2025', '') 
               for name in df['name'].tolist()]
ax2.set_xticklabels(short_names, rotation=45, ha='right', fontsize=10)
ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=10)
ax2.grid(axis='y', alpha=0.3)

# 保存综合比较图
output_path2 = output_dir / "model_comparison_normalized.png"
plt.savefig(output_path2, dpi=300, bbox_inches='tight')
print(f"综合比较图已保存到: {output_path2}")

plt.close('all')
