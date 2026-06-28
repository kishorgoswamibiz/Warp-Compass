# Warp Compass — UI Theme

Derived from `assets/webapp-theme-reference.png` (the Warp Drive Tech site). The PWA should feel
like a member of that family: clean, light, confident, with a vivid green accent.

> Implemented as CSS tokens in `pwa/src/styles/theme.css`. **Sample the exact greens from the
> reference image** to finalize — the values below are close approximations.

## Visual language

- **Light surface with a faint grid.** Off-white/mint background (`--wc-bg: #f3faf5`) overlaid
  with a subtle square grid (like the reference hero). Keeps it airy, not flat.
- **Vivid green accent** (`--wc-green: #15c95b`, deep `#0fa549`). Used for the keyword in a
  headline, primary buttons, and highlights — sparingly, for punch.
- **Bold near-black display type** (`--wc-ink: #0c0f0d`), heavy weight (800), tight tracking,
  large sizes. Headlines do the talking.
- **Rounded pill buttons** (`--wc-radius-pill: 999px`) with a soft green glow shadow.
- **Oversized stat numerals** (the `200+ / 40% / 30%` motif) — big, confident, with a small
  muted label beneath.
- **Generous whitespace**; centered hero; mobile-first (the PWA is phone-first).

## Tokens (see `theme.css` for the full set)

| Token | Value | Use |
|-------|-------|-----|
| `--wc-green` | `#15c95b` | primary accent, buttons |
| `--wc-green-deep` | `#0fa549` | hover/pressed |
| `--wc-ink` | `#0c0f0d` | headings, body |
| `--wc-ink-soft` | `#5b6660` | secondary text |
| `--wc-bg` / `--wc-bg-2` | `#f3faf5` / `#eaf6ee` | surfaces |
| `--wc-radius` / `--wc-radius-pill` | `16px` / `999px` | cards / buttons |

## Typography

- Display/headings: a bold geometric/grotesque (the reference uses a heavy condensed-ish face).
  Default stack is system + Inter; swap in the brand font when chosen (self-host for the PWA —
  no external font CDN, to keep offline/PWA behavior clean).
- Body: Inter / system UI.

## Components to build (as phases need them)

- **Session screen** (P5/P7): a large mic button (pill), live transcript, a calm "we're
  listening" state, pause/resume, typed-fallback input.
- **Brief/threads peek** (optional): the persona's current focus, read-only.
- **Onboarding** (P8): enter a name → mints `participant_id`, creates the bus subfolder.

## Accessibility & device

- Respect `viewport-fit=cover` and safe-area insets (notches).
- Hit targets ≥ 44px; high contrast for the green-on-white CTA text (use white text on green).
- Works portrait, phone-first; degrade gracefully to typed input if mic permission is denied.
