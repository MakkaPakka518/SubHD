---
name: SubHD Forward
description: Light, compact management panel for importing the generated Forward/rex module.
colors:
  ground: "#f4f7fb"
  surface: "#ffffff"
  field: "#f6f8fc"
  ink: "#192c48"
  muted: "#56667c"
  line: "#cdd7e4"
  control-line: "#74869e"
  accent: "#185cc7"
  accent-hover: "#104daa"
  accent-soft: "#eaf1fc"
  success: "#176b48"
  success-soft: "#e7f4ee"
  error: "#a92d39"
  error-soft: "#fff0f1"
  focus: "#2069d5"
  shadow: "#192c4814"
typography:
  body:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif'
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.6
  headline: { fontSize: "28px", fontWeight: 600, lineHeight: 1.35 }
  title: { fontSize: "16px", fontWeight: 600, lineHeight: 1.5 }
  label: { fontSize: "14px", fontWeight: 500 }
  small: { fontSize: "12px", fontWeight: 400, lineHeight: 1.6 }
  code:
    fontFamily: 'ui-monospace, "SFMono-Regular", Consolas, monospace'
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6
rounded: { panel: "12px", control: "6px" }
spacing:
  "8": "8px"
  "12": "12px"
  "16": "16px"
  "20": "20px"
  "24": "24px"
  "28": "28px"
  "32": "32px"
  "40": "40px"
  "48": "48px"
components:
  button-primary: { backgroundColor: "{colors.accent}", textColor: "{colors.surface}", typography: "{typography.label}", rounded: "{rounded.control}", padding: "10px 16px" }
  button-primary-hover: { backgroundColor: "{colors.accent-hover}" }
  button-secondary: { backgroundColor: "{colors.surface}", textColor: "{colors.ink}", typography: "{typography.label}", rounded: "{rounded.control}", padding: "10px 16px" }
  button-quiet: { backgroundColor: "transparent", textColor: "{colors.muted}", typography: "{typography.label}", rounded: "{rounded.control}", padding: "10px 16px" }
  password-field: { backgroundColor: "{colors.surface}", textColor: "{colors.ink}", typography: "{typography.body}", rounded: "{rounded.control}" }
  module-url: { backgroundColor: "{colors.field}", textColor: "{colors.ink}", typography: "{typography.code}", rounded: "{rounded.control}", padding: "12px", width: "100%" }
  service-badge: { backgroundColor: "{colors.accent-soft}", textColor: "{colors.accent}", rounded: "{rounded.control}", padding: "5px 10px" }
  service-badge-ready: { backgroundColor: "{colors.success-soft}", textColor: "{colors.success}" }
  module-card: { backgroundColor: "{colors.surface}", rounded: "{rounded.panel}", padding: "28px" }
---

# Design System: SubHD Forward

## Overview

A light, compact native HTML/CSS management panel. The main task is to log in, copy the generated `.js` module URL, and import it into Forward/rex. The generated module includes the backend address and module credential, so import requires no extra configuration.

**Key Characteristics:**
- System typography with a monospace module URL.
- Light blue-grey ground, white import surface, cobalt actions.
- Independently adapted desktop and mobile layouts.

Tokens mirror `static/panel.css`; markup and interaction behavior live in `static/index.html` and `static/panel.js`.

## Colors

| Tokens | Use |
| --- | --- |
| `accent`, `accent-hover`, `accent-soft` | Primary login/copy actions, links, hover, selection background and the reading/processing badge. |
| `ground`, `surface`, `field` | Page ground, header/import surface, URL background and quiet/secondary hover fill. |
| `ink`, `muted` | Main text and subdued labels, hints, secondary branding and header actions. |
| `control-line` | Password field and module URL boundaries. |
| `line` | Decorative header, card, status, setup and help dividers; secondary button border. |
| `success`, `success-soft` | Service badge when the overview reports no active download. |
| `error`, `error-soft` | Inline error text and background. |
| `focus`, `shadow` | Keyboard outline/input focus border and toast shadow. |

Input boundaries use the darker `control-line`, distinct from the lighter decorative `line`.

## Typography

The body uses the system stack above; the module URL alone uses the monospace stack. The four sizes are 12px for hints, badges and footer text; 14px for labels, buttons, status, help and the desktop URL; 16px for body text, section titles, the password input and mobile URL; and 28px for page/login headings.

Headings use weight 600; form labels, buttons and badges use 500; body and supporting text use 400. Buttons use line-height 1.5. Headings balance their wrapping; long page headings can break words. Status values use tabular numerals and wrap rather than truncate.

