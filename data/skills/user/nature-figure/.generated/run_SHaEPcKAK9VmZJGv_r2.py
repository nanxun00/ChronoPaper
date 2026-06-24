import os
import pathlib
import csv
import numpy as np

# 设置HOME环境变量以解决matplotlib配置目录问题
if "HOME" not in os.environ:
    os.environ["HOME"] = str(pathlib.Path(__file__).parent)

import matplotlib
import matplotlib.pyplot as plt

# 设置工作目录
root_dir = pathlib.Path(__file__).parent
output_dir = root_dir / 'output' / 'runs' / 'SHaEPcKAK9VmZJGv'
output_dir.mkdir(parents=True, exist_ok=True)

# 数据（从用户输入解析）
data_lines = """name,best_val,train_last,valid_last,params,size_mb,p_prec,p_rec,p_f1,s_prec,s_rec,s_f1,time_acc,mcc,p_res_mean_sec,p_res_std_sec,p_res_mae_sec,s_res_mean_sec,s_res_std_sec,s_res_mae_sec,test_p_prec,test_p_rec,test_p_f1,test_s_prec,test_s_rec,test_s_f1,test_time_acc,test_mcc,test_p_res_mean_sec,test_p_res_std_sec,test_p_res_mae_sec,test_s_res_mean_sec,test_s_res_std_sec,test_s_res_mae_sec
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

# 解析数据
reader = csv.DictReader(data_lines.splitlines())
data = list(reader)

# 提取关键指标并分组（按模型类型分组，去掉种子后缀）
def extract_model_name(name):
    """从完整名称中提取模型类型（去掉种子信息）"""
    if '_seed' in name:
        return name.split('_seed')[0]
    return name

# 按模型类型分组
model_groups = {}
for row in data:
    model_type = extract_model_name(row['name'])
    if model_type not in model_groups:
        model_groups[model_type] = []
    model_groups[model_type].append(row)

# 计算每个模型类型的平均值（用于柱状图）
metrics = ['best_val', 'p_f1', 's_f1', 'time_acc', 'mcc']
test_metrics = ['test_p_f1', 'test_s_f1', 'test_time_acc', 'test_mcc']

# 准备绘图数据
model_names = list(model_groups.keys())
train_avgs = {metric: [] for metric in metrics}
test_avgs = {metric: [] for metric in test_metrics}

for model_type in model_names:
    rows = model_groups[model_type]
    # 计算训练集指标的平均值
    for metric in metrics:
        vals = [float(row[metric]) for row in rows]
        train_avgs[metric].append(np.mean(vals))
    # 计算测试集指标的平均值
    for metric in test_metrics:
        vals = [float(row[metric]) for row in rows]
        test_avgs[metric].append(np.mean(vals))

# 设置matplotlib参数
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

# 创建图表
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('模型性能对比（不同种子平均值）', fontsize=16)

# 训练集指标1: p_f1 和 s_f1
ax1 = axes[0, 0]
x = np.arange(len(model_names))
width = 0.35
bars1 = ax1.bar(x - width/2, train_avgs['p_f1'], width, label='P波F1')
bars2 = ax1.bar(x + width/2, train_avgs['s_f1'], width, label='S波F1')
ax1.set_title('训练集 - P波与S波F1分数')
ax1.set_ylabel('F1分数')
ax1.set_xticks(x)
ax1.set_xticklabels(model_names, rotation=45, ha='right')
ax1.legend()
ax1.grid(axis='y', alpha=0.3)

# 训练集指标2: time_acc 和 mcc
ax2 = axes[0, 1]
bars3 = ax2.bar(x - width/2, train_avgs['time_acc'], width, label='时间准确率')
bars4 = ax2.bar(x + width/2, train_avgs['mcc'], width, label='MCC')
ax2.set_title('训练集 - 时间准确率与MCC')
ax2.set_ylabel('数值')
ax2.set_xticks(x)
ax2.set_xticklabels(model_names, rotation=45, ha='right')
ax2.legend()
ax2.grid(axis='y', alpha=0.3)

# 测试集指标1: test_p_f1 和 test_s_f1
ax3 = axes[1, 0]
bars5 = ax3.bar(x - width/2, test_avgs['test_p_f1'], width, label='P波F1')
bars6 = ax3.bar(x + width/2, test_avgs['test_s_f1'], width, label='S波F1')
ax3.set_title('测试集 - P波与S波F1分数')
ax3.set_ylabel('F1分数')
ax3.set_xticks(x)
ax3.set_xticklabels(model_names, rotation=45, ha='right')
ax3.legend()
ax3.grid(axis='y', alpha=0.3)

# 测试集指标2: test_time_acc 和 test_mcc
ax4 = axes[1, 1]
bars7 = ax4.bar(x - width/2, test_avgs['test_time_acc'], width, label='时间准确率')
bars8 = ax4.bar(x + width/2, test_avgs['test_mcc'], width, label='MCC')
ax4.set_title('测试集 - 时间准确率与MCC')
ax4.set_ylabel('数值')
ax4.set_xticks(x)
ax4.set_xticklabels(model_names, rotation=45, ha='right')
ax4.legend()
ax4.grid(axis='y', alpha=0.3)

plt.tight_layout()

# 保存图表
output_file = output_dir / 'model_performance_comparison.png'
plt.savefig(output_file, dpi=300, bbox_inches='tight')
print(f"图表已保存至: {output_file}")

# 生成第二个图表：模型大小与性能关系
fig2, (ax5, ax6) = plt.subplots(1, 2, figsize=(14, 6))
fig2.suptitle('模型参数数量与性能关系', fontsize=16)

# 提取每个模型的参数数量和大小
param_counts = []
size_mbs = []
best_vals = []
for model_type in model_names:
    rows = model_groups[model_type]
    # 使用第一个样本的参数数量（相同模型种子数量相同）
    param_counts.append(float(rows[0]['params']))
    size_mbs.append(float(rows[0]['size_mb']))
    # 使用best_val的平均值
    vals = [float(row['best_val']) for row in rows]
    best_vals.append(np.mean(vals))

# 参数数量与最佳验证分数关系
ax5.scatter(param_counts, best_vals, s=100, alpha=0.6)
for i, name in enumerate(model_names):
    ax5.annotate(name, (param_counts[i], best_vals[i]), 
                xytext=(5, 5), textcoords='offset points', rotation=45)
ax5.set_xlabel('参数数量')
ax5.set_ylabel('最佳验证分数')
ax5.set_title('参数数量与性能')
ax5.grid(alpha=0.3)

# 模型大小与性能关系
ax6.scatter(size_mbs, best_vals, s=100, alpha=0.6, c='orange')
for i, name in enumerate(model_names):
    ax6.annotate(name, (size_mbs[i], best_vals[i]), 
                xytext=(5, 5), textcoords='offset points', rotation=45)
ax6.set_xlabel('模型大小 (MB)')
ax6.set_ylabel('最佳验证分数')
ax6.set_title('模型大小与性能')
ax6.grid(alpha=0.3)

plt.tight_layout()
output_file2 = output_dir / 'model_size_vs_performance.png'
plt.savefig(output_file2, dpi=300, bbox_inches='tight')
print(f"图表已保存至: {output_file2}")

print(f"生成完成。所有文件保存在: {output_dir}")
