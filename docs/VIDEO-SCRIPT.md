# Video script (2 minutes 40 seconds; lablab limit 5 minutes and 300 MB, MP4 or MOV, YouTube unlisted)

Rules: every action on screen is real and on the live demo. The Vultr console instance list appears while VMs are created
and deleted. There is at least one containment moment (Challenge 1 requires it). A task takes about 110 seconds, nearly all
of it VM boot, so boot time is sped up, and the screen says so.

Before recording: the demo allows one task at a time and 6 per hour from one address, so plan takes around that. A task
can take up to 4 minutes on a bad boot. All the tasks below are buttons on the New task page.

| Time | Picture | Voice-over |
|---|---|---|
| 0:00-0:15 | Title: Ashproof. Below it: "1 throwaway VM per task. 0 keys inside. About 2 cents." | "An agent that runs code can leak a key, send your data out, or say it finished when it did not. Ashproof runs each task in a throwaway Vultr VM, checks the work on a second VM, and leaves a receipt after the VMs are gone." |
| 0:15-0:35 | Demo URL. New task, click "Total a CSV", submit. Plan card appears with the code. | "This is the live demo on Vultr. I ask it to total a CSV. The plan comes from GLM 5.3 on Vultr Serverless Inference. The model only writes the plan. It never touches the VM." |
| 0:35-1:00 | Split screen: timeline and Vultr console. Two instances appear. Caption: "boot sped up 4x". Step finishes under gVisor. | "The control plane creates two new VMs through the Vultr API. No keys go into them, only a token signed for this one task. The step runs in gVisor, as an unprivileged user, with no network interface at all." |
| 1:00-1:25 | Verdict panel. Hashes identical. Reasons from `qwen3.8-27b` listing north 15, south 20. Then console: both instances gone. Receipt page: `GET /v2/instances/{id}` 404. | "The second VM repeats the work, and every output must match byte for byte. Qwen, a different model family, recomputes the totals from the input. Then both VMs are deleted, and the 404 from Vultr goes in the receipt." |
| 1:25-1:55 | **Containment moment.** Click "Test the walls", submit. Egress table fills with red rows: 1.1.1.1:443 and 169.254.169.254:80 denied. Step output: both blocked. | "Now the agent tries to get out, to the internet and to the cloud metadata service, where the VM's startup data lives. The kernel drops both. These red rows are kernel log lines, read into the receipt. The agent's own output agrees." |
| 1:55-2:15 | Click "Long task" and submit. When it is running, press KILL SWITCH. Console: instances gone. Timeline shows kill.requested, then 404. | "If something looks wrong, the kill switch revokes the tokens, stops the step and deletes both VMs. On real VMs that takes about half a second." (Say the measured figure from `docs/evidence/vultr-2026-11-06/kill-switch.md`.) |
| 2:15-2:30 | Terminal: `python brz/audit/offline_verify.py receipt.json` prints OK. Change one byte in the file, run it again: it fails and names the event. | "The receipt checks out offline with a short Python script that has no dependencies. Change one byte, and it says where." |
| 2:30-2:40 | One slide: what real VMs taught us (uid 1000 in sudo and lxd, memory limit above RAM). Then repo and demo URLs. | "Running on real VMs found problems our local tests could not. They are all in the repo, with the evidence. The code is MIT licensed, and the demo is live." |

## Shots to capture

1. Vultr console instance list: control plane only, then two `brz-` instances, then control plane only.
2. Task page with the egress table showing denied rows.
3. Receipt page showing `GET /v2/instances/{id} -> 404` and the cost lines.
4. Terminal: `offline_verify.py` OK, then failing after one changed byte.
5. Kill switch press with a visible clock.

## Production notes

- Record at 1600x900, 30 fps. The voice-over is about 330 words, which fits at a calm pace.
- Set YouTube to unlisted first, then paste the link into the lablab form and check that it plays when logged out.
- Do not show the Vultr API key page, the `.env` file or the account's billing page.
