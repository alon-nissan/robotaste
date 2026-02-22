/**
 * Vite Configuration File
 *
 * === WHAT IS THIS? ===
 * Vite is the build tool that compiles your React + TypeScript code
 * and serves it during development. This file configures how it works.
 *
 * Think of it like Streamlit's config.toml but for the React build system.
 *
 * Plugins:
 * - react(): Enables React JSX syntax and hot-reload
 * - tailwindcss(): Processes Tailwind CSS utility classes into real CSS
 */

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),          // Enables React support (JSX, Fast Refresh)
    tailwindcss(),    // Processes Tailwind CSS classes
  ],
})
