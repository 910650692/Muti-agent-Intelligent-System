"""
环境模拟器 - 模拟车辆和环境传感器数据

支持：
1. 车辆状态（温度、挡位、GPS、电量等）
2. 外部环境（天气、时间、季节）
3. 用户上下文（从记忆系统读取）
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import random


@dataclass
class VehicleState:
    """车辆状态数据"""
    # 温度相关
    cabin_temperature: float  # 车内温度（°C）
    outdoor_temperature: float  # 车外温度（°C）

    # 车辆状态
    gear: str  # 挡位：P/D/R/N
    doors_closed: bool  # 车门是否关闭
    speed: float  # 车速（km/h）
    battery_level: int  # 电量（0-100）

    # 位置相关
    location: Dict[str, float]  # {"lat": xx, "lon": xx}

    # 导航相关
    is_navigation_active: bool  # 是否在导航中
    navigation_remaining_km: float  # 剩余里程（km）
    navigation_remaining_time: int  # 剩余时间（分钟）
    navigation_destination: Optional[str]  # 目的地名称

    # 环境感知
    rain_sensor_active: bool  # 雨量传感器是否激活

    # 时间上下文
    time_of_day: str  # morning/afternoon/evening/night
    current_time: str  # HH:MM
    current_date: str  # YYYY-MM-DD
    season: str  # 春季/夏季/秋季/冬季
    is_working_day: bool  # 是否工作日

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


class EnvironmentSimulator:
    """
    环境模拟器

    Demo模式：根据时间段和配置返回模拟数据
    未来可以接入真实传感器/WebSocket
    """

    def __init__(self, scenario_config: Optional[Dict] = None):
        """
        初始化

        Args:
            scenario_config: 场景配置（用于测试特定场景）
                例如：{"force_winter_morning": True}
        """
        self.scenario = scenario_config or {}
        self._init_base_data()

    def _init_base_data(self):
        """初始化基础数据（常用地址等）"""
        self.base_data = {
            "user_home": {"lat": 31.230, "lon": 121.470},
            "user_office": {"lat": 31.240, "lon": 121.480},
        }

    async def get_vehicle_state(self) -> VehicleState:
        """
        获取车辆状态（模拟）

        根据当前时间或强制场景返回数据
        """
        now = datetime.now()
        hour = now.hour

        # 强制场景：冬季上车（用于测试）
        if self.scenario.get("force_winter_morning"):
            return self._create_winter_morning_scene(now)

        # 强制场景：长途导航
        if self.scenario.get("force_long_trip"):
            return self._create_long_trip_scene(now)

        # 强制场景：夜间回家
        if self.scenario.get("force_goodnight"):
            return self._create_goodnight_scene(now)

        # 自动场景：根据时间判断
        if 8 <= hour < 9:
            # 早上上班时间
            return self._create_winter_morning_scene(now)
        elif 22 <= hour < 24:
            # 夜间回家
            return self._create_goodnight_scene(now)
        else:
            # 默认场景：随机生成
            return self._create_default_scene(now)

    def _create_winter_morning_scene(self, now: datetime) -> VehicleState:
        """冬季上车场景"""
        return VehicleState(
            cabin_temperature=12.0,  # 低于15°C，触发冬季关怀
            outdoor_temperature=5.0,
            gear="P",
            doors_closed=True,
            speed=0.0,
            battery_level=85,
            location=self.base_data["user_home"],
            is_navigation_active=False,
            navigation_remaining_km=0.0,
            navigation_remaining_time=0,
            navigation_destination=None,
            rain_sensor_active=False,
            time_of_day="morning",
            current_time=now.strftime("%H:%M"),
            current_date=now.strftime("%Y-%m-%d"),
            season=self._get_season(now.month),
            is_working_day=now.weekday() < 5,
        )

    def _create_long_trip_scene(self, now: datetime) -> VehicleState:
        """长途导航场景"""
        return VehicleState(
            cabin_temperature=24.0,
            outdoor_temperature=28.0,
            gear="D",
            doors_closed=True,
            speed=100.0,  # 高速行驶
            battery_level=25,  # 电量低，触发充电提醒
            location={"lat": 31.500, "lon": 121.800},
            is_navigation_active=True,
            navigation_remaining_km=120.0,  # 剩余120km
            navigation_remaining_time=75,  # 剩余75分钟
            navigation_destination="杭州西湖",
            rain_sensor_active=False,
            time_of_day=self._get_time_of_day(now.hour),
            current_time=now.strftime("%H:%M"),
            current_date=now.strftime("%Y-%m-%d"),
            season=self._get_season(now.month),
            is_working_day=now.weekday() < 5,
        )

    def _create_goodnight_scene(self, now: datetime) -> VehicleState:
        """夜间回家场景"""
        return VehicleState(
            cabin_temperature=22.0,
            outdoor_temperature=18.0,
            gear="P",
            doors_closed=True,
            speed=0.0,
            battery_level=60,
            location=self.base_data["user_home"],  # 在家附近
            is_navigation_active=False,
            navigation_remaining_km=0.0,
            navigation_remaining_time=0,
            navigation_destination=None,
            rain_sensor_active=False,
            time_of_day="night",
            current_time=now.strftime("%H:%M"),
            current_date=now.strftime("%Y-%m-%d"),
            season=self._get_season(now.month),
            is_working_day=now.weekday() < 5,
        )

    def _create_default_scene(self, now: datetime) -> VehicleState:
        """默认场景：随机生成"""
        return VehicleState(
            cabin_temperature=random.randint(20, 30),
            outdoor_temperature=random.randint(15, 35),
            gear="P",
            doors_closed=True,
            speed=0.0,
            battery_level=random.randint(50, 100),
            location=self.base_data["user_home"],
            is_navigation_active=False,
            navigation_remaining_km=0.0,
            navigation_remaining_time=0,
            navigation_destination=None,
            rain_sensor_active=False,
            time_of_day=self._get_time_of_day(now.hour),
            current_time=now.strftime("%H:%M"),
            current_date=now.strftime("%Y-%m-%d"),
            season=self._get_season(now.month),
            is_working_day=now.weekday() < 5,
        )

    async def get_user_context(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户上下文（从记忆系统读取）

        Returns:
            {
                "profile": {...},  # 用户画像
                "locations": [...],  # 常用地址
                "preferences": {...},  # 偏好设置
                "relationships": [...]  # 关系网络
            }
        """
        try:
            from app.memory.service import MemoryService

            memory_service = MemoryService()

            return {
                "profile": await memory_service.get_user_profile(user_id),
                "locations": await memory_service.get_all_locations(user_id),
                "preferences": await memory_service.get_all_preferences(user_id),
                "relationships": await memory_service.get_all_relationships(user_id),
            }
        except Exception as e:
            # 如果记忆系统不可用，返回空数据
            return {
                "profile": None,
                "locations": [],
                "preferences": {},
                "relationships": [],
            }

    def _get_season(self, month: int) -> str:
        """根据月份返回季节"""
        if month in [12, 1, 2]:
            return "冬季"
        elif month in [3, 4, 5]:
            return "春季"
        elif month in [6, 7, 8]:
            return "夏季"
        else:
            return "秋季"

    def _get_time_of_day(self, hour: int) -> str:
        """根据小时返回时段"""
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 18:
            return "afternoon"
        elif 18 <= hour < 22:
            return "evening"
        else:
            return "night"

    def set_scenario(self, scenario: Dict[str, Any]):
        """动态设置场景（用于测试）"""
        self.scenario = scenario
