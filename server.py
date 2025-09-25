import argparse, sqlite3, os, re
from flask import Flask, request, render_template_string, redirect, url_for, flash


TEMPLATE = """
<!doctype html>
<title>Safe Historical Search</title>
<style>
* { box-sizing: border-box; }
body { 
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; 
  margin: 0; padding: 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  min-height: 100vh;
  line-height: 1.6;
}
.container { 
  max-width: 1400px; margin: 0 auto; background: white; 
  min-height: 100vh; box-shadow: 0 0 50px rgba(0,0,0,0.1);
}
.header {
  background: linear-gradient(135deg, #1e3a8a 0%, #3730a3 100%);
  color: white; padding: 24px 32px; 
  box-shadow: 0 4px 20px rgba(0,0,0,0.1);
}
.header h1 { margin: 0; font-size: 28px; font-weight: 700; }
.header .subtitle { opacity: 0.9; font-size: 16px; margin-top: 4px; }
.content { padding: 32px; }
.search-section {
  background: #f8fafc; padding: 32px; border-radius: 16px; 
  margin-bottom: 32px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.search-row { display: flex; gap: 16px; align-items: center; margin-bottom: 20px; flex-wrap: wrap; }
.search-input { 
  flex: 1; min-width: 300px; padding: 16px 20px; font-size: 18px; 
  border: 2px solid #e2e8f0; border-radius: 12px; 
  transition: all 0.2s; background: white;
}
.search-input:focus{ 
  outline: none; border-color: #3b82f6; 
  box-shadow: 0 0 0 4px rgba(59,130,246,0.1); transform: translateY(-1px);
}
.search-btn { 
  padding: 16px 32px; font-size: 18px; font-weight: 600;
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); 
  color: white; border: none; border-radius: 12px; cursor: pointer; 
  transition: all 0.2s; box-shadow: 0 4px 12px rgba(59,130,246,0.3);
}
.search-btn:hover{ 
  transform: translateY(-2px); 
  box-shadow: 0 6px 20px rgba(59,130,246,0.4); 
}
.controls{ 
  display:flex; gap:20px; align-items:center; flex-wrap:wrap; 
  padding: 20px; background: white; border-radius: 12px; 
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
.control-group { display: flex; align-items: center; gap: 8px; }
.control-group label { font-weight: 500; color: #374151; white-space: nowrap; }
.control-group input, .control-group select { 
  padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 8px; 
  font-size: 14px; transition: border-color 0.2s;
}
.control-group input:focus, .control-group select:focus { 
  outline: none; border-color: #3b82f6; 
}
.checkbox-label { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.result{ 
  border: 1px solid #e5e7eb; padding: 24px; margin: 20px 0; 
  border-radius: 16px; background: white; 
  box-shadow: 0 2px 12px rgba(0,0,0,0.06); 
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.result:hover{ 
  transform: translateY(-4px); 
  box-shadow: 0 8px 25px rgba(0,0,0,0.12); 
  border-color: #3b82f6;
}
.result-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.result-title { font-size: 20px; font-weight: 700; color: #111827; margin: 0; }
.result-title a { color: inherit; text-decoration: none; }
.result-title a:hover { color: #3b82f6; }
.result-meta { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-bottom: 16px; }
.pill{ 
  padding: 6px 14px; border-radius: 20px; font-size: 13px; 
  font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;
  border: 1px solid;
}
.pill.anthropic { 
  background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%); 
  color: #1e40af; border-color: #93c5fd;
}
.pill.chatgpt { 
  background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%); 
  color: #166534; border-color: #86efac;
}
.pill.default { 
  background: linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%); 
  color: #374151; border-color: #d1d5db;
}
.result-content { font-size: 16px; line-height: 1.7; color: #374151; margin-bottom: 16px; }
mark{ background: linear-gradient(135deg, #fef08a 0%, #fde047 100%); padding: 3px 6px; border-radius: 6px; font-weight: 600; }
.result-actions { display: flex; gap: 16px; align-items: center; }
.result-actions a { 
  color: #6b7280; text-decoration: none; font-weight: 500; 
  transition: color 0.2s; display: flex; align-items: center; gap: 4px;
}
.result-actions a:hover { color: #3b82f6; }
.result-footer { 
  border-top: 1px solid #f3f4f6; padding-top: 12px; margin-top: 16px;
  font-size: 13px; color: #9ca3af; display: flex; gap: 16px;
}
.stats { 
  background: #f1f5f9; padding: 20px; border-radius: 12px; 
  margin-bottom: 24px; text-align: center; color: #475569; font-weight: 500;
}
.reindex-section {
  background: #fefefe; border: 2px dashed #d1d5db; 
  padding: 24px; border-radius: 12px; margin-bottom: 32px;
}
.reindex-form { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.reindex-input { 
  flex: 1; min-width: 300px; padding: 12px 16px; 
  border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px;
}
.reindex-btn { 
  padding: 12px 24px; background: #10b981; color: white; 
  border: none; border-radius: 8px; font-weight: 600; cursor: pointer;
  transition: background 0.2s;
}
.reindex-btn:hover { background: #059669; }
.flash-messages{ margin: 24px 0; }
.flash{ 
  padding: 16px 20px; border-radius: 12px; margin: 12px 0; 
  font-weight: 500; display: flex; align-items: center; gap: 12px;
}
.flash.success{ background: #d1fae5; color: #065f46; border-left: 4px solid #10b981; }
.flash.error{ background: #fee2e2; color: #991b1b; border-left: 4px solid #ef4444; }
.flash.warning{ background: #fef3c7; color: #92400e; border-left: 4px solid #f59e0b; }
@media (max-width: 768px) {
  .content { padding: 20px; }
  .search-row { flex-direction: column; }
  .search-input { min-width: 100%; }
  .controls { flex-direction: column; align-items: flex-start; gap: 12px; }
  .result-header { flex-direction: column; gap: 12px; }
}
</style>
<meta name="referrer" content="no-referrer"/>
<div class="container">
  <div class="header">
    <div style="display: flex; justify-content: space-between; align-items: center;">
      <div>
        <h1>🔍 Safe Historical Search</h1>
        <div class="subtitle">Lightning-fast search for your AI conversations</div>
      </div>
      <a href="{{ url_for('admin') }}" style="color: rgba(255,255,255,0.9); text-decoration: none; padding: 8px 16px; background: rgba(255,255,255,0.1); border-radius: 8px; transition: background 0.2s;">
        ⚙️ Admin
      </a>
    </div>
  </div>
  
  <div class="content">
    <div class="flash-messages">
      {% with messages = get_flashed_messages() %}
        {% if messages %}
          {% for message in messages %}
            <div class="flash {% if '✅' in message %}success{% elif '❌' in message %}error{% else %}warning{% endif %}">{{ message }}</div>
          {% endfor %}
        {% endif %}
      {% endwith %}
    </div>

    <div class="search-section">
      <form method="GET">
        <div class="search-row">
          <input type="text" name="q" value="{{q|e}}" placeholder="🔍 Search your conversations..." autofocus class="search-input"/>
          <button type="submit" class="search-btn">Search</button>
        </div>
        
        <div class="controls">
          <div class="control-group">
            <label class="checkbox-label">
              <input type="checkbox" name="wild" value="1" {% if wild %}checked{% endif %}>
              <span>Smart expand</span>
              <span style="font-size: 11px; color: #6b7280; margin-left: 4px;" title="Automatically adds wildcards to search terms for partial matching">(?)</span>
            </label>
          </div>
          <div class="control-group">
            <label>🤖 Provider</label>
            <select name="provider">
              <option value="" {% if not provider %}selected{% endif %}>All Providers</option>
              <option value="claude" {% if provider == 'claude' %}selected{% endif %}>🔵 Claude</option>
              <option value="chatgpt" {% if provider == 'chatgpt' %}selected{% endif %}>🟢 ChatGPT</option>
            </select>
          </div>
          <div class="control-group">
            <label>👤 Role</label>
            <select name="role">
              <option value="" {% if not role %}selected{% endif %}>All Roles</option>
              <option value="user" {% if role == 'user' %}selected{% endif %}>Human</option>
              <option value="assistant" {% if role == 'assistant' %}selected{% endif %}>Assistant</option>
              <option value="system" {% if role == 'system' %}selected{% endif %}>System</option>
            </select>
          </div>
          <div class="control-group">
            <label>📅 From</label>
            <input type="date" name="date_from" value="{{date_from}}"/>
          </div>
          <div class="control-group">
            <label>📅 To</label>
            <input type="date" name="date_to" value="{{date_to}}"/>
          </div>
          <div class="control-group">
            <label>📊 Sort</label>
            <select name="sort">
              <option value="rank" {% if sort == 'rank' %}selected{% endif %}>Relevance</option>
              <option value="newest" {% if sort == 'newest' %}selected{% endif %}>Newest</option>
              <option value="oldest" {% if sort == 'oldest' %}selected{% endif %}>Oldest</option>
            </select>
          </div>
        </div>
      </form>
    </div>


    {% if rows is not none %}
      <div class="stats">
        <strong>{{total_count}}</strong> result(s) found
        {% if total_pages > 1 %}
          • Page {{page}} of {{total_pages}}
          • Showing {{per_page}} per page
        {% endif %}
      </div>
      
      {% for r in rows %}
        <div class="result">
          <div class="result-header">
            <h3 class="result-title">
              <a href="{{ url_for('conversation', conv_id=r['conv_id']) }}">{{r['title']}}</a>
            </h3>
          </div>
          
          <div class="result-meta">
            <div class="pill {% if 'anthropic' in r['source'] %}anthropic{% elif 'chatgpt' in r['source'] %}chatgpt{% else %}default{% endif %}">
              {% if 'anthropic' in r['source'] %}🔵 Claude{% elif 'chatgpt' in r['source'] %}🟢 ChatGPT{% else %}{{r['source']}}{% endif %}
            </div>
            <div class="pill default">{{r['role']}}</div>
            {% if r['date'] %}<div class="pill default">{{r['date']}}</div>{% endif %}
          </div>
          
          <div class="result-content">{{r['snip']|safe}}</div>
          
          <div class="result-actions">
            <a href="{{ url_for('conversation', conv_id=r['conv_id']) }}">
              📖 View Full Conversation
            </a>
            {% if r['external_url'] %}
              <a href="{{ r['external_url'] }}" target="_blank" rel="noopener noreferrer">
                {% if 'chatgpt' in r['source'] %}🔗 Open in ChatGPT{% else %}🔗 Open in Claude{% endif %}
              </a>
            {% endif %}
          </div>
          
          <div class="result-footer">
            <span>ID: {{r['id']}}</span>
            <span>Conv: {{r['conv_id']}}</span>
          </div>
        </div>
      {% endfor %}
      
      {% if total_pages > 1 %}
        <div style="display: flex; justify-content: center; align-items: center; gap: 16px; margin: 32px 0; padding: 24px;">
          {% if has_prev %}
            <a href="?q={{q|e}}&wild={{wild|int}}&provider={{provider}}&role={{role}}&date_from={{date_from}}&date_to={{date_to}}&sort={{sort}}&page={{page-1}}&per_page={{per_page}}" 
               style="padding: 12px 20px; background: #3b82f6; color: white; text-decoration: none; border-radius: 8px; font-weight: 500;">
              ← Previous
            </a>
          {% endif %}
          
          <div style="display: flex; gap: 8px; align-items: center;">
            {% for p in range(1, total_pages + 1) %}
              {% if p == page %}
                <span style="padding: 8px 12px; background: #1e40af; color: white; border-radius: 6px; font-weight: 600;">{{p}}</span>
              {% elif p <= 3 or p >= total_pages - 2 or (p >= page - 1 and p <= page + 1) %}
                <a href="?q={{q|e}}&wild={{wild|int}}&provider={{provider}}&role={{role}}&date_from={{date_from}}&date_to={{date_to}}&sort={{sort}}&page={{p}}&per_page={{per_page}}" 
                   style="padding: 8px 12px; color: #374151; text-decoration: none; border-radius: 6px; transition: background 0.2s;">{{p}}</a>
              {% elif p == 4 or p == total_pages - 3 %}
                <span style="color: #9ca3af;">…</span>
              {% endif %}
            {% endfor %}
          </div>
          
          {% if has_next %}
            <a href="?q={{q|e}}&wild={{wild|int}}&provider={{provider}}&role={{role}}&date_from={{date_from}}&date_to={{date_to}}&sort={{sort}}&page={{page+1}}&per_page={{per_page}}" 
               style="padding: 12px 20px; background: #3b82f6; color: white; text-decoration: none; border-radius: 8px; font-weight: 500;">
              Next →
            </a>
          {% endif %}
        </div>
        
        <div style="text-align: center; margin: 16px 0;">
          <select onchange="window.location.href='?q={{q|e}}&wild={{wild|int}}&provider={{provider}}&role={{role}}&date_from={{date_from}}&date_to={{date_to}}&sort={{sort}}&page=1&per_page=' + this.value" 
                  style="padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 6px;">
            <option value="50" {% if per_page == 50 %}selected{% endif %}>50 per page</option>
            <option value="100" {% if per_page == 100 %}selected{% endif %}>100 per page</option>
            <option value="200" {% if per_page == 200 %}selected{% endif %}>200 per page</option>
            <option value="500" {% if per_page == 500 %}selected{% endif %}>500 per page</option>
          </select>
        </div>
      {% endif %}
    {% endif %}
  </div>
  
  <div style="text-align: center; padding: 32px; border-top: 1px solid #f3f4f6; color: #9ca3af; font-size: 14px;">
    Made with ❤️ in a time of war • Made in America • <a href="https://tom.ms" style="color: #6b7280; text-decoration: none;">tom.ms</a>
  </div>
</div>
"""

