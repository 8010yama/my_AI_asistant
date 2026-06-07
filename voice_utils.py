import requests

SPEAKER_ID = 14

def text_to_speech(text: str) -> bytes:
    try:
        query = requests.post(
            f"http://localhost:50021/audio_query?text={text}&speaker={SPEAKER_ID}",
            timeout=5
        )
        query_json = query.json()
        query_json["volumeScale"] = 2.0
        query_json["prePhonemeLength"] = 0.1
        audio = requests.post(
            f"http://localhost:50021/synthesis?speaker={SPEAKER_ID}",
            json=query_json,
            timeout=10
        )
        return audio.content if audio.status_code == 200 else b""
    except Exception:
        return b""
