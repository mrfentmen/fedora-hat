"""Tests for Fedora Hat Guy: persona, crown rules, routing, federation, and the write flow.

    python3 agents/fedora/tests/test_agent.py

The federation tests run against real child processes over stdio (a tiny offline
responder built in this file), and the client tests run the actual agent process through
the kit client with a sandboxed fs_root. No network anywhere.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DIR = Path(__file__).resolve().parent
AGENT_DIR = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[3]
for path in (str(REPO / "kit"), str(AGENT_DIR), str(DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import agent  # noqa: E402
import crown  # noqa: E402
import federation as fed  # noqa: E402
import persona as voice  # noqa: E402

FAKE_SIBLING = r"""
import sys, json
def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n"); sys.stdout.flush()
def recv():
    return json.loads(sys.stdin.readline())
req = recv()  # initialize
send({"jsonrpc":"2.0","id":req["id"],"result":{"protocolVersion":1,"agentCapabilities":{},
      "authMethods":[],"agentInfo":{"name":"fake-sibling","title":"Fake","version":"1.0.0"}}})
while True:
    try:
        req = recv()
    except Exception:
        break
    method = req.get("method", "")
    if method == "session/new":
        send({"jsonrpc":"2.0","id":req["id"],"result":{"sessionId":"fake-session","modes":[]}})
    elif method == "session/prompt":
        text = "".join(b.get("text","") for b in req.get("params",{}).get("prompt",[]))
        send({"jsonrpc":"2.0","method":"session/update","params":{"update":{
            "sessionUpdate":"agent_message_chunk","content":{"type":"text",
            "text":"FAKE ANSWER for %r\nsecond line\n" % text}}}})
        send({"jsonrpc":"2.0","id":req["id"],"result":{"stopReason":"end-turn"}})
    elif method in ("session/cancel", "session/load"):
        continue
    else:
        send({"jsonrpc":"2.0","id":req.get("id"),"error":{"code":-32601,"message":"unhandled"}})
"""


class PersonaTests(unittest.TestCase):
    """Yogi's brief, pinned: the guy is the persona, the contract is checkable."""

    def test_preamble_starts_as_dictated(self):
        self.assertTrue(voice.PREAMBLE.startswith("You are Fedora Hat Guy."))

    def test_preamble_carries_the_whole_life(self):
        for word in ("Discord", "code", "Doritos", "Mountain Dew", "World of Warcraft",
                     "waifu", "12 hours", "never miss", "errors in code"):
            self.assertIn(word, voice.PREAMBLE)

    def test_the_persona_is_not_called_a_creature(self):
        self.assertIn("persona agent", agent.FedoraAgent.title)
        self.assertNotIn("creature", agent.FedoraAgent.title.lower())

    def test_welcome_offers_the_crown_and_siblings(self):
        for word in ("never miss in Denver", "status", "ask tides", "brief me on"):
            self.assertIn(word, agent.WELCOME)


class RouteTests(unittest.TestCase):
    def test_never_miss_words_route_first(self):
        self.assertEqual(agent.route("never miss in Denver")[0], "never-miss")
        self.assertEqual(agent.route("NEVER-MISS air in Lisbon")[0], "never-miss")

    def test_status_words(self):
        self.assertEqual(agent.route("status")[0], "status")
        self.assertEqual(agent.route("list my watches")[0], "status")

    def test_catalog_and_ask_and_brief(self):
        self.assertEqual(agent.route("what siblings do you have?")[0], "catalog")
        self.assertEqual(agent.route("ask tides: what are the tides in Boston?"),
                         ("ask", {"agent": "tides", "question": "what are the tides in Boston?"}))
        skill, params = agent.route("brief me on Denver")
        self.assertEqual((skill, params["place"]), ("brief", "Denver"))

    def test_unroutable_falls_back_to_help(self):
        self.assertEqual(agent.route("tell me a joke")[0], "help")
        self.assertEqual(agent.route("")[0], "help")


