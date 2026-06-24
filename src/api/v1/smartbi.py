import json
import os
import re
import shutil
from src.services.rag.startup import startup
from fastapi import FastAPI, File, UploadFile, APIRouter, Depends, Body
from src.utils import setup_logger

smartbi = APIRouter(prefix="/smartbi")
router = smartbi

logger = setup_logger("server-smartbi")

@smartbi.get("/")
def get_databases(
):
    '''
        获取系统中所有数据库的信息
        此函数尝试调用数据库管理模块的get_databases()方法来获取数据库的列表
        调用成功的话，直接赶回数据库的列表；如果调用失败的话，返回字典信息
    '''
    try:
        database = startup.dbm.get_databases()
    except Exception as e:
        return {"message": f"获取数据库列表失败 {e}", "databases": []}
    return database

@smartbi.post("/generate-graph")
def query_test(query: str = Body(...), #分析目标
                    title: str = Body(...), #图表名
                    type: str = Body(...), #图表类型 柱状图/饼状图
                    meta: dict = Body(...)): #数据库源   db_name

    logger.debug(f"Query test in : {meta}")

    new_query=""
    result = startup.retriever.query_knowledgebase(query, history=None, refs={"meta": meta})
    results = result.get("results", [])
    new_query = "".join(result["entity"]["text"] for result in results[:5])

    logger.info("模型检索结果为：{}".format(new_query))

    prompt = """[
    你是一位专业的数据可视化专家，熟知 ECharts 5.x 版本的各项功能和特性。现在，你需要根据以下提供的知识库信息，并从中抽取出#分析目标中需要的信息，然后根据指定的图表类型，生成一段完整且可直接使用的 ECharts 代码，用于在网页中展示数据。并给出对数据分析的结论，并将结果封装在<输出表格></输出表格>  <分析结论></分析结论> 两个封闭<>标签

#知识库信息
{knowlege}
#分析目标
{objective}
#图表类型
{graph_type}
#标题
{title}

<输出表格>
你的输出结果应该是一个符合Echarts图标规范的名为option的{graph_type}图像，标题为{title}.请确保柱状图中每两个种类之间的距离适中，避免柱子重叠。你可以通过调整柱子的宽度（barWidth）和x轴的类别间距来实现这一点.
</输出表格>

<分析结论>
此处填写根据{objective}中的要求分析{knowlege}得出的结论
</分析结论>

#一个柱状图的例子
##知识库信息
一周内网站的访问量情况如下：周一的访问量是10次，到了周二，访问量增加到52次，周三的访问量继续上升，达到了200次，周四访问量进一步增加，达到了334次，周五是访问量的最高峰，达到了390次，周六访问量略有下降，为330次，周日的访问量则减少到了220次。

##图表类型
柱状图

##标题
Referer of a Website

<输出表格>
{{
    "title": {{
        "text": "Referer of a Website",
        "left": "left"
    }},
    "tooltip": {{
        "trigger": "axis",
        "axisPointer": {{
            "type": "shadow"
        }}
    }},
    "grid": {{
        "left": "3%",
        "right": "4%",
        "bottom": "3%",
        "containLabel": true
    }},
    "xAxis": [
        {{
            "type": "category",
            "data": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "axisTick": {{
                "alignWithLabel": true
            }}
        }}
    ],
    "yAxis": [
        {{
            "type": "value"
        }}
    ],
    "series": [
        {{
            "name": "Direct",
            "type": "bar",
            "barWidth": "60%",
            "data": [10, 52, 200, 334, 390, 330, 220]
        }}
    ]
}}
</输出表格>

<分析结论>
根据给定的数据，可以看出网站用户数在前四天内增长很快，最高峰达到了90人，但是在第五天出现了用户流失，到了第六天才又有用户增加。需要进一步分析为什么会出现用户流失，是否有对应的网站上线或者营销推广策略调整等因素导致。
</分析结论>

#你的输出必须满足以下要求：
输出结果必须包括<输出表格></输出表格>  <分析结论></分析结论> 两个封闭<>标签
<输出表格>此处填写echarts代码,echarts代码中必须根据##知识库信息填入具体的数据，echarts代码严格包裹在<输出表格>中，直接存放option对象，不要输出任何注释</输出表格><分析结论>此处填写分析的结论</分析结论>


    ]"""
    prompt= prompt.format(objective = query,
                  graph_type = type,
                  title = title,
                  knowlege = new_query)

    logger.info(f"prompt:{prompt}")

    content = ""
    # 初始化响应内容字典
    response_content = {
        'reasoning_content': '',
        'content': ''
    }

    # 使用模型预测响应，并实时生成响应块
    for delta in startup.model.predict(prompt, stream=True):
        if not delta.content:
            continue
        if startup.model.model_name == "deepseek-r1:32b" or startup.model.model_name == "deepseek-r1:14b":
            if hasattr(delta, 'is_full') and delta.is_full:
                if hasattr(delta, 'reasoning_content'):
                    response_content['reasoning_content'] = delta.reasoning_content
                response_content['content'] = delta.content
                content = delta.content
            else:
                if hasattr(delta, 'reasoning_content'):
                    response_content['reasoning_content'] += delta.reasoning_content
                response_content['content'] += delta.content
                content += delta.content

        else:
            if hasattr(delta, 'is_full') and delta.is_full:
                response_content['content'] = delta.content
                content = delta.content
            else:
                response_content['content'] += delta.content
                content += delta.content
    logger.info("模型响应结果为：",content)
    # print("————————————")
    # print(content)

    formatted_option=""
    output_table_match = re.search(r'<输出表格>(.*?)</输出表格>', content, re.DOTALL)
    analysis_conclusion_match = re.search(r'<分析结论>(.*?)</分析结论>', content, re.DOTALL)

    # 提取匹配的内容
    output_table_content = output_table_match.group(1).strip() if output_table_match else None
    analysis_conclusion_content = analysis_conclusion_match.group(1).strip() if analysis_conclusion_match else None

    # 去掉字符串中的注释和多余的空格
    content = output_table_content or ""
    if "option = " in content:
        option_str = content.replace("option = ", "").strip()
    else:
        option_str = content.strip()

    # 将单引号转换为双引号
    option_str = option_str.replace("'", '"')



    option_json = ""
    # 将字符串转换为 JSON 对象
    # try:
    #     option_json = json.loads(option_str)
    # except json.JSONDecodeError as e:
    #     print("JSON 解析错误:", e)

    if option_str.strip():  # 检查字符串是否为空或仅由空格组成
        try:
            option_json = json.loads(option_str)
        except json.JSONDecodeError as e:
            print("JSON 解析错误:", e)
    else:
        print("没有有效的JSON内容")

    print(f"处理后的字符串：{option_json}")

    result = {"option":option_json,"analysis":analysis_conclusion_content}

    return result

if __name__ == "__main__":
    query = """{\n    title: {\n        text: '销售数据',\n        left: 'center'\n    },\n    tooltip: {\n        trigger: 'axis',\n        axisPointer: {\n    
        type: 'shadow'\n        }\n    },\n    xAxis: [\n        {\n            type: 'category',\n            data: ['电子产品', '家居用品', '服装', '食品', '书籍', '化妆品', '运 
动器材'],\n            axisTick: {\n                alignWithLabel: true\n            }\n        }\n    ],\n    yAxis: [\n        {\n            type: 'value'\n        }\n    ],\n 
   series: [\n        {\n            name: '第一季度',\n            type: 'bar',\n            barWidth: '30%',\n            data: [150, 90, 200, 80, 120, 60, 100]\n        },\n    
    {\n            name: '第二季度',\n            type: 'bar',\n            barWidth: '30%',\n            data: [180, 110, 220, 90, 140, 70, 120]\n        }\n    ]\n}"""

    query = query.replace("\n", "")
    query = query.replace("\\", "")

    print(query)