ADMIN_TEMPLATE = """
<!doctype html>
<title>Admin - Safe Historical Search</title>
<style>
* { box-sizing: border-box; }
body { 
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; 
  margin: 0; padding: 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  min-height: 100vh;
  line-height: 1.6;
}
.container { 
  max-width: 900px; margin: 0 auto; background: white; 
  min-height: 100vh; box-shadow: 0 0 50px rgba(0,0,0,0.1);
}
.header {
  background: linear-gradient(135deg, #1e3a8a 0%, #3730a3 100%);
  color: white; padding: 24px 32px; 
  box-shadow: 0 4px 20px rgba(0,0,0,0.1);
}
.header h1 { margin: 0; font-size: 28px; font-weight: 700; }
.header .subtitle { opacity: 0.9; font-size: 16px; margin-top: 4px; }
.content { padding: 32px; }
.admin-section {
  background: #f8fafc; padding: 32px; border-radius: 16px; 
  margin-bottom: 32px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.admin-section h2 { margin: 0 0 20px 0; color: #1f2937; font-size: 24px; }
.admin-section p { color: #6b7280; margin-bottom: 24px; }
.reindex-form { display: flex; gap: 12px; align-items: flex-start; flex-wrap: wrap; }
.reindex-input { 
  flex: 1; min-width: 400px; padding: 16px 20px; 
  border: 2px solid #e2e8f0; border-radius: 12px; font-size: 16px;
  transition: all 0.2s;
}
.reindex-input:focus { 
  outline: none; border-color: #3b82f6; 
  box-shadow: 0 0 0 4px rgba(59,130,246,0.1);
}
.reindex-btn { 
  padding: 16px 32px; background: #10b981; color: white; 
  border: none; border-radius: 12px; font-weight: 600; cursor: pointer;
  transition: all 0.2s; font-size: 16px;
}
.reindex-btn:hover { background: #059669; transform: translateY(-1px); }
.back-link {
  display: inline-flex; align-items: center; gap: 8px; color: #6b7280; 
  text-decoration: none; font-weight: 500; margin-bottom: 32px;
  transition: color 0.2s;
}
.back-link:hover { color: #3b82f6; }
.flash-messages{ margin: 24px 0; }
.flash{ 
  padding: 16px 20px; border-radius: 12px; margin: 12px 0; 
  font-weight: 500; display: flex; align-items: center; gap: 12px;
}
.flash.success{ background: #d1fae5; color: #065f46; border-left: 4px solid #10b981; }
.flash.error{ background: #fee2e2; color: #991b1b; border-left: 4px solid #ef4444; }
.flash.warning{ background: #fef3c7; color: #92400e; border-left: 4px solid #f59e0b; }
.help-text { 
  background: #eff6ff; border: 1px solid #bfdbfe; padding: 16px; 
  border-radius: 8px; margin-top: 16px; font-size: 14px; color: #1e40af;
}
</style>
<meta name="referrer" content="no-referrer"/>
<div class="container">
  <div class="header">
    <div style="display: flex; justify-content: space-between; align-items: center;">
      <div>
        <h1>⚙️ Admin Panel</h1>
        <div class="subtitle">Manage your search index</div>
      </div>
    </div>
  </div>
  
  <div class="content">
    <a href="{{ url_for('home') }}" class="back-link">
      ← Back to Search
    </a>

    <div class="flash-messages">
      {% with messages = get_flashed_messages() %}
        {% if messages %}
          {% for message in messages %}
            <div class="flash {% if '✅' in message %}success{% elif '❌' in message %}error{% else %}warning{% endif %}">{{ message }}</div>
          {% endfor %}
        {% endif %}
      {% endwith %}
    </div>

    <div class="admin-section">
      <h2>🔄 Reindex Data</h2>
      <p>Update your search index with new or modified conversation exports. You can index single or multiple accounts by providing comma-separated paths.</p>
      
      <form method="POST" action="{{ url_for('reindex') }}" class="reindex-form">
        <input type="text" name="export" value="{{export_default|e}}" 
               placeholder="Path to export folder (or comma-separated paths for multiple accounts)" 
               class="reindex-input" required/>
        <button type="submit" class="reindex-btn">Reindex</button>
      </form>

      <div class="help-text">
        <strong>💡 Tips:</strong><br>
        • Single account: <code>/path/to/anthropic-data</code><br>
        • Multiple accounts: <code>/path/account1,/path/account2,/path/account3</code><br>
        • Each folder should contain: conversations.json, projects.json, users.json
      </div>
    </div>

    <div class="admin-section">
      <h2>📊 Database Info</h2>
      <p>Current database location: <code>{{db_path}}</code></p>
      <p>To completely rebuild the index, delete the database file and reindex your data.</p>
    </div>

    <div class="admin-section">
      <h2>📞 Support & Contact</h2>
      <p>Need help or found a bug? Visit the project repository for documentation, issues, and updates.</p>
      <p>
        <a href="https://github.com/t1c1/safe-historical-search" target="_blank" 
           style="display: inline-flex; align-items: center; gap: 8px; padding: 12px 20px; background: #1f2937; color: white; text-decoration: none; border-radius: 8px; font-weight: 500; transition: background 0.2s;">
          <span>📦</span> View on GitHub
        </a>
      </p>
    </div>
  </div>
  
  <div style="text-align: center; padding: 32px; border-top: 1px solid #f3f4f6; color: #9ca3af; font-size: 14px;">
    Made with ❤️ in a time of war • Made in America • <a href="https://tom.ms" style="color: #6b7280; text-decoration: none;">tom.ms</a>
  </div>
</div>
"""