class CrownTests(unittest.TestCase):
    """The rules in crown.py, one per order shape."""

    def test_default_crown_is_air_plus_quakes(self):
        entries = crown.crown_entries("never miss in Denver")
        self.assertEqual([e["kind"] for e in entries], ["air", "quakes"])
        air, quakes = entries
        self.assertEqual(air["threshold"], 150.0)
        self.assertEqual(air["place"], "Denver")
        self.assertEqual(quakes["magnitude"], 4.5)
        self.assertEqual(quakes["radius_km"], 120.0)
        self.assertEqual(air["name"], "air-Denver")
        self.assertEqual(quakes["name"], "quakes-Denver")

    def test_no_quakes_trims_the_crown(self):
        entries = crown.crown_entries("never miss in Denver, no quakes")
        self.assertEqual([e["kind"] for e in entries], ["air"])

    def test_no_air_trims_the_crown(self):
        entries = crown.crown_entries("never miss in Denver, no air")
        self.assertEqual([e["kind"] for e in entries], ["quakes"])

    def test_named_air_honours_the_number(self):
        entries = crown.crown_entries("never miss air in Lisbon over 90")
        self.assertEqual([e["kind"] for e in entries], ["air"])
        self.assertEqual(entries[0]["threshold"], 90.0)

    def test_named_air_accepts_under(self):
        entries = crown.crown_entries("never miss air in Lisbon under 50")
        self.assertEqual(entries[0]["when"], "below")
        self.assertEqual(entries[0]["threshold"], 50.0)

    def test_named_quakes_convert_miles_and_honour_magnitude(self):
        entries = crown.crown_entries(
            "never miss quakes within 50 mi around Fresno, every 5 minutes over 6")
        quake = entries[0]
        self.assertEqual(quake["kind"], "quakes")
        self.assertAlmostEqual(quake["radius_km"], 80.5, places=1)
        self.assertEqual(quake["magnitude"], 6.0)
        self.assertEqual(quake["every_s"], 300)
        self.assertEqual(quake["name"], "quakes-Fresno")

    def test_quakes_refuse_under_floors(self):
        with self.assertRaises(ValueError) as caught:
            crown.crown_entries("never miss quakes within 50 mi of Fresno under 3")
        self.assertIn("floor is crossed", str(caught.exception))

    def test_flood_needs_an_explicit_gauge(self):
        with self.assertRaises(ValueError) as caught:
            crown.crown_entries("never miss the river at Sacramento")
        self.assertIn("gauge id", str(caught.exception))

    def test_flood_with_gauge_stands(self):
        entries = crown.crown_entries("never miss the river gauge at EADM7")
        self.assertEqual(entries[0]["gauge"], "EADM7")
        self.assertEqual(entries[0]["kind"], "flood")

    def test_place_is_required(self):
        with self.assertRaises(ValueError) as caught:
            crown.crown_entries("never miss")
        self.assertIn("needs a place", str(caught.exception))

    def test_install_merges_and_describe_renders(self):
        entries = crown.crown_entries("never miss in Denver")
        merged, changed = crown.install("{}", entries, "2026-10-18T00:00:00+00:00")
        self.assertEqual(changed, "added")
        doc = json.loads(merged)
        self.assertEqual(len(doc["checks"]), 2)
        text = crown.describe(doc)
        self.assertIn("air-Denver", text)
        self.assertIn("US AQI 150.0 above", text)
        self.assertIn("quakes-Denver", text)
        self.assertIn("every 5 min", text)


class BriefTests(unittest.TestCase):
    def test_brief_names_the_silent_sibling(self):
        air = fed.SiblingTurn("air")
        air.ok = True
        air.text = "US AQI 44 - Good\nrow2\nrow3\nrow4\nrow5\nrow6"
        moon = fed.SiblingTurn("moon")
        moon.error = "nothing was answered"
        body, summary = agent._render_brief("Denver", [air, moon])
        self.assertIn("1 of 2", body)
        self.assertIn("[air]", body)
        self.assertIn("+2 more line(s)", body)
        self.assertIn("[moon] not answered: nothing was answered", body)
        self.assertEqual(summary, "1/2 sibling answers")


class FederationChildTests(unittest.TestCase):
    """Real child processes over stdio, pointed at the offline responder."""

    def _with_fake(self, tmp: str):
        old = os.environ.get("POLYMATH_FAKE_SIBLING")
        os.environ["POLYMATH_FAKE_SIBLING"] = str(Path(tmp) / "fake_sibling.py")
        (Path(tmp) / "fake_sibling.py").write_text(FAKE_SIBLING)
        return old

    def _without_fake(self, old):
        if old is None:
            os.environ.pop("POLYMATH_FAKE_SIBLING", None)
        else:
            os.environ["POLYMATH_FAKE_SIBLING"] = old

    def test_real_child_spawn_and_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = self._with_fake(tmp)
            try:
                turn = fed.run_sibling("air", "Denver")
            finally:
                self._without_fake(old)
            self.assertTrue(turn.ok, turn.error)
            self.assertIn("FAKE ANSWER for 'how is the air quality in Denver right now?'",
                          turn.text)
            self.assertEqual(turn.stop_reason, "end-turn")

    def test_fan_out_collects_named_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = self._with_fake(tmp)
            try:
                rows = fed.fan_out({"air": "Denver", "moon": "Lisbon"}, timeout=30)
            finally:
                self._without_fake(old)
            self.assertEqual([row.agent for row in rows], ["air", "moon"])
            self.assertTrue(all(row.ok for row in rows), [row.error for row in rows])

    def test_unconfigured_home_is_an_honest_row_not_a_crash(self):
        old = os.environ.pop("POLYMATH_FAKE_SIBLING", None)
        home = os.environ.pop("AWESOME_SERVERS_HOME", None)
        try:
            turn = fed.run_sibling("air", "Denver")
        finally:
            if old is not None:
                os.environ["POLYMATH_FAKE_SIBLING"] = old
            if home is not None:
                os.environ["AWESOME_SERVERS_HOME"] = home
        self.assertFalse(turn.ok)
        self.assertIn("AWESOME_SERVERS_HOME", turn.error)


