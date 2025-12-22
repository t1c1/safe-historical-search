/**
 * Cloudflare Worker for Inchive Landing & Waitlist + Admin
 * Serves static HTML, handles API, and provides basic Admin Auth
 */

// -----------------------------------------------------------------------------
// HTML TEMPLATES
// -----------------------------------------------------------------------------

const STYLES = `
    <style>
        :root {
            --bg-color: #0f172a;           /* Slate 900 */
            --text-color: #f1f5f9;         /* Slate 100 */
            --neon-blue: #60a5fa;          /* Blue 400 */
            --neon-orange: #fbbf24;        /* Amber 400 */
            --grid-line: rgba(96, 165, 250, 0.15);
            --glass-bg: rgba(15, 23, 42, 0.75);
            --danger: #ef4444;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; -webkit-font-smoothing: antialiased; }
        
        body {
            font-family: 'Share Tech Mono', monospace;
            background-color: var(--bg-color);
            color: var(--text-color);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            overflow-x: hidden;
            position: relative;
        }

        /* GRID BACKGROUND */
        .grid-floor {
            position: absolute;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background-image: 
                linear-gradient(var(--grid-line) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
            background-size: 60px 60px;
            background-position: center bottom;
            transform: perspective(1000px) rotateX(60deg) scale(2);
            transform-origin: center bottom;
            z-index: -2;
            animation: moveGrid 30s linear infinite;
            mask-image: linear-gradient(to top, rgba(15, 23, 42, 1) 0%, rgba(15, 23, 42, 0) 90%);
            -webkit-mask-image: linear-gradient(to top, rgba(15, 23, 42, 1) 0%, rgba(15, 23, 42, 0) 90%);
        }
        @keyframes moveGrid { 0% { background-position: center 0px; } 100% { background-position: center 50px; } }

        .horizon {
            position: absolute; bottom: 0; width: 100%; height: 60%;
            background: radial-gradient(ellipse at bottom, rgba(96, 165, 250, 0.2) 0%, transparent 70%);
            z-index: -1; pointer-events: none;
        }

        /* CONTAINER & TYPOGRAPHY */
        .container {
            text-align: center; max-width: 800px; padding: 60px 40px; z-index: 10;
            background: rgba(15, 23, 42, 0.85); border: 1px solid var(--neon-blue);
            box-shadow: 0 0 30px rgba(96, 165, 250, 0.15), inset 0 0 20px rgba(96, 165, 250, 0.05);
            position: relative; border-radius: 8px; margin: 2rem; backdrop-filter: blur(5px);
        }

        h1 {
            font-family: 'Orbitron', sans-serif; font-size: 3rem; font-weight: 700;
            letter-spacing: 4px; margin-bottom: 0.5rem; text-transform: uppercase; color: #fff;
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px rgba(96, 165, 250, 0.5);
        }

        /* FORM ELEMENTS */
        input {
            background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(96, 165, 250, 0.3);
            border-radius: 4px; padding: 12px 16px; color: #fff;
            font-family: 'Share Tech Mono', monospace; font-size: 1rem; outline: none;
            transition: all 0.3s ease; width: 100%; margin-bottom: 1rem;
        }
        input:focus { border-color: var(--neon-blue); box-shadow: 0 0 15px rgba(96, 165, 250, 0.2); }

        button {
            background: var(--neon-blue); color: #0f172a; border: none; border-radius: 4px;
            padding: 12px 24px; font-family: 'Orbitron', sans-serif; font-weight: 900;
            cursor: pointer; text-transform: uppercase; letter-spacing: 1px; transition: all 0.2s;
        }
        button:hover { background: #fff; transform: translateY(-1px); }

        /* TABLE (Admin) */
        table { width: 100%; border-collapse: collapse; margin-top: 20px; text-align: left; }
        th, td { padding: 12px; border-bottom: 1px solid rgba(96, 165, 250, 0.2); }
        th { color: var(--neon-blue); font-family: 'Orbitron', sans-serif; font-size: 0.8rem; }
        td { font-size: 0.9rem; color: #cbd5e1; }
        tr:hover td { background: rgba(96, 165, 250, 0.05); }

        .logout { position: absolute; top: 20px; right: 20px; font-size: 0.8rem; color: #ef4444; text-decoration: none; border: 1px solid #ef4444; padding: 5px 10px; border-radius: 4px; }
        .logout:hover { background: #ef4444; color: white; }
    </style>
`;

