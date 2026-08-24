# Claude Developer Environment

This is a VSCode devcontainer with [Claude Code](https://code.claude.com/docs) installed alongside flux-accounting. We restrict outbound network access with `init-firewall.sh`.
The [settings.json](settings.json) will be copied to `~/.claude/settings.json`  and you should setup `claude.env` to include your endpoint, credentials, and preferred models. For example:

```console
# Copy and edit this file
$ cp .devcontainer/claude/claude.env.example .devcontainer/claude/claude.env
```

See [the Claude Code Docs](https://code.claude.com/docs/en/env-vars) for environment variables you can define. Note that the firewall file requires the allowed domains, the list of hosts the container can reach in addition to GitHub. The most important part of [settings.json](settings.json) is the Permissions.
