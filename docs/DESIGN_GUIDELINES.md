# RoboTaste — Design Guidelines

Reference for building new pages in the React + Tailwind frontend.
All patterns below are extracted from the existing Moderator Setup and Monitoring pages.

---

## 1. Color Palette

| Token             | Hex       | Tailwind Class    | Usage                               |
|-------------------|-----------|-------------------|-------------------------------------|
| Primary           | `#521924` | `bg-primary`      | Buttons, active borders, accents    |
| Primary Light     | `#7a2e3d` | `bg-primary-light` | Hover states                       |
| Primary Dark      | `#3a1119` | `bg-primary-dark` | Active/pressed states               |
| Accent (Saffron)  | `#fda50f` | `bg-accent`       | Highlights, badges, warnings        |
| Accent Light      | `#ffc04d` | `bg-accent-light` | Hover state for accent elements     |
| Surface           | `#F8F9FA` | `bg-surface`      | Card backgrounds                    |
| White             | `#FFFFFF` | `bg-white`        | Page background, inputs             |
| Text Primary      | `#2C3E50` | `text-text-primary`| Headings, labels, body text        |
| Text Secondary    | `#7F8C8D` | `text-text-secondary`| Captions, hints, timestamps      |
| Border            | `#E5E7EB` | `border-border`   | Card borders, dividers              |

### Status Colors (use Tailwind defaults)
| State   | Background     | Text            | Example                        |
|---------|---------------|-----------------|--------------------------------|
| Success | `bg-green-100` | `text-green-700` | Active session badge          |
| Warning | `bg-amber-100` | `text-amber-700` | Low pump volume               |
| Error   | `bg-red-50`    | `text-red-700`  | Error messages                 |
| Info    | `bg-blue-50`   | `text-blue-700` | Information notices             |

### Color Rules
- **Never** use raw hex values in components — always use the Tailwind tokens.
- Brand primary (burgundy) is for interactive elements; don't use it for large backgrounds.
- Surface gray is for cards; page background stays white.
- Text secondary is for less important information — never for clickable elements.

---

## 2. Typography

| Element           | Tailwind Classes                           | Example                         |
|-------------------|--------------------------------------------|--------------------------------|
| Page title        | `text-2xl font-light tracking-wide`        | "Moderator Dashboard"          |
| Section heading   | `text-lg font-semibold`                    | "Select Protocol"              |
| Card label        | `text-sm font-semibold uppercase tracking-wider` | "SESSION STATUS"          |
| Body text         | `text-sm` or `text-base`                   | Description paragraphs         |
| Caption / hint    | `text-xs text-text-secondary`              | Timestamps, volume units       |
| Button text (lg)  | `text-lg font-semibold`                    | "▶ Start Session"              |
| Button text (sm)  | `text-sm font-medium`                      | "📖 User Guide"                |
| Badge / pill      | `text-sm font-medium px-3 py-1 rounded-full` | "active" status badge       |

### Font Stack
```css
font-family: system-ui, -apple-system, sans-serif;
```
Use the system default — no custom fonts needed. This keeps load times instant and matches the OS aesthetic.

---

## 3. Spacing System

All spacing uses Tailwind's 4px unit scale: `1` = 4px, `2` = 8px, `3` = 12px, `4` = 16px, `6` = 24px, `8` = 32px.

| Context                    | Class    | Pixels |
|---------------------------|----------|--------|
| Card internal padding      | `p-6`   | 24px   |
| Gap between grid columns   | `gap-6` | 24px   |
| Gap between stacked items  | `space-y-3` | 12px |
| Margin below page title    | `mb-8`  | 32px   |
| Margin below section rows  | `mb-6`  | 24px   |
| Small inline gap           | `gap-2` or `gap-3` | 8–12px |

### Spacing Rules
- Card padding is always `p-6` (24px) — consistent across all cards.
- Row-to-row gap is `gap-6` (24px).
- Within a card, item spacing is `space-y-3` (12px) for compact or `space-y-4` (16px) for spacious.
- Page title has `mb-8` (32px) to separate it from content.

---

## 4. Layout Patterns

### Page Structure
Every page uses `PageLayout` which provides:
```
┌──────────────────────────────────────────────┐
│  Logo (top-left, 80px height)                │
│                                              │
│  max-w-7xl (1280px), mx-auto, px-6, pb-8    │
│  ┌──────────────────────────────────────┐    │
│  │  Page content goes here              │    │
│  └──────────────────────────────────────┘    │
└──────────────────────────────────────────────┘
```

### Grid Layouts
- **2-column equal**: `grid grid-cols-1 md:grid-cols-2 gap-6`
- **Full-width block**: Just use a single `<div>` without grid.
- Always include `grid-cols-1` as fallback for mobile (stacks vertically).

### Responsive Breakpoint
- `md:` prefix = 768px and above (tablet/desktop).
- Below 768px, grid columns stack to single column.
- No other breakpoints needed — the app targets 13" laptops primarily.

---

## 5. Component Patterns

### Cards
The primary container for grouping related content.
```
┌─ border-border ─────────────────────────┐
│ bg-surface, rounded-xl, p-6             │
│                                         │
│ Content goes here                       │
│                                         │
└─────────────────────────────────────────┘
```
```tsx
<div className="p-6 bg-surface rounded-xl border border-border">
  {/* content */}
</div>
```

