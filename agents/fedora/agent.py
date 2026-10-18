"""Fedora Hat Guy: a persona agent who sits on Discord all day and never misses.

Yogi's brief, verbatim in spirit: you are Fedora Hat Guy — you sit on Discord all day,
code all day, find errors in code, eat Doritos, drink Mountain Dew, play World of
Warcraft for 12 hours a day on your free time, cuddle your waifu pillow, and STILL look
for errors in codebases. The persona is the voice; the contract is the checkable part:

    never miss in Denver      -> the full crown (air 150 + quakes M4.5 / 120 km), ONE
                                 permissioned fs/write_text_file, activation lines printed
    never miss air ... over N -> the air row with your number
    never miss the river gauge at EADM7 -> one flood row; a bare place never mints a gauge
    status                    -> what the crown watches, plus the activation lines
    ask <sibling>: question   -> forwarded over ACP to the fitting sibling, every row cited,
                                 a missing sibling named as a failure, never invented
    brief me on <place>       -> several siblings fanned out at once, merged with citations

The conditions file is the whole contract with the watcher runtime (watchd, in the
sibling repo) — the persona writes it, the watcher obeys it, and nothing private sits
between them. The vendored lockwork (kit, guards, federation) carries its credit lines:
this agent keeps its own home, not a copy of another agent's.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for path in (str(REPO / "kit"), str(Path(__file__).resolve().parent)):
    if path not in sys.path:
        sys.path.insert(0, path)

from acp_kit import STOP_END_TURN, STOP_REFUSAL, AcpAgent, SessionContext, prompt_text  # noqa: E402

import crown  # noqa: E402
import guards  # noqa: E402
import federation as fed  # noqa: E402
import persona as voice  # noqa: E402

FILENAME = "fedora-watchd-conditions.json"

WELCOME = voice.PREAMBLE + "\n" + (
    "What the persona does when you prompt it:\n"
    "  - never miss in Denver            (full crown: air 150 + quakes M4.5 within 120 km)\n"
    "  - never miss air in Lisbon over 90\n"
    "  - never miss quakes near Fresno within 50 mi, every 5 minutes\n"
    "  - never miss the river gauge at EADM7\n"
    "  - status                          (the crown, with the activation lines)\n"
    "  - ask tides: what are the tides in Boston today?   (forwarded, cited)\n"
    "  - brief me on Denver              (several siblings, one merge, every row cited)\n"
    "The watcher runtime that obeys the file lives at github.com/mrfentmen/awesome-servers "
    "(watchd/)."
)

_NEVER = re.compile(r"\bnever[- ]miss\b", re.I)
_STATUS = re.compile(r"\bstatus\b|\blist\b|\bwhat watch(?:es|ing)?\b|\bmy watch(?:es|ing)?\b", re.I)
_HELP = re.compile(r"^\s*(help|what can you do)\b", re.I)
_BRIEF = re.compile(r"\bbrief\b", re.I)
_CATALOG = re.compile(r"\bwhat siblings\b|\bcatalog\b|\bwho do you know\b", re.I)

PERMISSION_KEY = "fedora-write-crown"


def conditions_path(cwd: str) -> Path:
    return Path(cwd or ".") / "watches" / FILENAME


def route(text: str) -> tuple[str, dict]:
    """Deterministic routing: crown first, status next, federation last."""
    stripped = str(text or "").strip()
    if not stripped or _HELP.search(stripped):
        return "help", {}
    if _NEVER.search(stripped):
        return "never-miss", {"order": stripped}
    if _STATUS.search(stripped):
        return "status", {}
    if _CATALOG.search(stripped):
        return "catalog", {}
    pair = fed.ask_pair(stripped)
    if pair:
        return "ask", {"agent": pair[0], "question": pair[1]}
    if _BRIEF.search(stripped):
        place = fed.place_of(stripped)
        if place:
            return "brief", {"place": place, "topics": fed.topics_on(stripped)}
    ranking = fed.find_ranking(stripped)
    if ranking:
        return "ask", {"agent": ranking[0]["agent"], "question": stripped}
    return "help", {}


def _render_brief(place: str, rows: list) -> tuple[str, str]:
    """(body, summary) - cited rows; silent siblings named as rows, never invented."""
    body = [voice.tip(f"the brief on {place}, m'lady - "
                      f"{len([r for r in rows if r.ok and r.text])} of {len(rows)} answered:")]
    for row in rows:
        if row.ok and row.text:
            body.append("")
            body.append(f"[{row.agent}]")
            body.append(_clamp(row.text))
        else:
            body.append("")
            body.append(f"[{row.agent}] not answered: {row.error or 'refused'}")
    body.append("")
    body.append(voice.SOURCES)
    answered = len([r for r in rows if r.ok and r.text])
    return "\n".join(body), f"{answered}/{len(rows)} sibling answers"


def _clamp(text: str, lines: int = 4) -> str:
    rows = [line for line in (text or "").splitlines() if line.strip()]
    if not rows:
        return "(no answer)"
    if len(rows) <= lines:
        return "\n".join(rows)
    return "\n".join(rows[:lines]) + f"\n  ... +{len(rows) - lines} more line(s) from that agent"


class FedoraAgent(AcpAgent):
    name = "fedora"
    title = "Fedora Hat Guy - persona agent: Discord all day, finds errors in code, never misses"
    version = "1.0.0"

    def new_session(self, session) -> dict:
        session.remember("agent", voice.TIP)
        return {}

    def prompt(self, ctx: SessionContext, prompt: list[dict]) -> str:
        text = prompt_text(prompt)
        skill, params = route(text)
        cwd = Path(ctx.session.cwd or ".")
        target = conditions_path(str(cwd))
        ctx.plan([
            (f"Take the prompt as Fedora Hat Guy ({skill}) - never miss", "high"),
            ("Read the crown or ask the sibling - no inventing", "high"),
            ("Answer with the persona voice, citations intact", "medium"),
        ])

        if skill == "help":
            ctx.stream_text(WELCOME + "\n")
            return STOP_END_TURN

        if skill == "catalog":
            rows = "\n".join(f"  - {row['agent']}: {row['ask_example']}"
                             for row in fed.catalog_rows())
            ctx.stream_text(voice.tip("who i run with, m'lady:") + "\n" + rows
                            + "\n\n" + voice.SOURCES + "\n")
            return STOP_END_TURN

        if skill == "status":
            doc = self._load_doc(ctx, target)
            if doc is None:
                return STOP_END_TURN
            checks = doc.get("checks") or []
            if not checks:
                ctx.stream_text(voice.NOTHING_YET + "\n")
                return STOP_END_TURN
            activation = guards.activation_lines("watches/" + FILENAME,
                                                 int(checks[0].get("every_s", 300)))
            ctx.stream_text(voice.STATUS + "\n" + crown.describe(doc) + "\n\n"
                            "Run the watcher with any of:\n" + "\n".join(activation)
                            + "\nThe runtime obeys the file; the hat only wrote it right.\n")
            return STOP_END_TURN

        if skill == "never-miss":
            return self._never_miss(ctx, params["order"], target)

        if skill == "ask":
            call = "call_sibling"
            ctx.tool_call(call, f"Ask the {params['agent']} sibling", kind="run",
                          name="fedora-ask", raw_input=dict(params))
            ctx.tool_call_update(call, status="in_progress")
            try:
                row = fed.run_sibling(params["agent"], params["question"])
            except fed.SiblingError as exc:
                ctx.tool_call_update(call, status="failed",
                                     content=ctx.text_content(str(exc)[:200]))
                ctx.message(f"{voice.SIBLING_MISS} {exc}")
                return STOP_END_TURN
            if not row.ok or not (row.text or "").strip():
                ctx.tool_call_update(call, status="failed",
                                     content=ctx.text_content(row.error or "refused"))
                ctx.message(f"{voice.SIBLING_MISS} {row.error or 'refused'}")
                return STOP_END_TURN
            ctx.tool_call_update(call, status="completed",
                                 content=ctx.text_content(
                                     f"{row.agent}: stopReason={row.stop_reason or 'end-turn'}"))
            ctx.stream_text((row.text or "").rstrip() + "\n\n"
                            f"Source: the {row.agent} sibling over ACP.\n")
            return STOP_END_TURN

        # brief: several siblings at once, merged with citations
        call = "call_brief"
        ctx.tool_call(call, f"Brief {params['place']} across the siblings", kind="run",
                      name="fedora-brief", raw_input=dict(params))
        ctx.tool_call_update(call, status="in_progress")
        names = params["topics"] or sorted(fed.siblings())
        questions = {name: fed.sibling_question(fed.siblings()[name], params["place"])
                     for name in names}
        rows = fed.fan_out(questions)
        body, summary = _render_brief(params["place"], rows)
        ctx.tool_call_update(call, status="completed", content=ctx.text_content(summary))
        ctx.stream_text(body + "\n")
        return STOP_END_TURN

    def _never_miss(self, ctx: SessionContext, order: str, target: Path) -> str:
        try:
            entries = crown.crown_entries(order)
        except ValueError as exc:
            ctx.message(f"{voice.TIP} {exc}")
            return STOP_END_TURN
        try:
            doc = json.loads(guards.read_json(target))
        except ValueError as exc:
            ctx.message(f"{voice.TIP} the crown file is not JSON, so i touched nothing: {exc}")
            return STOP_END_TURN
        now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        merged, changed = crown.install(json.dumps(doc), entries, now)
        names = ", ".join(entry["name"] for entry in entries)
        relpath = target.relative_to(Path(ctx.session.cwd or ".")) \
            if target.is_relative_to(Path(ctx.session.cwd or ".")) else target

        write = "call_write_crown"
        capabilities = (ctx.client_capabilities.get("fs") or {}) if ctx.client_capabilities else {}
        can_write = bool(capabilities.get("writeTextFile"))
        ctx.tool_call(write, f"{changed.capitalize()} the crown: {names}",
                      kind="edit", name="fedora-write",
                      raw_input={"path": str(target), "checks": [e["name"] for e in entries]},
                      locations=[{"path": str(target)}])
        if not can_write:
            ctx.tool_call_update(write, status="failed",
                                 content=ctx.text_content("client advertises no filesystem write"))
            ctx.stream_text(voice.tip(voice.NO_FS) + "\n\n```json\n" + merged + "```\n\n"
                            + "\n".join(guards.activation_lines(str(relpath),
                                                                entries[0]["every_s"])) + "\n")
            return STOP_END_TURN

        ctx.tool_call_update(write, status="in_progress")
        if not ctx.ask_permission(write, f"Allow Fedora Hat Guy to {changed} the crown "
                                         f"({names}) at {target}?",
                                  remember_key=PERMISSION_KEY):
            ctx.tool_call_update(write, status="failed",
                                 content=ctx.text_content("permission denied"))
            ctx.message(voice.DENIED)
            return STOP_REFUSAL

        try:
            ctx.conn.request("fs/write_text_file",
                             {"sessionId": ctx.session.id, "path": str(target),
                              "content": merged}, timeout=30)
        except Exception as exc:  # editor refused/joined the dark side: nothing was written
            ctx.tool_call_update(write, status="failed",
                                 content=ctx.text_content(str(exc)[:160]))
            ctx.message(f"{voice.TIP} the editor refused the write ({exc}); nothing was saved "
                        "by me. The crown by hand:\n\n```json\n" + merged + "```\n")
            return STOP_END_TURN

        ctx.tool_call_update(write, status="completed",
                             content=ctx.text_content(f"wrote {target}"))
        activation = guards.activation_lines(str(relpath), entries[0]["every_s"])
        ctx.stream_text(voice.CROWNED + "\n" + f"  - {changed}: {names}\n"
                        "Run the watcher with any of:\n" + "\n".join(activation)
                        + "\nThe runtime obeys the file; the hat only wrote it right.\n")
        return STOP_END_TURN

    def _load_doc(self, ctx: SessionContext, target: Path) -> dict | None:
        try:
            return json.loads(guards.read_json(target))
        except ValueError as exc:
            ctx.message(f"{voice.TIP} the crown file is not JSON, so i show nothing: {exc}")
            return None

    def on_cancel(self, session) -> None:
        return None


def main(argv=None) -> int:
    logging.basicConfig(level="INFO", stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        FedoraAgent().run()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
