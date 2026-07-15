import os
import io
import json
import base64
import logging
import requests
import uuid
from collections.abc import MutableMapping, MutableSequence
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from docx import Document
import PyPDF2

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import database
from prompts import (
    FLOWER_CATEGORIES,
    CATEGORY_KEYS,
    CHAT_CATEGORY_KEYWORDS,
    FORBIDDEN_TEXT_PATTERNS,
    CHAT_ANSWER_FORBIDDEN_PATTERNS,
    CHAT_ANSWER_SANITIZE_REPLACEMENTS,
    CARD_TEXT_REPLACEMENTS,
    CLASSIFY_PROMPT,
    FACT_EXTRACT_PROMPT,
    CHAT_SYSTEM_PROMPT,
    build_card_suggestions_prompt,
    build_global_profile_prompt,
    build_chat_prompt,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Flower Dance Backend", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def isolate_user_memory(request: Request, call_next):
    if not request.url.path.startswith('/api/'):
        return await call_next(request)

    user_id = request.headers.get('X-Memory-User-ID', '')
    try:
        user_id = str(uuid.UUID(user_id))
    except ValueError:
        user_id = str(uuid.uuid4())

    database_token = database.set_active_user(user_id)
    memory_token = active_memory.set(demo_memories.get(user_id) or load_user_memory())
    try:
        response = await call_next(request)
        response.headers['X-Memory-User-ID'] = user_id
        return response
    finally:
        active_memory.reset(memory_token)
        database.reset_active_user(database_token)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CARD_TITLE_MAX_LENGTH = 50
CARD_TEXT_MAX_LENGTH = 60
MAX_FACTS_PER_CATEGORY = 3
MAX_CHAT_CARDS_PER_CATEGORY = 2
MIN_FACT_GROUNDING_LENGTH = 4
MIN_FACT_COVERAGE_LENGTH = 3


@dataclass
class UserMemory:
    user_id: str
    uploads: List[Dict[str, Any]]
    cards: Dict[str, List[Dict[str, Any]]]
    global_profile_cache: Optional[Dict[str, Any]]
    profile_rejections: Dict[str, int]
    is_demo_mode: bool = False
    current_demo_user: Optional[Dict[str, Any]] = None
    original_data_backup: Optional[Dict[str, Any]] = None


active_memory: ContextVar[Optional[UserMemory]] = ContextVar('active_memory', default=None)
demo_memories: Dict[str, UserMemory] = {}


def load_user_memory() -> UserMemory:
    cards_data = database.get_cards()
    for key in CATEGORY_KEYS:
        cards_data.setdefault(key, [])
    return UserMemory(
        user_id=database.get_active_user_id(),
        uploads=database.get_uploads(),
        cards=cards_data,
        global_profile_cache=database.get_global_profile(),
        profile_rejections=database.get_rejections(),
    )


def get_user_memory() -> UserMemory:
    memory = active_memory.get()
    if memory is None:
        raise RuntimeError('用户记忆上下文未初始化')
    return memory


class MemoryList(MutableSequence):
    def _value(self) -> List[Dict[str, Any]]:
        return get_user_memory().uploads

    def __getitem__(self, index):
        return self._value()[index]

    def __setitem__(self, index, value):
        self._value()[index] = value

    def __delitem__(self, index):
        del self._value()[index]

    def __len__(self):
        return len(self._value())

    def insert(self, index, value):
        self._value().insert(index, value)

    def copy(self):
        return self._value().copy()


class MemoryDict(MutableMapping):
    def __init__(self, attribute: str):
        self.attribute = attribute

    def _value(self) -> Dict[str, Any]:
        return getattr(get_user_memory(), self.attribute)

    def __getitem__(self, key):
        return self._value()[key]

    def __setitem__(self, key, value):
        self._value()[key] = value

    def __delitem__(self, key):
        del self._value()[key]

    def __iter__(self):
        return iter(self._value())

    def __len__(self):
        return len(self._value())

    def copy(self):
        return self._value().copy()


uploads: List[Dict[str, Any]] = MemoryList()
cards: Dict[str, List[Dict[str, Any]]] = MemoryDict('cards')
profile_rejections: Dict[str, int] = MemoryDict('profile_rejections')


def now_str() -> str:
    return datetime.now().isoformat(timespec="seconds")


def make_id() -> str:
    return f"{uuid.uuid4().hex[:16]}_{int(datetime.now().timestamp() * 1000)}"


def get_llm_config() -> Dict[str, str]:
    return {
        "api_key": os.getenv("LLM_API_KEY"),
        "base_url": os.getenv("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").rstrip("/"),
        "model": os.getenv("LLM_MODEL", "glm-4-flash"),
        "vision_model": os.getenv("LLM_VISION_MODEL", "glm-4v-flash"),
    }


def call_llm_text(
    user_prompt: str,
    system_prompt: Optional[str] = None,
    json_output: bool = True,
    model: Optional[str] = None,
) -> Any:
    cfg = get_llm_config()
    if not cfg["api_key"]:
        raise ValueError("后端尚未配置 LLM_API_KEY，无法调用大模型。请在启动后端前设置环境变量。")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    payload: Dict[str, Any] = {
        "model": model or cfg["model"],
        "messages": messages,
    }
    if json_output:
        payload["response_format"] = {"type": "json_object"}

    try:
        resp = requests.post(
            f"{cfg['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
    except requests.exceptions.RequestException as e:
        logger.error(f"LLM API error: {e}")
        raise ValueError(f"调用大模型失败：{str(e)}")


def call_llm_vision(image_base64: str, mime_type: str = "image/jpeg") -> Any:
    cfg = get_llm_config()
    if not cfg["api_key"]:
        raise ValueError("后端尚未配置 LLM_API_KEY，无法调用视觉大模型。请在启动后端前设置环境变量。")

    image_url = f"data:{mime_type};base64,{image_base64}"
    payload = {
        "model": cfg["vision_model"],
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "请理解这张图片的内容，识别图中的文字，然后以一段连贯的中文文字描述图片传递的信息。",
                    },
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            },
        ],
    }

    try:
        resp = requests.post(
            f"{cfg['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        logger.error(f"LLM vision API error: {e}")
        raise ValueError(f"调用视觉大模型失败：{str(e)}")


def extract_txt(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8", errors="ignore").strip()


def extract_pdf(file_bytes: bytes) -> str:
    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def extract_docx(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs).strip()


def guess_mime_type(filename: str) -> str:
    ext = filename.split(".")[-1].lower()
    mapping = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "gif": "image/gif",
    }
    return mapping.get(ext, "image/jpeg")


def extract_text_from_file(file: UploadFile, file_bytes: bytes) -> str:
    ext = file.filename.split(".")[-1].lower()
    if ext == "txt":
        return extract_txt(file_bytes)
    elif ext == "pdf":
        return extract_pdf(file_bytes)
    elif ext in ("docx", "doc"):
        return extract_docx(file_bytes)
    elif ext in ("png", "jpg", "jpeg", "webp", "gif"):
        image_base64 = base64.b64encode(file_bytes).decode("utf-8")
        return str(call_llm_vision(image_base64, guess_mime_type(file.filename)))
    else:
        raise ValueError(f"不支持的文件格式：.{ext}")


def build_fallback_new_text(facts: List[str]) -> str:
    if not facts:
        return ""
    parts = facts[:2]
    if len(parts) == 1:
        return f"你{parts[0]}。"
    return f"你{parts[0]}，{parts[1]}。"


def build_fallback_update_text(old_card: Dict[str, Any], new_facts: List[str]) -> str:
    old_facts = old_card.get("facts", [])
    old_text = old_card.get("card_text", "")

    if not new_facts:
        return old_text

    new_part = "，".join(new_facts[:2])

    if old_facts:
        old_part = "，".join(old_facts[:2])
        contrast_keywords = ["不再", "但", "却", "反而", "开始", "犹豫", "想", "不想", "决定", "放弃"]
        has_contrast = any(kw in new_part for kw in contrast_keywords) or any(kw in old_part for kw in contrast_keywords)
        if has_contrast:
            return f"你以前{old_part}，这次{new_part}。"
        else:
            return f"你以前{old_part}，这次{new_part}，情况还是一样。"
    else:
        return f"你{new_part}，这和之前「{old_text}」是连在一起的。"


def contains_forbidden_text(text: str) -> bool:
    if not text:
        return True
    for pat in FORBIDDEN_TEXT_PATTERNS:
        if pat in text:
            return True
    return False


def detect_chat_forbidden_words(text: str) -> List[str]:
    return [pat for pat in CHAT_ANSWER_FORBIDDEN_PATTERNS if pat in text]


def sanitize_chat_answer(text: str) -> str:
    for old, new in CHAT_ANSWER_SANITIZE_REPLACEMENTS.items():
        text = text.replace(old, new)
    return text


def clean_card_text_for_chat(text: str) -> str:
    for old, new in CARD_TEXT_REPLACEMENTS.items():
        text = text.replace(old, new)
    return text


def sanitize_card_text(text: str, facts: List[str]) -> str:
    if not contains_forbidden_text(text) and facts:
        return text
    return build_fallback_new_text(facts)


def has_fact_coverage(text: str, facts: List[str]) -> bool:
    if not text or not facts:
        return False
    for fact in facts:
        if fact in text:
            return True
        for length in (min(5, len(fact)), min(4, len(fact)), min(MIN_FACT_COVERAGE_LENGTH, len(fact))):
            if length < MIN_FACT_COVERAGE_LENGTH:
                continue
            for i in range(len(fact) - length + 1):
                if fact[i:i + length] in text:
                    return True
    return False


def is_fact_grounded(fact: str, raw_text: str, min_substring_len: int = MIN_FACT_GROUNDING_LENGTH) -> bool:
    if not fact or not raw_text:
        return False
    if fact in raw_text:
        return True
    for length in (min(6, len(fact)), min(5, len(fact)), min(4, len(fact))):
        if length < min_substring_len:
            continue
        for i in range(len(fact) - length + 1):
            if fact[i:i + length] in raw_text:
                return True
    return False


def filter_grounded_facts(new_facts: Dict[str, List[str]], raw_text: str) -> Dict[str, List[str]]:
    grounded: Dict[str, List[str]] = {}
    for cat, facts in new_facts.items():
        grounded[cat] = [f for f in facts if is_fact_grounded(f, raw_text)]
    return grounded


def is_splicing_update(old_text: str, new_text: str) -> bool:
    if not old_text or not new_text:
        return False
    if new_text.startswith(old_text):
        return True
    overlap = 0
    for i in range(min(len(old_text), len(new_text)), 0, -1):
        if old_text[:i] == new_text[:i]:
            overlap = i
            break
    if len(new_text) > 0 and overlap / len(new_text) >= 0.5:
        return True
    return False


def get_valid_categories(min_cards_per_category: int = 2) -> List[str]:
    return [k for k, v in cards.items() if len(v) >= min_cards_per_category]


@app.get("/")
async def serve_index():
    index_path = os.path.join(BASE_DIR, "frontend", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "index.html 不存在"}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "uploads": len(uploads),
        "cards": {key: len(value) for key, value in cards.items()},
    }


