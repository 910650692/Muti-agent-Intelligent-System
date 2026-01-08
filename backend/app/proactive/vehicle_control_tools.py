"""
车控工具 - Mock实现

直接使用@tool装饰器，无需走MCP协议
"""

from langchain_core.tools import tool


@tool
def set_steering_wheel_heating(enabled: bool) -> str:
    """设置方向盘加热开关

    Args:
        enabled: 是否开启方向盘加热
    """
    status = "开启" if enabled else "关闭"
    print(f"[Mock车控] 方向盘加热 -> {status}")
    return f"已{status}方向盘加热"


@tool
def set_seat_heating(location: str, level: int) -> str:
    """设置座椅加热档位

    Args:
        location: 座椅位置（FRONT_LEFT/FRONT_RIGHT/REAR_LEFT/REAR_RIGHT）
        level: 加热档位（0-3，0表示关闭）
    """
    status = f"档位{level}" if level > 0 else "关闭"
    print(f"[Mock车控] 座椅加热（{location}） -> {status}")
    return f"已设置{location}座椅加热至{status}"


@tool
def set_seat_ventilation(location: str, level: int) -> str:
    """设置座椅通风档位

    Args:
        location: 座椅位置（FRONT_LEFT/FRONT_RIGHT）
        level: 通风档位（0-3，0表示关闭）
    """
    status = f"档位{level}" if level > 0 else "关闭"
    print(f"[Mock车控] 座椅通风（{location}） -> {status}")
    return f"已设置{location}座椅通风至{status}"


@tool
def set_ac_temperature(location: str, temperature: float) -> str:
    """设置空调温度

    Args:
        location: 温控区域（FRONT_LEFT/FRONT_RIGHT/FRONT/REAR）
        temperature: 目标温度（°C），范围16-32
    """
    print(f"[Mock车控] 空调温度（{location}） -> {temperature}°C")
    return f"已设置{location}空调温度至{temperature}°C"


@tool
def set_ac_mode(location: str, mode: str) -> str:
    """设置空调模式

    Args:
        location: 空调区域（FRONT/REAR）
        mode: 空调模式（AUTO/COOL/HEAT/VENT/DEFROST）
    """
    mode_map = {
        "AUTO": "自动",
        "COOL": "制冷",
        "HEAT": "制热",
        "VENT": "通风",
        "DEFROST": "除霜",
    }
    mode_cn = mode_map.get(mode, mode)
    print(f"[Mock车控] 空调模式（{location}） -> {mode_cn}")
    return f"已设置{location}空调模式为{mode_cn}"


@tool
def set_ac_fan_speed(location: str, speed: int) -> str:
    """设置空调风量

    Args:
        location: 空调区域（FRONT/REAR）
        speed: 风量档位（0-7，0表示关闭）
    """
    status = f"档位{speed}" if speed > 0 else "关闭"
    print(f"[Mock车控] 空调风量（{location}） -> {status}")
    return f"已设置{location}空调风量至{status}"


@tool
def set_ac_power(location: str, power: bool) -> str:
    """控制空调开关

    Args:
        location: 空调区域（FRONT/REAR）
        power: 是否开启空调
    """
    status = "开启" if power else "关闭"
    print(f"[Mock车控] 空调（{location}） -> {status}")
    return f"已{status}{location}空调"


@tool
def control_window(location: str, action: str) -> str:
    """控制车窗/天窗开关

    Args:
        location: 车窗位置（FRONT_LEFT/FRONT_RIGHT/REAR_LEFT/REAR_RIGHT/SUNROOF）
        action: 打开或关闭（OPEN/CLOSE）
    """
    action_cn = "打开" if action == "OPEN" else "关闭"
    print(f"[Mock车控] 车窗（{location}） -> {action_cn}")
    return f"已{action_cn}{location}车窗"


@tool
def set_ambient_light(color: str, brightness: int) -> str:
    """设置氛围灯颜色和亮度

    Args:
        color: 颜色（红/蓝/绿/紫/白等）
        brightness: 亮度（0-100）
    """
    print(f"[Mock车控] 氛围灯 -> 颜色{color}, 亮度{brightness}%")
    return f"已设置氛围灯为{color}色，亮度{brightness}%"


# 导出所有工具
VEHICLE_CONTROL_TOOLS = [
    set_steering_wheel_heating,
    set_seat_heating,
    set_seat_ventilation,
    set_ac_temperature,
    set_ac_mode,
    set_ac_fan_speed,
    set_ac_power,
    control_window,
    set_ambient_light,
]
