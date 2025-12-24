/**
 * Inchive Unified API Worker
 * 
 * Handles: Landing, Auth, Search with multi-user data isolation
 * 
 * Routes:
 *   GET  /                    - Landing page
 *   POST /api/waitlist        - Join waitlist
 *   POST /api/auth/signup     - Create account
 *   POST /api/auth/login      - Login
 *   POST /api/auth/logout     - Logout
 *   GET  /api/auth/me         - Current user
 *   POST /api/search          - Semantic search (user-isolated)
 *   POST /api/conversations   - Import conversations
 *   GET  /api/conversations   - List user's conversations
 *   GET  /api/stats           - User stats
 */

// Utilities
const generateId = () => crypto.randomUUID();
const now = () => Math.floor(Date.now() / 1000);

async function sha256(text) {
  const encoder = new TextEncoder();
  const data = encoder.encode(text);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('');
}

async function generateToken() {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return Array.from(array).map(b => b.toString(16).padStart(2, '0')).join('');
}

// CORS headers
const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
};

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" }
  });
}

// Auth middleware
async function getUser(request, env) {
  // Check Authorization header (API key or Bearer token)
  const auth = request.headers.get("Authorization");
  
  if (auth?.startsWith("Bearer ")) {
    const token = auth.slice(7);
    const tokenHash = await sha256(token);
    
    // Try session token first
    const session = await env.DB.prepare(`
      SELECT s.*, u.* FROM sessions s
      JOIN users u ON u.id = s.user_id
      WHERE s.token_hash = ? AND s.expires_at > ?
    `).bind(tokenHash, now()).first();
    
    if (session) {
      return { id: session.user_id, email: session.email, plan: session.plan };
    }
    
    // Try API key
    const apiKey = await env.DB.prepare(`
      SELECT k.*, u.* FROM api_keys k
      JOIN users u ON u.id = k.user_id
      WHERE k.key_hash = ? AND (k.expires_at IS NULL OR k.expires_at > ?)
    `).bind(tokenHash, now()).first();
    
    if (apiKey) {
      // Update last used
      await env.DB.prepare(`UPDATE api_keys SET last_used_at = ? WHERE id = ?`)
        .bind(now(), apiKey.id).run();
      return { id: apiKey.user_id, email: apiKey.email, plan: apiKey.plan };
    }
  }
  
  // Check cookie
  const cookie = request.headers.get("Cookie");
  if (cookie) {
    const match = cookie.match(/session=([^;]+)/);
    if (match) {
      const tokenHash = await sha256(match[1]);
      const session = await env.DB.prepare(`
        SELECT s.*, u.* FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = ? AND s.expires_at > ?
      `).bind(tokenHash, now()).first();
      
      if (session) {
        return { id: session.user_id, email: session.email, plan: session.plan };
      }
    }
  }
  
  return null;
}

// Route handlers
async function handleSignup(request, env) {
  const { email, password, name } = await request.json();
  
  if (!email || !password) {
    return jsonResponse({ error: "Email and password required" }, 400);
  }
  
  // Check if user exists
  const existing = await env.DB.prepare("SELECT id FROM users WHERE email = ?")
    .bind(email.toLowerCase()).first();
  
  if (existing) {
    return jsonResponse({ error: "Email already registered" }, 409);
  }
  
  // Create user
  const userId = generateId();
  const passwordHash = await sha256(password + userId); // Simple hash with salt
  
  await env.DB.prepare(`
    INSERT INTO users (id, email, password_hash, name, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?)
  `).bind(userId, email.toLowerCase(), passwordHash, name || null, now(), now()).run();
  
  // Create session
  const token = await generateToken();
  const tokenHash = await sha256(token);
  const expiresAt = now() + 30 * 24 * 60 * 60; // 30 days
  
  await env.DB.prepare(`
    INSERT INTO sessions (id, user_id, token_hash, created_at, expires_at)
    VALUES (?, ?, ?, ?, ?)
  `).bind(generateId(), userId, tokenHash, now(), expiresAt).run();
  
  return new Response(JSON.stringify({ 
    success: true, 
    user: { id: userId, email: email.toLowerCase() }
  }), {
    status: 201,
    headers: {
      ...corsHeaders,
      "Content-Type": "application/json",
      "Set-Cookie": `session=${token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=${30 * 24 * 60 * 60}`
    }
  });
}

