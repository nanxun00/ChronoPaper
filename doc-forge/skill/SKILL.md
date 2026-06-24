# doc-forge — 软件工程文档优化工具链

## 触发方式

用户运行 `/doc-forge` 时执行本 skill。

---

## 工作流程

### 启动检测

1. 检查当前目录下是否存在 `output/` 目录且包含已有产物：
   - 存在 → 询问用户：
     ```
     检测到已有产物，请选择模式：
     [1] 全新生成（将创建新的时间戳目录）
     [2] 增量更新（选择要重新生成的模块）
         [a] 更新文档内容
         [b] 重新生成图表
         [c] 重新生成宣传图
     ```
   - 不存在 → 进入角色识别

2. 角色识别：
   ```
   你的角色是？
   [1] 产品需求方（甲方）— 我会用通俗语言引导你
   [2] 开发者/技术负责人 — 我会用技术语言和你沟通
   [3] 两者都有（团队协作）— 我会分别适配

   不确定就选 [1]，后续随时可以补充技术细节。
   ```

3. 根据角色调整全局行为：
   - **甲方模式**：提问用日常语言，跳过技术术语，侧重业务描述
   - **开发者模式**：提问可直接用技术术语，侧重架构和接口
   - **协作模式**：关键决策同时给出业务版和技术版说明

---

### 阶段 1 — 需求澄清（两步法）

#### 步骤 1A：自由描述

鼓励用户用任意方式描述项目，不要求结构化：

```
"请用你最舒服的方式描述你的想法。你可以：
 - 随便打一段话，想到什么说什么
 - 给一个参考产品或竞品名称，我来分析它
 - 发一张截图、一份已有的文档
 - 就说几个关键词也行

 不需要整理，不需要完整，现在脑子里有什么就说什么。"

提供输入方式选项：
 [1] 直接打字描述
 [2] 给一个参考产品/竞品名称，我来分析
 [3] 我有一份已有的文档/截图，帮我解读
```

如果用户选择 [2]，分析参考产品的功能、用户群体、核心流程，整理后让用户确认。
如果用户选择 [3]，读取文档或截图，提取关键信息，整理后让用户确认。

#### 步骤 1B：智能追问

基于步骤 1A 中用户提供的内容，分析信息缺口，生成 5-10 个编号问题。

规则：
- 标 * 为关键问题（建议回答），其余可输入 `skip` 跳过
- 输入 `?` 获取该题的详细说明
- 输入 `back` 返回上一题修改
- 可用简写批量回答，格式：`1: 回答, 2: 回答, 3: skip, ...`

**甲方模式**下的提问使用日常语言，示例：
```
* 1: 用户注册后需要审核通过才能用吗？
* 2: 支持哪些付款方式？（微信？支付宝？银行卡？）
  3: 商品大概分几类？有层级吗？（比如 服装→男装→T恤）
* 4: 需要后台管理吗？谁来管？管理员还是商家自己？
  5: 需要支持手机端吗？还是只做网页？
  6: 有没有技术上的偏好或限制？
  7: 系统里主要要管理哪些"东西"？
     （例如：用户、商品、订单、文章——不确定就 skip）
```

**开发者模式**下的提问可直接使用技术术语，示例：
```
* 1: 技术栈偏好？
* 2: 核心数据实体有哪些？
* 3: 认证方案？（JWT/Session/OAuth）
  4: 是否需要微服务架构？
  ...
```

追问可持续多轮。每轮基于上轮回答生成新的补充问题，直到无重大信息缺口。

#### 步骤 1C：矛盾扫描

分析已收集的所有需求，检测潜在冲突并标出。

冲突类型示例：
- [权衡点] "要功能丰富" vs "要界面极简"
- [约束冲突] "支持万人并发" vs "预算有限"
- [技术矛盾] "实时推送" vs "离线可用"
- [逻辑矛盾] "用户必须实名认证" vs "支持游客下单"

