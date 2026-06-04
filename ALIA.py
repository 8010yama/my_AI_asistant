import os
import datetime
import json
import re
import requests
import uvicorn
import io
import wave
from fastapi import FastAPI, Header, HTTPException, Response, Request
from pydantic import BaseModel
from dotenv import load_dotenv
from pyngrok import ngrok
from geopy.geocoders import Nominatim

from train_utils import (
    get_nearest_station,
    extract_destination,
    extract_arrive_time,
    get_next_trains,
    get_train_route,
    build_train_reply,
)
from weather_utils import get_weather_info, build_weather_reply
from map_utils import build_apple_maps_url, build_google_maps_nav_url, build_map_reply
from voice_utils import text_to_speech
from memo_utils import detect_memo_type, extract_memo_content, write_to_notion, build_memo_reply
from calendar_utils import (
    detect_calendar_type, extract_event_info, extract_update_info, extract_read_date,
    add_to_calendar, update_calendar_event, get_calendar_events,
    build_calendar_add_reply, build_calendar_update_reply, build_calendar_read_reply,
)

load_dotenv()
NGROK_TOKEN = os.getenv("NGROK_TOKEN")
API_KEY = os.getenv("API_KEY")

app = FastAPI()

SYSTEM_PROMPT = """あなたは優秀なAIアシスタントです。
以下のルールを厳守してください：
- 2文以内で簡潔に返答する。余計な提案や補足は不要。
- 「現在時刻」や「現在地」は、直接聞かれた場合や挨拶に必要な場合のみ読み上げる。
- 参考情報に天気・電車の情報が含まれる場合は、その内容をそのまま回答として使うこと。
- 現在時刻・現在地は状況把握のみに使い、夜遅ければ体調を気遣うなど自然なサポートをする。
- 日本語で返答すること。"""

class TextPayload(BaseModel):
    text: str
    lat: float = None
    lon: float = None

def get_address_from_gps(lat, lon):
    if lat is None or lon is None or not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return "位置情報不明"
    if lat == 0.0 and lon == 0.0:
        return "位置情報取得中..."
    try:
        geolocator = Nominatim(user_agent="my_ai_assistant_research")
        location = geolocator.reverse((lat, lon), language='ja')
        return location.address if location else "住所特定不可"
    except:
        return f"緯度:{lat}, 経度:{lon}"

def ask_alia_generator(text: str, dynamic_prompt: str):
    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "qwen2.5:3b",
            "messages": [
                {"role": "system", "content": dynamic_prompt},
                {"role": "user", "content": text}
            ],
            "stream": True
        },
        stream=True
    )
    sentence = ""
    for line in response.iter_lines():
        if line:
            chunk = json.loads(line)["message"]["content"]
            sentence += chunk
            if any(p in chunk for p in ["。", "！", "？", "\n"]):
                yield sentence
                sentence = ""
    if sentence.strip():
        yield sentence

