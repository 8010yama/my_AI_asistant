import os
import re
import datetime
import requests
from dotenv import load_dotenv

load_dotenv()
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN", "").strip()
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary").strip()

ADD_KEYWORDS = ["カレンダーに追加", "予定を入れて", "スケジュールに追加", "カレンダーに登録", "予定に追加", "カレンダーに書いて", "予定入れて", "カレンダーに追記", "追記して", "カレンダーに入れて"]
READ_KEYWORDS = ["今日の予定", "明日の予定", "今週の予定", "カレンダー確認", "スケジュール確認", "予定を確認", "予定ある", "何の予定", "予定教えて"]
UPDATE_KEYWORDS = ["時間にして", "時間に変えて", "時間を変えて", "まで延ばして", "時間延ばして", "を更新して", "設定して", "に変更して"]

WEEKDAY_MAP = {"月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6}


def detect_calendar_type(text: str):
    if any(k in text for k in UPDATE_KEYWORDS):
        return "update"
    if any(k in text for k in ADD_KEYWORDS):
        return "add"
    if any(k in text for k in READ_KEYWORDS):
        return "read"
    if re.search(r'^カレンダーに.{2,}', text):
        return "add"
    return None


def _get_access_token() -> str:
    res = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": GOOGLE_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
        timeout=10
    )
    token = res.json().get("access_token")
    if not token:
        print(f"[Calendar] トークン取得失敗: {res.text}")
    return token


def _parse_date(text: str) -> datetime.date:
    today = datetime.date.today()
    if "明後日" in text:
        return today + datetime.timedelta(days=2)
    if "明日" in text:
        return today + datetime.timedelta(days=1)
    if "今日" in text:
        return today

    m = re.search(r'(来週)?([月火水木金土日])曜', text)
    if m:
        target_wd = WEEKDAY_MAP[m.group(2)]
        days_ahead = (target_wd - today.weekday()) % 7 or 7
        if m.group(1):
            days_ahead += 7
        return today + datetime.timedelta(days=days_ahead)

    m = re.search(r'(\d{1,2})月(\d{1,2})日', text)
    if m:
        return datetime.date(today.year, int(m.group(1)), int(m.group(2)))

    return today


def _parse_time(text: str):
    m = re.search(r'午後(\d{1,2})時(?:(\d{1,2})分)?', text)
    if m:
        hour = int(m.group(1))
        return (hour + 12 if hour != 12 else 12), int(m.group(2) or 0)

    m = re.search(r'午前(\d{1,2})時(?:(\d{1,2})分)?', text)
    if m:
        hour = int(m.group(1))
        return (0 if hour == 12 else hour), int(m.group(2) or 0)

    for m in re.finditer(r'(\d{1,2})時(?:(\d{1,2})分)?', text):
        end = m.end()
        if text[end:end+2] == "まで":
            continue
        return int(m.group(1)), int(m.group(2) or 0)

    return None


def _parse_end_time(text: str):
    m = re.search(r'\d{1,2}時から(\d{1,2})時(?:(\d{1,2})分)?(?:の間|まで)', text)
    if m:
        return ("absolute", int(m.group(1)), int(m.group(2) or 0))

    m = re.search(r'(\d{1,2})時(?:(\d{1,2})分)?(?:まで|の間)', text)
    if m:
        return ("absolute", int(m.group(1)), int(m.group(2) or 0))

    m = re.search(r'(\d+)時間(?:(\d+)分)?', text)
    if m:
        minutes = int(m.group(1)) * 60 + int(m.group(2) or 0)
        return ("relative", minutes)

    m = re.search(r'(?<!時)(\d+)分', text)
    if m:
        return ("relative", int(m.group(1)))

    return None


def extract_event_info(text: str) -> tuple:
    date = _parse_date(text)
    time = _parse_time(text)
    end_info = _parse_end_time(text)

    if time:
        hour, minute = time
        start_dt = datetime.datetime(date.year, date.month, date.day, hour, minute)
        has_time = True

        if end_info and end_info[0] == "absolute":
            end_dt = datetime.datetime(date.year, date.month, date.day, end_info[1], end_info[2])
        elif end_info and end_info[0] == "relative":
            end_dt = start_dt + datetime.timedelta(minutes=end_info[1])
        else:
            end_dt = start_dt + datetime.timedelta(hours=1)
    else:
        start_dt = datetime.datetime(date.year, date.month, date.day)
        end_dt = start_dt
        has_time = False

    title = re.sub(r'カレンダーに(?:追加|登録|書いて|追記|入れて)?', '', text)
    title = re.sub(r'予定(?:を入れて|に追加|入れて)?', '', title)
    title = re.sub(r'スケジュールに(?:追加)?', '', title)
    title = re.sub(r'追記して?', '', title)
    title = re.sub(r'今日|明日|明後日|来週', '', title)
    title = re.sub(r'[月火水木金土日]曜日?', '', title)
    title = re.sub(r'\d{1,2}月\d{1,2}日', '', title)
    title = re.sub(r'午前|午後', '', title)
    title = re.sub(r'\d{1,2}時\d*分?まで', '', title)
    title = re.sub(r'\d+時間(?:\d+分)?', '', title)
    title = re.sub(r'\d{1,2}時\d*分?から?', '', title)
    title = title.strip('のにをでとは、。から 　')

    return title or "予定", start_dt, end_dt, has_time