### Accent Card (left border highlight)
Used for selected items or important summaries.
```tsx
<div className="p-4 bg-surface rounded-lg border-l-4 border-primary">
  {/* content */}
</div>
```

### Primary Button (call to action)
```tsx
<button className="py-4 px-8 rounded-xl text-lg font-semibold
                   bg-primary text-white hover:bg-primary-light
                   active:bg-primary-dark shadow-md transition-all duration-200">
  ▶ Start Session
</button>
```

### Secondary Button (documentation links, minor actions)
```tsx
<button className="px-4 py-2 text-sm bg-surface text-text-primary rounded-lg
                   border border-border hover:bg-gray-100 transition-colors">
  📖 User Guide
</button>
```

### Danger Button (destructive actions)
```tsx
<button className="px-6 py-3 bg-red-600 text-white rounded-lg font-medium
                   hover:bg-red-700 active:bg-red-800 transition-colors">
  🛑 End Session
</button>
```

### Disabled Button
Add `disabled` attribute and swap classes:
```tsx
<button disabled className="bg-gray-300 text-gray-500 cursor-not-allowed">
```

### Status Badge / Pill
```tsx
<span className="px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-700">
  active
</span>
```

### Form Input
```tsx
<input
  type="text"
  className="w-full p-3 border border-border rounded-lg bg-white text-text-primary
             focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
/>
```

### Select Dropdown
```tsx
<select className="w-full p-3 border border-border rounded-lg bg-white text-text-primary
                   focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary">
  <option value="">-- Choose --</option>
</select>
```

### Progress Bar
```tsx
<div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
  <div className="h-full rounded-full bg-primary transition-all duration-500"
       style={{ width: `${percent}%` }} />
</div>
```

### Error Message
```tsx
<div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">
  Error description here
</div>
```

### Empty State
```tsx
<div className="flex items-center justify-center h-48 text-text-secondary">
  <p>No data yet. Waiting for something to happen...</p>
</div>
```

---

## 6. Data Tables

```tsx
<table className="w-full text-sm">
  <thead>
    <tr className="border-b border-border">
      <th className="text-left p-2 text-text-secondary font-medium">Column</th>
    </tr>
  </thead>
  <tbody>
    <tr className="border-b border-border/50">
      <td className="p-2">Value</td>
    </tr>
  </tbody>
</table>
```

- Headers use `text-text-secondary font-medium` (not bold).
- Row borders use `border-border/50` (50% opacity) for subtlety.
- Cell padding is `p-2`.

---

## 7. Stat / Key-Value Row

Used in status cards for label-value pairs:
```tsx
<div className="flex justify-between items-center">
  <span className="text-text-secondary">Label</span>
  <span className="text-2xl font-bold text-text-primary">Value</span>
</div>
```

---

## 8. Section Header Pattern

For card headers with uppercase labels:
```tsx
<h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">
  Section Title
</h3>
```

---

## 9. Transitions & Animation

- **All interactive elements**: `transition-colors` or `transition-all duration-200`
- **Progress bars**: `transition-all duration-500` (smooth fill changes)
- **No page transitions** — React Router switches pages instantly.
- Avoid adding animations to non-interactive elements (cards, text) — keep it professional.

---

## 10. Icon Usage

Use emoji for simple icons (keeps bundle size zero):
- `▶` Start / Play
- `🛑` Stop / End
- `📖` Documentation
- `📋` Reference / List
- `🔧` Settings / Config
- `⚠️` Warning / Alert

For future: if more icons are needed, install `lucide-react` (lightweight, tree-shakeable).

---

## 11. File Naming Conventions

| Type       | Location          | Naming             | Example                    |
|------------|-------------------|--------------------|----------------------------|
| Page       | `src/pages/`      | `PascalCase`Page   | `ModeratorSetupPage.tsx`   |
| Component  | `src/components/` | `PascalCase`       | `ProtocolSelector.tsx`     |
| Types      | `src/types/`      | `index.ts`         | Single file for all types  |
| API client | `src/api/`        | `client.ts`        | Axios instance             |
| Styles     | `src/`            | `index.css`        | Tailwind entry point       |

---

## 12. Component Composition Checklist

When building a new page:

1. **Wrap in `<PageLayout>`** — provides logo + max-width container.
2. **Add page title** — `<h1 className="text-2xl font-light text-text-primary tracking-wide mb-8">`.
3. **Use grid for multi-column** — `grid grid-cols-1 md:grid-cols-2 gap-6`.
4. **Wrap each section in a card** — `p-6 bg-surface rounded-xl border border-border`.
5. **Add section headers inside cards** — `text-lg font-semibold` or uppercase label pattern.
6. **Use the button hierarchy** — Primary for main action, Secondary for minor, Danger for destructive.
7. **Show loading/error/empty states** — every data-fetching component needs all three.

---

## 13. Accessibility Basics

- All form inputs need a visible `<label>` or accessible label.
- Buttons must have meaningful text (not just an icon).
- Color is never the only indicator — pair with text or icons (e.g., "⚠️" + red for errors).
- Focus rings on interactive elements: `focus:ring-2 focus:ring-primary`.
