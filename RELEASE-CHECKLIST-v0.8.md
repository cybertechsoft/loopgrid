# LoopGrid v0.8 public release checklist

## A. Release gate

- [x] Automated regression suite: 46 tests PASS in the release packaging environment.
- [x] Run `validate_pilot.ps1` / pilot deployment validator on the Windows Docker/PostgreSQL evaluation machine.
- [x] Confirm final line: `LOOPGRID v0.8 PILOT DEPLOYMENT VALIDATION: PASS`.
- [x] Update `VALIDATION-RELEASE-RECORD-v0.8.md` target-machine row to PASS.
- [x] Recreate the final public source ZIP/checksum after the validation-record update.

## B. GitHub

- [ ] Replace old control-plane code/docs with the GitHub-ready v0.8 repository contents.
- [ ] Repository description: `The evidence plane for AI agents — portable, verifiable evidence for consequential agent decisions.`
- [ ] Confirm README contains no `immutable`, `ground truth`, or compliance-guarantee claims.
- [ ] Create release/tag `v0.8.0` with `CHANGELOG.md` notes.

## C. PyPI

- [ ] Publish Python SDK `loopgrid==0.8.0`.
- [ ] Confirm package page shows the evidence-plane description and v0.8 examples.

## D. npm

- [ ] Publish `@cybertechsoft/loopgrid@0.8.0`.
- [ ] Confirm package README/types are current.

## E. Landing page

- [ ] Deploy the prepared landing package only after GitHub/PyPI/npm point to v0.8.
- [ ] Verify loopgrid.io title, hero, design-partner CTA and trust language.
- [ ] Test all contact and developer links.

## F. Outreach

- [ ] Start with 10–20 highly targeted prospects rather than broad cold outreach.
- [ ] Offer one narrow design-partner workflow, not a generic platform demo.
- [ ] Record objections and requested trust/deployment features to prioritize v0.9.
