from src.utils.logging_config import logger


def select_model(config):
    model_provider = config.model_provider
    model_name = config.model_name

    logger.info(f"Selecting model from {model_provider} with {model_name}")

    if model_provider == "deepseek":
        from src.integrations.llm.chat import DeepSeekNew
        return DeepSeekNew(model_name)
    if model_provider == "deepseekNew":
        from src.integrations.llm.chat import DeepSeekLocal
        return DeepSeekLocal(model_name)
    if model_provider == "zhipu":
        from src.integrations.llm.chat import ZhipuNew
        return ZhipuNew(model_name)
    if model_provider == "qianfan":
        from src.integrations.llm.chat import Qianfan
        return Qianfan(model_name)
    if model_provider == "dashscope":
        from src.integrations.llm.chat import DashScope
        return DashScope(model_name)
    if model_provider == "openai":
        from src.integrations.llm.chat import OpenModelNew
        return OpenModelNew(model_name)
    if model_provider == "siliconflow":
        from src.integrations.llm.chat import SiliconFlowNew
        return SiliconFlowNew(model_name)
    if model_provider == "custom":
        model_info = next((x for x in config.custom_models if x["custom_id"] == model_name), None)
        if model_info is None:
            raise ValueError(f"Model {model_name} not found in custom models")
        from src.integrations.llm.chat import CustomModel
        return CustomModel(model_info)
    if model_provider is None:
        raise ValueError("Model provider not specified")
    raise ValueError(f"Model provider {model_provider} not supported")
