#!/usr/bin/env node
/*
 * fedora-hat — npx-ready launcher.
 *
 * Runs the actual python3 persona agent (agents/fedora/agent.py) as a child process,
 * exactly as the repo documents: same file, same protocol, same permissioned writes.
 * python3 must be on PATH; if it is not, the error says so instead of pretending.
 */
const { spawn } = require("child_process");
const path = require("path");

const agent = path.join(__dirname, "..", "agents", "fedora", "agent.py");
const child = spawn("python3", [agent, ...process.argv.slice(2)], { stdio: "inherit" });

child.on("error", (err) => {
  console.error("fedora-hat needs python3 on PATH (" + err.message + ").");
  process.exit(1);
});
child.on("exit", (code) => process.exit(code === null ? 0 : code));
