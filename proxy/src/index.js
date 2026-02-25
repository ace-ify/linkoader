/**
 * Linkoader Fetch Proxy — Cloudflare Worker
 *
 * Receives a request with target URL + headers, fetches it from
 * Cloudflare's trusted IP range, and returns the response.
 * Protected by a shared secret so only our backend can use it.
 */

export default {
  async fetch(request, env) {
    // Only accept POST
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204 });
    }

    if (request.method !== "POST") {
      return Response.json({ error: "POST only" }, { status: 405 });
    }

    // Verify secret
    const secret = request.headers.get("X-Proxy-Secret");
    if (!secret || secret !== env.PROXY_SECRET) {
      return Response.json({ error: "unauthorized" }, { status: 401 });
    }

    // Parse request body
    let body;
    try {
      body = await request.json();
    } catch {
      return Response.json({ error: "invalid JSON" }, { status: 400 });
    }

    const { url, method = "GET", headers = {}, payload } = body;

    if (!url) {
      return Response.json({ error: "url required" }, { status: 400 });
    }

    // Build fetch options
    const fetchOpts = {
      method,
      headers: new Headers(headers),
      redirect: "follow",
    };

    // Add body for POST/PUT requests
    if (payload && (method === "POST" || method === "PUT" || method === "PATCH")) {
      fetchOpts.body = typeof payload === "string" ? payload : JSON.stringify(payload);
    }

    // Make the request from Cloudflare's IP
    try {
      const resp = await fetch(url, fetchOpts);

      // Read response body
      const responseBody = await resp.text();

      // Return the response with original status and headers
      const responseHeaders = new Headers({
        "Content-Type": resp.headers.get("Content-Type") || "text/plain",
        "X-Original-Status": resp.status.toString(),
      });

      return new Response(responseBody, {
        status: resp.status,
        headers: responseHeaders,
      });
    } catch (err) {
      return Response.json(
        { error: "fetch_failed", message: err.message },
        { status: 502 }
      );
    }
  },
};
