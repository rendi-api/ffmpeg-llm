# claude-ffmpeg

A Claude Code plugin for working with FFmpeg. Describe what you want, get the command.

## Status

`skills/ffmpeg-command/` is fully populated — workflow, ~10 quick recipes, top gotchas, and 8 topic references covering encoding, filters, seeking/trimming, audio, video effects, text/subtitles, asset generation, and GPU acceleration. The slash command and agent remain thin wrappers; the skill is the brain.

## Install (local dev)

```bash
claude --plugin-dir ./claude-ffmpeg
```

## Layout

```
.claude-plugin/plugin.json              # manifest
skills/ffmpeg-command/SKILL.md          # model-invoked skill (workflow + recipes + gotchas)
skills/ffmpeg-command/references/       # topic deep-dives loaded on demand
commands/ffmpeg.md                      # /ffmpeg slash command
agents/ffmpeg-expert.md                 # subagent for hard cases
hooks/hooks.json                        # lifecycle hooks (empty)
```

## License

MIT

