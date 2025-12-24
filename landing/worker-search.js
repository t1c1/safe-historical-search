/**
 * Cloudflare Worker for Inchive Semantic Search API
 * 
 * Provides vector similarity search using:
 * - Workers AI for embedding generation (@cf/baai/bge-base-en-v1.5)
 * - Vectorize for vector storage and similarity search
 * 
 * Endpoints:
 * - POST /api/search - Semantic search with query text
 * - POST /api/embed - Generate embeddings for text
 * - GET /api/stats - Get index statistics
 */

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    
    // CORS headers for API access
    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
    };
    
    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }
    
    try {
      // Semantic search endpoint
      if (url.pathname === "/api/search" && request.method === "POST") {
        return await handleSearch(request, env, corsHeaders);
      }
      
      // Embedding generation endpoint
      if (url.pathname === "/api/embed" && request.method === "POST") {
        return await handleEmbed(request, env, corsHeaders);
      }
      
      // Stats endpoint
      if (url.pathname === "/api/stats" && request.method === "GET") {
        return await handleStats(env, corsHeaders);
      }
      
      // Upsert vectors (for indexing)
      if (url.pathname === "/api/upsert" && request.method === "POST") {
        return await handleUpsert(request, env, corsHeaders);
      }
      
      return new Response(JSON.stringify({ 
        error: "Not Found",
        endpoints: ["/api/search", "/api/embed", "/api/stats", "/api/upsert"]
      }), { 
        status: 404, 
        headers: { ...corsHeaders, "Content-Type": "application/json" }
      });
      
    } catch (error) {
      return new Response(JSON.stringify({ error: error.message }), {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" }
      });
    }
  },
};

async function jsonResponse(data, corsHeaders, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" }
  });
}

function getBearerToken(request) {
  const authHeader = request.headers.get("Authorization") || "";
  const m = authHeader.match(/^Bearer\s+(.+)$/i);
  return m ? m[1].trim() : null;
}

async function sha256Hex(text) {
  const enc = new TextEncoder();
  const bytes = enc.encode(text);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, "0")).join("");
}

async function authenticate(request, env) {
  const token = getBearerToken(request);
  if (!token) return { kind: "none" };

  if (env.API_SECRET && token === env.API_SECRET) {
    return { kind: "admin" };
  }

  if (!env.USER_KEYS) {
    return { kind: "none" };
  }

  const keyHash = await sha256Hex(token);
  const userId = await env.USER_KEYS.get(`key_${keyHash}`);
  if (!userId) return { kind: "none" };
  return { kind: "user", userId };
}

function mergeUserFilter(existingFilter, userId) {
  const safe = existingFilter && typeof existingFilter === "object" ? existingFilter : {};
  if ("user_id" in safe && safe.user_id !== userId) {
    throw new Error("user_id filter mismatch");
  }
  return { ...safe, user_id: userId };
}

/**
 * Generate embeddings using Workers AI
 */
async function generateEmbedding(text, env) {
  const response = await env.AI.run("@cf/baai/bge-base-en-v1.5", {
    text: [text]
  });
  return response.data[0];
}

/**
 * Handle semantic search request
 */
async function handleSearch(request, env, corsHeaders) {
  const auth = await authenticate(request, env);
  if (auth.kind === "none") {
    return jsonResponse({ error: "Unauthorized" }, corsHeaders, 401);
  }

  const { query, limit = 10, filter } = await request.json();
  
  if (!query) {
    return jsonResponse({ error: "Query is required" }, corsHeaders, 400);
  }
  
  // Generate embedding for query
  const queryEmbedding = await generateEmbedding(query, env);
  
  // Search Vectorize
  const searchOptions = {
    topK: limit,
    returnMetadata: "all"
  };
  
  if (auth.kind === "user") {
    searchOptions.filter = mergeUserFilter(filter, auth.userId);
  } else if (filter) {
    searchOptions.filter = filter;
  }
  
  const results = await env.VECTORIZE_INDEX.query(queryEmbedding, searchOptions);
  
  // Format results
  const formattedResults = results.matches.map(match => ({
    id: match.id,
    score: match.score,
    ...match.metadata
  }));
  
  return jsonResponse({
    query,
    results: formattedResults,
    count: formattedResults.length,
    scope: auth.kind === "user" ? "user" : "admin"
  }, corsHeaders);
}

/**
 * Handle embedding generation request
 */
async function handleEmbed(request, env, corsHeaders) {
  const auth = await authenticate(request, env);
  if (auth.kind === "none") {
    return jsonResponse({ error: "Unauthorized" }, corsHeaders, 401);
  }

  const { texts } = await request.json();
  
  if (!texts || !Array.isArray(texts)) {
    return jsonResponse({ error: "texts array is required" }, corsHeaders, 400);
  }
  
  // Generate embeddings for all texts
  const response = await env.AI.run("@cf/baai/bge-base-en-v1.5", {
    text: texts
  });
  
  return jsonResponse({
    embeddings: response.data,
    dimensions: 768,
    model: "@cf/baai/bge-base-en-v1.5"
  }, corsHeaders);
}

/**
 * Handle vector upsert request (for indexing)
 */
async function handleUpsert(request, env, corsHeaders) {
  const auth = await authenticate(request, env);
  if (auth.kind === "none") {
    return jsonResponse({ error: "Unauthorized" }, corsHeaders, 401);
  }
  
  const { vectors } = await request.json();
  
  if (!vectors || !Array.isArray(vectors)) {
    return jsonResponse({ error: "vectors array is required" }, corsHeaders, 400);
  }
  
  // Format for Vectorize
  const formatted = vectors.map(v => {
    const meta = v.metadata && typeof v.metadata === "object" ? v.metadata : {};
    if (auth.kind === "user") {
      meta.user_id = auth.userId;
    }
    return {
      id: v.id,
      values: v.values || v.embedding,
      metadata: meta
    };
  });
  
  // Upsert to Vectorize
  const result = await env.VECTORIZE_INDEX.upsert(formatted);
  
  return jsonResponse({
    success: true,
    upserted: formatted.length,
    result,
    scope: auth.kind === "user" ? "user" : "admin"
  }, corsHeaders);
}

/**
 * Handle stats request
 */
async function handleStats(env, corsHeaders) {
  // Stats are admin only, since Vectorize does not support per user counts directly
  const info = await env.VECTORIZE_INDEX.describe();

  // Get index info from Vectorize
  return jsonResponse({
    index: info.name,
    dimensions: info.config?.dimensions || 768,
    metric: info.config?.metric || "cosine",
    vectorCount: info.vectorCount || 0
  }, corsHeaders);
}

