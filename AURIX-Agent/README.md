# AURIX Agent

**A local-first desktop AI agent that can inspect a workspace, use bounded tools, edit files when enabled, and verify changes.**

Created by Kamlesh Suthar.

AURIX Agent uses Python's built-in Tkinter GUI and an OpenAI-compatible chat-completions endpoint. It needs no third-party Python packages for the initial version. Provider API usage may cost money or be subject to rate limits.

## What works in this version

- Clean desktop GUI with chat, a live activity panel, cancellation requests, workspace selection, and provider settings.
- OpenAI-compatible API providers; active provider is tried first, then enabled providers act as fallbacks.
- Tool-calling loop: the model can request tools, receive actual results, and continue through multiple steps.
- Workspace-confined tools: list files, read UTF-8 text, search for text, write files if explicitly enabled, check Python syntax, run `unittest` when explicitly enabled, and read Git status.
- Path traversal checks, excluded dependency/cache folders, text-size limits, subprocess timeouts, shell-free test execution, and tool-call limits.
- Provider keys and settings are stored locally in `~/.aurix-agent/config.json`; no keys are included in source control.
- Standard-library unit tests and a GitHub Actions test workflow.

## Requirements

- Python 3.11 or newer recommended.
- Windows 10/11, Linux, or macOS with Tkinter available. Most standard Windows Python installers include Tkinter.
- Internet access and an API key for a provider that supports the OpenAI chat-completions tool-calling protocol.

## Run on Windows

1. Download or clone this repository.
2. Open PowerShell inside the `AURIX-Agent` folder.
3. Run:

   ```powershell
   py -3.11 run_aurix.py
   ```

4. Open **Provider settings**. Set a provider name, its full HTTPS chat-completions endpoint, model ID, and API key. Click **Save provider**, then **Save settings**.
5. Select the folder AURIX should work in and describe one concrete task.

Provider endpoint examples (availability and model support depend on provider/account):

- OpenAI: `https://api.openai.com/v1/chat/completions`
- Google Gemini OpenAI-compatible endpoint: `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions`
- OpenRouter: `https://openrouter.ai/api/v1/chat/completions`

Configure the model ID and API key from the provider's current documentation. The endpoint must use HTTPS. The app cannot guarantee that every provider/model implements tool calling identically.

## Permissions and autonomy

AURIX plans and performs bounded tool calls automatically after you submit a task. **Allow file changes** and **Allow test runs** are off by default and need explicit user opt-in. The agent cannot run arbitrary shell commands through its tool interface. Test execution runs Python's `unittest` discovery against the selected workspace; test files themselves are executable code, so enable it only for a project you trust. `git_status` is read-only.

The selected workspace is the boundary for file access. Do not select a folder containing secrets you do not want to send to an AI provider. If the model calls a tool, its relevant results are sent back to the configured API provider. Do not paste passwords, private keys, recovery codes, or other secrets into chat.

This is a bounded AI agent, not a universal human-level system. It can misunderstand tasks, providers can be unavailable, and tool results should be reviewed before trusting changes. It does not operate invisibly in the background and does not promise to complete every possible task.

## Tests

```powershell
py -m unittest discover -s tests -v
```

## Troubleshooting

- **No Tkinter:** reinstall Python with Tcl/Tk support, or use a Python distribution that includes it.
- **Provider errors:** check endpoint, model identifier, key, billing/quota, network, and that the model supports tool calling on the selected API.
- **No tool use:** ask for a concrete task and confirm the provider supports the OpenAI-compatible tools protocol.
- **Writes blocked:** enable **Allow file changes** in the left panel.
- **Tests blocked:** enable **Allow test runs** only after reviewing the workspace's tests.

## License

MIT. See `LICENSE` in the parent repository.
