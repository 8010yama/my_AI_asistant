import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel

model = WhisperModel("medium", device="cpu", compute_type="int8")

SAMPLE_RATE = 16000
DURATION = 20

def record_audio(duration=DURATION):
    print(f"{duration}秒間録音します... 話しかけてください")
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32"
    )
    sd.wait()
    print("録音完了")
    return audio.flatten()

def transcribe(audio):
    segments, info = model.transcribe(audio, language="ja", vad_filter=True)
    text = " ".join([seg.text for seg in segments])
    return text.strip()

if __name__ == "__main__":
    while True:
        input("\nEnterを押すと録音開始（Ctrl+Cで終了）")
        audio = record_audio()
        print("認識中...")
        result = transcribe(audio)
        print(f"認識結果: {result}")