@app.post("/alia")
async def alia(payload: TextPayload, x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="認証エラー")

    now = datetime.datetime.now().strftime("%Y年%m月%d日 %H時%M分")
    address = get_address_from_gps(payload.lat, payload.lon)

    memo_type = detect_memo_type(payload.text)
    if memo_type:
        content = extract_memo_content(payload.text, memo_type)
        success = write_to_notion(content, memo_type)
        reply = build_memo_reply(success, memo_type)
        print(f"[メモ] {memo_type}: {content[:30]} → {'成功' if success else '失敗'}")
        audio = text_to_speech(reply)
        if not audio:
            return Response(status_code=204)
        output = io.BytesIO()
        with wave.open(output, 'wb') as w:
            with wave.open(io.BytesIO(audio), 'rb') as src:
                w.setparams(src.getparams())
                w.writeframes(src.readframes(src.getnframes()))
        return Response(content=output.getvalue(), media_type="audio/wav")

    calendar_type = detect_calendar_type(payload.text)
    if calendar_type == "add":
        title, start_dt, end_dt, has_time = extract_event_info(payload.text)
        success = add_to_calendar(title, start_dt, end_dt, has_time)
        reply = build_calendar_add_reply(success, title, start_dt, end_dt, has_time)
        print(f"[カレンダー] 追加: {title} → {'成功' if success else '失敗'}")
    elif calendar_type == "update":
        info = extract_update_info(payload.text)
        if info:
            date, start_hour, start_minute, new_end_dt = info
            success, title = update_calendar_event(date, start_hour, start_minute, new_end_dt)
            reply = build_calendar_update_reply(success, title, start_hour, new_end_dt)
            print(f"[カレンダー] 更新: {start_hour}時 → {'成功' if success else '失敗'}")
        else:
            reply = "更新する予定の時間が読み取れませんでした。"
    elif calendar_type == "read":
        target_date = extract_read_date(payload.text)
        events = get_calendar_events(target_date)
        reply = build_calendar_read_reply(events, target_date)
        print(f"[カレンダー] 読み込み: {target_date} → {len(events)}件")
    else:
        reply = None

    if reply:
        audio = text_to_speech(reply)
        if not audio:
            return Response(status_code=204)
        output = io.BytesIO()
        with wave.open(output, 'wb') as w:
            with wave.open(io.BytesIO(audio), 'rb') as src:
                w.setparams(src.getparams())
                w.writeframes(src.readframes(src.getnframes()))
        return Response(content=output.getvalue(), media_type="audio/wav")

    weather_context = ""
    if build_weather_reply(payload.text):
        weather_lat, weather_lon, weather_label = payload.lat, payload.lon, address

        clean_text = re.sub(r'(?:今日|明日|今週|今夜|今朝|現在|最近)の?', '', payload.text)
        place_match = re.search(r'(.{1,8}?)(?:の天気|の気温|の雨)', clean_text)
        if place_match:
            place = place_match.group(1).strip()
            skip = {"今日", "明日", "今", "現在", "最近", "ここ", "そこ", "この辺", ""}
            if place not in skip:
                try:
                    geolocator = Nominatim(user_agent="my_ai_assistant_research")
                    loc = geolocator.geocode(place, language='ja')
                    if loc:
                        weather_lat, weather_lon, weather_label = loc.latitude, loc.longitude, place
                        print(f"[天気] 場所抽出: {place} → {loc.latitude}, {loc.longitude}")
                    else:
                        print(f"[天気] ジオコード失敗: '{place}' → 現在地で代替")
                except Exception as e:
                    print(f"[天気] ジオコードエラー: {e}")

        if weather_lat and weather_lon:
            weather_info = get_weather_info(weather_lat, weather_lon)
            weather_context = f"\n\n参考情報（{weather_label}の天気）:\n{weather_info}"
            print(f"[天気] context: {weather_label} → {weather_info}")
        else:
            weather_context = "\n\n※位置情報が不明なため天気を取得できませんでした。"

    train_context = ""

    NEXT_TRAIN_KEYWORDS = [
        "次の電車", "あと何分", "電車あと", "何分で出る",
        "後何分", "電車いつ", "電車来る", "何分後に出る", "何分で出たらいい",
        "何分で出ればいい"
    ]
    TRAIN_KEYWORDS = [
        "電車", "乗り換え", "鉄道", "路線", "新幹線", "快速", "各停", "電車で"
    ]

    destination = extract_destination(payload.text)
    arrive_time = extract_arrive_time(payload.text)

    use_train = destination and any(k in payload.text for k in TRAIN_KEYWORDS + NEXT_TRAIN_KEYWORDS)

    if use_train:
        from_match = re.search(r"(.+?)から", payload.text)
        if from_match:
            start_station = from_match.group(1).split()[-1]
        else:
            start_station = get_nearest_station(address)

        if start_station:
            train_context = f"\n\n参考情報:\n{get_train_route(start_station, destination, arrive_time)}"
        else:
            train_context = f"\n\n※出発駅が特定できませんでした。現在地: {address}"

    elif any(k in payload.text for k in NEXT_TRAIN_KEYWORDS):
        from_match = re.search(r"(.+?)(?:駅|から)", payload.text)
        if from_match:
            station = from_match.group(1).split()[-1]
        else:
            station = get_nearest_station(address)

        if station:
            train_context = f"\n\n参考情報:\n{get_next_trains(station)}"
        else:
            train_context = f"\n\n※最寄り駅が特定できませんでした。現在地: {address}"

    full_system_prompt = f"{SYSTEM_PROMPT}\n\n現在時刻: {now}\n現在地: {address}{train_context}{weather_context}"
    print(f"受信: {payload.text} (場所: {address})")
    print(f"train_context:\n{train_context}")

    audio_chunks = []
    full_reply = ""

    map_url = None
    map_reply = None
    if destination:
        map_url = build_apple_maps_url(destination, payload.lat, payload.lon)
        print(f"[map] 目的地: {destination} → {map_url}")
        if not train_context:
            map_reply = build_map_reply(destination)

    train_reply = build_train_reply(train_context)

    if map_reply:
        sentences = [map_reply]
    elif train_reply:
        sentences = re.split(r"(?<=。)|(?<=！)", train_reply)
    else:
        sentences = list(ask_alia_generator(payload.text, full_system_prompt))

    for sentence in sentences:
        if sentence.strip():
            print(f"音声化中: {sentence}")
            chunk = text_to_speech(sentence)
            if chunk:
                audio_chunks.append(chunk)
                full_reply += sentence

    if not audio_chunks:
        return Response(status_code=204)

    output = io.BytesIO()
    with wave.open(io.BytesIO(audio_chunks[0]), 'rb') as first:
        params = first.getparams()
        with wave.open(output, 'wb') as merged:
            merged.setparams(params)
            for data in audio_chunks:
                with wave.open(io.BytesIO(data), 'rb') as w:
                    merged.writeframes(w.readframes(w.getnframes()))

    headers = {"X-Map-URL": map_url} if map_url else {}
    print(f"返答完了: {full_reply}")
    return Response(content=output.getvalue(), media_type="audio/wav", headers=headers)

@app.post("/navigate")
async def navigate(request: Request, x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="認証エラー")

    raw = await request.body()
    print(f"[navigate] raw body: {raw}")

    try:
        body = await request.json()
    except Exception as e:
        print(f"[navigate] JSON parse error: {e}")
        return {"url": ""}

    text = body.get("text", "")
    lat = body.get("lat")
    lon = body.get("lon")
    print(f"[navigate] text={text}, lat={lat}, lon={lon}")

    TRAIN_KEYWORDS = ["電車", "乗り換え", "鉄道", "路線", "新幹線", "快速", "各停", "電車で"]
    if any(k in text for k in TRAIN_KEYWORDS):
        print(f"[navigate] 電車リクエストのためマップスキップ")
        return {"url": None, "google_url": None}

    destination = extract_destination(text)
    if not destination:
        return {"url": None, "google_url": None}

    map_url = build_apple_maps_url(destination, lat, lon)
    google_url = build_google_maps_nav_url(destination)
    print(f"[navigate] {destination} → {map_url}")
    return {"url": map_url, "google_url": google_url}

if __name__ == "__main__":
    ngrok.set_auth_token(NGROK_TOKEN)
    tunnel = ngrok.connect(8000)
    print(f"✅ 外部URL: {tunnel.public_url}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
