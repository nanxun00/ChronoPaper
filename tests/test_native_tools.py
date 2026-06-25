from unittest.mock import patch

from src.integrations.native_tools.datetime_tool import get_current_datetime
from src.integrations.native_tools.weather_tool import get_weather


def test_get_current_datetime_default_timezone():
    result = get_current_datetime()
    assert result["ok"] is True
    assert result["timezone"] == "Asia/Shanghai"
    assert result["date"]
    assert result["time"]
    assert result["weekday"] in {"周一", "周二", "周三", "周四", "周五", "周六", "周日"}


def test_get_current_datetime_invalid_timezone():
    result = get_current_datetime("Not/A_Timezone")
    assert result["ok"] is False


@patch("src.integrations.native_tools.weather_tool.requests.get")
def test_get_weather_success(mock_get):
    def fake_get(url, params=None, timeout=0):
        class Resp:
            def raise_for_status(self):
                return None

            def json(self):
                if "geocoding" in url:
                    return {
                        "results": [
                            {
                                "name": "Taiyuan",
                                "country": "China",
                                "admin1": "Shanxi",
                                "latitude": 37.87,
                                "longitude": 112.56,
                            }
                        ]
                    }
                return {
                    "timezone": "Asia/Shanghai",
                    "current": {
                        "time": "2026-06-18T12:00",
                        "temperature_2m": 25.5,
                        "relative_humidity_2m": 40,
                        "wind_speed_10m": 12.3,
                        "weather_code": 0,
                    },
                }

        return Resp()

    mock_get.side_effect = fake_get
    result = get_weather("太原")
    assert result["ok"] is True
    assert result["city"] == "Taiyuan"
    assert result["weather"] == "晴"
    assert result["temperature_c"] == 25.5


def test_get_weather_empty_city():
    result = get_weather("  ")
    assert result["ok"] is False
