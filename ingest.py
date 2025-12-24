import json, re, html, time
from pathlib import Path
from typing import Generator, Dict, Any, List
from schema import Conversation, Turn, SourceType, Entity, Artifact

def _norm_text(x: Any) -> str:
    if x is None:
        return ""
    x = html.unescape(str(x))
    x = re.sub(r"\s+", " ", x).strip()
    return x

def parse_conversations_unified(p: Path) -> Generator[Conversation, None, None]:
    """Yield Conversation objects from Anthropic conversations.json."""
    raw = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    if not isinstance(raw, list):
        return

    for conv_data in raw:
        try:
            conv_id = conv_data.get("uuid") or conv_data.get("id") or Conversation.generate_id(json.dumps(conv_data))
            title = conv_data.get("name") or conv_data.get("summary") or "Anthropic Conversation"
            created_at = 0.0
            
            # Try to find earliest timestamp
            msgs = conv_data.get("chat_messages") or []
            turns = []
            
            for i, m in enumerate(msgs):
                role = m.get("sender") or m.get("role") or "user"
                content = m.get("text") or ""
                
                # Parse timestamp
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
                        pass
                
                if i == 0 and ts_val > 0:
                    created_at = ts_val

                turn_id = f"{conv_id}:{i}"
                turns.append(Turn(
                    id=turn_id,
                    role=role,
                    content=_norm_text(content),
                    timestamp=ts_val or time.time(),
                    metadata={k: v for k, v in m.items() if k not in ("text", "sender", "content")}
                ))

            yield Conversation(
                id=conv_id,
                title=title,
                source=SourceType.ANTHROPIC,
                created_at=created_at or time.time(),
                updated_at=time.time(), # TODO: Find last message timestamp
                turns=turns,
                metadata=conv_data
            )
            
        except Exception:
            continue

def parse_chatgpt_unified(p: Path) -> Generator[Conversation, None, None]:
    """Yield Conversation objects from ChatGPT conversations.json."""
    raw = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    if not isinstance(raw, list):
        return
    
    for conv_data in raw:
        try:
            conv_id = conv_data.get("id") or Conversation.generate_id(json.dumps(conv_data))
            title = conv_data.get("title") or "ChatGPT Conversation"
            create_time = conv_data.get("create_time") or 0.0
            
            mapping = conv_data.get("mapping", {})
            turns = []
            
            # Helper to collect messages in order (ChatGPT mapping is a tree)
            # For now, we linearize by timestamp
            messages = []
            for msg_id, msg_data in mapping.items():
                message = msg_data.get("message")
                if not message or not message.get("content"):
                    continue
                    
                role = message.get("author", {}).get("role", "user")
                content_parts = message.get("content", {}).get("parts", [])
                content = " ".join(str(part) for part in content_parts if part)
                
                if not content.strip():
                    continue
                
                ts = message.get("create_time") or 0.0
                messages.append({
                    "role": role,
                    "content": content,
                    "ts": float(ts),
                    "id": msg_id,
                    "metadata": message.get("metadata", {})
                })
            
            messages.sort(key=lambda x: x["ts"])
            
            for m in messages:
                turns.append(Turn(
                    id=m["id"],
                    role=m["role"],
                    content=_norm_text(m["content"]),
                    timestamp=m["ts"],
                    model=m["metadata"].get("model_slug"),
                    metadata=m["metadata"]
                ))

            yield Conversation(
                id=conv_id,
                title=title,
                source=SourceType.OPENAI,
                created_at=float(create_time),
                updated_at=turns[-1].timestamp if turns else float(create_time),
                turns=turns,
                metadata={"moderation_results": conv_data.get("moderation_results")}
            )
            
        except Exception:
            continue

# Keep legacy functions for now to avoid breaking existing indexing immediately
# but mark them as deprecated if we were adding docstrings. 
# We will redirect the indexer to use the unified parsers later.

def parse_conversations(p: Path) -> Generator[Dict[str, Any], None, None]:
    """Legacy: Flatten unified conversations back to doc dicts for SQLite."""
    for conv in parse_conversations_unified(p):
        for i, turn in enumerate(conv.turns):
            yield {
                "id": f"{conv.id}:{i}:{turn.role}:{abs(hash(turn.content))%10**9}",
                "conv_id": conv.id,
                "title": conv.title,
                "role": turn.role,
                "ts": turn.timestamp,
                "source": "anthropic.conversations.json",
                "extra": turn.metadata,
                "content": turn.content,
                "msg_index": i,
            }

def parse_chatgpt_conversations(p: Path) -> Generator[Dict[str, Any], None, None]:
    """Legacy: Flatten unified conversations back to doc dicts for SQLite."""
    for conv in parse_chatgpt_unified(p):
        for i, turn in enumerate(conv.turns):
            yield {
                "id": f"{conv.id}:{i}:{turn.role}:{abs(hash(turn.content))%10**9}",
                "conv_id": conv.id,
                "title": conv.title,
                "role": turn.role,
                "ts": turn.timestamp,
                "source": "chatgpt.conversations.json",
                "extra": turn.metadata,
                "content": turn.content,
                "msg_index": i,
            }

def parse_projects(p: Path) -> Generator[Dict[str, Any], None, None]:
    """Yield docs from anthropic-data/projects.json."""
    # Projects don't fit the Conversation model perfectly yet, keeping legacy for now
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
