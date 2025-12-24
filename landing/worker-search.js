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
  const { query, limit = 10, filter } = await request.json();
  
  if (!query) {
    return new Response(JSON.stringify({ error: "Query is required" }), {
      status: 400,
      headers: { ...corsHeaders, "Content-Type": "application/json" }
    });
  }
  
  // Generate embedding for query
  const queryEmbedding = await generateEmbedding(query, env);
  
  // Search Vectorize
  const searchOptions = {
    topK: limit,
    returnMetadata: "all"
  };
  
  if (filter) {
    searchOptions.filter = filter;
  }
  
  const results = await env.VECTORIZE_INDEX.query(queryEmbedding, searchOptions);
  
  // Format results
  const formattedResults = results.matches.map(match => ({
    id: match.id,
    score: match.score,
    ...match.metadata
  }));
  
  return new Response(JSON.stringify({
    query,
    results: formattedResults,
    count: formattedResults.length
  }), {
    headers: { ...corsHeaders, "Content-Type": "application/json" }
  });
}

/**
 * Handle embedding generation request
 */
async function handleEmbed(request, env, corsHeaders) {
  const { texts } = await request.json();
  
  if (!texts || !Array.isArray(texts)) {
    return new Response(JSON.stringify({ error: "texts array is required" }), {
      status: 400,
      headers: { ...corsHeaders, "Content-Type": "application/json" }
    });
  }
  
  // Generate embeddings for all texts
  const response = await env.AI.run("@cf/baai/bge-base-en-v1.5", {
    text: texts
  });
  
  return new Response(JSON.stringify({
    embeddings: response.data,
    dimensions: 768,
    model: "@cf/baai/bge-base-en-v1.5"
  }), {
    headers: { ...corsHeaders, "Content-Type": "application/json" }
  });
}

/**
 * Handle vector upsert request (for indexing)
 */
async function handleUpsert(request, env, corsHeaders) {
  // Simple auth check
  const authHeader = request.headers.get("Authorization");
  if (authHeader !== `Bearer ${env.API_SECRET}`) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { ...corsHeaders, "Content-Type": "application/json" }
    });
  }
  
  const { vectors } = await request.json();
  
  if (!vectors || !Array.isArray(vectors)) {
    return new Response(JSON.stringify({ error: "vectors array is required" }), {
      status: 400,
      headers: { ...corsHeaders, "Content-Type": "application/json" }
    });
  }
  
  // Format for Vectorize
  const formatted = vectors.map(v => ({
    id: v.id,
    values: v.values || v.embedding,
    metadata: v.metadata || {}
  }));
  
  // Upsert to Vectorize
  const result = await env.VECTORIZE_INDEX.upsert(formatted);
  
  return new Response(JSON.stringify({
    success: true,
    upserted: formatted.length,
    result
  }), {
    headers: { ...corsHeaders, "Content-Type": "application/json" }
  });
}

/**
 * Handle stats request
 */
async function handleStats(env, corsHeaders) {
  // Get index info from Vectorize
  const info = await env.VECTORIZE_INDEX.describe();
  
  return new Response(JSON.stringify({
    index: info.name,
    dimensions: info.config?.dimensions || 768,
    metric: info.config?.metric || "cosine",
    vectorCount: info.vectorCount || 0
  }), {
    headers: { ...corsHeaders, "Content-Type": "application/json" }
  });
}

