import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_MEMO_PAGE_ID = os.getenv("NOTION_MEMO_PAGE_ID")
NOTION_TODO_PAGE_ID = os.getenv("NOTION_TODO_PAGE_ID")

TODO_KEYWORDS = ["todoに追加", "タスクに追加", "やることリスト", "todo追加", "タスク追加", "やることに追加", "todoリストに", "todoリスト"]
MEMO_KEYWORDS = ["メモして", "覚えておいて", "書いておいて", "ノートに書いて", "記録して", "メモお願い"]

def _normalize(text: str) -> str:
    return text.lower().replace(" ", "").replace("　", "")

def detect_memo_type(text: str):
    normalized = _normalize(text)
    if any(k in normalized for k in TODO_KEYWORDS):
        return "todo"
    if any(k in text for k in MEMO_KEYWORDS):
        return "memo"
    if re.match(r'^メモ(?!リ)', text):
        return "memo"
    return None

def extract_memo_content(text: str, memo_type: str) -> str:
    if memo_type == "todo":
        cleaned = re.sub(
            r'(?:[Tt][Oo]\s*[Dd][Oo]|TODO|todo)(?:リスト)?(?:[にへ]追加|追加|[にへ])?',
            '', text
        )
        cleaned = re.sub(r'(?:タスク|やること)(?:[にへ]追加|追加|[にへ])?', '', cleaned)
    else:
        cleaned = re.sub(
            r'(?:メモして?|覚えておいて|書いておいて|ノートに書いて|記録して|メモお願い)',
            '', text
        )
    return cleaned.strip('をってにへ、。 　')

def write_to_notion(content: str, memo_type: str = "memo") -> bool:
    if not NOTION_TOKEN:
        print("[Notion] NOTION_TOKEN が未設定です")
        return False

    page_id = NOTION_TODO_PAGE_ID if memo_type == "todo" else NOTION_MEMO_PAGE_ID
    if not page_id:
        print(f"[Notion] {memo_type} 用の PAGE_ID が未設定です")
        return False

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    if memo_type == "todo":
        block = {
            "object": "block",
            "type": "to_do",
            "to_do": {
                "rich_text": [{"type": "text", "text": {"content": content}}],
                "checked": False,
            }
        }
    else:
        block = {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": content}}]
            }
        }

    try:
        res = requests.patch(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            headers=headers,
            json={"children": [block]},
            timeout=10
        )
        if res.status_code == 200:
            print(f"[Notion] {memo_type} 書き込み成功: {content[:30]}")
            return True
        print(f"[Notion] エラー {res.status_code}: {res.text}")
        return False
    except Exception as e:
        print(f"[Notion] 例外: {e}")
        return False

def build_memo_reply(success: bool, memo_type: str = "memo") -> str:
    if memo_type == "todo":
        return "TODOリストに追加しました。" if success else "TODOの追加に失敗しました。"
    return "Notionにメモを保存しました。" if success else "メモの保存に失敗しました。"
