# Project Relay data ledger

Scene JSON is the executable source of truth. This ledger is a human review
index. Every datum below has an illustrative basis.

| Datum ID | Exact value or range | Unit | Period | Page | Basis | Assumption/source IDs | Derivation | Decision use | Visible label |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- |
| pilot-duration | 12 | weeks | Pilot | 1, 2, 7 | illustrative | pilot-plan | Authored bound | Limits exposure | 12-week |
| pilot-routes | North first; East conditional | routes | Pilot | 1, 2, 7, 8 | illustrative | pilot-plan | Authored scope | East requires W6 gates and technician constraint | North first; East conditional |
| pilot-funding | 0.6 | USD millions | Pilot | 2, 8 | illustrative | pilot-funding | Authored total cap including conditional East | Funding decision | $0.6m |
| synthetic-job-count | 1,200 | jobs | 12 weeks | 3 | illustrative | synthetic-job-sample; synthetic-review-method | Synthetic review count | Establishes sample | 1,200-job |
| late-cause-dispatch | 61 | % | 12 weeks | 3 | illustrative | late-cause-split; synthetic-review-method | Primary-cause classification | Sets first fix | 61% dispatch variability |
| late-cause-technician | 24 | % | 12 weeks | 3 | illustrative | late-cause-split; synthetic-review-method | Primary-cause classification | Defines constraint | 24% technician availability |
| late-cause-handoff | 15 | % | 12 weeks | 3 | illustrative | late-cause-split; synthetic-review-method | Primary-cause classification | Monitor only | 15% access and handoff |
| route-base-north | 86 | priority points | Base | 4 | illustrative | base-route-scores; route-priority-method | Authored scenario score | Rank 1 | North route 86 |
| route-base-central | 78 | priority points | Base | 4 | illustrative | base-route-scores; route-priority-method | Authored scenario score | Rank 2 | Central route 78 |
| route-base-east | 73 | priority points | Base | 4 | illustrative | base-route-scores; route-priority-method | Authored scenario score | Rank 3 | East route 73 |
| route-constrained-north | 82 | priority points | Constrained | 4 | illustrative | technician-constraint; route-priority-method | Authored scenario score | Rank 1 | North route 82 |
| route-constrained-east | 76 | priority points | Constrained | 4 | illustrative | technician-constraint; route-priority-method | Authored scenario score | Rank 2 | East route 76 |
| route-constrained-central | 64 | priority points | Constrained | 4 | illustrative | technician-constraint; route-priority-method | Authored scenario score | Rank 3 | Central route 64 |
| adoption-range | 30–80, step 5 | % | Annual model | 5 | illustrative | adoption-range | Authored control domain | Tests gate | Adoption |
| adoption-value-formula | −1.5 + 0.06 × adoption | USD millions | Annual | 5 | illustrative | annual-value-formula; annual-value-method | Linear model | Computes annual value | Annual value |
| adoption-value-min | 0.3 at 30 | USD millions | Annual | 5 | illustrative | annual-value-formula | −1.5 + 0.06 × 30 | Below gate | $0.3m |
| adoption-value-gate | 1.8 at 55 | USD millions | Annual | 5 | illustrative | annual-value-formula; annual-value-hurdle | −1.5 + 0.06 × 55 | Proceed threshold | $1.8m |
| adoption-value-max | 3.3 at 80 | USD millions | Annual | 5 | illustrative | annual-value-formula | −1.5 + 0.06 × 80 | Upper witness | $3.3m |
| readiness-frequency | 6/12/18/24/30 | points | Pilot | 6 | illustrative | frequency-score | Direct contribution | Score input | Dispatch frequency |
| readiness-data | 10/20/30 | points | Pilot | 6 | illustrative | data-score | Direct contribution | Score input | Data quality |
| readiness-manager | 0/18 | points | Pilot | 6 | illustrative | manager-score | Direct contribution | Base 72; absent 54 | Manager capacity |
| readiness-integration | 0/10/20 | points | Pilot | 6 | illustrative | integration-score | Direct contribution | Score input | Integration depth |
| readiness-base | 72 | points | Pilot | 6 | illustrative | readiness-method | 24 + 20 + 18 + 10 | Proceed | 72 points |
| readiness-no-manager | 54 | points | Pilot | 6 | illustrative | readiness-method | 24 + 20 + 0 + 10 | Hold | 54 points |
| readiness-bands | Defer 16–49; Prepare 50–69; Pilot-ready 70–98 | points | Pilot | 6 | illustrative | readiness-method | Complete integer score range | Classification | Defer / Prepare / Pilot-ready |
| readiness-gate | 70 | points | Week 6 | 6, 7, 8 | illustrative | readiness-threshold | Binary threshold | East activation gate | 70-point readiness gate |
| east-review | End of Week 6 | weeks | Pilot | 2, 7, 8 | illustrative | pilot-plan | Adoption ≥55% AND readiness ≥70 AND technician-constraint case | East can start in Week 7 | W6 |
| scale-review | Week 12 | weeks | Pilot | 2, 7, 8 | illustrative | pilot-plan | Separate steering-committee decision | No automatic network expansion | W12 |

## Assumption and source register

| ID | Kind | Illustrative record |
| --- | --- | --- |
| pilot-plan | assumption | Original 12-week sequence. Approve the cap and start North in W1. Review both gates and the staffing case in W6. East may start in W7. Network expansion needs a separate W12 decision. |
| pilot-funding | assumption | Original synthetic $0.6m total funding cap, including East if activated at Week 6. This is not a separate North-only allocation. |
| synthetic-review-method | source | One synthetic primary cause per late job across the declared review. |
| synthetic-job-sample | assumption | 1,200 synthetic jobs across 12 weeks. |
| late-cause-split | assumption | 61 / 24 / 15 synthetic cause split. |
| base-route-scores | assumption | 86 / 78 / 73 synthetic priority scores. |
| technician-constraint | assumption | 82 / 76 / 64 synthetic constrained scores. |
| route-priority-method | source | Fixed 0–100 illustrative route-priority method. |
| adoption-range | assumption | 30–80% in five-point steps. |
| annual-value-formula | assumption | −1.5 + 0.06 × adoption in USD millions. |
| annual-value-hurdle | assumption | $1.8m decision hurdle. |
| annual-value-method | source | One fixed linear illustrative relationship. |
| frequency-score | assumption | Frequency contributes 6 / 12 / 18 / 24 / 30 points. |
| data-score | assumption | Data quality contributes 10 / 20 / 30 points. |
| manager-score | assumption | Manager capacity contributes 0 / 18 points. |
| integration-score | assumption | Integration contributes 0 / 10 / 20 points. |
| readiness-threshold | assumption | Activating East requires at least 70 points, alongside the adoption and staffing conditions. |
| readiness-method | source | Additive illustrative readiness score with fixed bands. |
