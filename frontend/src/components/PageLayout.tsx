/**
 * PageLayout Component — Wraps every page with consistent structure.
 *
 * === WHAT IS THIS? ===
 * A "layout" component provides the shared structure for all pages:
 * logo at top, consistent padding, max-width container, etc.
 *
 * Instead of repeating the logo + padding in every page, we wrap
 * each page with <PageLayout>...</PageLayout>.
 *
 * === KEY CONCEPTS ===
 * - `children`: A special React prop. Whatever you put BETWEEN the opening
 *   and closing tags of a component becomes `children`.
 *
 *   Example usage:
 *     <PageLayout>
 *       <h1>Hello</h1>    ← This <h1> is the "children"
 *     </PageLayout>
 *
 * - `React.ReactNode`: The TypeScript type for "anything that can be rendered"
 *   (text, HTML elements, other components, etc.)
 *
 * - `interface Props`: Defines what properties this component accepts.
 *   Think of it like function parameters in Python.
 */

import React from 'react';
import Logo from './Logo';

// Define the props (parameters) this component accepts
interface Props {
  children: React.ReactNode;  // The page content to render inside the layout
}

export default function PageLayout({ children }: Props) {
  return (
    // min-h-screen: minimum height = full viewport height
    // bg-white: white background
    <div className="min-h-screen bg-white">
      {/* Logo at the top of every page */}
      <Logo />

      {/* Main content area */}
      {/* max-w-7xl: maximum width ~1280px (prevents content from stretching on ultra-wide screens) */}
      {/* mx-auto: center horizontally */}
      {/* px-6: horizontal padding, pb-8: bottom padding */}
      <main className="max-w-7xl mx-auto px-6 pb-8">
        {children}
      </main>
    </div>
  );
}
