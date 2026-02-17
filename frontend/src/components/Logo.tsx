/**
 * Logo Component — Displays the Niv Lab logo at the top of every page.
 *
 * === WHAT IS A REACT COMPONENT? ===
 * A component is a function that returns JSX (HTML-like syntax).
 * Components are reusable — you write it once, then use it in multiple pages.
 *
 * Think of it like a Streamlit function that renders UI:
 *   Streamlit:  def render_logo(): st.image("logo.png")
 *   React:      function Logo() { return <img src="logo.png" /> }
 *
 * === KEY SYNTAX ===
 * - `export default function Logo()`: Makes this component available to import.
 * - `className="..."`: Like HTML's class="" but in React (because 'class' is reserved in JS).
 * - Tailwind classes: `py-4` = padding-y 4 units, `max-w-[250px]` = max-width 250px.
 *
 * === LOGO FILE ===
 * The logo lives in /public/niv_lab_logo.png. Files in /public/ are served as-is
 * at the root URL, so /niv_lab_logo.png works directly.
 */

export default function Logo() {
  return (
    // py-4: vertical padding, px-6: horizontal padding
    <div className="py-4 px-6">
      {/* The logo image. max-w-[250px] limits width to 250px (matches Streamlit version). */}
      {/* If the logo file doesn't exist, nothing breaks — the img just won't show. */}
      <img
        src="/niv_lab_logo.png"
        alt="Niv Taste Lab"
        className="max-w-[250px] h-auto"
      />
    </div>
  );
}
