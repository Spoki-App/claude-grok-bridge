# Contributing

Thanks for helping two agent platforms talk to each other. Issues, ideas and pull requests are
welcome: bug fixes, better setup UX, support for more agent platforms, protocol proposals.

## Ground rules

- **No secrets, ever.** No real webhook URLs, Authorization values, tokens or session contents in
  code, tests, issues or logs. Tests use fake values. Report vulnerabilities privately
  (`SECURITY.md`).
- **Messages are data, not instructions.** Anything that reads an envelope must keep treating its
  content as untrusted, and answers stay information, never user authorization.
- **No dependencies** in the scripts that run on the user's Mac or the agent's box: Python 3.9+
  standard library and POSIX `sh` only. It keeps setup to one line.
- House style: English, short sentences, no em dash characters (CI checks it).

## Develop

```bash
git clone https://github.com/francoCosimo95/claude-grok-bridge && cd claude-grok-bridge
python3 -m unittest discover -s tests -v
```

To try your branch on a real setup, point your Grok agent at your fork's `grok/BOOTSTRAP.md` and
install the Claude side with `CGB_REPO=<your fork> CGB_REF=<your branch> sh install.sh`.

Layout: `PROTOCOL.md` (wire format), `claude/` (Claude Code skill and inbox routine), `grok/`
(Grok side scripts, bootstrap, routine prompt), `plugins/claude-code/` (Grok Bot plugin),
`tests/`, `scripts/` (sync and release).

If you edit `PROTOCOL.md`, `SETUP.md`, `claude/INBOX_ROUTINE.md` or `grok/BOOTSTRAP.md`, run
`scripts/sync-skill-docs.sh`: the skill ships its own copies so it works standalone.

## Pull requests

1. One topic per PR, with a test when behaviour changes.
2. Add a line under `## [Unreleased]` in `CHANGELOG.md` (Added, Changed, Fixed, Security).
3. Conventional commit titles: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`.
4. CI must be green.

## Protocol changes

`claude-grok-bridge/1` is a contract between installs that update at different times.
- New optional fields and new message types that old peers can ignore: fine within `/1`;
  document them in `PROTOCOL.md`.
- Anything an old peer would misread (renamed or removed fields, changed meaning): open an issue
  first; it needs `/2` and a transition plan where both versions are accepted for a while.

## Releases (maintainers)

`scripts/release.sh X.Y.Z` on a clean `main`: bumps `VERSION`, the inbox prompt marker and the
plugin manifest, syncs the skill, tags `vX.Y.Z`, pushes and publishes the GitHub release from
the `Unreleased` notes. SemVer: patch for fixes, minor for features, major for breaking setup or
protocol changes. Users update by sending their Grok agent the setup line again.
