# iOS Safari simulator check — 2026-09-09

Environment: Xcode Simulator, iPhone 17, iOS 26.3, Safari.
Initial public version: 2da9ca9. Fixes retested against the local site in the same simulator.

## Verified through Simulator UI

- Load the existing nine-slide sample without an API key.
- Open the presentation; swipe from slide 1 to slide 2.
- Rotate to landscape; slide and navigation controls remain visible.
- Open native print preview: nine pages.
- Use the print share sheet to save a PDF into On My iPhone.
- Use HTML share sheet to save presentation.html into On My iPhone.
- Open Files and verify both saved artifacts are listed.
- Japanese system font was broken in this simulator; explicit Hiragino Sans rendered correctly. Retested Japanese page body and buttons after applying fallback.
- Sharing files plus a title produced an extra text file in Files. Retested files-only sharing: save sheet contains one named presentation file instead of two items.

## Fixes

- Explicit Japanese font for page text and form controls.
- Share the HTML file only, without a separate title item.
- Use deck title as document title while presenting, restoring original title on close.
- Explain landscape selection in native print dialog. Safari initially defaults to A4 portrait despite the slide print CSS.

## Limits

No real iPhone hardware, AI API generation, AirPlay, projector connection, or external recipient delivery was tested. The shared HTML saves successfully; reopening an interactive HTML deck from iOS Files is not verified. Use the in-browser presenter for presenting, and PDF for portable viewing.
