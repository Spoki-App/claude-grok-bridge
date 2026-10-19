## What and why

## Checklist
- [ ] `python -m unittest discover -s tests` passes
- [ ] Behaviour change noted under `## [Unreleased]` in `CHANGELOG.md`
- [ ] Docs updated; `scripts/sync.sh` run if VERSION or PROTOCOL.md changed
- [ ] Protocol untouched, or the change is backward compatible (see CONTRIBUTING.md)
- [ ] No secrets, tokens, real webhook URLs or session contents in code, tests or logs
- [ ] No em dash characters
