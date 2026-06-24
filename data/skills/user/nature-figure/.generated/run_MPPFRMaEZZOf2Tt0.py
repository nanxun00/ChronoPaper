import pathlib
import csv
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict

# 设置工作目录
WORK_DIR = pathlib.Path(__file__).parent
OUTPUT_DIR = WORK_DIR / "output" / "runs" / "MPPFRMaEZZOf2Tt0"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 读取数据
data = """name,best_val,train_last,valid_last,params,size_mb,p_prec,p_rec,p_f1,s_prec,s_rec,s_f1,time_acc,mcc,p_res_mean_sec,p_res_std_sec,p_res_mae_sec,s_res_mean_sec,s_res_std_sec,s_res_mae_sec,test_p_prec,test_p_rec,test_p_f1,test_s_prec,test_s_rec,test_s_f1,test_time_acc,test_mcc,test_p_res_mean_sec,test_p_res_std_sec,test_p_res_mae_sec,test_s_res_mean_sec,test_s_std_sec,test_s_res_mae_sec
BaselineTCN_seed2025,0.916799,0.008083,0.008489,983939,3.753,0.9621,0.9375,0.9496,0.8481,0.9230,0.8840,0.9937,-0.0659,0.0664,1.6153,0.2964,-0.0762,2.0459,0.3608,0.9683,0.9443,0.9562,0.8365,0.9325,0.8819,0.9937,-0.0703,0.0883,1.6628,0.2803,-0.0024,1.8703,0.3066
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

# 解析CSV数据
reader = csv.DictReader(data.strip().split('\n'))
rows = list(reader)

# 提取关键指标
key_metrics = ['test_p_f1', 'test_s_f1', 'test_time_acc', 'test_mcc']
model_names = []
metric_values = defaultdict(list)

for row in rows:
    model_name = row['name'].replace('_seed2023', '').replace('_seed2024', '').replace('_seed2025', '')
    model_names.append(model_name)
    for metric in key_metrics:
        metric_values[metric].append(float(row[metric]))

# 获取唯一模型名并排序
unique_models = sorted(set(model_names))

# 准备绘图数据
n_models = len(unique_models)
n_metrics = len(key_metrics)
bar_width = 0.15
x = np.arange(n_models)

# 创建图表
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
axes = axes.flatten()

# 绘制每个指标的柱状图
for i, metric in enumerate(key_metrics):
    ax = axes[i]
    values = []
    for model in unique_models:
        # 获取该模型所有种子的值并取平均
        model_vals = [float(rows[j][metric]) for j in range(len(rows)) 
                     if model_names[j] == model]
        values.append(np.mean(model_vals))
    
    bars = ax.bar(x, values, bar_width, alpha=0.7)
    
    # 设置标题和标签
    ax.set_title(f'Test {metric.upper()}', fontsize=12)
    ax.set_xticks(x)
    ax.set_xticklabels(unique_models, rotation=45, ha='right', fontsize=8)
    ax.set_ylim(min(0, min(values) - 0.1), max(values) + 0.1)
    ax.grid(axis='y', alpha=0.3)
    
    # 添加数值标签
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                f'{val:.3f}', ha='center', va='bottom', fontsize=8)

plt.suptitle('Model Performance Comparison', fontsize=14, y=1.02)
plt.tight_layout()

# 保存图表
output_path = OUTPUT_DIR / 'model_comparison.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
plt.close()

# 输出保存信息
print(f"图表已保存至: {output_path}")
