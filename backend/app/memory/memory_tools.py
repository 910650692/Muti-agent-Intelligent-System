"""
Memory MCP Tools - 记忆系统工具

为Agent提供记忆能力的MCP工具集
"""

from langchain_core.tools import tool
from .service import MemoryService

# 初始化全局MemoryService实例
memory_service = MemoryService(db_path="data/memory.db")


# ==================== Phase 1: 位置记忆工具 ====================

@tool
def memory_save_location(
    user_id: str,
    label: str,
    address: str,
    poi_id: str = None,
    lat: float = None,
    lon: float = None
) -> str:
    """
    保存用户的常用地址记忆

    Args:
        user_id: 用户ID
        label: 地址标签，如 "家"、"公司"、"对象家"、"妈妈家" 等
        address: 详细地址描述
        poi_id: 可选，POI ID
        lat: 可选，纬度
        lon: 可选，经度

    Returns:
        保存结果
    """
    success = memory_service.save_location(
        user_id=user_id,
        label=label,
        address=address,
        poi_id=poi_id,
        lat=lat,
        lon=lon
    )

    if success:
        return f"[OK] 已保存地址记忆：'{label}' -> '{address}'"
    else:
        return f"[FAIL] 保存地址记忆失败"


@tool
def memory_recall_location(user_id: str, query: str) -> str:
    """
    召回用户的地址记忆（支持模糊搜索）

    这个工具会尝试在用户的地址记忆中搜索匹配的地址。
    可以通过标签（如"家"、"公司"）或地址关键词进行搜索。

    使用场景：
    - 用户说"导航到我家"、"去公司" → query="家" 或 "公司"
    - 用户说"去对象家" → query="对象家"
    - 用户说"去科技园那个地方" → query="科技园"

    Args:
        user_id: 用户ID
        query: 搜索关键词（标签或地址片段）

    Returns:
        找到的地址信息，或未找到的提示
    """
    location = memory_service.search_location(user_id=user_id, query=query)

    if location:
        # 更新使用统计
        memory_service.update_location_usage(user_id, location['label'])

        result = f"找到地址记忆: {location['label']}\n"
        result += f"- 地址: {location['address']}\n"

        if location.get('poi_id'):
            result += f"- POI ID: {location['poi_id']}\n"
        if location.get('lat') and location.get('lon'):
            result += f"- 坐标: ({location['lat']}, {location['lon']})\n"

        result += f"- 使用次数: {location['use_count']} 次"
        return result
    else:
        return f"未找到与 '{query}' 相关的地址记忆。请用户提供具体地址，或先使用 memory_save_location 保存常用地址。"


@tool
def memory_list_locations(user_id: str) -> str:
    """
    列出用户保存的所有地址记忆

    Args:
        user_id: 用户ID

    Returns:
        地址列表
    """
    locations = memory_service.list_all_locations(user_id=user_id)

    if not locations:
        return "该用户还没有保存任何地址记忆"

    result = f"用户已保存 {len(locations)} 个地址:\n"
    for loc in locations:
        result += f"- {loc['label']}: {loc['address']} (使用{loc['use_count']}次)\n"

    return result


# ==================== Phase 1: 偏好记忆工具 ====================

@tool
def memory_save_preference(
    user_id: str,
    category: str,
    key: str,
    value: str
) -> str:
    """
    保存用户偏好记忆

    Args:
        user_id: 用户ID
        category: 偏好类别，必须是以下之一:
            - "navigation": 导航偏好（如避开高速、避开拥堵）
            - "music": 音乐偏好（如喜欢的类型、歌手）
            - "food": 饮食偏好（如喜欢的菜系、口味）
            - "vehicle": 车辆设置（如座椅位置、空调温度）
        key: 偏好键，如 "avoid_highway"、"favorite_genre"
        value: 偏好值（字符串格式，会自动处理JSON）

    Returns:
        保存结果

    示例：
        memory_save_preference("user123", "navigation", "avoid_highway", "true")
        memory_save_preference("user123", "music", "favorite_genre", "摇滚")
    """
    # 验证category
    valid_categories = ["navigation", "music", "food", "vehicle"]
    if category not in valid_categories:
        return f"[FAIL] 无效的偏好类别 '{category}'，必须是: {', '.join(valid_categories)}"

    success = memory_service.save_preference(
        user_id=user_id,
        category=category,
        key=key,
        value=value
    )

    if success:
        return f"[OK] 已保存偏好记忆: [{category}] {key} = {value}"
    else:
        return f"[FAIL] 保存偏好记忆失败"


