import os
import pathlib
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # 设置非交互式后端
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# 设置MPLCONFIGDIR环境变量以避免home目录错误
config_dir = pathlib.Path.cwd() / 'matplotlib_config'
config_dir.mkdir(exist_ok=True)
os.environ['MPLCONFIGDIR'] = str(config_dir)

# 设置HOME环境变量（如果未设置）
if 'HOME' not in os.environ or not os.path.exists(os.environ.get('HOME', '')):
    temp_home = pathlib.Path.cwd() / 'temp_home'
    temp_home.mkdir(exist_ok=True)
    os.environ['HOME'] = str(temp_home)

# 创建输出目录
output_dir = pathlib.Path("output/runs/UvVD7kiAw70ev96c")
output_dir.mkdir(parents=True, exist_ok=True)

# 准备数据（从用户提供的数据中提取关键指标）
data = {
    'Model': [
        'BaselineTCN_seed2025', 'BaselineInception_seed2024', 'PhaseNet_seed2024',
        'BaselineInception_seed2025', 'PhaseNet_seed2025', 'PhaseNet_seed2023',
        'EPick_ceed_seed2023', 'EPick_ceed_seed2024', 'EPick_ceed_seed2025',
        'PhaseNet_ceed_seed2024', 'PhaseNet_ceed_seed2025', 'PhaseNet_ceed_seed2023'
    ],
    'best_val': [
        0.916799, 0.897640, 0.883974, 0.903397, 0.168855, 0.903913,
        0.903608, 0.910250, 0.905570, 0.932782, 0.938046, 0.929150
    ],
    'test_p_f1': [
        0.9562, 0.9474, 0.9373, 0.9265, 0.0658, 0.9578,
        0.9621, 0.9594, 0.9551, 0.9754, 0.9744, 0.9738
    ],
    'test_s_f1': [
        0.8819, 0.8571, 0.8275, 0.8688, 0.2701, 0.8563,
        0.8537, 0.8524, 0.8486, 0.8844, 0.8918, 0.8900
    ],
    'test_time_acc': [
        0.9937, 0.9925, 0.9928, 0.9927, 0.0070, 0.9935,
        0.9935, 0.9934, 0.9934, 0.9945, 0.9945, 0.9947
    ],
    'params': [
        983939, 1323747, 235915, 1323747, 235915, 235915,
        628.2, 628.2, 628.2, 235.9, 235.9, 235.9
    ],
    'size_mb': [
        3.753, 5.050, 0.900, 5.050, 0.900, 0.900,
        2.4, 2.4, 2.4, 0.9, 0.9, 0.9
    ]
}

df = pd.DataFrame(data)

# 提取基础模型名称
df['BaseModel'] = df['Model'].str.split('_seed').str[0]

# 设置绘图风格（使用更简单的样式）
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")

# 创建图表
fig, axes = plt.subplots(2, 3, figsize=(18, 12))
fig.suptitle('Model Performance Comparison', fontsize=16, fontweight='bold', y=1.02)

# 1. 最佳验证分数
ax1 = axes[0, 0]
sns.barplot(data=df, x='BaseModel', y='best_val', hue='Model', ax=ax1, legend=False)
ax1.set_title('Best Validation Score')
ax1.set_ylabel('Score')
ax1.set_xlabel('')
ax1.tick_params(axis='x', rotation=45)
for p in ax1.patches:
    ax1.annotate(f'{p.get_height():.3f}', 
                (p.get_x() + p.get_width() / 2., p.get_height()), 
                ha='center', va='center', 
                xytext=(0, 5), 
                textcoords='offset points', fontsize=8)

# 2. 测试P波F1分数
ax2 = axes[0, 1]
sns.barplot(data=df, x='BaseModel', y='test_p_f1', hue='Model', ax=ax2, legend=False)
ax2.set_title('Test P-wave F1 Score')
ax2.set_ylabel('F1 Score')
ax2.set_xlabel('')
ax2.tick_params(axis='x', rotation=45)
for p in ax2.patches:
    ax2.annotate(f'{p.get_height():.3f}', 
                (p.get_x() + p.get_width() / 2., p.get_height()), 
                ha='center', va='center', 
                xytext=(0, 5), 
                textcoords='offset points', fontsize=8)

# 3. 测试S波F1分数
ax3 = axes[0, 2]
sns.barplot(data=df, x='BaseModel', y='test_s_f1', hue='Model', ax=ax3, legend=False)
ax3.set_title('Test S-wave F1 Score')
ax3.set_ylabel('F1 Score')
ax3.set_xlabel('')
ax3.tick_params(axis='x', rotation=45)
for p in ax3.patches:
    ax3.annotate(f'{p.get_height():.3f}', 
                (p.get_x() + p.get_width() / 2., p.get_height()), 
                ha='center', va='center', 
                xytext=(0, 5), 
                textcoords='offset points', fontsize=8)

# 4. 测试时间准确度
ax4 = axes[1, 0]
sns.barplot(data=df, x='BaseModel', y='test_time_acc', hue='Model', ax=ax4, legend=False)
ax4.set_title('Test Time Accuracy')
ax4.set_ylabel('Accuracy')
ax4.set_xlabel('')
ax4.tick_params(axis='x', rotation=45)
for p in ax4.patches:
    ax4.annotate(f'{p.get_height():.3f}', 
                (p.get_x() + p.get_width() / 2., p.get_height()), 
                ha='center', va='center', 
                xytext=(0, 5), 
                textcoords='offset points', fontsize=8)

# 5. 参数量（对数刻度）
ax5 = axes[1, 1]
sns.barplot(data=df, x='BaseModel', y='params', hue='Model', ax=ax5, legend=False)
ax5.set_title('Number of Parameters')
ax5.set_ylabel('Parameters (log scale)')
ax5.set_xlabel('')
ax5.set_yscale('log')
ax5.tick_params(axis='x', rotation=45)

# 6. 模型大小
ax6 = axes[1, 2]
sns.barplot(data=df, x='BaseModel', y='size_mb', hue='Model', ax=ax6, legend=False)
ax6.set_title('Model Size')
ax6.set_ylabel('Size (MB)')
ax6.set_xlabel('')
ax6.tick_params(axis='x', rotation=45)

# 调整布局
plt.tight_layout()

# 保存图表
chart_path = output_dir / 'model_performance_comparison.png'
plt.savefig(chart_path, dpi=300, bbox_inches='tight', facecolor='white')
plt.close()

print(f"图表已保存至: {chart_path}")
