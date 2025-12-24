from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum
import hashlib

class SourceType(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"
    UNKNOWN = "unknown"

@dataclass
class Entity:
    """Represents a person, organization, place, or concept."""
    id: str
    name: str
    type: str  # e.g., "person", "project", "technology"
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Artifact:
    """Represents a generated item like code, document, or image."""
    id: str
    type: str  # "code", "markdown", "image"
    content: str
    language: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Turn:
    """A single exchange in a conversation (user or assistant)."""
    id: str
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: float
    model: Optional[str] = None
    artifacts: List[Artifact] = field(default_factory=list)
    entities: List[Entity] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp)

@dataclass
class Conversation:
    """A full conversation history."""
    id: str
    title: str
    source: SourceType
    created_at: float
    updated_at: float
    turns: List[Turn] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def generate_id(content: str) -> str:
        """Generate a stable ID from content."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

