# ai-relayteam

**Switch AIs, work continues. Multiple AIs collaborate.**

> A handoff notebook that lives inside your project. Whichever AI you switch to, however many new windows you open, however long you've been away — the AI opens the project and knows where things stand, what comes next, and what it must not touch. You just make the calls.

---

## Sound familiar?

- **You ran out of quota.** You finally explained the task to Claude, then the quota ran out. You switch to Codex and explain everything again.
- **New window, total amnesia.** What was done yesterday, why a decision was made, which ideas were already rejected — the AI remembers none of it.
- **You became the messenger.** One AI writes the plan, another does the work, and you copy-paste between them all day. It's more tiring than doing it yourself.
- **The AI oversteps.** You said "continue" and it started rewriting code, committing, even deleting files.

All of these have the same root cause: **the state of your work lives only in chat history and the AI's head.** Change the chat, and the state is gone.

## What it is

In one sentence: **move "where the work stands" out of chat history and into a few files inside your project.**

Like nurses writing a handover note at shift change, or a building site keeping a daily log — whoever takes over doesn't need to ask the last person. They open the notebook and carry on. AI works the same way:

| File | Think of it as | What goes in it |
| --- | --- | --- |
| `AGENTS.md` | **The house rules** | Who leads, who does the work; how to hand over; what must be asked first (spending money, deleting, publishing) |
| `HANDOFF.md` | **The handover notebook** | What's in progress, how far it got, and **the one next step** |
| `STATUS.md` | **The report card** | What's actually done and the evidence for it; what isn't done yet |

