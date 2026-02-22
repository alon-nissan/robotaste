/**
 * API Client — Centralized HTTP communication with the FastAPI backend.
 *
 * === WHAT IS THIS? ===
 * This file creates a pre-configured "axios instance" that all our React
 * components use to make HTTP requests to the FastAPI backend.
 *
 * Think of it like a universal remote control for the API:
 * instead of writing `fetch("/api/protocols")` everywhere,
 * we just write `api.get("/protocols")` — the base URL is already configured.
 *
 * === KEY CONCEPTS ===
 * - Axios: A popular HTTP client library (like Python's `requests`).
 *   It makes GET/POST/PUT/DELETE requests and returns JSON data.
 * - Instance: A pre-configured axios object with the base URL already set.
 * - Interceptors: Functions that run before/after every request (like middleware).
 *   We don't use them yet, but they're useful for adding auth tokens later.
 *
 * === USAGE IN COMPONENTS ===
 *   import { api } from '../api/client';
 *   const protocols = await api.get('/protocols');
 *   // This calls GET /api/protocols (relative to the current origin)
 */

// axios: HTTP client library (like Python's `requests` but for JavaScript)
import axios from 'axios';

// Relative base URL — works from any origin (localhost, LAN IP, etc.).
// In dev mode, Vite proxies /api to the FastAPI backend (localhost:8000).
// In production, FastAPI serves both the frontend and API on the same port.
const API_BASE_URL = '/api';

/**
 * Pre-configured axios instance.
 *
 * Every request made with `api.get(...)` or `api.post(...)` will
 * automatically prepend the base URL and set the correct headers.
 *
 * Examples:
 *   api.get('/protocols')     → GET  /api/protocols
 *   api.post('/sessions', {}) → POST /api/sessions
 */
export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',  // Tell the server we're sending JSON
  },
});
