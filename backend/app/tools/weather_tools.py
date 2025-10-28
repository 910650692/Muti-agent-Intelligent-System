"""天气查询工具"""
from langchain_core.tools import tool
import requests
from datetime import datetime
from ..config import config


@tool
def get_weather(city: str, days: int = 0) -> str:
    """
    查询指定城市的天气

    Args:
        city: 城市名称 (中文或英文)
        days: 查询未来第几天的天气 (0=今天, 1=明天, 2=后天, 最多4天，即未来5天内)

    Returns:
        天气信息
    """
    try:
        api_key = config.OPENWEATHER_API_KEY

        # 验证 days 参数
        if days < 0 or days > 4:
            return "查询天气失败: 只能查询今天到未来4天的天气（共5天）"

        if days == 0:
            # 查询当前天气
            url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                "q": city,
                "appid": api_key,
                "units": "metric",
                "lang": "zh_cn"
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            return f"""
{city} 今天天气:
- 温度: {data['main']['temp']}°C
- 体感温度: {data['main']['feels_like']}°C
- 天气: {data['weather'][0]['description']}
- 湿度: {data['main']['humidity']}%
- 风速: {data['wind']['speed']} m/s
"""
        else:
            # 查询未来天气预报 (5-Day / 3-Hour Forecast)
            url = "https://api.openweathermap.org/data/2.5/forecast"
            params = {
                "q": city,
                "appid": api_key,
                "units": "metric",
                "lang": "zh_cn"
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # 5-Day Forecast 返回的是每3小时的数据，共40个数据点
            # 我们需要找到对应天数的中午12点的数据（或最接近的）
            target_forecasts = []

            for forecast in data['list']:
                forecast_time = datetime.fromtimestamp(forecast['dt'])
                # 计算距离现在多少天
                days_from_now = (forecast_time.date() - datetime.now().date()).days

                if days_from_now == days:
                    target_forecasts.append(forecast)

            if not target_forecasts:
                return f"查询天气失败: 未找到 {city} 未来第{days}天的天气数据"

            # 取中间时段的数据（通常是中午）
            forecast = target_forecasts[len(target_forecasts) // 2]
            forecast_date = datetime.fromtimestamp(forecast['dt']).strftime('%Y-%m-%d %H:%M')

            day_names = ["今天", "明天", "后天", "第3天", "第4天"]
            day_name = day_names[days] if days < len(day_names) else f"第{days}天"

            return f"""
{city} {day_name}天气 ({forecast_date}):
- 温度: {forecast['main']['temp']}°C
- 体感温度: {forecast['main']['feels_like']}°C
- 天气: {forecast['weather'][0]['description']}
- 湿度: {forecast['main']['humidity']}%
- 风速: {forecast['wind']['speed']} m/s
- 降水概率: {forecast.get('pop', 0) * 100:.0f}%
"""

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return f"查询天气失败: 未找到城市 '{city}'"
        return f"查询天气失败: HTTP {e.response.status_code}"
    except Exception as e:
        return f"查询天气失败: {str(e)}"


# 导出工具列表
weather_tools = [get_weather]