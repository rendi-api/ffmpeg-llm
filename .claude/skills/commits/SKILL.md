---
name: commits
description: Use this skill when the user asks to create a git commit, write a commit message, or commit changes. Enforces Conventional Commits format with type, optional scope, subject, body, and footer — used to produce readable history and generate changelogs.
---

# Git Commit Guidelines

Follow these rules whenever creating a git commit in this project. These rules produce readable messages that are easy to follow through project history and are used to generate the change log.

## Commit Message Format

Each commit message consists of a **header**, a **body**, and a **footer**. The header has a special format that includes a **type**, a **scope**, and a **subject**:

```
<type>(<scope>): <subject>
<BLANK LINE>
<body>
<BLANK LINE>
<footer>
```

- The **header is mandatory**.
- The **scope is optional**.
- Any line of the commit message **cannot be longer than 100 characters**. This makes the message easier to read on GitHub and in various git tools.
- The **footer** should contain a closing reference to an issue if any.

### Samples

```
docs(changelog): update change log to beta.5
```

```
fix(core): need to depend on latest rxjs and zone.js
```

## Revert

If the commit reverts a previous commit, it should begin with `revert:`, followed by the header of the reverted commit. In the body, it should say:

```
This reverts commit <hash>.
```

where `<hash>` is the SHA of the commit being reverted.

## Type

The `<type>` must be one of the following:

- **build**: Changes that affect the build system or external dependencies (example scopes: gulp, broccoli, npm)
- **chore**: Updating tasks etc; no production code change
- **ci**: Changes to our CI configuration files and scripts (example scopes: Travis, Circle, BrowserStack, SauceLabs)
- **docs**: Documentation only changes
- **feat**: A new feature
- **fix**: A bug fix
- **perf**: A code change that improves performance
- **refactor**: A code change that neither fixes a bug nor adds a feature
- **style**: Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc)
- **test**: Adding missing tests or correcting existing tests
- **sample**: A change to the samples

## How to Apply

1. Pick the single `<type>` that best describes the change. If a commit spans multiple types, prefer splitting it into separate commits.
2. Choose a `<scope>` that identifies the affected area (module, package, feature). Omit if the change is truly global.
3. Write the `<subject>` in the imperative mood, lowercase, no trailing period, under 100 chars including the type and scope prefix.
4. Leave a blank line, then write the body explaining **what** and **why** (not how). Wrap at 100 chars.
5. Leave a blank line, then add the footer with issue references (e.g., `Closes #123`) or `BREAKING CHANGE:` notes.
