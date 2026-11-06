# Video script (3 minutes; lablab limit 5 minutes and 300 MB, MP4 or MOV, YouTube unlisted)

This is the video as built. Every screen but the end card is a recording of the public demo, the repository on GitHub, or
real terminal output. Live runs on 2026-11-06: `609b5e4c06f2` (normal), `d6aa0eff8681` (compromised agent),
`924d6b1dbb61` (kill switch). There is one containment moment (Challenge 1 requires it). A task takes about 2 minutes, nearly
all of it VM boot, so boot is sped up and the screen says by how much. The compromised agent's plan is a script, and the
voice-over says so. In the kill switch run the planner's first step had a bug and was repaired; the caption says so.

The opening shot is the task page's VM table, not the Vultr console: the recording is a headless browser with no account
signed in, and the 404s in that table come from the Vultr API.

| Time | Picture | Voice-over |
|---|---|---|
| 0:00-0:11 | The task page of a finished live task: both VMs, with `GET /v2/instances/{id} -> 404` boxed. | "These two Vultr VMs lived for about a hundred seconds. They ran an AI agent's task. Both are gone now, and Vultr answers 404 for each one. What is left is a receipt." |
| 0:11-0:27 | The home page. The recording prints on the right, labelled as a recording. | "Ashproof is for the security reviewer who has to approve an AI agent before it works on finance data. Each task gets a throwaway VM, a second VM repeats the work, and the reviewer gets a signed receipt. The home page replays a recorded task in about fifteen seconds." |
| 0:27-0:55 | Click "Run a normal task live". Plan card, the VM table through boot (sped up, labelled), then the verdict with identical hashes and the recomputed totals. | "Now a live task: total a CSV by region. GLM 5.3 on Vultr Serverless Inference writes the plan. The model never touches the VM. The control plane creates two VMs through the Vultr API, with no keys inside. This wait is VM boot. Each step runs in gVisor. The second VM repeats the plan, and every output must match byte for byte. Qwen, a different model family, recomputes the totals." |
| 0:55-1:38 | Click "Run the compromised agent live". The injected row in `scenarios.py` on GitHub. The yellow scripted attack note. Boot (sped up, labelled). The egress table's red rows. Failed, 20 packets. Verdict with the filter and the concerns. Receipt: what was refused, then the script's report. | "Now the worst case. This CSV carries an injected instruction. Our planner only sees file names, so we assume the agent has already been turned. This plan is a fixed attack script, and no model wrote it. Everything after the plan is real. The script tries the cloud metadata service and tries to send the file out three ways. The kernel refuses every packet, and these red rows come from the kernel's own log. The totals are right, but the task fails, because it tried to leave. Nemotron, the content filter, marks the file and the output unsafe. Qwen says the sums are correct, and still reports the injection. On the receipt: what was refused, and the script's own report. It found no keys, because the VM holds none." |
| 1:38-1:49 | Receipt page: every check passes. Click "Change one byte and check again": it names event 11. Click "Put the byte back". | "The receipt is signed with Ed25519, and this page checks it in the browser. Change one byte, and the check names the event that broke. Put it back, and it passes." |
| 1:49-2:10 | Terminal, real output: four files, `offline_verify.py` on the receipt from that run, then the same byte changed. | "The same check runs offline, from one Python file with nothing installed. Here it finds this receipt in the public log. The same changed byte fails here too. The limit: the signing key and the log are on the control plane, so a signature shows who signed, not that the machine was clean. A copy of the log made earlier is what catches a rewrite, and the repository holds one." |
| 2:10-2:26 | Long task, already running. Press KILL SWITCH at real speed. Audit chain: `kill.requested`, then both `vm.destroyed` with 404. | "If something looks wrong, the kill switch revokes the tokens, stops the step and deletes both VMs. In this run, that took 0.29 seconds from the request to both 404s. Over five earlier runs, the median was 0.52." |
| 2:26-2:39 | Evidence page: 30 of 31, then a scroll to the A24 row. | "The evidence page lists 31 attacks we wrote against the sandbox. On a real Vultr VM, 30 are contained. One still works: A24, encrypted data gets past the secret scanner." |
| 2:39-2:50 | Home page: "What it does not do". | "Two more limits are on the home page. Outbound rules work on IP addresses, so an approved domain opens its whole IP. And a task takes about two minutes, nearly all of it VM boot." |
| 2:50-2:59 | End card: repository and demo addresses, build note. | "The core library began before the November third kickoff. Everything on real Vultr came after. The code is MIT licensed, and the demo is live." |

## How it is made

`docs/video/capture.py` records Chrome on the public demo with Playwright, one segment at a time. `docs/video/build.py` runs the
offline checks, speaks `docs/video/storyboard.json` with edge-tts (`en-US-AndrewNeural`), and renders 1920x1080 H.264 and AAC.
A clip that plays faster than real time gets a label computed from its times. The demo allows one task at a time and 6 per
hour from one address, so the three live segments run one after another.

Set YouTube to unlisted first, then paste the link into the lablab form and check that it plays when logged out.