@tool
def memory_get_preference(user_id: str, category: str, key: str = None) -> str:
    """
    获取用户偏好记忆

    Args:
        user_id: 用户ID
        category: 偏好类别 (navigation/music/food/vehicle)
        key: 可选，偏好键。如果不提供，返回该类别下所有偏好

    Returns:
        偏好值，或未找到的提示
    """
    if key:
        # 获取单个偏好
        value = memory_service.get_preference(user_id=user_id, category=category, key=key)

        if value is not None:
            return f"偏好 [{category}] {key} = {value}"
        else:
            return f"未找到偏好: [{category}] {key}"
    else:
        # 获取该类别下所有偏好
        prefs = memory_service.get_all_preferences(user_id=user_id, category=category)

        if not prefs:
            return f"该用户在 [{category}] 类别下还没有保存任何偏好"

        result = f"用户在 [{category}] 类别下的偏好:\n"
        for k, v in prefs.items():
            result += f"- {k}: {v}\n"

        return result


@tool
def memory_get_all_preferences(user_id: str) -> str:
    """
    获取用户的所有偏好记忆

    Args:
        user_id: 用户ID

    Returns:
        所有偏好的字典
    """
    all_prefs = memory_service.get_all_preferences(user_id=user_id)

    if not all_prefs:
        return "该用户还没有保存任何偏好记忆"

    result = "用户的所有偏好:\n"
    for category, prefs in all_prefs.items():
        result += f"\n[{category}]\n"
        for key, value in prefs.items():
            result += f"  - {key}: {value}\n"

    return result


# ==================== Phase 1 工具列表 ====================

phase1_tools = [
    # 位置记忆
    memory_save_location,
    memory_recall_location,
    memory_list_locations,
    # 偏好记忆
    memory_save_preference,
    memory_get_preference,
    memory_get_all_preferences,
]

# 默认导出Phase 1工具
memory_tools = phase1_tools


# ==================== Phase 2: 用户画像工具 ====================

@tool
def memory_save_user_profile(
    user_id: str,
    occupation: str = None,
    interests: str = None,
    age_range: str = None,
    name: str = None,
    mbti: str = None
) -> str:
    """
    保存/更新用户画像信息（支持增量更新）

    用于记录用户的基本信息和个性特征，为个性化服务提供基础。

    **重要特性**：
    - 支持**增量更新**：只需要传入新增/修改的字段，已有字段会保留
    - 可以多次调用来逐步完善用户画像
    - 只在用户明确提供信息时调用，不要自行推测

    Args:
        user_id: 用户ID（必填）
        occupation: 职业，如 "程序员"、"教师"、"医生"（可选）
        interests: 兴趣爱好，多个用逗号分隔，如 "篮球,阅读,旅游"（可选）
        age_range: 年龄段，如 "20-30"、"30-40"（可选）
        name: 姓名（可选）
        mbti: MBTI性格类型，如 "INTJ"、"ENFP"（可选）

    Returns:
        保存结果

    示例：
        # 第一次：只保存职业和兴趣
        用户："我是程序员，喜欢打篮球"
        → memory_save_user_profile("user123", occupation="程序员", interests="篮球")

        # 第二次：补充姓名（职业和兴趣会保留）
        用户："我叫张三"
        → memory_save_user_profile("user123", name="张三")

        # 结果：{ occupation: "程序员", interests: ["篮球"], name: "张三" }
    """
    # 解析 interests（逗号分隔字符串 → 列表）
    interests_list = None
    if interests:
        interests_list = [i.strip() for i in interests.split(',') if i.strip()]

    success = memory_service.save_user_profile(
        user_id=user_id,
        name=name,
        occupation=occupation,
        interests=interests_list,
        mbti=mbti,
        age_range=age_range
    )

    if success:
        parts = []
        if occupation:
            parts.append(f"职业: {occupation}")
        if interests_list:
            parts.append(f"兴趣: {', '.join(interests_list)}")
        if age_range:
            parts.append(f"年龄段: {age_range}")
        if name:
            parts.append(f"姓名: {name}")
        if mbti:
            parts.append(f"MBTI: {mbti}")

        info = ", ".join(parts) if parts else "用户画像"
        return f"[OK] 已保存用户画像: {info}"
    else:
        return f"[FAIL] 保存用户画像失败"


