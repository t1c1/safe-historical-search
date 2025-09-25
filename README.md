<div align="center">
  <img src="logo.png" alt="Safe Historical Search" width="100" height="100">
  
  # Safe Historical Search
  
  **🔍 Lightning-fast local search for your AI conversation history**
  
  *Privacy-first • SQLite FTS5 • Sub-second results*
  
  [![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](VERSION)
  [![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
  [![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
  [![Flask](https://img.shields.io/badge/flask-3.0+-red.svg)](https://flask.palletsprojects.com)
</div>

---

## 🚀 Quick Start

**Get up and running in under 2 minutes:**

> 💡 **Pro tip**: Works with any Anthropic Claude export. Future versions will support ChatGPT/OpenAI exports too!

### Step 1: Get your Claude data export first
1. **🔗 Go to [Claude Settings](https://claude.ai/settings/data-privacy-controls)**
2. **📤 Request a data export** and wait for download
3. **📂 Extract the zip** - you'll get these files:
   - `conversations.json`
   - `projects.json` 
   - `users.json`

### Step 2: Clone and setup (copy-paste ready):
```bash
git clone https://github.com/t1c1/safe-historical-search.git
cd safe-historical-search
mkdir -p files
# Copy your 3 export files into the ./files/ directory
```

### Step 3: Run the app:
```bash
chmod +x quickstart.sh && ./quickstart.sh
```

**🌐 Open the URL shown (auto-selects free port like http://127.0.0.1:5002)**

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

## ✨ Features

- ⚡ **Lightning-fast search** - SQLite FTS5 with sub-second results
- 🛡️ **Privacy-first** - Everything runs locally, your data never leaves your machine
- 📅 **Smart filtering** - Date ranges, relevance sorting, fuzzy search
- 🔗 **Claude integration** - Click through to view conversations in Claude
- 📊 **Multi-account support** - Index multiple exports simultaneously
- 🔄 **One-click reindex** - Update your search index from the web UI

---

## 🎯 Advanced Usage

### Multi-Account Support ✅ Already Works!
```bash
# Index multiple Claude accounts at once
python index.py --export /path/account1,/path/account2 --out ./index

# Or via web UI: enter "/path/account1,/path/account2" in Reindex form
```
Each account gets labeled by folder name and stored separately for filtering.

### Custom Configuration
- **🔗 Claude Links**: `export CLAUDE_URL_TEMPLATE="https://claude.ai/chat/{conv_id}"`
- **🌐 Custom Host**: `python server.py --host 0.0.0.0 --port 5001`
- **🔄 Rebuild Index**: `rm -rf ./index && python index.py --export ./files --out ./index`

### Search Tips
- **📅 Date Range**: Add `date_from=YYYY-MM-DD` and `date_to=YYYY-MM-DD`
- **🔍 Fuzzy Search**: Add `wild=1` to expand partial terms
- **📊 Sorting**: Use `?sort=rank|newest|oldest` or the UI dropdown

---

## 🗺️ Roadmap

### 🎯 Next Release (v0.2.0)
- **🤖 ChatGPT (OpenAI) logs import**
- **📱 Single-step installer**
- **🏷️ Account filtering** in search UI (multi-account already works via CLI)

### 🔮 Future
- **⚡ Incremental indexing** with file watcher
- **💾 Saved searches** and keyboard shortcuts
- **📊 Export analytics** and conversation insights
- **🔍 Advanced search operators** (AND, OR, NOT, quotes)

---

## 📋 Version Info

**Current**: `v0.1.0` • See [`CHANGELOG.md`](CHANGELOG.md) for release notes

---

<div align="center">
  
  **⭐ Star this repo if it helps you!**
  
  <sub>Built with ❤️ for AI conversation enthusiasts • [Report Issues](https://github.com/t1c1/safe-historical-search/issues) • [Contribute](https://github.com/t1c1/safe-historical-search/pulls)</sub>
  
</div>