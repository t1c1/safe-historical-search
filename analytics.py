import sqlite3
import json
import re
from datetime import datetime, timezone
from collections import Counter, defaultdict
from typing import Dict, List, Any, Optional
from pathlib import Path


class ConversationAnalytics:
    """Advanced analytics for AI conversation data"""
    
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
    
    def get_overview_stats(self) -> Dict[str, Any]:
        """Get high-level conversation statistics"""
        stats = {}
        
        # Total counts
        total_docs = self.conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
        total_convs = self.conn.execute("SELECT COUNT(DISTINCT conv_id) FROM docs").fetchone()[0]
        
        # Provider breakdown
        provider_stats = {}
        providers = self.conn.execute("""
            SELECT 
                CASE 
                    WHEN source LIKE '%anthropic%' THEN 'Claude'
                    WHEN source LIKE '%chatgpt%' THEN 'ChatGPT'
                    ELSE 'Other'
                END as provider,
                COUNT(*) as count,
                COUNT(DISTINCT conv_id) as conversations
            FROM docs 
            GROUP BY provider
        """).fetchall()
        
        for p in providers:
            provider_stats[p['provider']] = {
                'messages': p['count'],
                'conversations': p['conversations']
            }
        
        # Role breakdown
        role_stats = {}
        roles = self.conn.execute("""
            SELECT role, COUNT(*) as count 
            FROM docs 
            GROUP BY role
        """).fetchall()
        
        for r in roles:
            role_stats[r['role']] = r['count']
        
        # Date range
        date_range = self.conn.execute("""
            SELECT MIN(date) as earliest, MAX(date) as latest
            FROM docs WHERE date IS NOT NULL
        """).fetchone()
        
        return {
            'total_messages': total_docs,
            'total_conversations': total_convs,
            'providers': provider_stats,
            'roles': role_stats,
            'date_range': {
                'earliest': date_range['earliest'],
                'latest': date_range['latest']
            }
        }
    
    def get_temporal_patterns(self) -> Dict[str, Any]:
        """Analyze conversation patterns by time"""
        
        # Get all messages with timestamps
        rows = self.conn.execute("""
            SELECT ts, date, role, 
                   CASE 
                       WHEN source LIKE '%anthropic%' THEN 'Claude'
                       WHEN source LIKE '%chatgpt%' THEN 'ChatGPT'
                       ELSE 'Other'
                   END as provider
            FROM docs 
            WHERE ts > 0
        """).fetchall()
        
        patterns = {
            'by_hour': defaultdict(int),
            'by_day_of_week': defaultdict(int),
            'by_month': defaultdict(int),
            'by_provider_hour': defaultdict(lambda: defaultdict(int)),
            'activity_timeline': []
        }
        
        for row in rows:
            try:
                dt = datetime.fromtimestamp(row['ts'], tz=timezone.utc)
                
                # Hour of day (0-23)
                patterns['by_hour'][dt.hour] += 1
                
                # Day of week (0=Monday, 6=Sunday)
                patterns['by_day_of_week'][dt.strftime('%A')] += 1
                
                # Month
                patterns['by_month'][dt.strftime('%Y-%m')] += 1
                
                # Provider by hour
                patterns['by_provider_hour'][row['provider']][dt.hour] += 1
                
            except Exception:
                continue
        
        # Convert defaultdicts to regular dicts for JSON serialization
        return {
            'by_hour': dict(patterns['by_hour']),
            'by_day_of_week': dict(patterns['by_day_of_week']),
            'by_month': dict(patterns['by_month']),
            'by_provider_hour': {k: dict(v) for k, v in patterns['by_provider_hour'].items()}
        }
    
    def extract_topics(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Extract common topics from conversations"""
        
        # Get conversation titles and content samples
        rows = self.conn.execute("""
            SELECT DISTINCT conv_id, title, 
                   GROUP_CONCAT(content, ' ') as combined_content,
                   COUNT(*) as message_count,
                   MIN(date) as start_date,
                   MAX(date) as end_date,
                   CASE 
                       WHEN source LIKE '%anthropic%' THEN 'Claude'
                       WHEN source LIKE '%chatgpt%' THEN 'ChatGPT'
                       ELSE 'Other'
                   END as provider
            FROM docs 
            WHERE title IS NOT NULL AND title != ''
            GROUP BY conv_id
            ORDER BY message_count DESC
            LIMIT ?
        """, (limit,)).fetchall()
        
        topics = []
        for row in rows:
            # Simple keyword extraction from titles
            title_words = re.findall(r'\b[A-Za-z]{3,}\b', row['title'].lower())
            content_sample = (row['combined_content'] or '')[:500]
            
            # Extract entities (simple pattern matching)
            entities = {
                'companies': re.findall(r'\b(?:Google|Apple|Microsoft|Amazon|Meta|Tesla|OpenAI|Anthropic|Netflix|Spotify)\b', content_sample, re.IGNORECASE),
                'technologies': re.findall(r'\b(?:Python|JavaScript|React|AI|ML|SQL|API|AWS|Docker|Kubernetes)\b', content_sample, re.IGNORECASE),
                'topics': re.findall(r'\b(?:coding|programming|design|marketing|business|startup|product|data|analytics)\b', content_sample, re.IGNORECASE)
            }
            
            topics.append({
                'conv_id': row['conv_id'],
                'title': row['title'],
                'provider': row['provider'],
                'message_count': row['message_count'],
                'start_date': row['start_date'],
                'end_date': row['end_date'],
                'keywords': title_words[:5],  # Top 5 keywords from title
                'entities': {k: list(set(v)) for k, v in entities.items()},  # Unique entities
                'content_preview': content_sample[:200] + '...' if len(content_sample) > 200 else content_sample
            })
        
        return topics
    
    def get_conversation_summaries(self, conv_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Generate summaries for specific conversations"""
        summaries = {}
        
        for conv_id in conv_ids:
            rows = self.conn.execute("""
                SELECT title, role, content, date, ts,
                       CASE 
                           WHEN source LIKE '%anthropic%' THEN 'Claude'
                           WHEN source LIKE '%chatgpt%' THEN 'ChatGPT'
                           ELSE 'Other'
                       END as provider
                FROM docs 
                WHERE conv_id = ?
                ORDER BY ts, rowid
            """, (conv_id,)).fetchall()
            
            if not rows:
                continue
            
            # Basic conversation analysis
            total_messages = len(rows)
            user_messages = sum(1 for r in rows if r['role'] == 'user')
            assistant_messages = sum(1 for r in rows if r['role'] == 'assistant')
            
            # Word count estimation
            total_words = sum(len(r['content'].split()) for r in rows if r['content'])
            
            # Time span
            dates = [r['date'] for r in rows if r['date']]
            time_span = None
            if len(dates) >= 2:
                try:
                    start_date = min(dates)
                    end_date = max(dates)
                    if start_date != end_date:
                        time_span = f"{start_date} to {end_date}"
                    else:
                        time_span = start_date
                except Exception:
                    pass
            
            # Extract key themes (simple approach)
            all_content = ' '.join(r['content'] for r in rows if r['content'])
            themes = []
            
            # Common AI discussion themes
            theme_patterns = {
                'coding': r'\b(?:code|coding|programming|python|javascript|function|class|variable)\b',
                'business': r'\b(?:business|strategy|market|revenue|customer|product|startup)\b',
                'creative': r'\b(?:creative|design|art|writing|story|novel|poem|music)\b',
                'technical': r'\b(?:technical|architecture|system|database|api|server|cloud)\b',
                'analysis': r'\b(?:analysis|data|analytics|statistics|research|study|report)\b',
                'planning': r'\b(?:plan|planning|strategy|roadmap|timeline|schedule|project)\b'
            }
            
            for theme, pattern in theme_patterns.items():
                if re.search(pattern, all_content, re.IGNORECASE):
                    themes.append(theme)
            
            summaries[conv_id] = {
                'title': rows[0]['title'] or f"Conversation {conv_id}",
                'provider': rows[0]['provider'],
                'total_messages': total_messages,
                'user_messages': user_messages,
                'assistant_messages': assistant_messages,
                'estimated_words': total_words,
                'time_span': time_span,
                'themes': themes[:3],  # Top 3 themes
                'preview': all_content[:300] + '...' if len(all_content) > 300 else all_content
            }
        
        return summaries
    
    def search_with_analytics(self, query: str, **filters) -> Dict[str, Any]:
        """Enhanced search with analytics"""
        # Standard search logic here...
        # This would integrate with the existing search but add analytics
        pass
