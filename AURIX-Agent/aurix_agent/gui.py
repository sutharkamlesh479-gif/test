"""Minimal desktop GUI for AURIX Agent; built with Python's standard Tkinter."""
from __future__ import annotations
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from datetime import datetime

from .config import load_config, save_config, enabled_providers, CONFIG_PATH
from .core import AURIXAgent, AgentError

BG = "#101412"
PANEL = "#171D19"
PANEL_2 = "#1D2520"
FG = "#EEF4EF"
MUTED = "#96A59A"
GREEN = "#55D68B"
BORDER = "#2B3930"


class ProviderSettings(tk.Toplevel):
    def __init__(self, parent: "AURIXWindow"):
        super().__init__(parent)
        self.parent = parent
        self.config_data = load_config()
        self.providers = [dict(p) for p in self.config_data.get("providers", []) if isinstance(p, dict)]
        self.title("AURIX · Provider settings")
        self.configure(bg=BG)
        self.geometry("760x560")
        self.minsize(680, 500)
        self.transient(parent)
        self.grab_set()
        self._build()
        self._refresh_list()
        if self.providers:
            self.provider_list.selection_set(0)
            self._load_selected()

    def _build(self):
        tk.Label(self, text="AI PROVIDERS", bg=BG, fg=FG, font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=20, pady=(18, 4))
        tk.Label(self, text="Use an OpenAI-compatible chat-completions endpoint. API keys stay on this PC.", bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(0, 12))
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True, padx=20, pady=(0, 14))
        left = tk.Frame(outer, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, width=220)
        left.pack(side="left", fill="y", padx=(0, 14))
        left.pack_propagate(False)
        tk.Label(left, text="PROVIDERS", bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12, pady=(12, 8))
        self.provider_list = tk.Listbox(left, bg=PANEL, fg=FG, selectbackground="#254A34", selectforeground=FG, relief="flat", activestyle="none", font=("Segoe UI", 10), highlightthickness=0)
        self.provider_list.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.provider_list.bind("<<ListboxSelect>>", lambda _e: self._load_selected())
        left_buttons = tk.Frame(left, bg=PANEL)
        left_buttons.pack(fill="x", padx=8, pady=(0, 10))
        self._button(left_buttons, "＋ New", self._new).pack(side="left", expand=True, fill="x", padx=(0, 4))
        self._button(left_buttons, "Remove", self._remove, subtle=True).pack(side="left", expand=True, fill="x")

        form = tk.Frame(outer, bg=BG)
        form.pack(side="left", fill="both", expand=True)
        self.vars = {k: tk.StringVar() for k in ("name", "endpoint", "model", "api_key")}
        labels = [("Provider name", "name"), ("Chat completions URL (HTTPS)", "endpoint"), ("Model ID", "model"), ("API key", "api_key")]
        for row, (label, key) in enumerate(labels):
            tk.Label(form, text=label, bg=BG, fg=MUTED, font=("Segoe UI", 9)).grid(row=row*2, column=0, sticky="w", pady=(3, 5))
            entry = tk.Entry(form, textvariable=self.vars[key], bg=PANEL, fg=FG, insertbackground=FG, relief="flat", highlightbackground=BORDER, highlightthickness=1, font=("Segoe UI", 10), show="•" if key == "api_key" else "")
            entry.grid(row=row*2+1, column=0, sticky="ew", ipady=9)
        form.columnconfigure(0, weight=1)
        self.enabled_var = tk.BooleanVar(value=True)
        tk.Checkbutton(form, text="Provider enabled (used as fallback when needed)", variable=self.enabled_var, bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG, activeforeground=FG).grid(row=8, column=0, sticky="w", pady=(12, 8))
        help_text = "Examples:\nOpenAI: https://api.openai.com/v1/chat/completions\nGemini OpenAI-compatible: https://generativelanguage.googleapis.com/v1beta/openai/chat/completions\nOpenRouter: https://openrouter.ai/api/v1/chat/completions\n\nThe chosen API provider processes the prompts and any file excerpts you send to it. Do not include secrets in tasks."
        tk.Label(form, text=help_text, justify="left", anchor="w", bg=BG, fg=MUTED, font=("Segoe UI", 9)).grid(row=9, column=0, sticky="ew", pady=(10, 0))
        tk.Label(self, text=f"Local settings file: {CONFIG_PATH}", bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", padx=20, pady=(0, 8))
        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill="x", padx=20, pady=(0, 18))
        self._button(bottom, "Save provider", self._save_provider).pack(side="left")
        self._button(bottom, "Set active", self._set_active, subtle=True).pack(side="left", padx=8)
        self._button(bottom, "Save settings", self._save_all, primary=True).pack(side="right")

    def _button(self, parent, text, command, primary=False, subtle=False):
        bg = GREEN if primary else (PANEL_2 if subtle else "#24352A")
        fg = "#0D1710" if primary else FG
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg, activebackground="#6AE69C", activeforeground="#0D1710", relief="flat", bd=0, cursor="hand2", font=("Segoe UI", 9, "bold"), padx=12, pady=8)

    def _refresh_list(self):
        selected_name = self.vars["name"].get()
        self.provider_list.delete(0, tk.END)
        for provider in self.providers:
            status = "●" if provider.get("enabled", True) else "○"
            self.provider_list.insert(tk.END, f"{status}  {provider.get('name', 'Unnamed')}")
        for i, provider in enumerate(self.providers):
            if provider.get("name") == selected_name:
                self.provider_list.selection_set(i)
                self.provider_list.see(i)
                break

    def _selected_index(self):
        selection = self.provider_list.curselection()
        return selection[0] if selection else None

    def _load_selected(self):
        index = self._selected_index()
        if index is None or index >= len(self.providers):
            return
        provider = self.providers[index]
        for key in self.vars:
            self.vars[key].set(str(provider.get(key, "")))
        self.enabled_var.set(bool(provider.get("enabled", True)))

    def _new(self):
        for key in self.vars:
            self.vars[key].set("")
        self.vars["name"].set("New provider")
        self.vars["endpoint"].set("https://api.openai.com/v1/chat/completions")
        self.vars["model"].set("gpt-4o-mini")
        self.vars["api_key"].set("")
        self.enabled_var.set(True)
        self.provider_list.selection_clear(0, tk.END)

    def _remove(self):
        index = self._selected_index()
        if index is None:
            return
        if not messagebox.askyesno("Remove provider", "Remove this provider from local settings?", parent=self):
            return
        del self.providers[index]
        self._refresh_list()
        if self.providers:
            self.provider_list.selection_set(min(index, len(self.providers)-1))
            self._load_selected()
        else:
            self._new()

    def _save_provider(self):
        values = {key: var.get().strip() for key, var in self.vars.items()}
        if not values["name"] or not values["endpoint"].startswith("https://") or not values["model"]:
            messagebox.showerror("Invalid provider", "Name, model, and an HTTPS chat-completions URL are required.", parent=self)
            return
        values["enabled"] = self.enabled_var.get()
        index = self._selected_index()
        if index is not None and index < len(self.providers):
            self.providers[index] = values
        else:
            match = next((i for i,p in enumerate(self.providers) if p.get("name") == values["name"]), None)
            if match is None:
                self.providers.append(values)
            else:
                self.providers[match] = values
        self._refresh_list()
        self.provider_list.selection_clear(0, tk.END)
        found = next((i for i,p in enumerate(self.providers) if p.get("name") == values["name"]), None)
        if found is not None:
            self.provider_list.selection_set(found)
        messagebox.showinfo("Provider saved", "Provider is ready. Click Save settings to write configuration to this PC.", parent=self)

    def _set_active(self):
        index = self._selected_index()
        if index is None or index >= len(self.providers):
            messagebox.showwarning("Select provider", "Select a provider first.", parent=self)
            return
        self.config_data["active_provider"] = self.providers[index].get("name", "")
        messagebox.showinfo("Active provider", f"Active provider set to {self.config_data['active_provider']} (save settings to persist).", parent=self)

    def _save_all(self):
        index = self._selected_index()
        if index is not None:
            values = {key: var.get().strip() for key, var in self.vars.items()}
            if values["name"] and values["endpoint"].startswith("https://") and values["model"]:
                values["enabled"] = self.enabled_var.get()
                self.providers[index] = values
        self.config_data["providers"] = self.providers
        if not any(p.get("name") == self.config_data.get("active_provider") and p.get("enabled", True) for p in self.providers):
            active = next((p for p in self.providers if p.get("enabled", True)), None)
            self.config_data["active_provider"] = active.get("name") if active else ""
        save_config(self.config_data)
        self.parent.refresh_provider_label()
        messagebox.showinfo("Saved", "Provider settings saved locally. API keys were not uploaded to GitHub.", parent=self)
        self.destroy()


class AURIXWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AURIX Agent")
        self.geometry("1180x780")
        self.minsize(900, 640)
        self.configure(bg=BG)
        self.config_data = load_config()
        self.workspace = tk.StringVar(value=str(Path.home()))
        self.allow_writes = tk.BooleanVar(value=False)
        self.allow_execution = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Ready")
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.cancel_event: threading.Event | None = None
        self._configure_style()
        self._build()
        self.refresh_provider_label()
        self.after(120, self._poll_events)

    def _configure_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=FG, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("TCheckbutton", background=PANEL, foreground=FG, font=("Segoe UI", 9))
        style.map("TCheckbutton", background=[("active", PANEL)], foreground=[("active", FG)])

    def _button(self, parent, text, command, primary=False, subtle=False):
        bg = GREEN if primary else (PANEL_2 if subtle else "#24352A")
        fg = "#0D1710" if primary else FG
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg, activebackground="#6AE69C", activeforeground="#0D1710", relief="flat", bd=0, cursor="hand2", font=("Segoe UI", 10, "bold"), padx=14, pady=10)

    def _build(self):
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=22, pady=(18, 14))
        tk.Label(top, text="AURIX", bg=BG, fg=GREEN, font=("Segoe UI", 23, "bold")).pack(side="left")
        tk.Label(top, text="AGENT", bg=BG, fg=FG, font=("Segoe UI", 23, "normal")).pack(side="left", padx=(7, 0))
        tk.Label(top, text="Think  ·  Plan  ·  Use tools  ·  Verify", bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(side="left", padx=(18, 0), pady=(8, 0))
        tk.Label(top, textvariable=self.status, bg=PANEL, fg=GREEN, font=("Segoe UI", 9, "bold"), padx=12, pady=7).pack(side="right")

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=22, pady=(0, 14))
        side = tk.Frame(body, bg=PANEL, width=252, highlightbackground=BORDER, highlightthickness=1)
        side.pack(side="left", fill="y", padx=(0, 14))
        side.pack_propagate(False)
        tk.Label(side, text="WORKSPACE", bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=15, pady=(16, 8))
        self.workspace_label = tk.Label(side, textvariable=self.workspace, bg=PANEL, fg=FG, font=("Segoe UI", 9), wraplength=218, justify="left", anchor="w")
        self.workspace_label.pack(fill="x", padx=15)
        self._button(side, "Choose folder", self._choose_workspace, subtle=True).pack(fill="x", padx=14, pady=(10, 18))
        tk.Frame(side, bg=BORDER, height=1).pack(fill="x", padx=14)
        tk.Label(side, text="AI PROVIDER", bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=15, pady=(16, 8))
        self.provider_label = tk.Label(side, text="Not configured", bg=PANEL, fg=FG, font=("Segoe UI", 10, "bold"), wraplength=215, anchor="w", justify="left")
        self.provider_label.pack(fill="x", padx=15)
        self._button(side, "Provider settings", self._open_settings, subtle=True).pack(fill="x", padx=14, pady=(10, 18))
        tk.Frame(side, bg=BORDER, height=1).pack(fill="x", padx=14)
        tk.Label(side, text="PERMISSIONS", bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=15, pady=(16, 7))
        ttk.Checkbutton(side, text="Allow file changes", variable=self.allow_writes).pack(anchor="w", padx=12, pady=4)
        ttk.Checkbutton(side, text="Allow test runs", variable=self.allow_execution).pack(anchor="w", padx=12, pady=4)
        tk.Label(side, text="Both are off by default. The agent can inspect files and check Python syntax without enabling them.", bg=PANEL, fg=MUTED, wraplength=218, justify="left", font=("Segoe UI", 8)).pack(anchor="w", padx=15, pady=(5, 14))
        tk.Frame(side, bg=BORDER, height=1).pack(fill="x", padx=14)
        tk.Label(side, text="LOCAL-FIRST CONTROLS", bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=15, pady=(14, 5))
        tk.Label(side, text="No hidden background mode. Tool activity stays visible here. API prompts and shared excerpts go to your configured provider.", bg=PANEL, fg=MUTED, wraplength=218, justify="left", font=("Segoe UI", 8)).pack(anchor="w", padx=15)

        main = tk.Frame(body, bg=BG)
        main.pack(side="left", fill="both", expand=True)
        chat_head = tk.Frame(main, bg=BG)
        chat_head.pack(fill="x", pady=(0, 8))
        tk.Label(chat_head, text="Task workspace", bg=BG, fg=FG, font=("Segoe UI", 15, "bold")).pack(side="left")
        self._button(chat_head, "Clear chat", self._clear_chat, subtle=True).pack(side="right")
        chat_box = tk.Frame(main, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        chat_box.pack(fill="both", expand=True)
        self.chat = tk.Text(chat_box, bg=PANEL, fg=FG, insertbackground=FG, relief="flat", wrap="word", padx=18, pady=16, font=("Segoe UI", 10), state="disabled", spacing1=2, spacing3=8)
        self.chat.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(chat_box, command=self.chat.yview)
        scroll.pack(side="right", fill="y")
        self.chat.configure(yscrollcommand=scroll.set)
        self.chat.tag_configure("user", foreground=GREEN, font=("Segoe UI", 10, "bold"), spacing1=8)
        self.chat.tag_configure("assistant", foreground=FG, font=("Segoe UI", 10, "bold"), spacing1=8)
        self.chat.tag_configure("body", foreground=FG, lmargin1=0, lmargin2=0)
        self.chat.tag_configure("muted", foreground=MUTED, font=("Segoe UI", 9))
        self._append_chat("assistant", "AURIX", "Ready. Choose a project folder, configure an AI provider, then describe the outcome you want. I will inspect, use available tools, and verify where possible.")

        activity_header = tk.Frame(main, bg=BG)
        activity_header.pack(fill="x", pady=(13, 6))
        tk.Label(activity_header, text="LIVE ACTIVITY", bg=BG, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(side="left")
        self.activity = tk.Text(main, bg=PANEL, fg=MUTED, height=5, state="disabled", relief="flat", wrap="word", padx=12, pady=8, font=("Consolas", 8))
        self.activity.pack(fill="x")
        composer = tk.Frame(main, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        composer.pack(fill="x", pady=(12, 0))
        self.prompt = tk.Text(composer, bg=PANEL, fg=FG, insertbackground=FG, height=3, relief="flat", wrap="word", padx=14, pady=12, font=("Segoe UI", 10))
        self.prompt.pack(side="left", fill="both", expand=True)
        self.prompt.bind("<Control-Return>", self._shortcut_send)
        buttons = tk.Frame(composer, bg=PANEL)
        buttons.pack(side="right", fill="y", padx=10, pady=10)
        self.run_button = self._button(buttons, "Run task", self._start_task, primary=True)
        self.run_button.pack(fill="x")
        self.cancel_button = self._button(buttons, "Stop", self._cancel_task, subtle=True)
        self.cancel_button.pack(fill="x", pady=(8, 0))
        tk.Label(main, text="Ctrl + Enter to run · Changes and test execution require explicit opt-in", bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(6, 0))

    def refresh_provider_label(self):
        self.config_data = load_config()
        providers = enabled_providers(self.config_data)
        active = self.config_data.get("active_provider")
        chosen = next((p for p in providers if p.get("name") == active), providers[0] if providers else None)
        if chosen:
            self.provider_label.configure(text=f"{chosen.get('name')}\n{chosen.get('model')}")
        else:
            self.provider_label.configure(text="Not configured · add a provider")

    def _choose_workspace(self):
        selected = filedialog.askdirectory(initialdir=self.workspace.get(), title="Choose AURIX workspace")
        if selected:
            self.workspace.set(selected)
            self._activity("workspace", f"Workspace set to {selected}")

    def _open_settings(self):
        ProviderSettings(self)

    def _append_chat(self, role, label, content):
        self.chat.configure(state="normal")
        stamp = datetime.now().strftime("%H:%M")
        tag = "user" if role == "user" else "assistant"
        self.chat.insert(tk.END, f"{label}  ·  {stamp}\n", tag)
        self.chat.insert(tk.END, content.strip() + "\n\n", "body")
        self.chat.configure(state="disabled")
        self.chat.see(tk.END)

    def _activity(self, kind, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.activity.configure(state="normal")
        self.activity.insert(tk.END, f"{stamp}  {kind.upper():<9} {message}\n")
        lines = int(self.activity.index("end-1c").split(".")[0])
        if lines > 70:
            self.activity.delete("1.0", f"{lines-70}.0")
        self.activity.configure(state="disabled")
        self.activity.see(tk.END)

    def _clear_chat(self):
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("Task running", "Stop the current task before clearing chat.", parent=self)
            return
        self.chat.configure(state="normal")
        self.chat.delete("1.0", tk.END)
        self.chat.configure(state="disabled")
        self.history = []
        self._append_chat("assistant", "AURIX", "Chat cleared. Workspace and settings are unchanged.")

    def _shortcut_send(self, _event):
        self._start_task()
        return "break"

    def _start_task(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Task running", "Current task is still running. Use Stop before starting another.", parent=self)
            return
        task = self.prompt.get("1.0", "end-1c").strip()
        if not task:
            return
        self.config_data = load_config()
        if not enabled_providers(self.config_data):
            messagebox.showwarning("Configure provider", "Open Provider settings and configure at least one enabled provider with a compatible endpoint/model and API key.", parent=self)
            self._open_settings()
            return
        self.prompt.delete("1.0", tk.END)
        self._append_chat("user", "YOU", task)
        self.status.set("Working")
        self.run_button.configure(state="disabled")
        self.cancel_event = threading.Event()
        if not hasattr(self, "history"):
            self.history = []
        task_history = list(self.history)
        self.history.append({"role": "user", "content": task})
        # Capture Tk variables on the UI thread; background threads should not call Tcl/Tk.
        workspace_path = self.workspace.get()
        allow_writes = self.allow_writes.get()
        allow_execution = self.allow_execution.get()
        config_snapshot = self.config_data

        def worker_body():
            try:
                agent = AURIXAgent(
                    config=config_snapshot,
                    workspace=workspace_path,
                    allow_writes=allow_writes,
                    allow_execution=allow_execution,
                    event=lambda kind, message: self.events.put((kind, message)),
                    cancel=self.cancel_event,
                )
                answer = agent.run(task, history=task_history)
                self.events.put(("answer", answer))
                self.history.append({"role": "assistant", "content": answer})
            except (AgentError, OSError, ValueError) as exc:
                self.events.put(("error", str(exc)))
            except Exception as exc:
                self.events.put(("error", f"Unexpected error: {type(exc).__name__}: {exc}"))
            finally:
                self.events.put(("idle", "Ready"))

        self.worker = threading.Thread(target=worker_body, daemon=True, name="aurix-agent")
        self.worker.start()

    def _cancel_task(self):
        if self.cancel_event and self.worker and self.worker.is_alive():
            self.cancel_event.set()
            self._activity("control", "Cancellation requested; any current network request may finish before stopping.")

    def _poll_events(self):
        try:
            while True:
                kind, message = self.events.get_nowait()
                if kind == "answer":
                    self._append_chat("assistant", "AURIX", message)
                elif kind == "error":
                    self._append_chat("assistant", "AURIX · ERROR", message)
                    self._activity("error", message.replace("\n", " · ")[:500])
                elif kind == "idle":
                    self.status.set("Ready")
                    self.run_button.configure(state="normal")
                else:
                    self._activity(kind, message)
                    if kind == "complete":
                        self.status.set("Completed")
                    elif kind in {"thinking", "tool"}:
                        self.status.set("Working")
        except queue.Empty:
            pass
        self.after(120, self._poll_events)


def main():
    app = AURIXWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
