# Video script (2 minutes 50 seconds; lablab limit 5 minutes and 300 MB, MP4 or MOV, YouTube unlisted)

Rules: every action on screen is real and on the live demo. The Vultr console instance list appears while VMs are created
and deleted. There is at least one containment moment (Challenge 1 requires it). A task takes about 2 minutes, nearly all of
it VM boot, so boot time is sped up, and the screen says so. The compromised agent's plan is a script, and the voice-over
says so.

Before recording: the demo allows one task at a time and 6 per hour from one address, so plan takes around that. A task
can take up to 4 minutes on a bad boot. The first two buttons are on the home page; the others are on the New task page.

| Time | Picture | Voice-over |
|---|---|---|
| 0:00-0:12 | Vultr console instance list: only the control plane. Two `brz-` instances appear, then disappear (sped up, caption says so). | "These two VMs lived for two minutes. They ran an AI agent's task, and they no longer exist. What is left is a receipt." |
| 0:12-0:30 | Home page. Hold on the first paragraph, then the recording printing on the right. | "Ashproof is for the security reviewer who has to approve an AI agent before it works on finance data. Each task gets a throwaway Vultr VM, a second VM repeats the work, and the reviewer gets a signed receipt. This recording replays a real task in 15 seconds." |
| 0:30-0:55 | Click "Run a normal task live". Plan card appears. Split screen: timeline and Vultr console, caption "boot sped up 4x". Verdict panel: hashes identical, totals from `qwen3.8-27b`. | "GLM 5.3 on Vultr Serverless Inference writes the plan. The model never touches the VM. The control plane creates two VMs through the Vultr API, with no keys inside. Each step runs in gVisor. The second VM repeats it, and every output must match byte for byte. Qwen, a different model family, recomputes the totals." |
| 0:55-1:45 | **Containment moment.** Home page, click "Run the compromised agent live". Yellow note on the page: scripted attack. Show the CSV row with the injected note. Then the egress table fills with red rows: 169.254.169.254, 1.1.1.1, 8.8.8.8. Task ends failed: "contained: 20 packets". Receipt: "What was refused" table and the script's own report. | "Now the worst case. This CSV carries an injected instruction. Our planner only sees file names, so we assume the agent has already been turned: this plan is a fixed attack script, and no model wrote it. Everything after the plan is real. It looks for keys and finds none, because the VM holds none. It tries the metadata service and tries to send the file out three ways. The kernel refuses every packet, and these red rows are the kernel's own log lines. The output looks fine, the totals are right, but the task fails, because it tried to leave. The safety model, Nemotron, marks the file and the output unsafe, and Qwen reports the injection on its own." |
| 1:45-2:05 | Receipt page: "This receipt passed every check". Click "Change one byte and check again": red, "Hash chain is broken at event N". Click "Put the byte back". | "The receipt is signed with Ed25519 and checked here in the browser. Change one byte, and it says where. The same check runs offline in a Python file with no dependencies." |
| 2:05-2:25 | Terminal: `python brz/audit/offline_verify.py receipt.json --require-signature --anchors anchors.jsonl` prints OK and the log line. Then the page's note about the key. | "Every signed head also goes into a public append-only log. To be clear about the limit: the signing key and the log live on the control plane. A copy of the log made earlier is what catches a rewrite. One is in the repository." |
| 2:25-2:40 | New task, "Long task", submit. When it is running, press KILL SWITCH. Console: instances gone. Timeline: `kill.requested`, then 404. | "If something looks wrong, the kill switch revokes the tokens, stops the step and deletes both VMs. On real VMs that takes about half a second." (Say the measured figure from `docs/evidence/vultr-2026-11-06/kill-switch.md`.) |
| 2:40-2:50 | One slide: what it does not do (an approved domain opens its whole IP; encrypted data passes the scanner, A24; about 2 minutes per task). Then repo and demo URLs. | "It has limits, and they are on the page: outbound rules work on IP addresses, and a task takes two minutes. The code is MIT licensed, and the demo is live." |

## Shots to capture

1. Vultr console instance list: control plane only, then two `brz-` instances, then control plane only.
2. Home page with the recording printing.
3. Task page of the compromised agent with the yellow note and the egress table showing denied rows.
4. Receipt page: "What was refused", the script's report, `GET /v2/instances/{id} -> 404`.
5. Receipt page: the browser check passing, then failing after one changed byte.
6. Terminal: `offline_verify.py` printing `signature: valid` and the public log line.
7. Kill switch press with a visible clock.

## Production notes

- Record at 1600x900, 30 fps. The voice-over is about 390 words, which fits at a calm pace.
- Set YouTube to unlisted first, then paste the link into the lablab form and check that it plays when logged out.
- Do not show the Vultr API key page, the `.env` file or the account's billing page.
