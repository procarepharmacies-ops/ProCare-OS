"""Knowledge graph — index and search all business knowledge in one place.

Indexes the docs/ folder, CLAUDE.md, findings.md, progress.md, and any
Markdown content in the project into a searchable knowledge base. Agents
can query this before executing tasks for context.

This is an in-memory full-text search over the project's documentation.
No external dependencies — pure Python.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

# Project root: config.py -> app -> backend -> src -> <repo root>
ROOT = Path(__file__).resolve().parents[4]

# Directories and files to index
DOC_DIRS = [
    ROOT / "docs",
    Path("D:/Procare Vault"),
]
SINGLE_FILES = [
    ROOT / "CLAUDE.md",
    ROOT / "findings.md",
    ROOT / "progress.md",
    ROOT / "task_plan.md",
    ROOT / "README.md",
]

# Topic classification by filename pattern
TOPIC_MAP = {
    "architecture": ["01-architecture", "ORCHESTRATION_BLUEPRINT"],
    "estock": ["02-eStock", "05-data-quality", "estock"],
    "clinical": ["03-titan", "clinical"],
    "ai_automation": ["04-ai-automation"],
    "roadmap": ["06-roadmap"],
    "multi_branch": ["07-multi-branch"],
    "cloud": ["08-google-cloud"],
    "audit": ["09-cash-audit", "09-performance"],
    "backup": ["10-historical"],
    "android": ["12-android"],
    "pharmacy_ops": ["CLAUDE", "README"],
    "memory": ["findings", "progress", "task_plan"],
    "schema": ["procare-schema", "dashboard-queries", "procedures", "performance-analysis"],
}


@dataclass
class KnowledgeNode:
    """One indexed document or section."""
    id: str
    title: str
    path: str
    topic: str
    content: str
    headings: list[str] = field(default_factory=list)


class KnowledgeGraph:
    """In-memory searchable index of all project documentation."""

    def __init__(self) -> None:
        self.nodes: dict[str, KnowledgeNode] = {}
        self._indexed = False

    def index(self) -> dict:
        """(Re-)index all documentation. Returns summary stats."""
        self.nodes.clear()
        count = 0

        # Index single files
        for fpath in SINGLE_FILES:
            if fpath.exists():
                self._index_file(fpath)
                count += 1

        # Index doc directories
        for ddir in DOC_DIRS:
            if ddir.exists():
                for f in sorted(ddir.glob("*.md")):
                    self._index_file(f)
                    count += 1

        # Index SQL files
        sql_dir = ROOT / "sql"
        if sql_dir.exists():
            for f in sorted(sql_dir.glob("*.sql")):
                self._index_file(f)
                count += 1

        self._indexed = True
        return {
            "indexed": count,
            "topics": list(self.topics().keys()),
            "total_nodes": len(self.nodes),
        }

    def _index_file(self, fpath: Path) -> None:
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return

        name = fpath.stem
        node_id = name.lower().replace(" ", "_")

        # Extract headings
        headings = re.findall(r"^#+\s+(.+)$", content, re.MULTILINE)

        # Extract title (first heading or filename)
        title = headings[0] if headings else name

        # Classify topic
        topic = "general"
        for t, patterns in TOPIC_MAP.items():
            if any(p.lower() in name.lower() for p in patterns):
                topic = t
                break

        # Handle paths outside ROOT (e.g., D:/Procare Vault)
        try:
            rel_path = str(fpath.relative_to(ROOT))
        except ValueError:
            rel_path = str(fpath)

        self.nodes[node_id] = KnowledgeNode(
            id=node_id,
            title=title,
            path=rel_path,
            topic=topic,
            content=content,
            headings=headings[:20],
        )

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Full-text search across all indexed knowledge."""
        if not self._indexed:
            self.index()

        if not query.strip():
            return []

        terms = query.lower().split()
        results = []

        for node in self.nodes.values():
            text = (node.title + " " + node.content).lower()
            # Score: count how many terms match, weighted by title matches
            score = 0
            for term in terms:
                if term in node.title.lower():
                    score += 3
                if term in text:
                    score += 1
                    # Bonus for exact heading matches
                    for h in node.headings:
                        if term in h.lower():
                            score += 2

            if score > 0:
                # Extract snippet around first match
                snippet = _extract_snippet(node.content, terms[0])
                results.append({
                    "id": node.id,
                    "title": node.title,
                    "path": node.path,
                    "topic": node.topic,
                    "score": score,
                    "snippet": snippet,
                    "headings": node.headings[:5],
                })

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:limit]

    def topics(self) -> dict[str, list[dict]]:
        """Return knowledge organized by topic."""
        if not self._indexed:
            self.index()

        out: dict[str, list[dict]] = {}
        for node in self.nodes.values():
            if node.topic not in out:
                out[node.topic] = []
            out[node.topic].append({
                "id": node.id,
                "title": node.title,
                "path": node.path,
                "headings": node.headings[:5],
                "size": len(node.content),
            })
        return out

    def get_node(self, node_id: str) -> dict | None:
        """Get full content of a knowledge node."""
        if not self._indexed:
            self.index()
        node = self.nodes.get(node_id)
        if not node:
            return None
        return {
            "id": node.id,
            "title": node.title,
            "path": node.path,
            "topic": node.topic,
            "content": node.content,
            "headings": node.headings,
        }


def _extract_snippet(text: str, term: str, context: int = 150) -> str:
    """Extract a snippet of text around the first occurrence of term."""
    idx = text.lower().find(term.lower())
    if idx < 0:
        return text[:context] + "…" if len(text) > context else text
    start = max(0, idx - context // 2)
    end = min(len(text), idx + len(term) + context // 2)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet


# Singleton instance
_graph = KnowledgeGraph()


def search(query: str, limit: int = 10) -> list[dict]:
    return _graph.search(query, limit)


def topics() -> dict[str, list[dict]]:
    return _graph.topics()


def get_node(node_id: str) -> dict | None:
    return _graph.get_node(node_id)


def refresh() -> dict:
    return _graph.index()
