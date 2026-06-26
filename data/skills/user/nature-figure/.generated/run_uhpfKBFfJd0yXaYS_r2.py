#!/usr/bin/env python3
import os
os.environ['MPLCONFIGDIR'] = '/tmp/matplotlib'
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import re

# ---------- 解析 LaTeX 表格 ----------
raw = r"""\label{tab:Ablation_CEED_b}
\begin{tabular}{lcccccc}
\hline
Model & \makecell{P-Res\\Mean} & \makecell{P-Res\\Std} & \makecell{P-Res\\MAE} & \makecell{S-Res\\Mean} & \makecell{S-Res\\Std} & \makecell{S-Res\\MAE} \\
\hline
Base & $0.0549\pm0.03$ & $0.8987\pm0.12$ & $0.1429\pm0.03$ & $-0.0173\pm0.01$ & $0.8723\pm0.01$ & $0.1522\pm0.01$ \\
Base + MS & $0.0102\pm0.02$ & $0.5498\pm0.17$ & $\underline{0.0695\pm0.01}$ & $0.0031\pm0.02$ & $0.9018\pm0.05$ & $0.1279\pm0.01$ \\
Base + PW-TL & $-0.0106\pm0.04$ & $0.9262\pm0.32$ & $0.1252\pm0.01$ & $\underline{0.0009\pm0.01}$ & $0.6767\pm0.12$ & $0.1230\pm0.01$ \\
Base + MS + SG & $0.0079\pm0.01$ & $\mathbf{0.4210\pm0.05}$ & $\mathbf{0.0639\pm0.01}$ & $0.0247\pm0.03$ & $0.6607\pm0.31$ & $0.1177\pm0.02$ \\
Base + MS + SG + CBAM & $\underline{0.0038\pm0.02}$ & $\underline{0.5417\pm0.03}$ & $0.0766\pm0.01$ & $-0.0062\pm0.02$ & $\underline{0.6347\pm0.11}$ & $\underline{0.1176\pm0.01}$ \\
PhaseRiskNet & $0.0224\pm0.04$ & $0.8140\pm0.07$ & $0.0964\pm0.01$ & $-0.0119\pm0.05$ & $0.9803\pm0.30$ & $0.1382\pm0.03$ \\
PhaseRiskNet-S & $\mathbf{0.0011\pm0.02}$ & $0.8289\pm0.28$ & $0.0943\pm0.02$ & $\mathbf{0.0006\pm0.01}$ & $\mathbf{0.5783\pm0.15}$ & $\mathbf{0.1105\pm0.00}$ \\
\hline
\end{tabular}
\end{table}"""

def parse_latex_table(text):
    lines = text.strip().splitlines()
    models = []
    data = []
    for line in lines:
        if '\\hline' in line or line.startswith('%') or 'Model' in line or '\\label' in line or '\\begin' in line or '\\end' in line:
            continue
        if '\\\\' not in line:
            continue
        line = line.replace('\\\\', '').strip()
        parts = [p.strip() for p in line.split('&')]
        if len(parts) < 7:
            continue
        model_name = parts[0]
        def extract_val(s):
            s = s.replace('$', '').replace('\\pm', ' ').replace('\\mathbf{', '').replace('\\underline{', '').replace('}', '')
            m = re.search(r'(-?\d+\.\d+)', s)
            return float(m.group(1)) if m else 0.0
        vals = []
        for i in range(1, 7):
            vals.append(extract_val(parts[i]))
        models.append(model_name)
        data.append(vals)
    return models, np.array(data)

models, arr = parse_latex_table(raw)
metrics_names = ['P-Res Mean', 'P-Res Std', 'P-Res MAE', 'S-Res Mean', 'S-Res Std', 'S-Res MAE']

# ---------- 绘图 ----------
output_dir = Path('output/runs/uhpfKBFfJd0yXaYS')
output_dir.mkdir(parents=True, exist_ok=True)

n_metrics = len(metrics_names)
fig, axes = plt.subplots(2, 3, figsize=(18, 10))
axes_flat = axes.flatten()
colors = plt.cm.tab10(np.linspace(0, 1, len(models)))
x = np.arange(len(models))
width = 0.6

for idx, ax in enumerate(axes_flat):
    vals = arr[:, idx]
    bars = ax.bar(x, vals, width, color=colors, edgecolor='black', linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(models, rotation=25, ha='right', fontsize=9)
    ax.set_ylabel(metrics_names[idx], fontsize=11)
    ax.set_title(metrics_names[idx], fontsize=13, fontweight='bold')
    ax.axhline(0, color='gray', linewidth=0.8, linestyle='--')
    for bar, val in zip(bars, vals):
        y_pos = bar.get_height()
        if y_pos >= 0:
            va = 'bottom'; offset = 0.005
        else:
            va = 'top'; offset = -0.005
        ax.text(bar.get_x() + bar.get_width()/2., y_pos + offset,
                f'{val:.4f}', ha='center', va=va, fontsize=7, rotation=45)

plt.suptitle('Ablation Study on CEED Dataset (P-Res & S-Res Metrics)', fontsize=16, y=1.02)
plt.tight_layout()
plt.savefig(output_dir / 'model_comparison.png', dpi=300, bbox_inches='tight')
plt.close()

fig2, axes2 = plt.subplots(1, 2, figsize=(14, 5))

# P-Res MAE
ax = axes2[0]
vals = arr[:, 2]
bars = ax.bar(x, vals, width, color=colors, edgecolor='black')
ax.set_xticks(x)
ax.set_xticklabels(models, rotation=25, ha='right', fontsize=9)
ax.set_ylabel('P-Res MAE')
ax.set_title('P-Res MAE Comparison', fontweight='bold')
for bar, val in zip(bars, vals):
    ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.002,
            f'{val:.4f}', ha='center', va='bottom', fontsize=8, rotation=45)

# S-Res Mean
ax = axes2[1]
vals = arr[:, 3]
bars = ax.bar(x, vals, width, color=colors, edgecolor='black')
ax.set_xticks(x)
ax.set_xticklabels(models, rotation=25, ha='right', fontsize=9)
ax.set_ylabel('S-Res Mean')
ax.set_title('S-Res Mean Comparison', fontweight='bold')
for bar, val in zip(bars, vals):
    y_pos = bar.get_height()
    offset = 0.002 if y_pos >= 0 else -0.005
    ax.text(bar.get_x() + bar.get_width()/2., y_pos + offset,
            f'{val:.4f}', ha='center', va='bottom' if y_pos>=0 else 'top', fontsize=8, rotation=45)

plt.tight_layout()
plt.savefig(output_dir / 'key_metrics_highlight.png', dpi=300, bbox_inches='tight')
plt.close()

print(f"Figures saved to {output_dir.resolve()}")
