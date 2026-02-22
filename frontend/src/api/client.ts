/**
 * API Client — Centralized HTTP communication with the FastAPI backend.
 *
 * === WHAT IS THIS? ===
 * This file creates a pre-configured "axios instance" that all our React
 * components use to make HTTP requests to the FastAPI backend.
 *
 * Think of it like a universal remote control for the API:
 * instead of writing `fetch("http://localhost:8000/api/protocols")` everywhere,
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
 *   // This calls GET http://localhost:8000/api/protocols
 */

// axios: HTTP client library (like Python's `requests` but for JavaScript)
import axios from 'axios';

// The base URL for all API requests.
// During development, FastAPI runs on port 8000.
// In production, this would be your deployed server URL.
const API_BASE_URL = 'http://localhost:8000/api';

/**
 * Pre-configured axios instance.
 *
 * Every request made with `api.get(...)` or `api.post(...)` will
 * automatically prepend the base URL and set the correct headers.
 *
 * Examples:
 *   api.get('/protocols')     → GET  http://localhost:8000/api/protocols
 *   api.post('/sessions', {}) → POST http://localhost:8000/api/sessions
 */
export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',  // Tell the server we're sending JSON
  },
});