SQL = """
SELECT d.id, d.conv_id, d.title, d.role, d.date, d.source,
       snippet(docs_fts, 0, '<mark>', '</mark>', ' … ', 12) as snip
FROM docs_fts
JOIN docs d ON d.rowid = docs_fts.rowid
WHERE docs_fts MATCH ?
ORDER BY rank
"""


def make_app(db_path: str):
    app = Flask(__name__)
    app.secret_key = os.environ.get("FLASK_SECRET", "dev")
    db_holder = {"conn": sqlite3.connect(db_path, check_same_thread=False), "db_path": db_path}
    db_holder["conn"].row_factory = sqlite3.Row
    claude_url_template = os.environ.get("CLAUDE_URL_TEMPLATE", "https://claude.ai/chat/{conv_id}")

    @app.route("/", methods=["GET"])
    def home():
        q = request.args.get("q", "").strip()
        wild = request.args.get("wild") == "1"
        date_from = request.args.get("date_from") or None
        date_to = request.args.get("date_to") or None
        sort = request.args.get("sort") or "rank"
        provider_filter = request.args.get("provider", "")
        role_filter = request.args.get("role", "")
        page = int(request.args.get("page", "1"))
        per_page = int(request.args.get("per_page", "100"))
        
        # Limit per_page to reasonable values
        per_page = min(max(per_page, 10), 500)
        offset = (page - 1) * per_page

        rows = None
        total_count = 0

        def expand_tokens(txt):
            parts = [p for p in txt.replace('\u2013', ' ').replace('\u2014', ' ').split() if p]
            expanded = []
            for p in parts:
                if any(op in p for op in ['"', "'", "AND", "OR", "NOT", "NEAR", ":"]):
                    expanded.append(p)
                elif len(p) > 2:
                    expanded.append(p + '*')
                else:
                    expanded.append(p)
            return " ".join(expanded)

        # Easter egg for precision tom
        if q.lower().strip() == "precision tom":
            enriched = [{
                "id": "easter-egg-1",
                "conv_id": "precision-tom-2025",
                "title": "🎯 Precision Tom Easter Egg",
                "role": "system",
                "date": "2025-01-24",
                "source": "easter.egg",
                "snip": "You found the <mark>precision tom</mark> easter egg! 🎉 This search tool was built with precision, care, and attention to detail. Thanks for exploring!",
                "external_url": None
            }]
            return render_template_string(
                TEMPLATE,
                q=q,
                rows=enriched,
                wild=wild,
                date_from=date_from or "",
                date_to=date_to or "",
                sort=sort,
                page=1,
                per_page=100,
                total_count=1,
                total_pages=1,
                has_prev=False,
                has_next=False,
                export_default=export_default,
            )

        if q:
            base_sql = (
                "SELECT d.id, d.conv_id, d.title, d.role, d.date, d.source, "
                "snippet(docs_fts, 0, '<mark>', '</mark>', ' … ', 12) as snip "
                "FROM docs_fts JOIN docs d ON d.rowid = docs_fts.rowid "
                "WHERE docs_fts MATCH ?"
            )
            params = []
            q_try = expand_tokens(q) if wild else q
            params.append(q_try)
            if date_from:
                base_sql += " AND (d.date IS NOT NULL AND d.date >= ?)"
                params.append(date_from)
            if date_to:
                base_sql += " AND (d.date IS NOT NULL AND d.date <= ?)"
                params.append(date_to)
            if provider_filter:
                if provider_filter == "claude":
                    base_sql += " AND d.source LIKE '%anthropic%'"
                elif provider_filter == "chatgpt":
                    base_sql += " AND d.source LIKE '%chatgpt%'"
            if role_filter:
                base_sql += " AND d.role = ?"
                params.append(role_filter)
            # Get total count first
            count_sql = base_sql.replace(
                "SELECT d.id, d.conv_id, d.title, d.role, d.date, d.source, snippet(docs_fts, 0, '<mark>', '</mark>', ' … ', 12) as snip",
                "SELECT COUNT(*)"
            )
            total_count = db_holder["conn"].execute(count_sql, tuple(params)).fetchone()[0]
            
            # Add sorting and pagination
            if sort == "newest":
                base_sql += " ORDER BY (d.date IS NULL), d.date DESC"
            elif sort == "oldest":
                base_sql += " ORDER BY (d.date IS NULL), d.date ASC"
            else:
                base_sql += " ORDER BY rank"
            
            base_sql += f" LIMIT {per_page} OFFSET {offset}"
            rows = db_holder["conn"].execute(base_sql, tuple(params)).fetchall()
            
            # Fallback with expanded tokens if no results
            if not rows and not wild and offset == 0:
                q_try = expand_tokens(q)
                params[0] = q_try
                # Recalculate count with expanded query
                total_count = db_holder["conn"].execute(count_sql, tuple(params)).fetchone()[0]
                rows = db_holder["conn"].execute(base_sql, tuple(params)).fetchall()

        export_default = os.path.abspath(os.path.join(os.path.dirname(__file__), 'files'))
        def looks_like_uuid(u: str) -> bool:
            try:
                return bool(re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", u or ""))
            except Exception:
                return False
        
        def safe_url_format(template: str, conv_id: str, source: str = "") -> str:
            try:
                # Handle ChatGPT links
                if "chatgpt" in source.lower():
                    return f"https://chatgpt.com/c/{conv_id}"
                
                # Handle Claude links with template
                if "{conv_id}" in template:
                    return template.replace("{conv_id}", conv_id)
                elif "%7Bconv_id%7D" in template:
                    return template.replace("%7Bconv_id%7D", conv_id)
                else:
                    # If no placeholder, just append the conv_id
                    return f"{template.rstrip('/')}/{conv_id}"
            except Exception:
                return None
        
        enriched = None if rows is None else [
            {
                "id": r["id"],
                "conv_id": r["conv_id"],
                "title": r["title"],
                "role": r["role"],
                "date": r["date"],
                "source": r["source"],
                "snip": r["snip"],
                "external_url": (
                    safe_url_format(claude_url_template, r["conv_id"], r["source"]) 
                    if (r["source"] and (
                        ("anthropic" in r["source"] and looks_like_uuid(r["conv_id"])) or
                        ("chatgpt" in r["source"] and r["conv_id"])
                    )) else None
                ),
            } for r in rows
        ]
        
        # Calculate pagination info
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 0
        has_prev = page > 1
        has_next = page < total_pages
        
        return render_template_string(
            TEMPLATE,
            q=q,
            rows=enriched,
            wild=wild,
            date_from=date_from or "",
            date_to=date_to or "",
            sort=sort,
            provider=provider_filter,
            role=role_filter,
            page=page,
            per_page=per_page,
            total_count=total_count,
            total_pages=total_pages,
            has_prev=has_prev,
            has_next=has_next,
            export_default=export_default,
        )

    @app.route("/reindex", methods=["POST"])
    def reindex():
        export = request.form.get("export", "").strip()
        if not export:
            flash("❌ Please provide a path to your export directory.")
            return redirect(url_for('home'))
        if not os.path.exists(export):
            flash(f"❌ Directory not found: {export}")
            return redirect(url_for('home'))
        if not os.path.isdir(export):
            flash(f"❌ Path is not a directory: {export}")
            return redirect(url_for('home'))
        
        # Check for required files
        required_files = ["conversations.json", "projects.json", "users.json"]
        missing_files = [f for f in required_files if not os.path.exists(os.path.join(export, f))]
        if missing_files:
            flash(f"⚠️ Missing files in export directory: {', '.join(missing_files)}")
            # Continue anyway - some files might be optional
        out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'index'))
        try:
            from pathlib import Path
            from indexer import build_index_multi
            exports = [e.strip() for e in export.split(',') if e.strip()]
            srcs = []
            for e in exports:
                p = Path(e)
                if p.is_dir():
                    srcs.append((p.name or "default", p))
            if not srcs:
                raise RuntimeError("No valid export directories.")
            db_path = build_index_multi(srcs, Path(out_dir))
        except Exception as e:
            flash(f"❌ Reindex failed: {str(e)[:100]}...")
            return redirect(url_for('home'))
        try:
            db_holder["conn"].close()
            db_holder["conn"] = sqlite3.connect(str(db_path), check_same_thread=False)
            db_holder["conn"].row_factory = sqlite3.Row
            db_holder["db_path"] = str(db_path)
            flash("✅ Reindex complete! Database updated successfully.")
        except Exception as e:
            flash(f"⚠️ Reindex complete, but failed to reload database: {str(e)[:50]}..."        )
        return redirect(url_for('admin'))

    @app.route("/admin", methods=["GET"])
    def admin():
        export_default = os.path.abspath(os.path.join(os.path.dirname(__file__), 'files'))
        return render_template_string(
            ADMIN_TEMPLATE,
            export_default=export_default,
            db_path=db_holder["db_path"]
        )

    @app.route('/favicon.ico')
    def favicon():
        return ("", 204)

    DETAIL_TEMPLATE = """
<!doctype html>
<title>Conversation {{conv_id}}</title>
<style>
body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; }
.topbar{ display:flex; align-items:center; gap:12px; justify-content:space-between; }
.pill{ background:#eef2ff; color:#374151; border:1px solid #d1d5db; padding:2px 8px; border-radius:999px; font-size:0.8em; }
.muted{ color:#777; }
.msg{ border:1px solid #e5e7eb; border-radius:10px; padding:12px; margin:12px 0; background:#fff; }
.role{ font-weight:600; margin-bottom:6px; display:flex; gap:8px; align-items:center; }
.content{ white-space:pre-wrap; line-height:1.4; }
.actions a{ color:#374151; }
</style>
<div class="topbar">
  <div>
    <h2 style="margin:0;">{{title}}</h2>
    <div class="muted">Conversation <code>{{conv_id}}</code></div>
  </div>
  <div class="actions">
    {% if external_url %}<a href="{{external_url}}" target="_blank" rel="noopener noreferrer">Open in Claude ↗</a>{% endif %}
    &nbsp;|&nbsp;
    <a href="{{ url_for('home', q='conv_id:"' ~ conv_id ~ '"') }}">Back to search</a>
  </div>
</div>

{% if first_date %}
  <div class="pill">First message {{first_date}}</div>
{% endif %}

{% for m in messages %}
  <div class="msg">
    <div class="role">{{m['role']}} {% if m['date'] %}<span class="pill">{{m['date']}}</span>{% endif %}</div>
    <div class="content">{{m['content']}}</div>
  </div>
{% endfor %}
"""

    @app.route("/conv/<conv_id>")
    def conversation(conv_id):
        rows = db_holder["conn"].execute(
            "SELECT title, role, date, ts, content, source FROM docs WHERE conv_id=? ORDER BY ts, rowid",
            (conv_id,)
        ).fetchall()
        if not rows:
            flash(f"❌ Conversation not found: {conv_id}")
            return redirect(url_for('home'))
        title = rows[0]["title"] or f"Conversation {conv_id}"
        first_date = None
        for r in rows:
            if r["date"]:
                first_date = r["date"]
                break
        # Only enable external link for Anthropic conversations that look like UUIDs
        def looks_like_uuid(u: str) -> bool:
            try:
                return bool(re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", u or ""))
            except Exception:
                return False
        sources = {r["source"] for r in rows if r["source"]}
        is_anthropic = any("anthropic" in s for s in sources)
        is_chatgpt = any("chatgpt" in s for s in sources)
        external_url = None
        
        if is_chatgpt:
            external_url = f"https://chatgpt.com/c/{conv_id}"
        elif is_anthropic and looks_like_uuid(conv_id):
            try:
                if "{conv_id}" in claude_url_template:
                    external_url = claude_url_template.replace("{conv_id}", conv_id)
                elif "%7Bconv_id%7D" in claude_url_template:
                    external_url = claude_url_template.replace("%7Bconv_id%7D", conv_id)
                else:
                    # If no placeholder, just append the conv_id
                    external_url = f"{claude_url_template.rstrip('/')}/{conv_id}"
            except Exception:
                external_url = None
        messages = [{"role": r["role"], "date": r["date"], "content": r["content"]} for r in rows]
        return render_template_string(
            DETAIL_TEMPLATE,
            conv_id=conv_id,
            title=title,
            messages=messages,
            first_date=first_date,
            external_url=external_url,
        )

    return app


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="./index/chatgpt.db")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5001)
    args = ap.parse_args()
    app = make_app(args.db)
    app.run(host=args.host, port=args.port, debug=False)




