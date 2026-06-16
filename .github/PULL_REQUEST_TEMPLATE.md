## Summary

- Describe the change in 1-3 bullets.

## Verification

- [ ] `python3 -m unittest discover -s tests`
- [ ] `python3 scripts/validate_skill.py`
- [ ] `python3 -m py_compile scripts/render_slide_spec.py scripts/validate_skill.py scripts/review_slide_spec.py tests/test_render_slide_spec.py tests/test_review_slide_spec.py tests/test_validate_skill.py`
- [ ] `git diff --check`

## Marketplace Readiness

- [ ] README links still work.
- [ ] `marketplace/manifest.json` version matches the intended release.
- [ ] New examples are linked from README, `EXAMPLES.md`, or a relevant reference file.
- [ ] New public claims avoid affiliation, endorsement, or certification language.

## Notes