const LANDING_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Inchive - Human-Centric AI</title>
    <meta name="description" content="Inchive is a personal AI built on the principles of Subsidiarity and Privacy.">
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap" rel="stylesheet">
    ${STYLES}
    <style>
        .input-group { display: flex; gap: 15px; margin-bottom: 1.5rem; max-width: 500px; margin: 0 auto 1.5rem; }
        input[type="email"] { margin-bottom: 0; }
        
        .principles { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-bottom: 3rem; text-align: left; }
        .principle-card { padding: 20px; border-left: 3px solid var(--neon-blue); background: rgba(15, 23, 42, 0.4); border-radius: 0 4px 4px 0; transition: all 0.3s ease; }
        .principle-card:hover { background: rgba(96, 165, 250, 0.1); transform: translateX(5px); }
        .principle-card h3 { color: var(--neon-blue); font-family: 'Orbitron', sans-serif; margin-bottom: 10px; font-size: 1rem; }
        .principle-card p { font-size: 0.9rem; line-height: 1.5; color: #94a3b8; }

        @media (max-width: 768px) {
            .principles { grid-template-columns: 1fr; }
            .input-group { flex-direction: column; }
            button { width: 100%; }
        }
        
        .status { height: 24px; color: var(--neon-orange); opacity: 0; transition: opacity 0.3s; margin-top: 1rem; }
        .status.visible { opacity: 1; }
        
        .footer { margin-top: 3rem; font-size: 0.7rem; color: rgba(96, 165, 250, 0.15); text-transform: uppercase; cursor: default; transition: 0.5s; }
        .footer:hover { color: var(--neon-orange); text-shadow: 0 0 10px var(--neon-orange); opacity: 1; }
    </style>
</head>
<body>
    <div class="grid-floor"></div>
    <div class="horizon"></div>
    <div class="container">
        <h1>Inchive</h1>
        <p style="color:var(--neon-blue); margin-bottom:2rem; letter-spacing:1px;">Technology at the Service of the Person</p>

        <div class="principles">
            <div class="principle-card"><h3>Subsidiarity</h3><p>Data ownership belongs to the individual.</p></div>
            <div class="principle-card"><h3>Privacy</h3><p>Your thoughts are your own. Protected.</p></div>
            <div class="principle-card"><h3>Human Centric</h3><p>Tools to enhance intellect, not replace agency.</p></div>
        </div>

        <form id="waitlistForm">
            <div class="input-group">
                <input type="email" id="email" placeholder="Your Email Address" required autocomplete="email">
                <button type="submit">Join</button>
            </div>
            <div id="status" class="status">Your data. Your control. Welcome home.</div>
        </form>
    </div>
    <div class="footer">Ad Majorem Dei Gloriam</div>

    <script>
        const form = document.getElementById('waitlistForm');
        const status = document.getElementById('status');
        const btn = form.querySelector('button');

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('email').value;
            const originalText = btn.textContent;
            btn.textContent = "Verifying...";
            btn.disabled = true;

            try {
                const response = await fetch('/api/join', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email })
                });
                if (response.ok) {
                    status.textContent = "Confirmed. You have been added to the secure registry.";
                    status.classList.add('visible');
                    form.reset();
                } else throw new Error('ACCESS DENIED');
            } catch (err) {
                status.textContent = "SYSTEM ERROR: " + err.message;
                status.style.color = "#ef4444";
                status.classList.add('visible');
            } finally {
                btn.textContent = originalText;
                btn.disabled = false;
            }
        });
    </script>
</body>
</html>`;

const LOGIN_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>System Login</title>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Share+Tech+Mono&display=swap" rel="stylesheet">
    ${STYLES}
</head>
<body>
    <div class="grid-floor"></div>
    <div class="horizon"></div>
    <div class="container" style="max-width: 400px;">
        <h1>System Access</h1>
        <form action="/api/login" method="POST">
            <input type="password" name="password" placeholder="ENTER ACCESS CODE" required autofocus>
            <button type="submit" style="width:100%">Authenticate</button>
        </form>
    </div>
</body>
</html>`;