class ClientChildTests(unittest.TestCase):
    """The actual agent process, over ACP, with a sandboxed filesystem."""

    def _client_cls(self):
        from acp_kit import AcpClient
        return AcpClient

    def test_help_greets_as_the_persona(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = self._client_cls()(
                command=[sys.executable, str(AGENT_DIR / "agent.py")],
                permission="allow-once", fs_root=tmp, stderr=subprocess.DEVNULL)
            with client:
                client.initialize()
                session = client.new_session(cwd=tmp)
                turn = client.prompt("help", session_id=session)
                self.assertEqual(turn["stopReason"], "end_turn")
                self.assertTrue(turn["text"].startswith("You are Fedora Hat Guy."))
                self.assertIn("never miss in Denver", turn["text"])

    def test_never_miss_writes_one_file_through_permission(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = self._client_cls()(
                command=[sys.executable, str(AGENT_DIR / "agent.py")],
                permission="allow-once", fs_root=tmp, stderr=subprocess.DEVNULL)
            with client:
                client.initialize()
                session = client.new_session(cwd=tmp)
                turn = client.prompt("never miss in Denver", session_id=session)
                self.assertEqual(turn["stopReason"], "end_turn")
                self.assertIn("i never miss", turn["text"])
                self.assertEqual(len(client.permission_requests), 1)
                written = [w for w in client.written_files
                           if w["path"].endswith("fedora-watchd-conditions.json")]
                self.assertEqual(len(written), 1)
                doc = json.loads(written[0]["content"])
                self.assertEqual([c["name"] for c in doc["checks"]],
                                 ["air-Denver", "quakes-Denver"])
                self.assertIn("air-Denver", turn["text"])

    def test_status_after_install_lists_the_crown(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = self._client_cls()(
                command=[sys.executable, str(AGENT_DIR / "agent.py")],
                permission="allow-once", fs_root=tmp, stderr=subprocess.DEVNULL)
            with client:
                client.initialize()
                session = client.new_session(cwd=tmp)
                client.prompt("never miss air in Lisbon over 90", session_id=session)
                turn = client.prompt("status", session_id=session)
                self.assertIn("US AQI 90.0 above", turn["text"])
                self.assertIn("air-Lisbon", turn["text"])

    def test_status_on_empty_crown_is_honest(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = self._client_cls()(
                command=[sys.executable, str(AGENT_DIR / "agent.py")],
                permission="allow-once", fs_root=tmp, stderr=subprocess.DEVNULL)
            with client:
                client.initialize()
                session = client.new_session(cwd=tmp)
                turn = client.prompt("status", session_id=session)
                self.assertIn("nothing is installed yet", turn["text"])

    def test_ask_forwards_to_a_real_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = None
            fake_path = Path(tmp) / "fake_sibling.py"
            fake_path.write_text(FAKE_SIBLING)
            old = os.environ.get("POLYMATH_FAKE_SIBLING")
            os.environ["POLYMATH_FAKE_SIBLING"] = str(fake_path)
            try:
                client = self._client_cls()(
                    command=[sys.executable, str(AGENT_DIR / "agent.py")],
                    permission="allow-once", fs_root=tmp, stderr=subprocess.DEVNULL)
                with client:
                    client.initialize()
                    session = client.new_session(cwd=tmp)
                    turn = client.prompt("ask air: how is the air in Denver?",
                                         session_id=session)
            finally:
                self._without_fake(old)
            self.assertEqual(turn["stopReason"], "end_turn")
            self.assertIn("FAKE ANSWER for 'how is the air in Denver?'", turn["text"])
            self.assertIn("Source: the air sibling over ACP", turn["text"])

    def _without_fake(self, old):
        if old is None:
            os.environ.pop("POLYMATH_FAKE_SIBLING", None)
        else:
            os.environ["POLYMATH_FAKE_SIBLING"] = old


if __name__ == "__main__":
    unittest.main()
