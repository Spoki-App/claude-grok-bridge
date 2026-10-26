# Security

## Reporting

Please report vulnerabilities **privately** through GitHub:
https://github.com/Spoki-App/claude-grok-bridge/security/advisories/new

Do not open a public issue, and do not include real webhook URLs, tokens or session contents in
the report: describe the issue and how to reproduce it with fake values. You will get an answer
within a few days.

## What matters most here

- Leaking a credential: the Grok routine webhook key, the inbox routine token, or anything from
  the agent's box or the user's Mac.
- Prompt injection through an envelope that makes either side act beyond the protocol (for
  example run commands, change other routines, or treat an answer as user authorization).
- The inbox routine gaining access beyond its `Claude_Code_Remote` connector, or touching
  triggers other than its own `grok-bridge reply` and `grok-bridge ask` triggers.
- Install or update paths that could run code from somewhere other than a tagged release of
  this repository.

## Trust boundary for relayed owner requests

A `request` with `on_behalf_of: "owner"` is trusted because it comes from the owner's own Claude
account (the inbox) or the owner's Mac (the fast lane), not because it is signed. A signature
would not stop the realistic attacker, a prompt-injected session on that same Mac, which holds
any local secret too. So the agent's own rules stay the backstop: anything reserved to the
owner (money, production, merges, messages sent as the owner) gets `needs_confirmation` and is
asked in the agent's chat. See [#7](https://github.com/Spoki-App/claude-grok-bridge/issues/7).

## Supported versions

Only the latest release gets fixes. Updating is one line: send your Grok agent the setup line
again.