def extract_update_info(text: str):
    date = _parse_date(text)
    time = _parse_time(text)
    end_info = _parse_end_time(text)

    if not time or not end_info:
        return None

    start_hour, start_minute = time
    start_dt = datetime.datetime(date.year, date.month, date.day, start_hour, start_minute)

    if end_info[0] == "absolute":
        new_end_dt = datetime.datetime(date.year, date.month, date.day, end_info[1], end_info[2])
    else:
        new_end_dt = start_dt + datetime.timedelta(minutes=end_info[1])

    return date, start_hour, start_minute, new_end_dt


def extract_read_date(text: str) -> datetime.date:
    return _parse_date(text)


def add_to_calendar(title: str, start_dt: datetime.datetime, end_dt: datetime.datetime, has_time: bool) -> bool:
    access_token = _get_access_token()
    if not access_token:
        return False

    if has_time:
        event = {
            "summary": title,
            "start": {"dateTime": start_dt.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "Asia/Tokyo"},
            "end":   {"dateTime": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),   "timeZone": "Asia/Tokyo"},
        }
    else:
        event = {
            "summary": title,
            "start": {"date": start_dt.strftime("%Y-%m-%d")},
            "end":   {"date": (start_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")},
        }

    res = requests.post(
        f"https://www.googleapis.com/calendar/v3/calendars/{GOOGLE_CALENDAR_ID}/events",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json=event,
        timeout=10
    )
    if res.status_code == 200:
        print(f"[Calendar] 追加成功: {title} {start_dt} → {end_dt}")
        return True
    print(f"[Calendar] エラー {res.status_code}: {res.text}")
    return False


def update_calendar_event(date: datetime.date, start_hour: int, start_minute: int, new_end_dt: datetime.datetime) -> tuple:
    events = get_calendar_events(date)
    matching = [
        e for e in events
        if "dateTime" in e.get("start", {})
        and datetime.datetime.fromisoformat(e["start"]["dateTime"]).hour == start_hour
        and datetime.datetime.fromisoformat(e["start"]["dateTime"]).minute == start_minute
    ]

    if not matching:
        return False, None

    event = matching[0]
    title = event.get("summary", "予定")
    access_token = _get_access_token()
    if not access_token:
        return False, title

    res = requests.patch(
        f"https://www.googleapis.com/calendar/v3/calendars/{GOOGLE_CALENDAR_ID}/events/{event['id']}",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json={"end": {"dateTime": new_end_dt.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "Asia/Tokyo"}},
        timeout=10
    )
    if res.status_code == 200:
        print(f"[Calendar] 更新成功: {title} → {new_end_dt}")
        return True, title
    print(f"[Calendar] 更新エラー {res.status_code}: {res.text}")
    return False, title


def get_calendar_events(target_date: datetime.date) -> list:
    access_token = _get_access_token()
    if not access_token:
        return []

    time_min = f"{target_date.strftime('%Y-%m-%d')}T00:00:00+09:00"
    time_max = f"{target_date.strftime('%Y-%m-%d')}T23:59:59+09:00"

    res = requests.get(
        f"https://www.googleapis.com/calendar/v3/calendars/{GOOGLE_CALENDAR_ID}/events",
        headers={"Authorization": f"Bearer {access_token}"},
        params={
            "timeMin": time_min,
            "timeMax": time_max,
            "singleEvents": "true",
            "orderBy": "startTime",
            "timeZone": "Asia/Tokyo",
        },
        timeout=10
    )
    if res.status_code != 200:
        print(f"[Calendar] 取得エラー {res.status_code}: {res.text}")
        return []
    return res.json().get("items", [])


def _fmt_date(dt) -> str:
    return dt.strftime("%#m月%#d日") if os.name == "nt" else dt.strftime("%-m月%-d日")


def build_calendar_add_reply(success: bool, title: str, start_dt: datetime.datetime, end_dt: datetime.datetime, has_time: bool) -> str:
    if not success:
        return "カレンダーへの追加に失敗しました。"
    date_str = _fmt_date(start_dt)
    if has_time:
        duration = int((end_dt - start_dt).total_seconds() // 60)
        time_str = start_dt.strftime("%H時%M分")
        dur_str = f"{duration // 60}時間{duration % 60}分" if duration % 60 else f"{duration // 60}時間"
        return f"{date_str}{time_str}から{dur_str}の{title}をカレンダーに追加しました。"
    return f"{date_str}に{title}をカレンダーに追加しました。"


def build_calendar_update_reply(success: bool, title, start_hour: int, new_end_dt: datetime.datetime) -> str:
    if not success:
        return "該当する予定が見つからなかったか、更新に失敗しました。"
    return f"{start_hour}時からの{title}を{new_end_dt.strftime('%H時%M分')}までに更新しました。"


def build_calendar_read_reply(events: list, target_date: datetime.date) -> str:
    date_str = _fmt_date(target_date)
    if not events:
        return f"{date_str}の予定はありません。"

    reply = f"{date_str}の予定は{len(events)}件です。"
    for event in events[:3]:
        title = event.get("summary", "無題")
        start = event.get("start", {})
        if "dateTime" in start:
            dt = datetime.datetime.fromisoformat(start["dateTime"])
            reply += f"{dt.strftime('%H時%M分')}から{title}。"
        else:
            reply += f"{title}、終日。"
    return reply
