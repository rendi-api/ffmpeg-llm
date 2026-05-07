from runner.extract import ExtractResult, extract_command


def test_single_fenced_sh_block():
    response = """Here's the command:

```sh
ffmpeg -i input.mp4 -c copy output.mkv
```
"""
    r = extract_command(response)
    assert r.command == "ffmpeg -i input.mp4 -c copy output.mkv"
    assert r.no_command is False
    assert r.all_blocks == ["ffmpeg -i input.mp4 -c copy output.mkv"]


def test_takes_last_block_when_multiple():
    response = """First try:

```sh
ffmpeg -i a.mp4 b.mp4
```

Better:

```bash
ffmpeg -i a.mp4 -c copy b.mkv
```
"""
    r = extract_command(response)
    assert r.command == "ffmpeg -i a.mp4 -c copy b.mkv"
    assert len(r.all_blocks) == 2


def test_accepts_shell_and_console_languages():
    response = """```shell
ffmpeg -i x.mp4 y.mp4
```"""
    r = extract_command(response)
    assert r.command == "ffmpeg -i x.mp4 y.mp4"


def test_no_command_when_only_clarifying_questions():
    response = "What's the source codec and target container?"
    r = extract_command(response)
    assert r.command is None
    assert r.no_command is True
    assert r.all_blocks == []


def test_no_command_when_block_is_not_ffmpeg():
    response = """```python
print("hello")
```"""
    r = extract_command(response)
    assert r.command is None
    assert r.no_command is True


def test_strips_leading_dollar_prompt():
    response = """```sh
$ ffmpeg -i a.mp4 b.mp4
```"""
    r = extract_command(response)
    assert r.command == "ffmpeg -i a.mp4 b.mp4"