@tool
def memory_get_user_profile(user_id: str) -> str:
    """
    获取用户画像信息

    用于召回用户的基本信息，在需要个性化推荐时使用。

    Args:
        user_id: 用户ID

    Returns:
        用户画像信息，或未找到的提示
    """
    profile = memory_service.get_user_profile(user_id=user_id)

    if not profile:
        return "该用户还没有保存画像信息"

    result = "用户画像:\n"
    if profile.get('name'):
        result += f"- 姓名: {profile['name']}\n"
    if profile.get('occupation'):
        result += f"- 职业: {profile['occupation']}\n"
    if profile.get('interests'):
        result += f"- 兴趣: {', '.join(profile['interests'])}\n"
    if profile.get('age_range'):
        result += f"- 年龄段: {profile['age_range']}\n"
    if profile.get('mbti'):
        result += f"- MBTI: {profile['mbti']}\n"

    return result


# ==================== Phase 2: 关系网络工具 ====================

@tool
def memory_save_relationship(
    user_id: str,
    name: str,
    relation: str = None,
    home_address: str = None,
    phone: str = None
) -> str:
    """
    保存关系网络信息（联系人）

    用于记录用户的联系人信息（朋友、家人、同事等），方便后续快速导航或联系。
    **重要**：只在用户明确提供信息时调用。

    使用场景：
    - 用户说"导航到我朋友张三家，地址是XX路XX号" → 询问是否保存
    - 用户说"记住张三的地址" → 调用此工具

    Args:
        user_id: 用户ID（必填）
        name: 联系人姓名（必填）
        relation: 关系，如 "朋友"、"同事"、"对象"、"母亲"、"父亲"（可选）
        home_address: 家庭地址（可选）
        phone: 电话号码（可选）

    Returns:
        保存结果

    示例：
        用户："导航到我朋友张三家，朝阳路123号"
        → memory_save_relationship("user123", name="张三", relation="朋友", home_address="朝阳路123号")
    """
    success = memory_service.save_relationship(
        user_id=user_id,
        name=name,
        relation=relation,
        home_address=home_address,
        phone=phone
    )

    if success:
        info_parts = [f"姓名: {name}"]
        if relation:
            info_parts.append(f"关系: {relation}")
        if home_address:
            info_parts.append(f"地址: {home_address}")
        if phone:
            info_parts.append(f"电话: {phone}")

        info = ", ".join(info_parts)
        return f"[OK] 已保存联系人信息: {info}"
    else:
        return f"[FAIL] 保存联系人信息失败"


@tool
def memory_get_relationship(user_id: str, name: str) -> str:
    """
    获取关系网络信息（通过姓名查询）

    用于召回联系人的信息（地址、电话等）。

    Args:
        user_id: 用户ID
        name: 联系人姓名

    Returns:
        联系人信息，或未找到的提示
    """
    relationship = memory_service.get_relationship(user_id=user_id, name=name)

    if not relationship:
        return f"未找到联系人 '{name}' 的信息"

    result = f"联系人信息: {relationship['name']}\n"
    if relationship.get('relation'):
        result += f"- 关系: {relationship['relation']}\n"
    if relationship.get('home_address'):
        result += f"- 地址: {relationship['home_address']}\n"
    if relationship.get('phone'):
        result += f"- 电话: {relationship['phone']}\n"

    return result


@tool
def memory_list_relationships(user_id: str) -> str:
    """
    列出用户的所有联系人

    Args:
        user_id: 用户ID

    Returns:
        联系人列表
    """
    relationships = memory_service.list_all_relationships(user_id=user_id)

    if not relationships:
        return "该用户还没有保存任何联系人信息"

    result = f"用户已保存 {len(relationships)} 个联系人:\n"
    for rel in relationships:
        info = f"- {rel['name']}"
        if rel.get('relation'):
            info += f" ({rel['relation']})"
        if rel.get('home_address'):
            info += f": {rel['home_address']}"
        result += info + "\n"

    return result


# ==================== Phase 2 工具列表 ====================

phase2_tools = [
    # 用户画像
    memory_save_user_profile,
    memory_get_user_profile,
    # 关系网络
    memory_save_relationship,
    memory_get_relationship,
    memory_list_relationships,
]

# 更新默认导出（包含 Phase 1 + Phase 2）
memory_tools = phase1_tools + phase2_tools


# ==================== Phase 3: 预留 ====================
# Phase 3 will add:
#   - memory_smart_recall
#   - memory_save_conversation_snapshot
#   - memory_get_context_summary
