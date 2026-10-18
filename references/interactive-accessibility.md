# Interactive accessibility review

The semantic HTML is authoritative. SVG geometry is visual evidence and stays
hidden from the accessibility tree.

## Author obligations

- Use native buttons, ranges, selects, headings, lists, and dialogs.
- Keep reading order and focus order aligned with the visible decision flow.
- Expose selected, expanded, pressed, and modal states with native/ARIA state.
- Trap focus inside evidence/overview/help dialogs; Escape closes the top
  overlay and returns focus to its opener.
- While a control has focus, arrow keys, Space, Enter, and Escape belong to
  that control or overlay and must not change pages accidentally.
- Make the visible status sentence identical to the debounced `aria-live`
  sentence. Do not announce hidden SVG labels.
- Give every operating target at least 44×44 CSS pixels.

## Required views

Review 1280×720, 390×844, real browser-toolbar 200% zoom, reduced motion, OS
high contrast, greyscale, keyboard-only operation, and touch. Do not shrink
body text below the product floor to make a desktop composition fit. Compact
views may reflow vertically and scroll.

Static/live toggles and dialog close actions return focus predictably. The
declared `printState` must communicate the same conclusion without interaction.
If the runtime fails, the static fallback remains readable and controls become
unavailable rather than misleading.

## Automated versus manual evidence

Automated tests cover Chromium/Firefox navigation, control state, focus guards,
semantic equality, `aria-live`, reduced motion, forced colors, desktop/compact
geometry, print/PDF, and failure fallback. These do not prove Safari, physical
iPhone touch, browser-toolbar 200%, VoiceOver, NVDA, real high contrast, or
projector behavior. Keep those rows unchecked until a named person records the
environment, date, result, and notes.

Use [presenter operation](presenter-operation.md) for the live checklist and
[scene authoring](interactive-scene-schema.md) for the closed component model.
