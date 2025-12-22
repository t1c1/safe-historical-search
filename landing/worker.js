/**
 * Cloudflare Worker for Inchive Landing & Waitlist
 * Serves the static HTML on GET and handles API on POST
 */

// Embed the HTML directly for single-file deployment simplicity
const HTML_CONTENT = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Inchive - Human-Centric AI</title>
    <meta name="description" content="Inchive is a personal AI built on the principles of Subsidiarity and Privacy. Your data stays local. You retain ownership. Technology serving the human person.">
    <meta name="keywords" content="Catholic Social Teaching AI, Subsidiarity, Privacy, Local AI, Personal Knowledge">
    <meta property="og:title" content="Inchive - Technology for the Human Person">
    <meta property="og:description" content="A personal AI OS that respects your dignity. Local-first, privacy-focused, and built to serve you, not use you.">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://inchive.com">
    <meta property="og:image" content="https://inchive.com/og-image.png">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Inchive - Your Personal AI OS">
    <meta name="twitter:description" content="Your life's work, unified. The operating system for your mind.">
    <link rel="canonical" href="https://inchive.com">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #000000;
            --text-color: #c5c6c7;
            --neon-blue: #4dabf7; /* Soft Blue */
            --neon-orange: #ffd43b; /* Gold/Yellow */
            --grid-line: rgba(77, 171, 247, 0.1);
            --glass-bg: rgba(15, 20, 25, 0.85);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

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

        /* THE GRID - Toned down for more "Order/Creation" vibe */
        .grid-floor {
            position: absolute;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background-image: 
                linear-gradient(var(--grid-line) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
            background-size: 50px 50px;
            background-position: center bottom;
            transform: perspective(1000px) rotateX(60deg) scale(2);
            transform-origin: center bottom;
            z-index: -2;
            animation: moveGrid 20s linear infinite;
            mask-image: linear-gradient(to top, rgba(0,0,0,1) 0%, rgba(0,0,0,0) 80%);
            -webkit-mask-image: linear-gradient(to top, rgba(0,0,0,1) 0%, rgba(0,0,0,0) 80%);
        }

        @keyframes moveGrid {
            0% { background-position: center 0px; }
            100% { background-position: center 50px; }
        }

        /* Horizon Glow */
        .horizon {
            position: absolute;
            bottom: 0;
            width: 100%;
            height: 60%;
            background: radial-gradient(ellipse at bottom, rgba(77, 171, 247, 0.1) 0%, transparent 70%);
            z-index: -1;
            pointer-events: none;
        }

        /* Container */
        .container {
            text-align: center;
            max-width: 800px;
            padding: 60px 40px;
            z-index: 10;
            background: var(--glass-bg);
            border: 1px solid var(--neon-blue);
            box-shadow: 
                0 0 30px rgba(0, 0, 0, 0.5),
                inset 0 0 20px rgba(77, 171, 247, 0.05);
            position: relative;
            border-radius: 8px;
            margin: 2rem;
        }

        /* Corner accents - Removed "aggressive" angles for stability */
        
        h1 {
            font-family: 'Orbitron', sans-serif;
            font-size: 4rem;
            font-weight: 700;
            letter-spacing: 4px;
            margin-bottom: 0.5rem;
            text-transform: uppercase;
            color: #fff;
            text-shadow: 0 0 15px rgba(77, 171, 247, 0.5);
        }

        p.subtitle {
            font-size: 1.2rem;
            color: var(--neon-blue);
            margin-bottom: 2rem;
            font-weight: 400;
            letter-spacing: 1px;
        }

        .principles {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 20px;
            margin-bottom: 3rem;
            text-align: left;
        }
        
        .principle-card {
            padding: 15px;
            border-left: 2px solid var(--neon-orange);
            background: rgba(255, 255, 255, 0.03);
        }

        .principle-card h3 {
            color: var(--neon-orange);
            font-family: 'Orbitron', sans-serif;
            margin-bottom: 8px;
            font-size: 0.9rem;
            letter-spacing: 1px;
        }

        .principle-card p {
            font-size: 0.85rem;
            line-height: 1.4;
            color: #aaa;
        }

        /* Form */
        .input-group {
            display: flex;
            gap: 15px;
            margin-bottom: 1.5rem;
            max-width: 500px;
            margin-left: auto;
            margin-right: auto;
        }

        input[type="email"] {
            flex: 1;
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid #444;
            border-radius: 4px;
            padding: 16px 20px;
            color: #fff;
            font-family: 'Share Tech Mono', monospace;
            font-size: 1rem;
            outline: none;
            transition: all 0.3s ease;
        }

        input[type="email"]:focus {
            border-color: var(--neon-blue);
            box-shadow: 0 0 10px rgba(77, 171, 247, 0.1);
        }

        button {
            background: var(--neon-blue);
            color: #000;
            border: none;
            border-radius: 4px;
            padding: 16px 32px;
            font-family: 'Orbitron', sans-serif;
            font-size: 0.9rem;
            font-weight: 700;
            cursor: pointer;
            text-transform: uppercase;
            letter-spacing: 1px;
            transition: all 0.2s;
        }

        button:hover {
            background: #fff;
            box-shadow: 0 0 15px rgba(255, 255, 255, 0.3);
        }


        button:active {
            transform: scale(0.98);
        }

        .status {
            height: 24px;
            font-size: 1rem;
            color: var(--neon-orange);
            opacity: 0;
            transition: opacity 0.3s;
            text-shadow: 0 0 8px rgba(255, 170, 0, 0.6);
        }

        .status.visible {
            opacity: 1;
        }

        /* Footer */
        .footer {
            margin-top: 3rem;
            font-size: 0.8rem;
            color: rgba(0, 255, 255, 0.4);
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        
        /* Floating Data Particles */
        .particle {
            position: absolute;
            width: 2px;
            height: 2px;
            background: var(--neon-blue);
            box-shadow: 0 0 4px var(--neon-blue);
            z-index: -1;
            animation: floatUp linear infinite;
        }
        
        @keyframes floatUp {
            0% { transform: translateY(100vh); opacity: 0; }
            50% { opacity: 0.8; }
            100% { transform: translateY(-10vh); opacity: 0; }
        }

    </style>
</head>
<body>

    <div class="grid-floor"></div>
    <div class="horizon"></div>
    
    <!-- JS will generate particles -->
    <div id="particles"></div>

    <div class="container">
        <h1>Inchive</h1>
        <p class="subtitle">Technology at the Service of the Person</p>

        <div class="principles">
            <div class="principle-card">
                <h3>Subsidiarity</h3>
                <p>Data ownership belongs to the individual, not the collective cloud.</p>
            </div>
            <div class="principle-card">
                <h3>Privacy</h3>
                <p>Your thoughts are your own. We build walls to protect your dignity.</p>
            </div>
            <div class="principle-card">
                <h3>Human Centric</h3>
                <p>Tools designed to enhance your intellect, not replace your agency.</p>
            </div>
        </div>

        <form id="waitlistForm">
            <div class="input-group">
                <input type="email" id="email" placeholder="Your Email Address" required autocomplete="email">
                <button type="submit">Join</button>
            </div>
            <div id="status" class="status">Your data. Your control. Welcome home.</div>
        </form>
    </div>

    <div class="footer">
        &copy; 2025 Inchive System &bull; Ad Majorem Dei Gloriam
    </div>

    <script>
        // Generate Particles
        const particleContainer = document.getElementById('particles');
        for(let i=0; i<30; i++) {
            const p = document.createElement('div');
            p.className = 'particle';
            p.style.left = Math.random() * 100 + 'vw';
            p.style.animationDuration = (Math.random() * 5 + 3) + 's';
            p.style.animationDelay = (Math.random() * 5) + 's';
            particleContainer.appendChild(p);
        }

        const form = document.getElementById('waitlistForm');
        const status = document.getElementById('status');
        const btn = form.querySelector('button');

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('email').value;
            
            // Set Loading State
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
                } else {
                    const data = await response.json();
                    throw new Error(data.error || 'ACCESS DENIED');
                }
            } catch (err) {
                console.error(err);
                status.textContent = "SYSTEM ERROR: " + err.message;
                status.style.color = "#ff4444";
                status.classList.add('visible');
            } finally {
                btn.textContent = originalText;
                btn.disabled = false;
            }
        });
    </script>
