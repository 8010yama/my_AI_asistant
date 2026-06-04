import os
import datetime
import requests
from dotenv import load_dotenv

load_dotenv()
YAHOO_APP_ID = os.getenv("YAHOO_APP_ID")

def _get_daily_forecast(lat, lon):
    today = datetime.date.today().isoformat()
    now_hour = datetime.datetime.now().hour
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_mean"
        f"&hourly=precipitation"
        f"&timezone=auto"
        f"&start_date={today}&end_date={today}"
    )
    res = requests.get(url, timeout=5)
    res.raise_for_status()
    data = res.json()

    avg_temp = data["daily"]["temperature_2m_mean"][0]

    RAIN_THRESHOLD = 0.5  # mm/h未満は無視
    rain_start = None
    for t, p in zip(data["hourly"]["time"], data["hourly"]["precipitation"]):
        hour = int(t[11:13])
        if p >= RAIN_THRESHOLD and hour > now_hour and rain_start is None:
            rain_start = t[11:16]  # 未来の時刻のみ参照

    return avg_temp, rain_start

def _get_current_rainfall(lat, lon):
    url = (
        f"https://map.yahooapis.jp/weather/V1/place"
        f"?coordinates={lon},{lat}&output=json&appid={YAHOO_APP_ID}"
    )
    res = requests.get(url, timeout=5)
    res.raise_for_status()
    data = res.json()
    weather_list = data["Feature"][0]["Property"]["WeatherList"]["Weather"]
    observations = [w for w in weather_list if w["Type"] == "observation"]
    return observations[-1]["Rainfall"] if observations else 0.0

def get_weather_info(lat, lon):
    lines = []

    avg_temp, rain_start = None, None
    try:
        avg_temp, rain_start = _get_daily_forecast(lat, lon)
        lines.append(f"本日の平均気温: {avg_temp}°C")
    except Exception as e:
        print(f"[weather_utils] Open-Meteoエラー: {type(e).__name__}: {e}")
        lines.append("気温予報の取得に失敗しました。")

    try:
        current_rain = _get_current_rainfall(lat, lon)
        if current_rain > 0:
            if rain_start:
                lines.append(f"現在雨が降っており、{rain_start}以降も続く予報（{current_rain}mm/h）")
            else:
                lines.append(f"現在雨が降っているが、この後は止む予報（{current_rain}mm/h）")
        else:
            if rain_start:
                lines.append(f"雨の予報: {rain_start}頃から")
            else:
                lines.append("今日は雨の予報なし")
    except Exception as e:
        print(f"[weather_utils] Yahoo降水エラー: {type(e).__name__}: {e}")
        lines.append(f"雨の予報: {rain_start}頃から" if rain_start else "今日は雨の予報なし")

    return "\n".join(lines)


def build_weather_reply(text):
    WEATHER_KEYWORDS = ["天気", "雨", "傘", "気温", "暑い", "寒い"]
    return any(k in text for k in WEATHER_KEYWORDS)
