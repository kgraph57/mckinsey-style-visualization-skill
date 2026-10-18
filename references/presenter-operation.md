# Presenter operation

Open the self-contained `deck.interactive.html` in a browser. The file makes no
automatic network request; a validated source link navigates only after an
explicit click.

## Controls

- Previous/Next, page numbers, Arrow keys, Page Up/Down: navigate pages when
  focus is not inside a control.
- `Alt+O`: overview.
- `Alt+R`: reset the current scene.
- `Alt+D`: run or replay the deterministic demo.
- `Alt+F`: request fullscreen; use the browser command if the API is denied.
- `Alt+H`: help.
- Escape: close the top overlay and return focus.
- “View static conclusion”: show the declared print state; “Return to live
  view” restores the live state.

An installation may offer an unmodified-key profile, but the default shortcuts
remain modified to avoid browser and assistive-technology conflicts. The page
strip, overview, reset, replay, evidence, and help buttons are always operable
without memorizing shortcuts.

## Safe sharing and offline use

State is encoded in a bounded same-document fragment. Never put patient,
credential, confidential, or personal information in the deck, fragment, or
source label. Share only approved synthetic or business-safe inputs.

The HTML is offline/self-contained. Evidence text remains available offline;
validated links require the presenter's explicit activation and then use the
browser. If runtime boot or one scene fails, present the static conclusion and
do not claim live recalculation.

## Print and release checklist

Print/export uses `printState`; a reader must understand the recommendation
without operating the deck. Before release, inspect every PDF page and run the
manual checklist for Safari, physical iPhone/touch, actual toolbar 200% zoom,
AirPlay or HDMI/projector, VoiceOver/NVDA, real high contrast, and hosted
`frame-ancestors` response headers. A meta CSP does not prove hosted framing
protection.

See [accessibility](interactive-accessibility.md) and
[interaction selection](interaction-selection.md).