输出冲突清单，让用户做取舍：
```
⚠ 检测到以下潜在冲突：

[C1] 您提到"功能要丰富"又提到"界面要简洁"
     → 优先哪个？ [a] 功能完整  [b] 界面简洁

[C2] 您提到需要"实时消息推送"又提到"支持离线使用"
     → 理解为：离线时缓存消息，上线后自动推送？
     [a] 是的，这样就行  [b] 不需要离线了  [c] 我再想想
```

如果无冲突 → 直接跳过此步骤。

#### 步骤 1D：产物选择

```
选择要生成的产物（默认 all）：
[1] 开发文档（需求文档）
[2] PlantUML 图表（用例图、流程图、时序图等）
[3] 宣传图 / 原型图（Banner、功能展示、线框图）
[all] 全部生成
```

---

### 阶段 2 — 逐节生成与精炼

#### 2.2.1 确定章节结构

1. 根据阶段 1 收集的信息，列出文档的章节大纲：

```
"根据你的需求，文档将包含以下章节：
 1. 项目概述
 2. 用户角色与权限
 3. 功能需求清单
 4. 核心业务流程
 5. 数据模型
 6. 非功能性需求（性能、安全等）

 你觉得这个结构合适吗？可以：
 - 增加/删除章节
 - 调整顺序
 - 或者直接确认开始"
```

2. 用户确认后，创建骨架文件（带占位符的 markdown）：
   保存到 `output/{project-name}/docs/{timestamp}-requirements.md`
   每个章节用 `<!-- 待填充 -->` 占位。
   同时更新 `output/.last-run.json`：
   ```json
   {
     "project": "{project-name}",
     "timestamp": "{timestamp}",
     "output_dir": "{当前工作目录的绝对路径}/output/{project-name}",
     "doc_forge_dir": "{doc-forge 安装目录的绝对路径}"
   }
   ```
   > `output_dir` 为产物统一输出目录（绝对路径），后续所有产物（文档、图表、图像）都保存到此目录下。
   > `doc_forge_dir` 为 doc-forge 工具链的安装目录（包含 scripts/ 的目录），用于定位渲染脚本。

#### 2.2.2 逐节精炼循环

对每个章节依次执行以下步骤：

**Step 1：澄清提问**

```
"现在开始写【{章节名}】章节。
 关于这部分，我有几个问题："
```

生成 3-5 个关于该章节的澄清问题。根据角色模式调整提问语言。
用户可简写回答，可 skip。

**Step 2：头脑风暴（仅对复杂章节）**

对于功能需求、数据模型等复杂章节，生成 5-15 个可能的内容点让用户选择：

```
"【功能需求】章节，我梳理了以下可能的功能点：
 1. 用户注册/登录
 2. 商品浏览与搜索
 3. 购物车管理
 4. 订单创建与支付
 ...

 请选择：保留哪些？删除哪些？要合并哪些？"
```

简单章节（如项目概述）跳过此步。

**Step 3：起草**

根据用户选择，起草该章节内容。
使用 Edit 工具替换骨架文件中的 `<!-- 待填充 -->` 占位符。

**Step 4：用户确认与修改**

展示该章节内容，询问：
```
[确认] 进入下一节  [修改] 指出需要调整的地方
```

用户提出修改意见后，精确修改（不重印全文）。可多轮迭代，直到用户满意。

**Step 5：进入下一节**

用户确认当前章节 → 开始下一个章节的 Step 1。

#### 2.2.3 整体审阅

所有章节完成后：

1. 通读全文，检查：
   - 章节间是否有重复内容
   - 术语是否前后一致
   - 逻辑是否连贯
   - 是否有空洞的占位符未填充

2. 主动提示发现的冗余和遗漏

3. 生成润色版本：
   - 消除模糊表述（"尽快"、"适当"、"可能"、"一般"、"较好"）
   - 确保每条功能点有 `验收标准：` 字段
   - 确保数据模型字段标注类型
   - 为跳过的信息项添加标注（如 `⚠ 技术栈待确认`）

