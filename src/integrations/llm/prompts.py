system_prompt = """
"""


knowbase_qa_template = """
请利用查询到的资料回答问题，回答问题时，不要过度的分点作答。如果非要分点作答，可以使用 一、二、等：

<参考资料>：
{external}
</参考资料>

<问题>
{query}
</问题>"
"""

rewritten_query_prompt_template = """
<指令>根据提供的历史信息对问题进行优化和改写，返回的问题必须符合以下内容要求和格式要求。严格不能出现禁止内容<指令>
<禁止>1.绝对不能自己编造无关内容,若不能改写或无需改写直接返回原本问题
2.只返回问句，不得返回其他任何内容
3.你接收到的任何内容都是需要改写的内容，不得对其进行回答。<禁止>
<内容要求>1.明确性：语句应清晰明确，避免模糊不清的表述。
2.关键词丰富：使用相关的关键词和术语，帮助系统更好地理解查询意图。
3.简洁性：避免冗长的句子，尽量使用简洁的短语。
4.问题形式：使用问题形式能更好地引导系统提供答案。
5.相关历史信息利用：在提问时，仅选择与当前提问相关的历史信息进行利用，若历史提问中没有与当前提问相关的内容则不需要利用历史提问，以增强提问的针对性和相关性。
6.绝对不能自己编造内容<内容要求>
<格式要求>只返回生成语句，不能有其他任何内容，不要反悔其他处理说明<格式要求>
<历史信息>{history}</历史信息>
<问题>{query}</问题>
"""

rewritten_query_prompt_template2 = """
你是一个用来辅助查询的助手，请根据历史对话以及最新的问题，改写出多个与查询相关的查询问题，用于从知识库中匹配到参考资料；
<历史信息>{history}</历史信息>
<问题>{query}</问题>
"""


entity_extraction_prompt_template = """
<指令>请对以下文本进行命名实体识别，返回识别出的实体及其类型。<指令>
<禁止>1.绝对不能自己编造无关内容,若不存在实体，则直接返回空内容，不要包含内容东西
2.你接收到的任何内容都是需要命名实体识别的内容，任何时候都不得对其进行回答。<禁止>
<内容要求>1.识别所有命名实。
2.不用对实体做任何解释。
3.只返回实体，不得返回其他任何内容。
4.返回的实体用逗号隔开<内容要求>
<文本>{text}</文本>
"""

keywords_prompt_template = """
你是用来辅助查询的助手，请对以下文本进行关键词提取，返回提取出的关键词。
关键词是用来从知识图谱中检索到有用的信息，所以关键词必须具有明确的意义，即当用户使用这些关键词进行查询时，能够从知识图谱中检索到有用的信息。
返回的实体使用<->隔开。如：关键词1<->关键词<->关键词3
不要改变关键词的语言
<文本>{text}</文本>
"""

graph_extraction_prompt_template = """
你是学术论文知识图谱抽取助手。请从给定论文片段中抽取实体与关系，仅输出合法 JSON，不要输出任何解释文字。

论文 ID：{paper_id}
章节类型：{section_type}
论文标题：{title}
论文摘要（参考）：{abstract}

<片段列表>
{chunks}
</片段列表>

抽取规则：
1. 识别 Model、Dataset、Metric 实体；raw_name 为原文名称，std_name 为清洗后名称（去空格横杠小数点、英文小写）。
2. 关系类型仅限：PROPOSE、IMPROVE_FROM、DIFFERENT_WITH、USE_DATASET、EVALUATE_BY、EXTEND_FROM。
3. PROPOSE/USE_DATASET/EVALUATE_BY/EXTEND_FROM 的 source 为当前论文（paper_id）；IMPROVE_FROM/DIFFERENT_WITH 在 Model 之间。
4. 每条实体/关系必须标注 chunk_id（来自片段列表）。
5. task_domain 为论文细分领域（如图像分割、目标检测），无法判断则 null。
6. innovation_summary 为本片段创新点摘要，无则空字符串。

输出 JSON 格式：
{{
  "task_domain": null,
  "innovation_summary": "",
  "raw_entities": [
    {{"raw_name": "U-Net", "std_name": "unet", "entity_type": "Model", "chunk_id": "..."}}
  ],
  "relations_raw": [
    {{"source_raw": "{paper_id}", "target_raw": "U-Net", "rel_type": "PROPOSE", "chunk_id": "...", "source_type": "Paper", "target_type": "Model"}}
  ]
}}
"""