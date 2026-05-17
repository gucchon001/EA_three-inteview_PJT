# UI Component Conventions

This scaffold is optimized for Jinja2 + HTMX + Tailwind CSS + DaisyUI.

## Defaults

- Use DaisyUI classes directly in Jinja templates and HTMX fragments.
- Use Alpine.js only for local UI state such as modal open/close, tabs, and transient toasts.
- Keep Flowbite out of the default dependency set. Add it only when a concrete screen needs a component DaisyUI cannot cover.
- Keep normal browser interactions on server-rendered HTML pages and fragments. JSON APIs are for workers, scripts, E2E helpers, or external integrations.

## Recommended Components

| Use case | DaisyUI components |
|---|---|
| Dashboard metrics | `stats`, `stat`, `progress`, `badge` |
| Lists and admin views | `table`, `badge`, `dropdown`, `join` |
| Forms | `form-control`, `label`, `input`, `select`, `textarea`, `btn` |
| Workflow progress | `steps`, `step`, `progress`, `loading` |
| Validation and errors | `alert`, `badge`, `collapse` |
| Approval gates | `modal`, `checkbox`, `steps`, `alert` |
| Feedback | `rating`, `textarea`, `alert` |

## Layout Rules

- Prefer table and section layouts for dense LMS/admin workflows.
- Use cards for repeated items, modal content, or clearly framed tools. Avoid nesting cards inside cards.
- Avoid fixed widths such as `w-96` in reusable components. Let the parent grid or section control width.
- Return DaisyUI `alert` fragments for HTMX errors so the response can be swapped directly into the target.
- For production, compile Tailwind from template paths instead of relying on CDN loading.
