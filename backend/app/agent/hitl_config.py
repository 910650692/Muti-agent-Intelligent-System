"""Human-in-the-Loop (HITL) 配置

定义哪些工具需要人工确认、哪些返回结果需要用户选择
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class HITLConfig:
    """HITL 配置类"""

    # ===== 执行前确认：高风险操作 =====
    # 这些工具在执行前需要用户确认
    require_confirmation: List[str] = field(default_factory=lambda: [
        # 导航控制类 - 使用实际工具名（带 sgm-navigation_ 前缀）
        "sgm-navigation_com_sgm_navi_hmi_set_destination",
        "sgm-navigation_com_sgm_navi_hmi_add_via_poi",
        # 兼容不带前缀的名称
        "com_sgm_navi_hmi_set_destination",
        "com_sgm_navi_hmi_add_via_poi",
        "start_navigation",
        "stop_navigation",
        # 订票/支付类
        "book_ticket",
        "cancel_ticket",
        "pay_order",
        # 记忆系统 - 隐私敏感信息需要用户确认
        "memory_save_user_profile",
        "memory_save_relationship",
    ])

    # ===== 执行后选择：返回候选列表的工具 =====
    # 这些工具返回多个结果时需要用户选择
    #
    # ⚠️ 设计理念：
    # 1. POI 搜索工具已移除 - 让 LLM 自己判断如何处理多个结果
    #    - 查询场景：用户想看所有结果，LLM 直接返回
    #    - 导航场景：LLM 通过对话询问用户选择哪个
    # 2. 只保留真正需要强制选择的工具（如果有）
    require_selection: List[str] = field(default_factory=lambda: [
        # 如果有其他需要强制选择的工具，添加在这里
        # 例如：路线方案选择（多条路线让用户选）
    ])

    # ===== 缺参追问：友好的提示语 =====
    # 当工具参数缺失时，使用这些提示语追问用户
    param_prompts: Dict[str, Dict[str, str]] = field(default_factory=lambda: {
        "get_weather": {
            "city": "请问您想查询哪个城市的天气？"
        },
        "sgm-navigation_com_sgm_navi_hmi_request_poi_search": {
            "keyword": "请问您想搜索什么地点？"
        },
        "com_sgm_navi_hmi_request_poi_search": {
            "keyword": "请问您想搜索什么地点？"
        },
        "search_poi": {
            "keyword": "请问您想搜索什么地点？"
        },
        "search_nearby_poi": {
            "keyword": "请问您想找附近的什么？"
        },
        "sgm-navigation_com_sgm_navi_hmi_set_destination": {
            "poi_name": "请问您想导航去哪里？"
        },
        "com_sgm_navi_hmi_set_destination": {
            "poi_name": "请问您想导航去哪里？"
        },
        "start_navigation": {
            "destination": "请问您想导航去哪里？"
        },
        "query_tickets": {
            "from_station": "请问您从哪里出发？",
            "to_station": "请问您要去哪里？",
            "date": "请问您要查询哪天的票？"
        },
    })

    # ===== 确认消息模板 =====
    confirmation_templates: Dict[str, str] = field(default_factory=lambda: {
        "sgm-navigation_com_sgm_navi_hmi_set_destination": "即将为您导航到 {poi_name}，确认启动导航吗？",
        "com_sgm_navi_hmi_set_destination": "即将为您导航到 {poi_name}，确认启动导航吗？",
        "sgm-navigation_com_sgm_navi_hmi_add_via_poi": "确认要添加途经点吗？",
        "com_sgm_navi_hmi_add_via_poi": "确认要添加途经点吗？",
        "start_navigation": "即将为您导航到 {destination}，确认启动导航吗？",
        "stop_navigation": "确认要停止当前导航吗？",
        "book_ticket": "确认要预订 {train_no} 次列车（{from_station} → {to_station}）吗？",
        "cancel_ticket": "确认要取消订单吗？此操作不可撤销。",
        # 记忆系统确认消息
        "memory_save_user_profile": "检测到以下个人信息，是否保存？",
        "memory_save_relationship": "检测到以下联系人信息，是否保存？",
        "default": "确认要执行此操作吗？"
    })

    # ===== 选择消息模板 =====
    selection_templates: Dict[str, str] = field(default_factory=lambda: {
        "sgm-navigation_com_sgm_navi_hmi_request_poi_search": "找到 {count} 个结果，请选择您要去的地点：",
        "com_sgm_navi_hmi_request_poi_search": "找到 {count} 个结果，请选择您要去的地点：",
        "search_poi": "找到 {count} 个结果，请选择：",
        "search_nearby_poi": "在附近找到 {count} 个地点，请选择：",
        "query_tickets": "找到 {count} 个车次，请选择：",
        "default": "找到多个结果，请选择："
    })


# 全局配置实例
hitl_config = HITLConfig()


def need_confirmation(tool_name: str) -> bool:
    """检查工具是否需要执行前确认"""
    return tool_name in hitl_config.require_confirmation


def need_selection(tool_name: str) -> bool:
    """检查工具是否可能需要执行后选择"""
    return tool_name in hitl_config.require_selection


def get_missing_param_prompt(tool_name: str, param_name: str) -> Optional[str]:
    """获取缺失参数的追问提示语"""
    tool_prompts = hitl_config.param_prompts.get(tool_name, {})
    return tool_prompts.get(param_name)


def get_confirmation_message(tool_name: str, args: Dict[str, Any]) -> str:
    """生成确认消息"""
    template = hitl_config.confirmation_templates.get(
        tool_name,
        hitl_config.confirmation_templates["default"]
    )
    try:
        return template.format(**args)
    except KeyError:
        return hitl_config.confirmation_templates["default"]


def get_selection_message(tool_name: str, count: int) -> str:
    """生成选择消息"""
    template = hitl_config.selection_templates.get(
        tool_name,
        hitl_config.selection_templates["default"]
    )
    return template.format(count=count)


def is_candidate_list(result: Any, min_count: int = 2) -> tuple[bool, list]:
    """
    判断工具返回结果是否是候选列表

    Args:
        result: 工具返回结果
        min_count: 最小候选数量（默认2个以上才需要选择）

    Returns:
        (是否是候选列表, 候选项列表)
    """
    import json

    # 尝试解析 JSON
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
        except json.JSONDecodeError:
            return False, []
    else:
        parsed = result

    # 检查是否是列表
    if isinstance(parsed, list) and len(parsed) >= min_count:
        return True, parsed

    # 检查是否是包含列表的字典
    if isinstance(parsed, dict):
        # 常见的列表字段名（一级）
        list_keys = ["results", "items", "data", "list", "candidates", "pois", "trains", "mPoiInfoList"]
        for key in list_keys:
            if key in parsed and isinstance(parsed[key], list) and len(parsed[key]) >= min_count:
                return True, parsed[key]

        # 检查嵌套结构（如 value.mPoiInfoList）
        if "value" in parsed and isinstance(parsed["value"], dict):
            value = parsed["value"]
            for key in list_keys:
                if key in value and isinstance(value[key], list) and len(value[key]) >= min_count:
                    return True, value[key]

        # 检查 content[0].text 格式（MCP 返回格式）
        if "content" in parsed and isinstance(parsed["content"], list) and len(parsed["content"]) > 0:
            content_item = parsed["content"][0]
            if isinstance(content_item, dict) and "text" in content_item:
                try:
                    text_parsed = json.loads(content_item["text"])
                    # 递归检查
                    return is_candidate_list(text_parsed, min_count)
                except (json.JSONDecodeError, TypeError):
                    pass

    return False, []
