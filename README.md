<div align="center">
  <img src="logo.png" alt="Safe Historical Search" width="100" height="100">
  
  # Safe Historical Search
  
  **🔍 Lightning-fast local search for your AI conversation history**
  
  *Privacy-first • SQLite FTS5 • Sub-second results • Interactive filtering*
  
  [![Version](https://img.shields.io/badge/version-0.2.0-blue.svg)](VERSION)
  [![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
  [![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
  [![Flask](https://img.shields.io/badge/flask-3.0+-red.svg)](https://flask.palletsprojects.com)
</div>

---

## 🚀 Quick Start

**Get up and running in under 2 minutes:**

> 💡 **Pro tip**: Works with both Claude (Anthropic) and ChatGPT (OpenAI) exports! Mix and match multiple accounts from both providers.

### Step 1: Get your AI conversation exports

**For Claude (Anthropic):**
1. **🔗 Go to [Claude Settings](https://claude.ai/settings/data-privacy-controls)**
2. **📤 Request a data export** and wait for download
3. **📂 Extract the zip** - you'll get: `conversations.json`, `projects.json`, `users.json`

**For ChatGPT (OpenAI):**
1. **🔗 Go to [ChatGPT Data Controls](https://chatgpt.com/settings/data-controls)**
2. **📤 Export your data** and wait for download
3. **📂 Extract the zip** - you'll get: `conversations.json`, `user.json`, `shared_conversations.json`, `message_feedback.json`

### Step 2: Clone and setup (copy-paste ready):
```bash
git clone https://github.com/t1c1/safe-historical-search.git
cd safe-historical-search
mkdir -p files
# Copy your export files into the ./files/ directory
# For Claude: conversations.json, projects.json, users.json
# For ChatGPT: conversations.json, user.json, shared_conversations.json, message_feedback.json
# Or mix both providers in the same folder!
```

### Step 3: Run the app:
```bash
chmod +x quickstart.sh && ./quickstart.sh
```

**🌐 Open the URL shown (auto-selects free port like http://127.0.0.1:5002)**

---

## ✨ New Features (v0.2.0)

### 🎯 Interactive Filtering
- **Click any pill to filter** - Provider (🔵 Claude, 🟢 ChatGPT), role (user/assistant), or date
- **Smart expand enabled by default** - Automatic wildcard matching for better results
- **Instant filtering** - No page refresh needed, preserves your search

### 🔍 Expandable Context
- **"🔍 Show context" button** on every search result
- **Full conversation preview** with highlighted current message
- **Color-coded messages** - Blue for user, green for assistant
- **Smart highlighting** - Current search result marked with "📍 Current Result"

### 🎨 Enhanced UI/UX
- **Beautiful hover effects** on interactive elements
- **Loading states** for better feedback
- **Error handling** with user-friendly messages
- **Responsive design** that works on all screen sizes

---

## 🎯 Use Cases & Examples

### 🔬 **Research & Knowledge Mining**
Perfect for researchers, consultants, and knowledge workers who need to find specific information from their AI conversations.

**Example scenarios:**
- *"What was that Python code solution for handling async requests?"*
- *"Find all discussions about machine learning model architectures"*
- *"Show me conversations where I discussed pricing strategies"*

**How to use:**
1. Search for `"async requests python"` with Smart Expand on
2. Click 🔍 Show context to see the full code solution
3. Filter by 🤖 assistant role to see only AI responses

### 💼 **Business Intelligence**
Extract insights from your AI brainstorming sessions and strategic discussions.

**Example scenarios:**
- *"All conversations about competitor analysis from Q3"*
- *"Find discussions where I explored new product features"*
- *"Show me all the marketing campaign ideas I discussed"*

**How to use:**
1. Use date filters: Click any date pill or set date ranges
2. Search for `"competitor analysis"` or `"product features"`
3. Filter by provider to see which AI gave better insights

### 📚 **Learning & Education**
Students and lifelong learners can quickly find educational content and explanations.

**Example scenarios:**
- *"That explanation of quantum computing concepts"*
- *"All my chemistry homework help conversations"*
- *"Find the step-by-step calculus problem solutions"*

**How to use:**
1. Search for subject keywords like `"quantum computing"`
2. Click 👤 user pill to see your original questions
3. Use context expansion to see the full Q&A thread

### 🛠️ **Technical Troubleshooting**
Developers and IT professionals can quickly find solutions to recurring problems.

**Example scenarios:**
- *"How did I fix that Docker networking issue?"*
- *"Find all conversations about database optimization"*
- *"Show me the debugging steps for API rate limiting"*

**How to use:**
1. Search for error messages or technical terms
2. Filter by date to find recent solutions
3. Expand context to see the complete troubleshooting process

### 🎨 **Creative Projects**
Writers, designers, and creators can rediscover ideas and inspiration.

**Example scenarios:**
- *"Find all the story plot ideas I brainstormed"*
- *"Show me design feedback conversations"*
- *"All discussions about character development"*

**How to use:**
1. Search for creative keywords like `"story plot"` or `"character"`
2. Use Smart Expand to catch variations and related terms
3. Browse context to see how ideas evolved over time

### 📊 **Personal Analytics**
Understand your AI usage patterns and conversation topics.

**Example scenarios:**
- *"How often do I ask coding questions vs. creative writing?"*
- *"Which AI provider do I use more for technical topics?"*
- *"What are my most common conversation topics?"*

**How to use:**
1. Filter by provider (🔵 Claude vs 🟢 ChatGPT) to compare usage
2. Filter by role to see question vs. answer patterns
3. Use date ranges to track usage over time

---

## ⚙️ Manual Setup

<details>
<summary>Click to expand manual installation steps</summary>

```bash
# 🐍 Create virtual environment
python -m venv .venv
source .venv/bin/activate

# 📦 Install dependencies
pip install -r requirements.txt

# 📁 Prepare data directory
mkdir -p ./files
# Copy your export files into ./files/

# 🔍 Build search index
python index.py --export ./files --out ./index

# 🚀 Start server
python server.py --db ./index/chatgpt.db --port 5001
```

</details>

---

## 🔧 Advanced Features

### Multi-Account Support ✅ Already Works!
```bash
# Index multiple accounts at once
python index.py --export /path/account1,/path/account2 --out ./index

# Or via web UI: enter "/path/account1,/path/account2" in Reindex form
```
Each account gets labeled by folder name and stored separately for filtering.

### Custom Configuration
- **🔗 Claude Links**: `export CLAUDE_URL_TEMPLATE="https://claude.ai/chat/{conv_id}"`
- **🌐 Custom Host**: `python server.py --host 0.0.0.0 --port 5001`
- **🔄 Rebuild Index**: `rm -rf ./index && python index.py --export ./files --out ./index`

### Search Tips & Tricks
- **📅 Date Filtering**: Click date pills or use URL params `date_from=YYYY-MM-DD&date_to=YYYY-MM-DD`
- **🔍 Smart Expand**: Enabled by default, automatically adds wildcards for partial matching
- **🎯 Role Filtering**: Click user/assistant pills to filter by message type
- **📊 Sorting**: Use `?sort=rank|newest|oldest` or the UI dropdown
- **🔗 Provider Filtering**: Click Claude/ChatGPT pills to filter by AI provider

### Power User Features
- **Keyboard Navigation**: Tab through results, Enter to expand context
- **URL Bookmarking**: All filters and searches are URL-encoded for bookmarking
- **Batch Operations**: Select multiple results (coming in v0.3.0)

---

## 🛡️ Privacy & Security

### 100% Local Processing
- **No cloud dependencies** - Everything runs on your machine
- **No data transmission** - Your conversations never leave your computer
- **No tracking** - No analytics, cookies, or external requests
- **Offline capable** - Works without internet connection

### Data Storage
- **SQLite database** - Single file, easy to backup or delete
- **Original exports preserved** - Your source files remain untouched
- **Easy cleanup** - Delete the `./index` folder to remove all processed data

---

## 🗺️ Roadmap

### ✅ Completed in v0.2.0
- ~~**🎯 Interactive clickable filters**~~ ✅ Done - Click pills to filter instantly
- ~~**🔍 Expandable conversation context**~~ ✅ Done - Full thread preview with highlighting
- ~~**📅 Smart date picker**~~ ✅ Done - Native calendar widgets
- ~~**🤖 Combined assistant/system roles**~~ ✅ Done - Simplified to Human/Assistant
- ~~**⚡ Real-time filtering**~~ ✅ Done - Instant results when clicking filters

### 🎯 Next Release (v0.3.0)
- **🔍 Advanced search operators** (AND, OR, NOT, quotes, parentheses)
- **💾 Saved searches** and search history
- **⌨️ Keyboard shortcuts** for power users
- **📊 Basic conversation statistics** in search results

### 🔮 Future Releases
- **⚡ Incremental indexing** with file watcher for auto-updates
- **📊 Advanced conversation analytics** and insights dashboard  
- **🏷️ Custom tagging** and categorization system
- **📤 Export filtered results** to various formats
- **🔌 Plugin system** for custom data sources

---

## 🛠️ Technical Details

### Architecture
- **Backend**: Python 3.8+ with Flask web framework
- **Database**: SQLite with FTS5 full-text search extension
- **Frontend**: Vanilla JavaScript with modern CSS Grid/Flexbox
- **Search**: Sub-second results using optimized SQL queries

### Performance
- **Index size**: ~10-20MB per 1000 conversations
- **Search speed**: <100ms for most queries
- **Memory usage**: <50MB typical, <200MB with large datasets
- **Startup time**: <2 seconds for most databases

### File Support
- **Claude exports**: `conversations.json`, `projects.json`, `users.json`
- **ChatGPT exports**: `conversations.json`, `user.json`, `shared_conversations.json`, `message_feedback.json`
- **Mixed providers**: Automatically detects and handles both formats

---

## 📋 Version Info

**Current**: `v0.2.0` • See [`CHANGELOG.md`](CHANGELOG.md) for release notes

### What's New in v0.2.0
- ✨ Interactive clickable filters for provider, role, and date
- 🔍 Expandable conversation context with full thread preview
- 🎯 Smart expand enabled by default for better search results
- 🎨 Enhanced UI with hover effects and loading states
- 🛠️ Improved error handling and user feedback

---

<div align="center">
  
  **⭐ Star this repo if it helps you find your AI conversations faster!**
  
  <sub>Built with ❤️ for AI conversation enthusiasts • Privacy-first • Made in America</sub>
  
  <sub>[Report Issues](https://github.com/t1c1/safe-historical-search/issues) • [Contribute](https://github.com/t1c1/safe-historical-search/pulls) • [Documentation](https://github.com/t1c1/safe-historical-search/wiki)</sub>
  
</div>