4. 告知用户文档路径：
   ```
   ✔ 文档已生成：
     output/{project-name}/docs/{timestamp}-requirements.md
   ```

---

### 阶段 2.5 — 双视角验证（可选）

```
"文档已生成。是否需要验证文档的可读性和可行性？
 [1] 验证（推荐）— 用两种视角检查文档
 [2] 跳过 — 直接进入下一步"
```

#### 视角一：甲方可读性测试

模拟无上下文的新读者读取文档，测试：

1. 预测甲方读者可能提出的问题（5-10 个）：
   "作为产品需求方，我看到这份文档可能会问：
    - '验收标准里的 XX 是什么意思？'
    - '这个功能我想要的和写的不是一个意思？'
    - ..."

2. 检查这些问题能否从文档中找到答案

3. 汇总结果：
   - ✔ 甲方能理解的部分
   - ⚠ 可能产生歧义的部分
   - ✘ 甲方可能看不懂的技术术语

#### 视角二：开发者可行性测试

以"开发者视角"审视文档，测试：

1. 需求是否足够明确，可以直接进入开发？
2. 是否缺少关键信息？（接口定义、边界条件、异常处理、权限控制）
3. 哪些地方存在歧义，需要和甲方进一步确认？

#### 汇总与修复

将两个视角发现的问题汇总为确认清单：

```
⚠ 以下问题需要确认：
[1] 【甲方视角】"验收标准：响应时间 < 2s" — 甲方是否理解为页面加载？
[2] 【开发者视角】缺少异常处理说明 — 支付失败后怎么处理？
[3] ...
```

用户逐条回答后，回到阶段 2 修改对应章节。无问题 → 进入阶段 3。

---

### 阶段 3 — 生成 PlantUML 图表

（仅当用户选择了 [2] 或 [all]）

0. 首先询问用户图表输出格式（可多选）：
   ```
   选择图表输出格式（可多选，空格分隔）：
   [1] PNG  — 位图，适合网页展示
   [2] SVG  — 矢量图，无损缩放，适合演示文稿
   [3] PDF  — 矢量 PDF，适合打印和文档嵌入
   [all] 全部格式
   ```
   用户选择后，记录为 formats 数组（如 `['png', 'svg', 'pdf']`），后续每种图按此数组循环生成。

1. 参考 `templates/plantuml-prompts.md`，基于文档内容生成以下四种图的 PlantUML 代码。

2. **渲染流程**（避免中文路径导致的 `file://` URL 编码问题）：

   **Step 1：创建临时渲染脚本**
   
   将所有图表的 PlantUML 代码和渲染逻辑写入一个临时 `.mjs` 文件，保存到 `{doc_forge_dir}/export-diagrams-{timestamp}.mjs`。
   
   脚本模板：
   ```javascript
   import { downloadDiagram } from './scripts/plantuml-render.js';
   
   const OUT = '{output_dir}/diagrams';
   const TS = '{timestamp}';
   const formats = [{用户选择的格式数组，如 ['png', 'svg']}];
   
   const diagrams = [
     { name: 'dfd', uml: `{数据流图的PlantUML代码}` },
     { name: 'usecase', uml: `{用例图的PlantUML代码}` },
     { name: 'activity', uml: `{活动图的PlantUML代码}` },
     { name: 'sequence', uml: `{时序图的PlantUML代码}` }
   ];
   
   let success = 0, fail = 0;
   for (const d of diagrams) {
     for (const fmt of formats) {
       const outPath = `${OUT}/${TS}-${d.name}.${fmt}`;
       try {
         await downloadDiagram(d.uml, outPath, fmt);
         console.log(`✔ ${d.name} (${fmt}): ${outPath}`);
         success++;
       } catch (e) {
         console.error(`✘ ${d.name} (${fmt}): ${e.message}`);
         fail++;
       }
     }
   }
   console.log(`\n完成：${success} 成功，${fail} 失败`);
   ```
   
   **Step 2：从 doc-forge 目录运行脚本**
   
   ```bash
   cd "{doc_forge_dir}" && node "./export-diagrams-{timestamp}.mjs"
   ```
   
   > ⚠ 必须 `cd` 到 `doc_forge_dir` 再运行，确保 Node.js 能正确解析 `node_modules/` 中的依赖包（如 `plantuml-encoder`）。
   
   **Step 3：清理临时文件**
   
   ```bash
   rm "{doc_forge_dir}/export-diagrams-{timestamp}.mjs"
   ```