## Layout

- **Desktop, above 640px:** Header, page and footer share a centered 1040px maximum width with 32px inline gutters. The header is at least 76px high; page padding is 48px top and 40px bottom. Login is capped at 440px, with top margin `clamp(28px, 12dvh, 120px)`. The import surface has 28px padding. URL and copy button sit side by side with a 16px gap; status uses two columns with a 40px column gap.
- **Mobile, at or below 640px:** Header height drops to 64px. Page padding is 28px top, 32px bottom and at least 16px on each side. Login uses 36px top and 48px bottom margins. Import padding becomes 20px by 16px; URL and full-width copy button stack with a 12px gap. Status becomes one column; module footer and cache actions stack. The cache button precedes its hint. Header actions retain their accessible names while their text is visually hidden; the format label is hidden.
- **Touch and safe areas:** Mobile buttons, icon controls, brand, module download and footer links have at least 48px height; icon controls have at least 48px width. Header actions are separated by 8px. `viewport-fit=cover` is enabled; the header clears the top inset and mobile page/header gutters respect side insets. Footer bottom padding and toast bottom placement use `max(24px, env(safe-area-inset-bottom))`.
- **Scrolling and overflow:** The page uses native document scrolling, `100dvh` minimum body height and a stable scrollbar gutter. Horizontal page overflow is clipped; flexible columns can shrink and long URLs/status values wrap. The URL textarea requests content sizing between 74px and 160px, without manual resizing.

## Elevation & Depth

White surfaces, pale field fill and half-pixel dividers establish depth. Header and import surface have no shadow. The toast alone uses `0 4px 14px var(--color-shadow)`, with white text on the ink background. It sits above content and is capped at viewport width minus 32px.

## Shapes

The import surface uses the panel radius; buttons, input boundaries, badges, errors and toast use the control radius. Borders and decorative dividers are 0.5px. Icons are 20px outline SVGs with rounded stroke ends and joins; badges are compact rounded rectangles.

## Components

### Actions and feedback

Primary buttons are cobalt with white text and deepen on hover. Secondary buttons are white with a divider-colored border; quiet header actions are transparent with muted text. Secondary/quiet hover uses the pale field fill. Buttons have 44px minimum desktop height, 10px by 16px padding and an 8px content gap. Disabled buttons use 0.6 opacity and a not-allowed cursor; login/refresh busy states use `aria-busy` and a wait cursor.

Button background, border and press transitions last 160ms. Pressed buttons and the password visibility control move down 1px. Reduced motion removes button transitions and smooth scrolling. Copy/cache feedback is a polite live-status toast shown for 3200ms.

### Login

The password input has a persistent label, associated hint/error, native required validation and a 24-character minimum. It uses `autocomplete="current-password"`, with capitalization and spellcheck disabled. The visibility button switches its accessible label and `aria-pressed` state. Missing server configuration reveals the API_TOKEN setup note.

Submitting disables the login button and changes its label to “正在登录…”. Success reveals the workspace/header actions and focuses the copy button. Logout clears the displayed module URL and password, then focuses the password input. Failed login and request errors use inline alert messages; recent download errors use the same visual error treatment.

### Module URL

The generated URL is a read-only, left-to-right textarea, with spellcheck disabled. Clicking it selects the full value. Copy remains disabled until overview data supplies the URL. Clipboard success shows “模块链接已复制”; failure focuses/selects the URL and asks the user to copy it manually. The `.js` download link is a secondary text action below the field.

### Status and help

Overview data supplies browser installation, download activity, region, version, cache counts and last successful download. The badge is soft cobalt while reading/processing and green when no download is active; its text names the state. No download history displays “尚无记录”. Refresh disables its button while pending; unauthorized refresh returns to login. Cache clearing is disabled during an active download or when the cache is empty, and refreshes status after success.

Help uses native `details`/`summary`; its chevron rotates when expanded. It remains inline in the page flow.

### Focus and keyboard input

Interactive elements retain native keyboard behavior and a 2px focus-visible outline with 3px offset. The password input uses zero outline offset inside its group, whose border changes to the focus color. A focus-revealed skip link targets the main content.

On mobile, password focus scrolls the input to the viewport center after 250ms and adds 140px bottom space to the login area. Reduced-motion users get instant focus scrolling. Form submission blurs the input before requesting login.

## Do's and Don'ts

- Do keep copying the generated module URL as the prominent workspace action and preserve independently adapted desktop/mobile layouts.
- Don't replace darker input boundaries with decorative divider color or suppress native text selection and visible keyboard focus.