Mainstream AI coding assistants read `AGENTS.md` automatically when they open a project (it's an open convention; Claude Code reads it through a one-line `CLAUDE.md`). So you don't have to explain anything each time — the AI looks it up itself.

## Before and after

| Before | After |
| --- | --- |
| Switch AIs, explain the task from scratch | The new AI reads the notebook and tells you where things stand and what's next |
| The AI wades through pages of history to catch up | The notebook only covers "now" — a few pages is enough (in our own project, what a new AI has to read dropped from about 311 KB to about 12 KB, 96% less) |
| You copy-paste between two AIs | The lead AI hands work to the worker AI directly, collects the result, checks it, then reports to you |
| Say "continue" and the AI starts changing things | "Continue" only asks for a status report; nothing happens until you say go |
| The lead AI runs out of quota and work stops | Another AI steps in as acting lead under the rules; when the original lead returns, it reviews what changed before taking back over |

## Three ways to use it

**① One AI (most people start here)**
You normally use one AI coding assistant — Claude Code, Codex, WorkBuddy, or another. With the notebook in place, you can switch windows or come back days later and pick up where you left off, no re-explaining.

**② One lead + one worker**
For example: **Claude as lead** (plans, splits tasks, checks results) + **Codex as worker**. Claude hands work to Codex in the background, checks what comes back, then reports to you — no copy-pasting. Clear division of labour, and it saves quota.
Every report starts with who is speaking (e.g. "Claude, lead: …"), so you always know who's in charge.

**③ Several workers**
Put them in order. If the first one runs out of quota or fails, the lead switches to the next one under the rules — and tells you who it switched to and whether anything cost money.

Which mode, and who leads, is one line in `AGENTS.md`. Change it any time.

## Install with one sentence (no coding needed)

First **open your project folder** in your AI coding assistant (for a new project, create an empty folder and open that), then send it this:

```text
Following https://github.com/clarkzoe2026-a11y/ai-relayteam/blob/main/INSTALL.md, install the handoff notebook into my current project.
```

The AI does the rest: it downloads the templates, reads your project to work out where things stand, then asks you just two or three questions (which AI, your preferences, whether its guess about your progress is right), fills everything in, and shows you the result to confirm. It won't overwrite files you already have.

After that, whichever AI or window you use, just say "continue". When a piece of work is done, have the AI write the progress back into `HANDOFF.md`.

<details>
<summary>Prefer to do it by hand? (manual install)</summary>

1. On this page, click the green "Code" button → "Download ZIP", then unzip.
2. Copy the 5 files in the `templates-en` folder into your project folder.
3. Open `AGENTS.md`: under "Current setup" write which AI you use, and replace "User preferences" with your own habits. Open `HANDOFF.md`: replace the example with your project's real goal, progress and next step.
4. Open the project in your AI and say "continue".

</details>

## Two optional tools

Everything works without them. They just give you more peace of mind:

- **Leak guard**: before every commit, checks who the commit is attributed to, so your real name or personal email doesn't end up online.
- **Automatic progress backup**: whenever the notebook changes, it syncs to your own GitHub. If your computer dies or you switch machines, your progress is still there. macOS only for now.

How to install: [Leak guard](docs/en/identity-guard.md) and [Automatic progress backup](docs/en/sync.md).

## Being straight with you

- **It's a method plus two small tools, not software that runs by itself.** It works because AIs read the files and follow the rules. Mainstream AI coding assistants mostly do, but AIs do make mistakes now and then — which is why every important action is designed to ask you first.
- **What we've tested**: Claude Code as lead with Codex as worker. Other combinations (Codex as lead, or other AIs) should work under the same rules but haven't been tested yet. See [modes](docs/en/modes.md) and [dispatching work](docs/en/dispatch.md).
- **One-sentence install** was tested with Codex and WorkBuddy: they read the project, asked everything in one round, installed the 5 files without overwriting anything or committing on their own, and a new window picked up correctly after "continue". After publishing, we ran it once more straight from the public URL (Codex downloading the templates from GitHub), and it passed again.
- Automatic progress backup is macOS only for now.
- **English templates and docs are available.** The templates are in `templates-en/`, and the docs are in `docs/en/`. During installation, the AI chooses templates based on the language you use.
- This comes from our own daily work: we used it on our own projects, hit the snags, then wrote it up to share.

## FAQ

**Do I need to know how to code?**
No. Send one sentence to your AI and it's installed. The two optional tools can be installed by your AI too.

**Which AIs does it work with?**
Any AI coding assistant that reads these files in your project. Codex and others read `AGENTS.md` natively; Claude Code reads it through a one-line `CLAUDE.md`. Tested: Claude Code and Codex, all modes. WorkBuddy was tested too: one-sentence install worked, and in a new window "continue" made it read the rules and notebook, state who it is, and wait for your go-ahead (WorkBuddy's own memory folder was present, so its help can't be fully ruled out; if it ever skips the rules, start with "read AGENTS.md first").

**Does it cost extra?**
The kit itself is free (MIT licence). Your AIs use your own plans as usual. The rules state that anything that would cost money must be asked about first.

**Will my project be uploaded anywhere?**
No. Everything stays on your computer and in your own repository. Only if you install the automatic progress backup are the progress files synced — to your own GitHub.

**How is this different from an AI's built-in "memory"?**
Built-in memory lives inside that one AI. Switch AIs and it's gone, and you can't see what it remembered. The notebook is plain files in your project: you can read them, edit them, and any AI can use them.

## Related projects

We're not the only open-source project working on this. Each has its strengths — pick what fits:

| Project | What it does | How it differs from ai-relayteam |
| --- | --- | --- |
| [agent-handoff-kit](https://github.com/Adamchanadam/agent-handoff-kit) | A "session baton": writes progress, decisions and next steps into project files so different AIs can carry on across chats; adds commands and a dashboard | Focused on continuity, more features, needs Node.js |
| [relay-between-agents](https://github.com/Gwendolenmave/relay-between-agents) | One AI plans, another builds, and the human stops copy-pasting between them | Focused on the collaboration half |
| [agent-baton](https://github.com/codeprakhar25/agent-baton) | Watches Claude Code / Codex quota, warns before the limit and writes a handoff automatically | Focused on the moment quota runs out; installs an npm package |
| [tagteam](https://github.com/cephalopod-ai/tagteam) | Runs several coding agents from one command: a supervisor briefs and reviews, a worker implements, looping until it passes | A CLI program you run in the terminal |

**What's different about ai-relayteam**: continuity across AIs and collaboration among AIs live in one set of rules; there are explicit rules for an acting lead when the lead runs out of quota, and for handing back; nothing to install — copy 5 text files and go.

## Docs

- [Choosing and filling in a mode](docs/en/modes.md)
- [How the lead hands work to other AIs](docs/en/dispatch.md)
- [Handover rules: when an AI is unavailable](docs/en/handover.md)
- [Working on several projects at once](docs/en/multi-project.md)
- [Provenance: telling "actually done" from "the AI says it's done"](docs/en/provenance.md)

中文说明：[README.md](README.md)

Licence: [MIT](LICENSE) — free to use, modify and share.