3. 生成的图表类型：
   - **数据流图（dfd）** — 展示系统数据流向和处理过程
   - **用例图（usecase）** — 展示用户角色与系统功能的交互
   - **活动图（activity）** — 展示核心业务流程的执行步骤
   - **时序图（sequence）** — 展示组件间的时序交互

2. 每张完成后告知路径（以选择 png + svg 为例）：
   ```
   ✔ 图表已生成：
     output/{project-name}/diagrams/{timestamp}-dfd.png
     output/{project-name}/diagrams/{timestamp}-dfd.svg
     output/{project-name}/diagrams/{timestamp}-usecase.png
     output/{project-name}/diagrams/{timestamp}-usecase.svg
     output/{project-name}/diagrams/{timestamp}-activity.png
     output/{project-name}/diagrams/{timestamp}-activity.svg
     output/{project-name}/diagrams/{timestamp}-sequence.png
     output/{project-name}/diagrams/{timestamp}-sequence.svg
   ```

---

### 阶段 4 — 生成宣传图 / 原型图

（仅当用户选择了 [3] 或 [all]）

1. 根据文档内容，生成以下三类图像的英文提示词：

   **Banner 图**（突出项目名称、核心价值、视觉风格）
   示例提示词结构：
   ```
   A clean tech-style banner for a developer tool called "{project-name}".
   Tagline: "{one-line description}". Dark background, modern typography,
   subtle code or diagram motifs. 16:9 ratio.
   ```

   **功能展示图**（以卡片形式呈现 2-3 个核心功能）
   示例提示词结构：
   ```
   A feature showcase illustration for "{project-name}". Show {feature1},
   {feature2}, and {feature3} as clean UI cards on a light background.
   Flat design style.
   ```

   **UI 原型图**（线框图风格，展示主界面布局）
   示例提示词结构：
   ```
   A wireframe mockup of the main interface for "{project-name}".
   Show the primary workflow: {core-flow}. Grayscale, minimal, annotated.
   ```

2. 展示提示词给用户预览，用户可直接确认或修改
3. 询问图像模型：
   ```
   选择图像生成模型：
   [1] gpt-image-1  — 最高质量，通常需 OpenAI Tier 1
   [2] dall-e-3     — 质量好（推荐）
   [3] dall-e-2     — 成本最低，分辨率较低
   ```
4. 调用 `{doc_forge_dir}/scripts/image-generate.js` 的 `generateImage()` 生成图像
5. 保存到 `{output_dir}/images/{timestamp}-{type}.png`
6. 每张完成后告知路径

---

### 完成汇总

全部产物生成完毕后输出（所有路径使用 `{output_dir}` 绝对路径）：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✔ 所有产物已生成，保存于：
  {output_dir}/

📄 文档
  docs/{timestamp}-requirements.md

🗂 图表
  diagrams/{timestamp}-dfd.png
  diagrams/{timestamp}-usecase.png
  diagrams/{timestamp}-activity.png
  diagrams/{timestamp}-sequence.png

🖼 图像
  images/{timestamp}-banner.png
  images/{timestamp}-features.png
  images/{timestamp}-wireframe.png

最新产物路径记录于：output/.last-run.json
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