</body>
</html>`;

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Serve HTML on root
    if (url.pathname === "/" && request.method === "GET") {
      return new Response(HTML_CONTENT, {
        headers: { "Content-Type": "text/html" },
      });
    }

    // Handle API
    if (url.pathname === "/api/join" && request.method === "POST") {
      return handleJoin(request, env);
    }

    // 404 for anything else
    return new Response("Not Found", { status: 404 });
  },
};

async function handleJoin(request, env) {
  try {
    const { email } = await request.json();

    if (!email || !email.includes("@")) {
      return new Response(JSON.stringify({ error: "Invalid email" }), {
        status: 400,
        headers: { "Content-Type": "application/json" }
      });
    }

    // Metadata
    const metadata = {
      timestamp: new Date().toISOString(),
      ip: request.headers.get("CF-Connecting-IP"),
      userAgent: request.headers.get("User-Agent")
    };

    // Store in KV
    if (env.INCHIVE_WAITLIST) {
        // CONFIRMATION LOGIC:
        // We ensure the email is written to the binding.
        await env.INCHIVE_WAITLIST.put(email, JSON.stringify(metadata));
    } else {
        // Fallback for local dev without bindings
        console.log("KV not bound, would save:", email, metadata);
    }

    return new Response(JSON.stringify({ 
        success: true, 
        message: "Email confirmed in storage" 
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
}