async function handleLogin(request, env) {
  const { email, password } = await request.json();
  
  const user = await env.DB.prepare("SELECT * FROM users WHERE email = ?")
    .bind(email.toLowerCase()).first();
  
  if (!user) {
    return jsonResponse({ error: "Invalid credentials" }, 401);
  }
  
  const passwordHash = await sha256(password + user.id);
  if (passwordHash !== user.password_hash) {
    return jsonResponse({ error: "Invalid credentials" }, 401);
  }
  
  // Create session
  const token = await generateToken();
  const tokenHash = await sha256(token);
  const expiresAt = now() + 30 * 24 * 60 * 60;
  
  await env.DB.prepare(`
    INSERT INTO sessions (id, user_id, token_hash, created_at, expires_at)
    VALUES (?, ?, ?, ?, ?)
  `).bind(generateId(), user.id, tokenHash, now(), expiresAt).run();
  
  return new Response(JSON.stringify({ 
    success: true,
    user: { id: user.id, email: user.email, plan: user.plan }
  }), {
    headers: {
      ...corsHeaders,
      "Content-Type": "application/json",
      "Set-Cookie": `session=${token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=${30 * 24 * 60 * 60}`
    }
  });
}

async function handleLogout(request, env) {
  const cookie = request.headers.get("Cookie");
  if (cookie) {
    const match = cookie.match(/session=([^;]+)/);
    if (match) {
      const tokenHash = await sha256(match[1]);
      await env.DB.prepare("DELETE FROM sessions WHERE token_hash = ?")
        .bind(tokenHash).run();
    }
  }
  
  return new Response(JSON.stringify({ success: true }), {
    headers: {
      ...corsHeaders,
      "Content-Type": "application/json",
      "Set-Cookie": "session=; Path=/; HttpOnly; Max-Age=0"
    }
  });
}

async function handleSearch(request, env, user) {
  const { query, limit = 10, source } = await request.json();
  
  if (!query) {
    return jsonResponse({ error: "Query required" }, 400);
  }
  
  // Generate embedding for query
  const embeddingResponse = await env.AI.run("@cf/baai/bge-base-en-v1.5", {
    text: [query]
  });
  const queryVector = embeddingResponse.data[0];
  
  // Search with user isolation
  const filter = { user_id: user.id };
  if (source) filter.source = source;
  
  const results = await env.VECTORIZE_INDEX.query(queryVector, {
    topK: limit,
    filter,
    returnMetadata: "all"
  });
  
  return jsonResponse({
    query,
    results: results.matches.map(m => ({
      id: m.id,
      score: m.score,
      ...m.metadata
    })),
    count: results.matches.length
  });
}

async function handleListConversations(request, env, user) {
  const url = new URL(request.url);
  const source = url.searchParams.get("source");
  const limit = parseInt(url.searchParams.get("limit") || "50");
  const offset = parseInt(url.searchParams.get("offset") || "0");
  
  let query = "SELECT * FROM conversations WHERE user_id = ?";
  const params = [user.id];
  
  if (source) {
    query += " AND source = ?";
    params.push(source);
  }
  
  query += " ORDER BY created_at DESC LIMIT ? OFFSET ?";
  params.push(limit, offset);
  
  const conversations = await env.DB.prepare(query).bind(...params).all();
  const total = await env.DB.prepare(
    "SELECT COUNT(*) as count FROM conversations WHERE user_id = ?"
  ).bind(user.id).first();
  
  return jsonResponse({
    conversations: conversations.results,
    total: total.count,
    limit,
    offset
  });
}

