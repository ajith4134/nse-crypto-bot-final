# vp4 — "Recursive Self-Improvement (RSI) for agents" — Dennis Yu whiteboard (videoplayback (4).mp4, 19:20)

## One-paragraph summary
Dennis Yu ("marketing mechanic") gives a whiteboard framework for **Recursive
Self-Improvement of AI-agent workforces**: prototype a task with a browser-side agent
(Claude in Chrome), distill it into a **skill.md**, embed that in a **"definitive
article"** (canonical how-to for the task) only after ≥3 successful human-supervised
cycles; move it to a persistent runtime (**Cowork** on an always-on machine) where a
LIBRARY of skill files call/trigger one another (time triggers like a weekly "fleet
audit", or agent-done triggers); every execution writes a **"meta article"** (the agent's
own notes: what it did, edge cases, cost in tokens); executions increment a per-agent
track record (the "thousand-task library": agent A₁ 1000 runs, A₂ 200, A₃ 50), and meta
articles feed back into the definitive article — the **self-learning loop** = RSI. Mature,
proven agents then graduate to a cloud-hosted **"Upwork of agents"** marketplace with
per-task pricing (cost in tokens vs value; Costco pricing), where the accumulated track
record and proof — not the code — is the moat.

## Every distinct idea (timestamp + whiteboard refs)
1. **RSI definition** [00:00]: take something you've done, make agents repeat and learn
   from themselves so they improve without you watching. (Anthropic: 8× more code than a
   few quarters ago via RSI [00:18].) Doing this builds a compounding advantage [00:29].
2. **Prototype in the browser first** [01:25–02:18]: Claude-in-Chrome-style side
   assistant, already logged in to WordPress/CRM; demonstrate the task; record actions
   ("watch and train") or feed Zoom transcripts — this **creates skills**.
3. **skill.md → definitive article** [02:18–02:57, board: Claude-in-Chrome → skill.md →
   definitive article]: the skill file for a task gets embedded in a "definitive article"
   = "this is how you get this task done"; everything persists to files (Obsidian, local,
   Google Docs).
4. **Rule of three** [02:57–03:17, board "3" loop]: only after ≥3 supervised cycles do you
   trust it — repetition surfaces edge cases and hones inputs. Don't scale (jump to
   Cowork) before the skill files are tuned — "you're just scaling something that isn't
   ready to be scaled" [07:57–08:10].
5. **Named, person-like agents** [03:17–04:41, board "Jennifer"]: Jennifer = article
   grader with her own logic + growing body of knowledge (repository of rules/content +
   tools she can call, e.g. ahrefs via MCP); Ethan = knowledge panels; Cam = positive
   comments. Treat agents like people: pay per task, monitor output, onboard them to more
   duties as they prove out. Agents are input→output workers acting on other systems
   (CRM, ads, calls), not chatbots [03:48].
6. **Cowork = persistence layer** [04:45–05:59, board CoWork/laptop]: browser sessions
   die; move to a runtime that stays alive on an always-on machine (MacBook Pro ≥24GB,
   amphetamine/no-sleep) — persistence = repeats without you present. (Mentions agent
   "memory and dreaming".)
7. **Skill libraries that call each other** [05:52–06:40]: many skill.md files; a
   checklist (build website: collect content → spin up site → design → landing page →
   ads → traffic) becomes a chain where each agent **triggers** the next.
8. **Triggers/scheduling** [06:51–07:43, board schedule/trigger]: time-based ("every
   Friday wake up and run a **fleet audit** across all sites"; Cam's daily
   positive-mentions sweep) or event-based ("I did my thing, now your turn").
9. **Meta articles = per-execution self-documentation** [08:10–09:09, board meta
   article]: "tell the agent: every time you do something, also take notes" — what it
   did, edge cases, **cost** (e.g. 5,000 tokens ≈ 3¢) vs **value** (human cost $5) —
   written to a persistent file database.
10. **Track records** [09:09–09:34, board A₁ 1000 / A₂ 200 / A₃ 50]: executions
    increment; agents with more reps are trusted more; the busiest agent (80/20) gets
    smartest and informs what you sell.
11. **The loop** [09:34–09:46]: meta articles (examples) are linked back into the
    definitive article → "this self-learning loop is how you create recursive
    self-improvement."
12. **Economics** [10:04–11:16, 13:21–14:11]: business = a collection of tasks with
    different values; document cost per task in tokens; price above cost, below human
    value (Costco pricing: charge $1 for what costs 1¢ and is worth $5); dynamic pricing
    as costs change.
13. **"Upwork of agents"** [11:16–13:21, board UpWork/Claude Code grid]: a two-sided
    marketplace of proven agents (manage via Claude Code); supply = your trained agents,
    demand = customers; better than SaaS subscriptions — agents hired per task; example:
    an appliance-repair CRM agent built for one company rented to similar companies.
    Don't release an agent until it's done the task enough times.
14. **Cloud graduation** [16:20–17:19]: marketplace needs payments/interface/independence
    from your laptop → move persistence from personal machine to AWS/cloud.
15. **Proof is the moat** [17:22–18:42]: publish the meta/definitive articles as
    blogs/videos, even open-source the skill.md — "you could take the skill file, but
    Jennifer's EXPERIENCE (thousands of documented runs) is something you don't have"
    (Facebook open-sources code, keeps data). Relationships + proof + customers = value.
16. **Break work into many single-purpose agents, not one Superman agent** [15:28–15:40]:
    otherwise "there's no loop, no clear path of improvement"; when one agent learns, all
    other agents automatically learn (shared files) [15:20–15:25]; SOP thinking — "what
    gets measured gets managed", agent-AI edition [15:46].

## Open questions
- None blocking (whiteboard scribbles like "flt audit" = fleet audit, "Agency" side-note
  are all explained by narration).
