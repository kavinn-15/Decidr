import test from "node:test";
import assert from "node:assert/strict";
import {
  normalizeApiBaseUrl,
  isLocalHostname,
  getApiBaseUrl,
  buildApiUrl,
  PRODUCTION_API_URL,
  LOCAL_API_URL,
} from "./config.ts";

test("normalizeApiBaseUrl strips trailing slashes and redundant /api suffixes", () => {
  assert.equal(normalizeApiBaseUrl("http://localhost:8000/"), "http://localhost:8000");
  assert.equal(normalizeApiBaseUrl("http://localhost:8000///"), "http://localhost:8000");
  assert.equal(normalizeApiBaseUrl("https://decidr-backend.onrender.com/api"), "https://decidr-backend.onrender.com");
  assert.equal(normalizeApiBaseUrl("https://decidr-backend.onrender.com/api/"), "https://decidr-backend.onrender.com");
  assert.equal(normalizeApiBaseUrl(""), "");
  assert.equal(normalizeApiBaseUrl(null), "");
  assert.equal(normalizeApiBaseUrl(undefined), "");
});

test("isLocalHostname correctly identifies local development hosts", () => {
  assert.equal(isLocalHostname("localhost"), true);
  assert.equal(isLocalHostname("127.0.0.1"), true);
  assert.equal(isLocalHostname("0.0.0.0"), true);
  assert.equal(isLocalHostname("my-machine.local"), true);
  assert.equal(isLocalHostname("decidr-pi.vercel.app"), false);
  assert.equal(isLocalHostname("decidr.vercel.app"), false);
  assert.equal(isLocalHostname("decidr-backend.onrender.com"), false);
  assert.equal(isLocalHostname(""), false);
});

test("buildApiUrl handles missing leading slashes and paths cleanly", () => {
  const url1 = buildApiUrl("/auth/status");
  assert.match(url1, /\/auth\/status$/);

  const url2 = buildApiUrl("auth/register");
  assert.match(url2, /\/auth\/register$/);

  const url3 = buildApiUrl("/meetings/1/review");
  assert.match(url3, /\/meetings\/1\/review$/);
});

test("browser runtime on decidr-pi.vercel.app routes to Render backend even if env was localhost", () => {
  const origWindow = (globalThis as unknown as { window?: unknown }).window;
  const origApiUrl = process.env.NEXT_PUBLIC_API_URL;
  try {
    (globalThis as unknown as { window: unknown }).window = {
      location: {
        hostname: "decidr-pi.vercel.app",
      },
    };
    process.env.NEXT_PUBLIC_API_URL = "http://localhost:8000";

    assert.equal(getApiBaseUrl(), PRODUCTION_API_URL);
    assert.equal(buildApiUrl("/auth/status"), `${PRODUCTION_API_URL}/auth/status`);
    assert.equal(buildApiUrl("/auth/register"), `${PRODUCTION_API_URL}/auth/register`);
    assert.equal(buildApiUrl("/auth/login"), `${PRODUCTION_API_URL}/auth/login`);
  } finally {
    if (origWindow !== undefined) {
      (globalThis as unknown as { window: unknown }).window = origWindow;
    } else {
      delete (globalThis as unknown as { window?: unknown }).window;
    }
    if (origApiUrl !== undefined) {
      process.env.NEXT_PUBLIC_API_URL = origApiUrl;
    } else {
      delete process.env.NEXT_PUBLIC_API_URL;
    }
  }
});

test("browser runtime on localhost routes to local backend", () => {
  const origWindow = (globalThis as unknown as { window?: unknown }).window;
  const origApiUrl = process.env.NEXT_PUBLIC_API_URL;
  try {
    (globalThis as unknown as { window: unknown }).window = {
      location: {
        hostname: "localhost",
      },
    };
    delete process.env.NEXT_PUBLIC_API_URL;

    assert.equal(getApiBaseUrl(), LOCAL_API_URL);
    assert.equal(buildApiUrl("/auth/status"), `${LOCAL_API_URL}/auth/status`);
  } finally {
    if (origWindow !== undefined) {
      (globalThis as unknown as { window: unknown }).window = origWindow;
    } else {
      delete (globalThis as unknown as { window?: unknown }).window;
    }
    if (origApiUrl !== undefined) {
      process.env.NEXT_PUBLIC_API_URL = origApiUrl;
    } else {
      delete process.env.NEXT_PUBLIC_API_URL;
    }
  }
});

test("production resolution defaults to Render backend in production NODE_ENV", () => {
  const envMap = process.env as Record<string, string | undefined>;
  const origNodeEnv = envMap.NODE_ENV;
  const origApiUrl = envMap.NEXT_PUBLIC_API_URL;
  try {
    envMap.NODE_ENV = "production";
    delete envMap.NEXT_PUBLIC_API_URL;

    assert.equal(getApiBaseUrl(), PRODUCTION_API_URL);
    assert.equal(buildApiUrl("/auth/login"), `${PRODUCTION_API_URL}/auth/login`);
  } finally {
    envMap.NODE_ENV = origNodeEnv;
    if (origApiUrl !== undefined) {
      envMap.NEXT_PUBLIC_API_URL = origApiUrl;
    } else {
      delete envMap.NEXT_PUBLIC_API_URL;
    }
  }
});

test("production ignores accidental localhost NEXT_PUBLIC_API_URL during production builds", () => {
  const envMap = process.env as Record<string, string | undefined>;
  const origNodeEnv = envMap.NODE_ENV;
  const origApiUrl = envMap.NEXT_PUBLIC_API_URL;
  try {
    envMap.NODE_ENV = "production";
    envMap.NEXT_PUBLIC_API_URL = "http://localhost:8000";

    assert.equal(getApiBaseUrl(), PRODUCTION_API_URL);
  } finally {
    envMap.NODE_ENV = origNodeEnv;
    if (origApiUrl !== undefined) {
      envMap.NEXT_PUBLIC_API_URL = origApiUrl;
    } else {
      delete envMap.NEXT_PUBLIC_API_URL;
    }
  }
});

test("development environment defaults to LOCAL_API_URL when unset", () => {
  const envMap = process.env as Record<string, string | undefined>;
  const origNodeEnv = envMap.NODE_ENV;
  const origApiUrl = envMap.NEXT_PUBLIC_API_URL;
  try {
    envMap.NODE_ENV = "development";
    delete envMap.NEXT_PUBLIC_API_URL;

    assert.equal(getApiBaseUrl(), LOCAL_API_URL);
  } finally {
    envMap.NODE_ENV = origNodeEnv;
    if (origApiUrl !== undefined) {
      envMap.NEXT_PUBLIC_API_URL = origApiUrl;
    } else {
      delete envMap.NEXT_PUBLIC_API_URL;
    }
  }
});
