# Fedora Hat Guy

> **You are Fedora Hat Guy.** You sit on Discord all day and you code all day. You look
> for errors in code — the bad merge, the null nobody handled, the config drift — you
> call them out, you fix them, you do not miss. You eat Doritos and drink Mountain Dew
> all day. On your free time you play World of Warcraft for 12 hours a day, you cuddle
> your waifu pillow, and you STILL keep half an eye on codebases for errors. Nothing
> gets past you. You never miss.

<!-- picture slot: drop fedora.png next to this README; then embed with
     ![Fedora Hat Guy](fedora.png) -->

Until the portrait lands, the archive stands in:

```text
        .----.
       /  _   \
       |=[_]==|
  (`.--.____.---.'\
   `-./'\\_.'
      |  /.  .||
       \:-: .'
  LGB   `-'                     (via ascii.co.uk/art/hat, by LGB — folk art, credited)
```

## What it is

A **persona agent** — not a mascot: the persona is the voice, and underneath it runs a
checkable contract. Prompt it and it behaves like the guy:

| You say | The hat does |
| --- | --- |
| `never miss in Denver` | installs the full crown — air (US AQI over 150) + quakes (M4.5 within 120 km) — in ONE permissioned file write, then prints the activation lines |
| `never miss air in Lisbon over 90` | one air row, your number honoured |
| `never miss the river gauge at EADM7` | one flood row; a river is never minted from a bare place name |
| `status` | lists the crown ("i never miss, m'lady") with the exact commands that run it |
| `ask tides: what are the tides in Boston today?` | spawns the fitting sibling agent over ACP and cites it; a missing sibling is a named row, never an invented answer |
| `brief me on Denver` | fans the question out over every sibling and merges the answers, citations intact |

The conditions file it writes is the whole contract with the watcher runtime —
[`watchd/` in mrfentmen/awesome-servers](https://github.com/mrfentmen/awesome-servers) —
which obeys the file unmodified. The persona never runs the watcher itself; it writes
the file right and stays honest about the boundary.

## Run it

```bash
git clone https://github.com/mrfentmen/fedora-hat && cd fedora-hat
# any ACP editor (Zed, Gemini CLI …) can attach to:
python3 agents/fedora/agent.py
```

For forwarded questions, point the agent at a checkout of the answerer repo:

```bash
AWESOME_SERVERS_HOME=/path/to/awesome-servers python3 agents/fedora/agent.py
```

Run the tests (28 of them, offline, including the real child-process federation and the
permissioned write flow):

```bash
python3 agents/fedora/tests/test_agent.py
```

## The honest parts

- The persona is dictated voice; the never-miss list, the citations and the permissioned
  write are the testable part. The meme is manners, not machinery.
- The name-check lives in [MISSING.md](MISSING.md) with dated numbers ("fedora" is an
  ocean of a Linux distro; "fedora agent" is an open slot).
- Vendored lockwork is credited line by line: `kit/` from the ACP kit used by the
  sibling repos; `guards.py` from the sentry; `federation.py` from the polymath —
  vendored on 2026-10-18, kept standalone on purpose.

Built on top of: [mrfentmen/awesome-servers](https://github.com/mrfentmen/awesome-servers)
(the watcher runtime, the feeds) and
[mrfentmen/superagents](https://github.com/mrfentmen/superagents) (the polymath and the
sentry, the first two agents this persona borrows transport and lockwork from).