async function handleImportConversations(request, env, user) {
  const { conversations, source } = await request.json();
  
  if (!conversations || !Array.isArray(conversations)) {
    return jsonResponse({ error: "conversations array required" }, 400);
  }
  
  let imported = 0;
  let vectorsToInsert = [];
  
  for (const conv of conversations) {
    const convId = generateId();
    
    // Insert conversation metadata
    await env.DB.prepare(`
      INSERT INTO conversations (id, user_id, source, external_id, title, created_at, turn_count)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).bind(
      convId, user.id, source || "unknown",
      conv.id || null, conv.title || "Untitled",
      conv.created_at || now(), conv.turns?.length || 0
    ).run();
    
    // Prepare vectors for each turn
    if (conv.turns) {
      for (const turn of conv.turns) {
        if (turn.content && turn.content.length > 20) {
          vectorsToInsert.push({
            id: `${convId}:${turn.id || generateId()}`,
            text: turn.content.slice(0, 2000),
            metadata: {
              user_id: user.id,
              conv_id: convId,
              source: source || "unknown",
              role: turn.role,
              title: conv.title || "Untitled"
            }
          });
        }
      }
    }
    imported++;
  }
  
  // Batch embed and insert vectors
  if (vectorsToInsert.length > 0) {
    const batchSize = 50;
    for (let i = 0; i < vectorsToInsert.length; i += batchSize) {
      const batch = vectorsToInsert.slice(i, i + batchSize);
      const texts = batch.map(v => v.text);
      
      const embeddings = await env.AI.run("@cf/baai/bge-base-en-v1.5", { text: texts });
      
      const vectors = batch.map((v, idx) => ({
        id: v.id,
        values: embeddings.data[idx],
        metadata: v.metadata
      }));
      
      await env.VECTORIZE_INDEX.upsert(vectors);
    }
  }
  
  return jsonResponse({
    success: true,
    imported,
    vectors: vectorsToInsert.length
  });
}

async function handleStats(request, env, user) {
  const convCount = await env.DB.prepare(
    "SELECT COUNT(*) as count FROM conversations WHERE user_id = ?"
  ).bind(user.id).first();
  
  const bySource = await env.DB.prepare(`
    SELECT source, COUNT(*) as count, SUM(turn_count) as turns
    FROM conversations WHERE user_id = ?
    GROUP BY source
  `).bind(user.id).all();
  
  return jsonResponse({
    conversations: convCount.count,
    by_source: bySource.results,
    plan: user.plan
  });
}

// Landing page HTML
const LANDING_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Inchive - Human-Centric AI</title>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap" rel="stylesheet">
    <style>
        :root { --bg: #0f172a; --text: #f1f5f9; --blue: #60a5fa; --orange: #fbbf24; }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Share Tech Mono', monospace; background: var(--bg); color: var(--text); min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .grid { position: fixed; inset: 0; background-image: linear-gradient(rgba(96,165,250,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(96,165,250,0.1) 1px, transparent 1px); background-size: 60px 60px; transform: perspective(1000px) rotateX(60deg) scale(2); transform-origin: center bottom; animation: grid 30s linear infinite; z-index: -1; }
        @keyframes grid { to { background-position: 0 50px; } }
        .container { text-align: center; max-width: 800px; padding: 60px 40px; background: rgba(15,23,42,0.9); border: 1px solid var(--blue); border-radius: 8px; margin: 2rem; }
        h1 { font-family: 'Orbitron', sans-serif; font-size: 3rem; color: #fff; text-shadow: 0 0 20px var(--blue); margin-bottom: 0.5rem; }
        .tagline { color: var(--blue); margin-bottom: 2rem; letter-spacing: 1px; }
        .cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 2rem; text-align: left; }
        .card { padding: 20px; border-left: 3px solid var(--blue); background: rgba(15,23,42,0.5); }
        .card h3 { color: var(--blue); font-family: 'Orbitron'; margin-bottom: 10px; font-size: 0.9rem; }
        .card p { color: #94a3b8; font-size: 0.85rem; line-height: 1.5; }
        .form { display: flex; gap: 15px; max-width: 500px; margin: 0 auto; }
        input { flex: 1; background: rgba(15,23,42,0.6); border: 1px solid rgba(96,165,250,0.3); border-radius: 4px; padding: 12px 16px; color: #fff; font-family: inherit; }
        input:focus { outline: none; border-color: var(--blue); }
        button { background: var(--blue); color: #0f172a; border: none; border-radius: 4px; padding: 12px 24px; font-family: 'Orbitron'; font-weight: 900; cursor: pointer; }
        button:hover { background: #fff; }
        .status { height: 24px; color: var(--orange); margin-top: 1rem; }
        .footer { margin-top: 2rem; font-size: 0.7rem; color: rgba(96,165,250,0.3); }
        @media (max-width: 768px) { .cards { grid-template-columns: 1fr; } .form { flex-direction: column; } }
    </style>
</head>
<body>
    <div class="grid"></div>
    <div class="container">
        <h1>INCHIVE</h1>
        <p class="tagline">Technology at the Service of the Person</p>
        <div class="cards">
            <div class="card"><h3>Subsidiarity</h3><p>Data ownership belongs to the individual.</p></div>
            <div class="card"><h3>Privacy</h3><p>Your thoughts are your own. Protected.</p></div>
            <div class="card"><h3>Human Centric</h3><p>Tools to enhance intellect, not replace agency.</p></div>
        </div>
        <form id="form" class="form">
            <input type="email" id="email" placeholder="Your Email Address" required>
            <button type="submit">Join</button>
        </form>
        <div id="status" class="status"></div>
        <div class="footer">Ad Majorem Dei Gloriam</div>
    </div>
    <script>
        document.getElementById('form').onsubmit = async (e) => {
            e.preventDefault();
            const email = document.getElementById('email').value;
            const status = document.getElementById('status');
            try {
                const res = await fetch('/api/waitlist', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }) });
                status.textContent = res.ok ? 'Welcome to the future.' : 'Error occurred.';
            } catch { status.textContent = 'Network error.'; }
        };
    </script>
</body>
</html>`;

// Main handler
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    
    // CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }
    
    // Landing page
    if (url.pathname === "/" && request.method === "GET") {
      return new Response(LANDING_HTML, { headers: { "Content-Type": "text/html" } });
    }
    
    // Waitlist (public)
    if (url.pathname === "/api/waitlist" && request.method === "POST") {
      const { email } = await request.json();
      if (email && env.WAITLIST) {
        await env.WAITLIST.put(email, JSON.stringify({ timestamp: new Date().toISOString() }));
      }
      return jsonResponse({ success: true });
    }
    
    // Auth endpoints (public)
    if (url.pathname === "/api/auth/signup" && request.method === "POST") {
      return handleSignup(request, env);
    }
    if (url.pathname === "/api/auth/login" && request.method === "POST") {
      return handleLogin(request, env);
    }
    if (url.pathname === "/api/auth/logout" && request.method === "POST") {
      return handleLogout(request, env);
    }
    
    // Protected endpoints - require auth
    const user = await getUser(request, env);
    
    if (url.pathname === "/api/auth/me" && request.method === "GET") {
      if (!user) return jsonResponse({ error: "Unauthorized" }, 401);
      return jsonResponse({ user });
    }
    
    if (url.pathname === "/api/search" && request.method === "POST") {
      if (!user) return jsonResponse({ error: "Unauthorized" }, 401);
      return handleSearch(request, env, user);
    }
    
    if (url.pathname === "/api/conversations") {
      if (!user) return jsonResponse({ error: "Unauthorized" }, 401);
      if (request.method === "GET") return handleListConversations(request, env, user);
      if (request.method === "POST") return handleImportConversations(request, env, user);
    }
    
    if (url.pathname === "/api/stats" && request.method === "GET") {
      if (!user) return jsonResponse({ error: "Unauthorized" }, 401);
      return handleStats(request, env, user);
    }
    
    return jsonResponse({ error: "Not found" }, 404);
  }
};
