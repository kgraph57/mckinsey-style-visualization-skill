# Interaction selection

Interaction is a decision tool, not decoration. Design the story as static
slides first, then promote only the pages whose operation improves fact
verification, insight, action, a decision, or evidence retrieval.

## Trigger boundary

For a reference-led うちた-style or click-through presentation, use the
[story-led motion route](motion-story.md): an overview, direct exhibit evidence,
one relevant operation per page, a cursor demo and a readable static export.
The table below describes the separate classic/closed-scene builder route.

| Request | Route |
| --- | --- |
| slide, deck, presentation / スライド、資料 | classic builder only |
| animated deck, quiet reveal / アニメーション付きスライド | classic builder only |
| interactive deck, dynamic deck, live scenario, what-if, clickable evidence, drill-down, scenario slider, live model, auto-demo | classic, then interactive builder |
| 動くスライド、動的スライド、インタラクティブ、クリックで根拠、条件を変えて再計算、試算、スライダー、深掘り、自動デモ | classic, then interactive builder |

“Animated” means a quiet reveal unless the request also asks the audience or
presenter to change state, inspect evidence, or recalculate.

## Storyboard first

For each page record ten columns before authoring a scene:

1. page number;
2. title-only assertion;
3. evidence;
4. audience decision/job;
5. static visual pattern;
6. source/provenance;
7. main interaction;
8. what may change;
9. what must not change;
10. static/print conclusion.

The last four columns are required only when interaction is proposed. One page
has at most one main interaction.

## Choose by job

| Decision job | Candidate scene / view |
| --- | --- |
| Inspect source or assumption | `evidence_only` |
| Compare a small set of named scenarios | `state_toggle` + ranked/bar/dot view |
| Test one continuous assumption | `slider_model` + bar/dot view |
| Combine a bounded set of readiness inputs | `score_model` + recommendation panel |
| Reveal one level of supporting detail | `drilldown` |
| Open one concise answer at a time | `accordion` |

Reject interaction when its rationale is “engagement”, “wow”, or “make it
move”. A valid rationale is specific: “Changing adoption reveals the exact
point at which the funding recommendation changes.”

## Restraint rules

- Preserve the assertion, source, units, domain, threshold, and invariant
  anchor while state changes.
- Keep scales fixed; never make a scenario look better by moving an axis.
- Use motion only to explain a state change. Respect reduced motion.
- Apply the two-spatial-axes-plus-one-scenario ceiling.
- Remove controls that do not alter evidence or a decision. Move supporting
  detail to evidence. Move optional analysis to an appendix.

Build the classic artifact first, then follow
[scene authoring](interactive-scene-schema.md) and the
[accessibility review](interactive-accessibility.md).
