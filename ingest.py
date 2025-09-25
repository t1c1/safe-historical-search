import json, re, html, time
from pathlib import Path
from typing import Generator, Dict, Any


def _norm_text(x: Any) -> str:
    if x is None:
        return ""
    x = html.unescape(str(x))
    x = re.sub(r"\s+", " ", x).strip()
    return x


def parse_conversations(p: Path) -> Generator[Dict[str, Any], None, None]:
    """Yield docs from anthropic-data/conversations.json.

    Expected top-level: list of conversations; each has uuid, name, summary,
    created_at, updated_at, and chat_messages list with sender, text, timestamps.
    """
    raw = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    if not isinstance(raw, list):
        return
    for conv in raw:
        try:
            conv_id = conv.get("uuid") or conv.get("id") or f"anthropic:{abs(hash(json.dumps(conv)))%10**9}"
            title = conv.get("name") or conv.get("summary") or "Anthropic Conversation"
            msgs = conv.get("chat_messages") or []
            for i, m in enumerate(msgs):
                role = m.get("sender") or m.get("role") or "user"
                content = m.get("text") or ""
                ts_iso = None
                content_blocks = m.get("content")
                if isinstance(content_blocks, list) and content_blocks:
                    block0 = content_blocks[0]
                    ts_iso = block0.get("start_timestamp") or block0.get("stop_timestamp")
                ts_iso = ts_iso or m.get("created_at") or m.get("updated_at")
                ts_val = 0.0
                if isinstance(ts_iso, str):
                    try:
                        from datetime import datetime
                        try:
                            dt = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
                        except Exception:
                            ts_iso2 = re.sub(r"\.(\d+)(Z|[+-]\d\d:\d\d)$", r"\2", ts_iso)
                            dt = datetime.fromisoformat(ts_iso2.replace("Z", "+00:00"))
                        ts_val = dt.timestamp()
                    except Exception:
                        ts_val = 0.0
                yield {
                    "id": f"{conv_id}:{i}:{role}:{abs(hash(str(m)))%10**9}",
                    "conv_id": conv_id,
                    "title": title,
                    "role": role,
                    "ts": ts_val,
                    "source": "anthropic.conversations.json",
                    "extra": {k: v for k, v in m.items() if k not in ("text", "sender")},
                    "content": _norm_text(content),
                    "msg_index": i,
                }
        except Exception:
            continue


def parse_projects(p: Path) -> Generator[Dict[str, Any], None, None]:
    """Yield docs from anthropic-data/projects.json."""
    raw = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    if not isinstance(raw, list):
        return
    for proj in raw:
        try:
            conv_id = proj.get("uuid") or f"anthropic-project:{abs(hash(json.dumps(proj)))%10**9}"
            title = proj.get("name") or "Anthropic Project"
            description = proj.get("description") or ""
            yield {
                "id": f"{conv_id}:project",
                "conv_id": conv_id,
                "title": title,
                "role": "system",
                "ts": time.time(),
                "source": "anthropic.projects.json",
                "extra": {k: v for k, v in proj.items() if k not in ("name", "description")},
                "content": _norm_text(description),
                "msg_index": 0,
            }
            docs = proj.get("docs") or []
            for i, d in enumerate(docs, start=1):
                filename = d.get("filename") or d.get("name") or "doc"
                content = d.get("content") or ""
                yield {
                    "id": f"{conv_id}:doc:{i}",
                    "conv_id": conv_id,
                    "title": f"{title}: {filename}",
                    "role": "system",
                    "ts": time.time(),
                    "source": "anthropic.projects.json",
                    "extra": {k: v for k, v in d.items() if k != "content"},
                    "content": _norm_text(content),
                    "msg_index": i,
                }
        except Exception:
            continue


def parse_users(p: Path) -> Generator[Dict[str, Any], None, None]:
    """Yield a simple doc for anthropic-data/users.json."""
    raw = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    if isinstance(raw, list) and raw:
        content = json.dumps(raw[0], ensure_ascii=False)
    else:
        content = json.dumps(raw, ensure_ascii=False)
    doc_id = f"anthropic-user:{abs(hash(content))%10**9}"
    yield {
        "id": doc_id,
        "conv_id": "anthropic_user",
        "title": "Anthropic User Profile",
        "role": "system",
        "ts": time.time(),
        "source": "anthropic.users.json",
        "extra": None,
        "content": content,
        "msg_index": 0,
    }


def parse_chatgpt_conversations(p: Path) -> Generator[Dict[str, Any], None, None]:
    """Yield docs from ChatGPT export conversations.json.
    
    Expected format: list of conversations with id, title, create_time, 
    mapping containing messages with role, content, create_time.
    """
    raw = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    if not isinstance(raw, list):
        return
    
    for conv in raw:
        try:
            conv_id = conv.get("id") or f"chatgpt:{abs(hash(json.dumps(conv)))%10**9}"
            title = conv.get("title") or "ChatGPT Conversation"
            
            # ChatGPT stores messages in mapping -> <msg_id> -> message structure
            mapping = conv.get("mapping", {})
            messages = []
            
            # Build message list from mapping
            for msg_id, msg_data in mapping.items():
                message = msg_data.get("message")
                if not message or not message.get("content"):
                    continue
                    
                role = message.get("author", {}).get("role", "user")
                content_parts = message.get("content", {}).get("parts", [])
                content = " ".join(str(part) for part in content_parts if part)
                
                if not content.strip():
                    continue
                
                # Parse timestamp
                create_time = message.get("create_time")
                ts_val = 0.0
                if create_time:
                    try:
                        ts_val = float(create_time)
                    except (ValueError, TypeError):
                        ts_val = 0.0
                
                messages.append({
                    "role": role,
                    "content": content,
                    "ts": ts_val,
                    "msg_id": msg_id
                })
            
            # Sort messages by timestamp
            messages.sort(key=lambda x: x["ts"])
            
            # Yield each message as a document
            for i, m in enumerate(messages):
                yield {
                    "id": f"{conv_id}:{i}:{m['role']}:{abs(hash(m['content']))%10**9}",
                    "conv_id": conv_id,
                    "title": title,
                    "role": m["role"],
                    "ts": m["ts"],
                    "source": "chatgpt.conversations.json",
                    "extra": {"msg_id": m["msg_id"]},
                    "content": _norm_text(m["content"]),
                    "msg_index": i,
                }
        except Exception:
            continue


def parse_chatgpt_user(p: Path) -> Generator[Dict[str, Any], None, None]:
    """Yield a simple doc for ChatGPT user.json."""
    try:
        raw = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
        content = json.dumps(raw, ensure_ascii=False)
        doc_id = f"chatgpt-user:{abs(hash(content))%10**9}"
        yield {
            "id": doc_id,
            "conv_id": "chatgpt_user",
            "title": "ChatGPT User Profile", 
            "role": "system",
            "ts": time.time(),
            "source": "chatgpt.user.json",
            "extra": None,
            "content": content,
            "msg_index": 0,
        }
    except Exception:
        pass




