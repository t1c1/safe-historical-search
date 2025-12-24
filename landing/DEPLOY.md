# Deployment Guide for Inchive Landing Page

This guide will help you deploy the landing page to Cloudflare Workers. It acts as both the frontend (serving the HTML) and the backend (storing emails).

## Prerequisites
- Node.js installed (you have v20)
- `npm install -g wrangler` (you have v3)

## Steps

### 1. Login to Cloudflare
Run this command and authorize in the browser:
```bash
wrangler login
```

### 2. Create the Database (KV Namespace)
Run this command to create the storage for emails:
```bash
wrangler kv:namespace create INCHIVE_WAITLIST
```

It will output something like:
```
{ binding = "INCHIVE_WAITLIST", id = "e8f9..." }
```

**Copy that ID.**

### 3. Update Configuration
Open `landing/wrangler.toml` and uncomment the `kv_namespaces` section, replacing `REPLACE_ME_WITH_ID` with the ID you just copied.

Example:
```toml
kv_namespaces = [
  { binding = "INCHIVE_WAITLIST", id = "e8f923485720934857..." }
]
```

### 4. Deploy
Run the deploy command from the `landing` directory:
```bash
cd landing
wrangler deploy
```

### 5. Done!
Wrangler will print your live URL (e.g., `https://inchive-landing.username.workers.dev`).
Visit that URL to see your site live.

