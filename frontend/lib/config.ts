/**
 * Centralized API configuration for Decidr frontend.
 *
 * Supports:
 * - Production backend on Render: https://decidr-backend.onrender.com
 * - Local backend for development: http://localhost:8000
 * - Explicit override via NEXT_PUBLIC_API_URL environment variable
 */

export const PRODUCTION_API_URL = "https://decidr-backend.onrender.com";
export const LOCAL_API_URL = "http://localhost:8000";

/**
 * Normalizes an API base URL:
 * - Trims leading/trailing whitespace
 * - Strips trailing slashes
 * - Strips accidental /api suffix because FastAPI routes are mounted at the root
 */
export function normalizeApiBaseUrl(url?: string | null): string {
  if (!url) return "";
  let cleaned = url.trim().replace(/\/+$/, "");
  if (cleaned.endsWith("/api")) {
    cleaned = cleaned.slice(0, -4).replace(/\/+$/, "");
  }
  return cleaned;
}

/**
 * Determines whether a given hostname represents a local development environment.
 */
export function isLocalHostname(hostname?: string | null): boolean {
  if (!hostname) return false;
  return (
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    hostname === "0.0.0.0" ||
    hostname.endsWith(".local")
  );
}

/**
 * Resolves the effective API base URL for the current environment.
 *
 * Resolution Order:
 * 1. If running in a browser on a deployed hostname (e.g. *.vercel.app, decidr-pi.vercel.app):
 *    - If NEXT_PUBLIC_API_URL is configured and is NOT a localhost URL, use it.
 *    - Otherwise, default strictly to PRODUCTION_API_URL (prevents localhost ERR_CONNECTION_REFUSED in production).
 * 2. If running on the server or during Next.js build:
 *    - If NEXT_PUBLIC_API_URL is configured:
 *        - If NODE_ENV is production and the URL contains localhost, default to PRODUCTION_API_URL.
 *        - Otherwise use the normalized NEXT_PUBLIC_API_URL.
 *    - If NODE_ENV is production, default to PRODUCTION_API_URL.
 *    - Otherwise default to LOCAL_API_URL.
 * 3. If running in browser on localhost:
 *    - Use NEXT_PUBLIC_API_URL if configured, otherwise LOCAL_API_URL.
 */
export function getApiBaseUrl(): string {
  const envUrl = normalizeApiBaseUrl(process.env.NEXT_PUBLIC_API_URL);

  // 1. Browser runtime check
  if (typeof window !== "undefined" && window.location) {
    const isLocal = isLocalHostname(window.location.hostname);
    if (!isLocal) {
      if (envUrl && !envUrl.includes("localhost") && !envUrl.includes("127.0.0.1")) {
        return envUrl;
      }
      return PRODUCTION_API_URL;
    }
    // Browser is on localhost
    if (envUrl) {
      return envUrl;
    }
    return LOCAL_API_URL;
  }

  // 2. Server-side / Build-time check
  if (envUrl) {
    if (process.env.NODE_ENV === "production" && (envUrl.includes("localhost") || envUrl.includes("127.0.0.1"))) {
      return PRODUCTION_API_URL;
    }
    return envUrl;
  }

  if (process.env.NODE_ENV === "production") {
    return PRODUCTION_API_URL;
  }

  return LOCAL_API_URL;
}

/**
 * Constructs a fully qualified API endpoint URL.
 * Guarantees proper leading slashes and prevents duplicated slashes or /api prefixes.
 */
export function buildApiUrl(endpoint: string): string {
  const base = getApiBaseUrl();
  const path = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  return `${base}${path}`;
}

/**
 * Exported constant for backward compatibility.
 * Re-evaluated per call through buildApiUrl/getApiBaseUrl in api.ts.
 */
export const API_BASE = getApiBaseUrl();
