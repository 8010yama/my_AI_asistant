import re
from urllib.parse import quote
from geopy.geocoders import Nominatim

NAV_KEYWORDS = [
    "案内", "ナビ", "経路", "行き方", "連れて行って", "道順",
    "まで行く", "まで案内", "に向かう", "に行く", "に連れて行って",
    "行きたい", "に行きたい", "まで連れて行って"
]

def is_navigation_request(text: str) -> bool:
    return any(k in text for k in NAV_KEYWORDS)

def extract_nav_destination(text: str) -> str | None:
    patterns = [
        r'(.{1,20}?)まで(?:案内|ナビ|行き方|道順|連れて行って)',
        r'(.{1,20}?)(?:に|へ)(?:行きたい|向かいたい|連れて行って|案内して)',
        r'(.{1,20}?)(?:に|へ)(?:行く|向かう)',
        r'(.{1,20}?)への経路',
        r'(.{1,20}?)までの道',
        r'(.{1,20}?)のナビ',
    ]
    skip = {"そこ", "ここ", "あそこ", "どこか", "家", ""}
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            dest = m.group(1).strip()
            dest = re.sub(r'^(?:の|に|へ|で|を|から|は|が)', '', dest)
            if dest and dest not in skip:
                return dest
    return None

def geocode_place(place: str):
    try:
        geolocator = Nominatim(user_agent="my_ai_assistant_research")
        loc = geolocator.geocode(place, language='ja')
        if loc:
            return loc.latitude, loc.longitude
    except Exception as e:
        print(f"[map_utils] ジオコードエラー: {e}")
    return None, None

def build_google_maps_nav_url(destination: str) -> str:
    dest_encoded = quote(destination)
    return f"google.navigation:q={dest_encoded}&avoid=tf"

def build_apple_maps_url(destination: str, from_lat=None, from_lon=None) -> str:
    dest_encoded = quote(destination)
    if from_lat and from_lon:
        return f"maps://?saddr={from_lat},{from_lon}&daddr={dest_encoded}&dirflg=d"
    return f"maps://?daddr={dest_encoded}&dirflg=d"

def build_map_reply(destination: str) -> str:
    return f"{destination}へのナビを開始します。"
