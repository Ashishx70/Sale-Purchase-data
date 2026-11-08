# Professional Glassmorphism & Zero Cartoon Emoji UI Rules

## CRITICAL UI & DESIGN RULE: Professional Glassmorphism & Zero Cartoon Emojis

Whenever ANY new popup, modal, card, banner, alert, button, badge, or UI component is created or modified in this project:

### 1. Zero Cartoon Emojis (Strictly Forbidden)
- Under no circumstances should cartoon emojis (such as 🗑️, 🚀, ⚡, 🎉, ⚠️, 📦, 🟢, 🔴, etc.) be used for buttons, modal headers, icons, or action elements.
- ONLY use professional, clean SVG vector icons (Lucide / Feather / Heroicons style outline or duo-tone SVGs with clean stroke paths, precise sizing e.g. 16x16, 18x18, 20x20, with proper `stroke`, `stroke-width="2"` or `stroke-width="2.2"`, `stroke-linecap="round"`).

### 2. Transparent Glassmorphism Design for All Buttons & Modals
- All buttons, badges, modals, and interactive surfaces MUST use a sleek, modern, professional transparent glass (frosted glass) aesthetic:
  - **Glass Background**: Translucent `rgba(...)` fills (e.g., `background: rgba(255, 255, 255, 0.08)` to `rgba(255, 255, 255, 0.85)` or dark glass `rgba(15, 23, 42, 0.65)`).
  - **Frosted Blur**: `backdrop-filter: blur(10px) saturate(180%);` and `-webkit-backdrop-filter: blur(10px) saturate(180%);`.
  - **Subtle Glass Borders**: Fine translucent borders such as `border: 1px solid rgba(255, 255, 255, 0.25)` or `border: 1px solid rgba(226, 232, 240, 0.8)`.
  - **Soft Depth & Glow**: `box-shadow: 0 8px 24px -4px rgba(15, 23, 42, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.4)`.
  - **Smooth Micro-Interactions**: Hover and active transitions (`transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1)`) with subtle background opacity shifts and glow on hover.
- Colors must follow an elegant enterprise palette (indigo, slate, emerald, rose) with refined typography (`Outfit`, `Inter`).
