from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum
import hashlib
import re

class SourceType(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"
    UNKNOWN = "unknown"

class NodeType(Enum):
    CONVERSATION = "conversation"
    TURN = "turn"
    ENTITY = "entity"
    ARTIFACT = "artifact"
    CLAIM = "claim"
    DECISION = "decision"
    TASK = "task"

class EdgeType(Enum):
    CONTAINS = "contains"          # conversation -> turn
    MENTIONS = "mentions"          # turn -> entity
    PRODUCES = "produces"          # turn -> artifact
    ASSERTS = "asserts"            # turn -> claim
    DECIDES = "decides"            # turn -> decision
    CREATES_TASK = "creates_task"  # turn -> task
    RELATED_TO = "related_to"      # any -> any
    REFERENCES = "references"      # turn -> turn (cross-conversation)
    FOLLOWS = "follows"            # turn -> turn (same conversation)

@dataclass
class Entity:
    """Represents a person, organization, place, or concept."""
    id: str
    name: str
    type: str  # e.g., "person", "project", "technology"
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CodeBlock:
    """A code snippet extracted from content."""
    id: str
    language: str
    content: str
    start_line: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Link:
    """A URL extracted from content."""
    id: str
    url: str
    text: Optional[str] = None
    domain: Optional[str] = None
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
class Claim:
    """A fact or assertion extracted from a conversation."""
    id: str
    content: str
    confidence: float = 1.0  # 0.0 to 1.0
    source_turn_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Decision:
    """A decision made during a conversation."""
    id: str
    summary: str
    rationale: Optional[str] = None
    alternatives: List[str] = field(default_factory=list)
    source_turn_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Task:
    """A TODO or action item extracted from a conversation."""
    id: str
    description: str
    status: str = "open"  # open, in_progress, done, cancelled
    priority: Optional[str] = None  # low, medium, high
    due_date: Optional[float] = None
    source_turn_id: Optional[str] = None
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
    code_blocks: List[CodeBlock] = field(default_factory=list)
    links: List[Link] = field(default_factory=list)
    claims: List[Claim] = field(default_factory=list)
    decisions: List[Decision] = field(default_factory=list)
    tasks: List[Task] = field(default_factory=list)
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

@dataclass
class Node:
    """A node in the Knowledge Graph."""
    id: str
    type: NodeType
    label: str
    data: Any  # The actual object (Conversation, Turn, Entity, etc.)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Edge:
    """An edge/relationship in the Knowledge Graph."""
    id: str
    type: EdgeType
    source_id: str
    target_id: str
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


# Extraction utilities

def extract_code_blocks(content: str, turn_id: str) -> List[CodeBlock]:
    """Extract code blocks from markdown content."""
    pattern = r'```(\w*)\n(.*?)```'
    blocks = []
    for i, match in enumerate(re.finditer(pattern, content, re.DOTALL)):
        lang = match.group(1) or "text"
        code = match.group(2).strip()
        block_id = f"{turn_id}:code:{i}"
        blocks.append(CodeBlock(
            id=block_id,
            language=lang,
            content=code,
            start_line=content[:match.start()].count('\n')
        ))
    return blocks

def extract_links(content: str, turn_id: str) -> List[Link]:
    """Extract URLs from content."""
    # Match markdown links and bare URLs
    md_pattern = r'\[([^\]]*)\]\((https?://[^\)]+)\)'
    url_pattern = r'(?<!\()(https?://[^\s\)\]]+)'
    
    links = []
    seen_urls = set()
    
    # Markdown links first
    for i, match in enumerate(re.finditer(md_pattern, content)):
        url = match.group(2)
        if url not in seen_urls:
            seen_urls.add(url)
            domain = re.search(r'https?://([^/]+)', url)
            links.append(Link(
                id=f"{turn_id}:link:{len(links)}",
                url=url,
                text=match.group(1),
                domain=domain.group(1) if domain else None
            ))
    
    # Bare URLs
    for match in re.finditer(url_pattern, content):
        url = match.group(1)
        if url not in seen_urls:
            seen_urls.add(url)
            domain = re.search(r'https?://([^/]+)', url)
            links.append(Link(
                id=f"{turn_id}:link:{len(links)}",
                url=url,
                domain=domain.group(1) if domain else None
            ))
    
    return links