function getAdminHtml(emails) {
    const rows = emails.map(e => {
        const meta = e.metadata ? JSON.parse(e.metadata) : {};
        return `<tr>
            <td>${e.email}</td>
            <td>${meta.timestamp ? new Date(meta.timestamp).toLocaleDateString() : '-'}</td>
            <td>${meta.ip || '-'}</td>
        </tr>`;
    }).join('');

    return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Console</title>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Share+Tech+Mono&display=swap" rel="stylesheet">
    ${STYLES}
    <style>.container { max-width: 1000px; }</style>
</head>
<body>
    <div class="grid-floor"></div>
    <div class="horizon"></div>
    <a href="/logout" class="logout">TERMINATE SESSION</a>
    
    <div class="container">
        <h1>Waitlist Data</h1>
        <p>Total Entries: <span style="color:var(--neon-orange)">${emails.length}</span></p>
        
        <table>
            <thead>
                <tr>
                    <th>Email</th>
                    <th>Date</th>
                    <th>IP Origin</th>
                </tr>
            </thead>
            <tbody>
                ${rows}
            </tbody>
        </table>
    </div>
</body>
</html>`;
}

// -----------------------------------------------------------------------------
// MAIN WORKER LOGIC
// -----------------------------------------------------------------------------

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // --- PUBLIC ROUTES ---

    if (url.pathname === "/" && request.method === "GET") {
      return new Response(LANDING_HTML, { headers: { "Content-Type": "text/html" } });
    }

    if (url.pathname === "/api/join" && request.method === "POST") {
      return handleJoin(request, env);
    }

    // --- ADMIN ROUTES ---

    if (url.pathname === "/admin") {
        if (!await isAuthenticated(request, env)) {
            return new Response(LOGIN_HTML, { headers: { "Content-Type": "text/html" } });
        }
        return handleAdminDashboard(env);
    }

    if (url.pathname === "/api/login" && request.method === "POST") {
        return handleLogin(request, env);
    }

    if (url.pathname === "/logout") {
        return new Response("Logged out", {
            status: 302,
            headers: { 
                "Location": "/",
                "Set-Cookie": "auth=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT"
            }
        });
    }

    return new Response("Not Found", { status: 404 });
  },
};

// -----------------------------------------------------------------------------
// HANDLERS
// -----------------------------------------------------------------------------

async function handleJoin(request, env) {
  try {
    const { email } = await request.json();
    if (!email || !email.includes("@")) throw new Error("Invalid email");

    const metadata = {
      timestamp: new Date().toISOString(),
      ip: request.headers.get("CF-Connecting-IP"),
      userAgent: request.headers.get("User-Agent")
    };

    if (env.INCHIVE_WAITLIST) {
        await env.INCHIVE_WAITLIST.put(email, JSON.stringify(metadata));
    }

    return new Response(JSON.stringify({ success: true }), {
      headers: { "Content-Type": "application/json" }
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), { status: 500 });
  }
}

async function handleLogin(request, env) {
    const formData = await request.formData();
    const password = formData.get("password");
    
    // Simple check against env var
    if (password === env.ADMIN_PASSWORD) {
        // In a real app, use a proper session token or JWT. 
        // For this simple deployment, we'll just set a basic cookie.
        const headers = new Headers();
        headers.append("Set-Cookie", `auth=${env.ADMIN_PASSWORD}; Path=/; HttpOnly; SameSite=Strict; Max-Age=3600`);
        headers.append("Location", "/admin");
        
        return new Response("Redirecting...", { status: 302, headers });
    }

    return new Response("Access Denied", { status: 403 });
}

async function handleAdminDashboard(env) {
    if (!env.INCHIVE_WAITLIST) {
        return new Response("KV Not Bound", { status: 500 });
    }

    // List keys (emails)
    const list = await env.INCHIVE_WAITLIST.list({ limit: 100 });
    
    // Fetch values in parallel (for metadata)
    const emails = await Promise.all(list.keys.map(async (k) => {
        const metadata = await env.INCHIVE_WAITLIST.get(k.name);
        return { email: k.name, metadata };
    }));

    return new Response(getAdminHtml(emails), {
        headers: { "Content-Type": "text/html" }
    });
}

async function isAuthenticated(request, env) {
    const cookieHeader = request.headers.get("Cookie");
    if (!cookieHeader) return false;
    
    // Very basic cookie parsing
    const cookies = Object.fromEntries(cookieHeader.split('; ').map(x => x.split('=')));
    return cookies.auth === env.ADMIN_PASSWORD;
}