@app.post("/api/upload-content")
async def upload_content(
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    raw_text = ""
    source_type = "text"
    filename = None

    if file and file.filename:
        file_bytes = await file.read()
        if not file_bytes:
            return {"error": "上传文件为空"}
        filename = file.filename
        source_type = f"file:{filename.split('.')[-1].lower()}"
        try:
            raw_text = extract_text_from_file(file, file_bytes)
        except Exception as e:
            logger.exception("File extraction failed")
            return {"error": str(e)}
    elif text is not None and text.strip():
        raw_text = text.strip()
    else:
        return {"error": "请提供文本或上传文件"}

    if not raw_text:
        return {"error": "未能从输入中提取到有效文本"}

    upload_id = make_id()
    uploads.append({
        "id": upload_id,
        "source_type": source_type,
        "filename": filename,
        "raw_text": raw_text,
        "created_at": now_str(),
    })
    
    database.add_upload(upload_id, source_type, raw_text, filename)

    try:
        classify_result = call_llm_text(
            user_prompt=f"请判断以下用户内容涉及哪些分类，只返回 JSON。\n\n内容：\n{raw_text}",
            system_prompt=CLASSIFY_PROMPT,
        )
        involved_categories = [
            c for c in classify_result.get("categories", [])
            if c in CATEGORY_KEYS
        ]
        if not involved_categories:
            return {
                "upload_id": upload_id,
                "involved_categories": [],
                "suggestions": [],
                "message": "AI 认为这段内容暂不涉及任何分类",
            }

        facts_result = call_llm_text(
            user_prompt=f"请从以下内容中，为涉及的分类提取具体事实。\n\n涉及分类：{', '.join(involved_categories)}\n\n内容：\n{raw_text}",
            system_prompt=FACT_EXTRACT_PROMPT,
        )
        new_facts = filter_grounded_facts(facts_result.get("facts", {}), raw_text)

        suggestion_result = call_llm_text(
            user_prompt=build_card_suggestions_prompt(
                uploads[-1], involved_categories, new_facts, cards, uploads,
                card_text_max_length=CARD_TEXT_MAX_LENGTH,
            ),
        )
        suggestions = suggestion_result.get("suggestions", [])

        processed = []
        for sug in suggestions:
            cat = sug.get("category")
            if cat not in involved_categories:
                continue
            stype = sug.get("type")
            if stype not in ("update", "new"):
                continue

            item = {
                "type": stype,
                "category": cat,
                "proposed_text": str(sug.get("proposed_text", "")).strip(),
                "reason": str(sug.get("reason", "")).strip(),
                "facts": new_facts.get(cat, []),
            }

            old_card = None
            if stype == "update":
                card_id = sug.get("card_id")
                old_card = next((c for c in cards.get(cat, []) if c["id"] == card_id), None)
                if not old_card:
                    item["type"] = "new"
                    item["source_ids"] = [upload_id]
                else:
                    item["card_id"] = card_id
                    item["old_text"] = old_card["card_text"]
                    item["source_ids"] = list(dict.fromkeys(old_card.get("source_ids", []) + [upload_id]))
                    item["old_facts"] = old_card.get("facts", [])
            elif stype == "new":
                item["source_ids"] = [upload_id]

            is_bad = (
                contains_forbidden_text(item["proposed_text"])
                or not has_fact_coverage(item["proposed_text"], item["facts"])
            )
            if item["type"] == "update" and old_card:
                is_bad = is_bad or is_splicing_update(old_card["card_text"], item["proposed_text"])

            if is_bad:
                if item["type"] == "update" and old_card:
                    item["proposed_text"] = build_fallback_update_text(old_card, item["facts"])
                    item["reason"] = "AI 原输出不合规，已按事实兜底重写"
                else:
                    item["proposed_text"] = build_fallback_new_text(item["facts"])
                    item["reason"] = "AI 原输出不合规，已按事实兜底重写"

            if item["proposed_text"]:
                processed.append(item)

        covered = {s["category"] for s in processed}
        for cat in involved_categories:
            if cat not in covered and new_facts.get(cat):
                if cards.get(cat):
                    old_card = cards[cat][0]
                    processed.append({
                        "type": "update",
                        "category": cat,
                        "card_id": old_card["id"],
                        "old_text": old_card["card_text"],
                        "proposed_text": build_fallback_update_text(old_card, new_facts.get(cat, [])),
                        "reason": "基于新提取的事实自动补全",
                        "source_ids": list(dict.fromkeys(old_card.get("source_ids", []) + [upload_id])),
                        "facts": new_facts.get(cat, []),
                        "old_facts": old_card.get("facts", []),
                    })
                else:
                    processed.append({
                        "type": "new",
                        "category": cat,
                        "proposed_text": build_fallback_new_text(new_facts.get(cat, [])),
                        "reason": "基于提取的事实自动补全",
                        "source_ids": [upload_id],
                        "facts": new_facts.get(cat, []),
                    })

        return {
            "upload_id": upload_id,
            "involved_categories": involved_categories,
            "suggestions": processed,
        }

    except Exception as e:
        logger.exception("Upload content processing failed")
        return {"error": str(e), "upload_id": upload_id}


@app.post("/api/confirm-cards")
async def confirm_cards(payload: dict):
    decisions = payload.get("decisions", [])
    updated_categories = set()
    updated_cards = []
    created_cards = []

    for decision in decisions:
        if not decision.get("accepted", False):
            continue

        stype = decision.get("type")
        cat = decision.get("category")
        new_text = str(decision.get("new_text") or decision.get("text") or "").strip()
        if not new_text or cat not in CATEGORY_KEYS:
            continue

        new_facts = decision.get("facts", []) or []

        if stype == "update":
            card_id = decision.get("card_id")
            card = next((c for c in cards.get(cat, []) if c["id"] == card_id), None)
            if card:
                card["card_text"] = new_text
                card["updated_at"] = now_str()
                card["source_ids"] = list(dict.fromkeys(
                    card.get("source_ids", []) + (decision.get("source_ids", []) or [])
                ))
                old_facts = card.get("facts", [])
                merged_facts = list(dict.fromkeys(old_facts + new_facts))
                card["facts"] = merged_facts
                updated_categories.add(cat)
                updated_cards.append({"id": card["id"], "category": cat, "text": new_text})
                
                database.update_card(card_id, {
                    "title": new_text[:CARD_TITLE_MAX_LENGTH] + "..." if len(new_text) > CARD_TITLE_MAX_LENGTH else new_text,
                    "content": json.dumps({
                        "card_text": new_text,
                        "source_ids": card["source_ids"],
                        "facts": merged_facts,
                    }),
                    "evidence": "",
                })
        elif stype == "new":
            new_card = {
                "id": make_id(),
                "card_text": new_text,
                "category": cat,
                "created_at": now_str(),
                "updated_at": now_str(),
                "source_ids": decision.get("source_ids", []),
                "facts": new_facts,
            }
            cards[cat].append(new_card)
            updated_categories.add(cat)
            created_cards.append({"id": new_card["id"], "category": cat, "text": new_text})
            
            database.add_card({
                "id": new_card["id"],
                "category": cat,
                "title": new_text[:CARD_TITLE_MAX_LENGTH] + "..." if len(new_text) > CARD_TITLE_MAX_LENGTH else new_text,
                "content": json.dumps({
                    "card_text": new_text,
                    "source_ids": new_card["source_ids"],
                    "facts": new_facts,
                }),
                "evidence": "",
                "created_at": new_card["created_at"],
                "updated_at": new_card["updated_at"],
            })

    get_user_memory().global_profile_cache = None
    database.clear_global_profile()

    return {
        "success": True,
        "updated_categories": list(updated_categories),
        "updated": updated_cards,
        "created": created_cards,
    }


@app.get("/api/cards")
def get_cards():
    valid_categories = get_valid_categories()
    global_available = len(valid_categories) >= 3
    return {
        "categories": cards,
        "upload_count": len(uploads),
        "global_profile_available": global_available,
    }


@app.post("/api/global-profile")
def generate_global_profile():
    valid_categories = get_valid_categories()
    if len(valid_categories) < 3:
        return {
            "error": "卡片数量不足，无法生成全局画像。需要至少 3 个不同分类，且每个分类至少 2 张卡片。",
            "available": False,
        }

    memory = get_user_memory()
    rejected_texts = []
    if memory.global_profile_cache:
        for line in memory.global_profile_cache.get("lines", []):
            if profile_rejections.get(line.get("id"), 0) > 0:
                rejected_texts.append(line.get("text", ""))

    try:
        result = call_llm_text(
            user_prompt=build_global_profile_prompt(cards, rejected_texts=rejected_texts),
        )
        lines = result.get("lines", [])
        for line in lines:
            line["id"] = make_id()
            line.setdefault("card_ids", [])

        memory.global_profile_cache = {
            "available": True,
            "generated_at": now_str(),
            "lines": lines,
        }
        database.save_global_profile(memory.global_profile_cache)
        return memory.global_profile_cache
    except Exception as e:
        logger.exception("Global profile generation failed")
        return {"error": str(e), "available": False}


@app.post("/api/reject-profile-line")
def reject_profile_line(payload: dict):
    line_id = payload.get("line_id")
    text = payload.get("text", "")
    if not line_id:
        return {"error": "缺少 line_id"}
    profile_rejections[line_id] = profile_rejections.get(line_id, 0) + 1
    database.add_rejection(line_id, text)
    return {"success": True, "line_id": line_id, "rejections": profile_rejections[line_id]}


@app.post("/api/chat")
async def chat(payload: dict):
    question = payload.get("question", "").strip()
    if not question:
        return {"error": "问题不能为空"}

    matched_categories = []
    for cat, kw_list in CHAT_CATEGORY_KEYWORDS.items():
        if any(kw in question for kw in kw_list):
            matched_categories.append(cat)
    if not matched_categories:
        matched_categories = ["narcissus"]

    referenced_cards = []
    seen_ids = set()
    for cat in matched_categories:
        cat_cards = cards.get(cat, [])
        selected = cat_cards[-MAX_CHAT_CARDS_PER_CATEGORY:] if len(cat_cards) >= MAX_CHAT_CARDS_PER_CATEGORY else cat_cards
        for card in selected:
            if card["id"] not in seen_ids:
                referenced_cards.append({**card, "category": cat})
                seen_ids.add(card["id"])

    if not referenced_cards:
        return {
            "answer": "我目前还没有关于这个问题的记忆卡片。你可以先上传一些相关内容，让我更了解你。",
            "referenced_cards": [],
            "categories": matched_categories,
        }

    try:
        prompt = build_chat_prompt(question, referenced_cards)
        result = call_llm_text(
            user_prompt=prompt,
            system_prompt=CHAT_SYSTEM_PROMPT,
        )
        answer = result.get("answer", "").strip()

        violations = detect_chat_forbidden_words(answer)
        if violations:
            logger.warning(f"Chat answer contains forbidden words: {violations}, retrying...")
            cards_summary = "\n".join(
                f"- {FLOWER_CATEGORIES.get(card.get('category', ''), {}).get('name', card.get('category', ''))}：{clean_card_text_for_chat(card.get('card_text', ''))}"
                for card in referenced_cards
            )
            retry_prompt = (
                "请用完全不同的表达方式重写下面这段回答，严格避免出现抽象评价词。\n\n"
                f"原文：{answer}\n\n"
                "【必须基于的认知卡片】\n"
                f"{cards_summary}\n\n"
                "【重写要求】\n"
                "1. 用具体动作和情境描述卡片内容，例如「你会先算投入产出」「你遇到挫折会把情绪转成新目标」。\n"
                "2. 把多张卡片放在一起综合分析，说明它们之间的关系。\n"
                "3. 最后给出「如果……就……；否则/反之……」形式的具体建议。\n"
                "4. 禁止出现：展现出、显示出、反映出、体现出、说明了、表明、深思熟虑、值得考虑、可以想想等抽象或套话表达；可用「意味着」「放在一起看」替代。\n"
                f"5. 返回严格合法 JSON：{{\"answer\": \"重写后的回答\", \"referenced_cards\": {json.dumps([c['id'] for c in referenced_cards], ensure_ascii=False)}}}"
            )
            result = call_llm_text(
                user_prompt=retry_prompt,
                system_prompt=CHAT_SYSTEM_PROMPT,
            )
            answer = result.get("answer", "").strip()
            violations = detect_chat_forbidden_words(answer)
            if violations:
                logger.warning(f"Chat answer still contains forbidden words after retry: {violations}")

        answer = sanitize_chat_answer(answer)

        ref_ids = result.get("referenced_cards", [c["id"] for c in referenced_cards])
        if not answer:
            return {
                "answer": "我检索到了相关卡片，但暂时无法生成回答。",
                "referenced_cards": [c["id"] for c in referenced_cards],
                "categories": matched_categories,
            }
        return {
            "answer": answer,
            "referenced_cards": ref_ids,
            "categories": matched_categories,
        }
    except Exception as e:
        logger.exception("Chat generation failed")
        return {"error": str(e)}


@app.get("/api/demo/users")
def get_demo_users():
    import glob
    demo_users = []
    users_dir = os.path.join(BASE_DIR, "assets", "demo", "users")
    for f in glob.glob(os.path.join(users_dir, "user_*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                demo_users.append(data["user_info"])
        except Exception as e:
            logger.error(f"Failed to load demo user {f}: {e}")
    return {"users": demo_users}


@app.post("/api/demo/enter")
async def enter_demo_mode(user_id: Optional[str] = None):
    memory = get_user_memory()
    if memory.is_demo_mode:
        return {"error": "已在演示模式中"}

    memory.original_data_backup = {
        "uploads": memory.uploads.copy(),
        "cards": {k: v.copy() for k, v in memory.cards.items()},
        "global_profile_cache": memory.global_profile_cache,
        "profile_rejections": memory.profile_rejections.copy(),
    }
    
    if user_id:
        file_name = user_id.replace("demo_", "") + ".json"
        user_file = os.path.join(BASE_DIR, "assets", "demo", "users", file_name)
        if not os.path.exists(user_file):
            return {"error": f"演示用户 {user_id} 不存在"}
        try:
            with open(user_file, "r", encoding="utf-8") as fp:
                user_data = json.load(fp)
            
            memory.uploads = user_data.get("uploads", [])
            cards_data = user_data.get("cards", {})
            memory.cards = {key: cards_data.get(key, []) for key in CATEGORY_KEYS}
            memory.current_demo_user = user_data.get("user_info", {})
        except Exception as e:
            logger.error(f"Failed to load demo user data: {e}")
            return {"error": f"加载演示数据失败: {str(e)}"}
    else:
        memory.uploads = []
        memory.cards = {key: [] for key in CATEGORY_KEYS}
        memory.current_demo_user = None

    memory.global_profile_cache = None
    memory.profile_rejections = {}
    memory.is_demo_mode = True
    demo_memories[memory.user_id] = memory
    
    return {
        "success": True,
        "mode": "demo",
        "user": memory.current_demo_user,
        "uploads_count": len(memory.uploads),
        "cards_count": sum(len(v) for v in memory.cards.values()),
    }


@app.post("/api/demo/exit")
async def exit_demo_mode():
    memory = get_user_memory()
    if not memory.is_demo_mode:
        return {"error": "不在演示模式中"}

    if memory.original_data_backup:
        memory.uploads = memory.original_data_backup["uploads"]
        memory.cards = memory.original_data_backup["cards"]
        memory.global_profile_cache = memory.original_data_backup["global_profile_cache"]
        memory.profile_rejections = memory.original_data_backup["profile_rejections"]

    memory.is_demo_mode = False
    memory.current_demo_user = None
    memory.original_data_backup = None
    demo_memories.pop(memory.user_id, None)
    
    return {
        "success": True,
        "mode": "normal",
        "uploads_count": len(memory.uploads),
        "cards_count": sum(len(v) for v in memory.cards.values()),
    }


@app.get("/api/demo/status")
def get_demo_status():
    memory = get_user_memory()
    return {
        "is_demo_mode": memory.is_demo_mode,
        "current_user": memory.current_demo_user,
        "uploads_count": len(memory.uploads),
        "cards_count": sum(len(v) for v in memory.cards.values()),
    }


@app.get("/api/demo/sample-texts")
def get_sample_texts():
    import glob
    texts = []
    texts_dir = os.path.join(BASE_DIR, "assets", "demo", "texts")
    for f in sorted(glob.glob(os.path.join(texts_dir, "*.txt"))):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                texts.append({
                    "filename": os.path.basename(f),
                    "content": fp.read().strip(),
                })
        except Exception as e:
            logger.error(f"Failed to load sample text {f}: {e}")
    return {"texts": texts}


@app.get("/api/demo/questions")
def get_demo_questions():
    questions = [
        "我最大的优势是什么？",
        "最近发生了什么变化？",
        "我有哪些压力来源？",
        "我的兴趣有哪些？",
        "我的工作状态如何？",
        "我的学习方式有什么特点？",
        "我的情绪变化趋势是什么？",
        "哪个花神维度最活跃？",
        "我最近应该关注什么？",
        "我的成长方向是什么？",
        "我适合什么样的工作？",
        "我和家人的关系如何？",
        "我的社交模式是什么？",
        "我有哪些好习惯？",
        "我需要改进什么？",
        "我的决策风格是什么？",
        "我的健康状况如何？",
        "我在感情方面的状态怎样？",
        "我的技能特长是什么？",
        "我未来的发展潜力在哪里？",
    ]
    return {"questions": questions}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
