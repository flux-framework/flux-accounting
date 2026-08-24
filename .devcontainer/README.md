# Developer Containers

| Directory | Description |
| --- | --- |
| [default](default) | flux-core, the flux-sched build dependencies, sqlite3, black |
| [claude](claude) | the same, plus [Claude Code](https://code.claude.com/docs) and an egress firewall |

Pick `default` unless you want Claude Code. If you pick `claude`, do the
credentials step below **before** you open the container.

## Opening one

In VS Code, run **Dev Containers: Reopen in Container** and choose the
environment when prompted. From a terminal instead:

```console
$ npm install -g @devcontainers/cli
$ devcontainer up --workspace-folder . --config .devcontainer/default/devcontainer.json
$ devcontainer exec --workspace-folder . bash
```

Then build as usual.

## Setting up Claude Code

Nothing is read from your host machine, so the container starts with no
credentials and a firewall that only lets it reach GitHub and
`api.anthropic.com`. 

**1. Copy the template**

```console
$ cp .devcontainer/claude/claude.env.example .devcontainer/claude/claude.env
```

**2. Customize it**

*Using api.anthropic.com* — uncomment `ANTHROPIC_API_KEY`, paste a key from
[console.anthropic.com](https://console.anthropic.com), and delete the rest of
the file. That's everything.

*Using a gateway or proxy* — you need four things from whoever runs it: a token,
the base URL, the model ids it publishes, and its hostname. Set
`ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`, the `ANTHROPIC_*_MODEL` variables,
and put the hostname in `ALLOWED_DOMAINS`.

**3. Open the container**, then run `claude` in a terminal.

`claude.env` is gitignored and lives in the workspace, so it survives a
container rebuild. 

### Permissions

We block reads and edits of `~/.claude`, `.env`, `.env.*`, and `secrets/`. 
