"""原生 Tool 查询意图识别。"""


def query_needs_datetime(query: str) -> bool:
    q = (query or "").strip()
    if not q:
        return False
    keywords = (
        "几点", "几号", "多少号", "星期", "周几", "礼拜", "今天", "明天",
        "现在几", "当前时间", "现在时间", "今天日期", "今天是哪天", "哪天",
        "what time", "what date", "日期",
    )
    q_lower = q.casefold()
    return any((kw in q) if any("\u4e00" <= c <= "\u9fff" for c in kw) else (kw in q_lower) for kw in keywords)


def query_needs_native_tools(query: str) -> bool:
    q = (query or "").strip()
    if not q:
        return False
    keywords = (
        "天气", "气温", "温度", "下雨", "下雪", "降雨", "风力", "湿度",
        "几点", "几号", "多少号", "星期", "周几", "礼拜", "今天", "明天",
        "现在几", "当前时间", "现在时间", "今天日期", "今天是哪天", "哪天",
        "what time", "what date", "weather",
    )
    q_lower = q.casefold()
    return any((kw in q) if any("\u4e00" <= c <= "\u9fff" for c in kw) else (kw in q_lower) for kw in keywords)


def is_simple_datetime_query(query: str) -> bool:
    q = (query or "").strip()
    if not q or not query_needs_datetime(q):
        return False
    if any(k in q for k in ("天气", "气温", "温度", "下雨", "下雪", "weather")):
        return False
    if any(k in q for k in ("介绍", "为什么", "如何", "论文", "查询", "搜索", "帮我写", "分析")):
        return False
    return len(q) <= 32
