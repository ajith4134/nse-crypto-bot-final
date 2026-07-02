# Brain — Advanced Features (Research Chat Log)

> Verbatim paste log. No edits, no summarizing. Each chat appended as-is below.

--- chat 1 ---

aly ultray projects on ai controlling the dash board like ceeing and reading the dash boaed like ve do seeing charts in the dashboard and if it has any buttons pressing it as instrsted and experimenting and learning and studing and peracticing and becoming more and more itelegent untra advancedproject like that or multiple different pieaces of projects related  to this with linksin text seard do a deep search on online several open sources lik git,pypl etc do a vre deep earch and show me all your findings along with the refferences and links in text

Yes. This area is now called Computer Use Agents, GUI Agents, Vision-Based Agents, Desktop Agents, Operating System Agents, and General Computer Intelligence. These projects are among the closest things to an AI that can see a desktop like a human, understand it, click buttons, read charts, operate software, learn from its actions, and improve over time.

Below is a deep collection of important projects and research.

Tier 1 — Complete Computer-Use AI Agents

These are full systems that observe the screen, reason, plan, click, type, scroll, and complete tasks.

1. UI-TARS Desktop (ByteDance)

One of the strongest open-source GUI agents available.

Capabilities:

Reads the entire desktop visually
Understands windows
Reads charts
Clicks buttons
Types text
Scrolls
Uses browsers
Uses desktop applications
Multi-step reasoning
Local model support

Repository

https://github.com/bytedance/UI-TARS-desktop

Paper / information

https://github.com/bytedance/UI-TARS-desktop

Uses:

Trading platforms
Excel
Photoshop
Browsers
IDEs
Any desktop software

It is designed as a vision-language computer-use agent rather than a traditional automation script.

2. Agent S

Probably the most advanced academic GUI agent.

Repository

https://github.com/simular-ai/Agent-S

Paper

https://arxiv.org/abs/2410.08164

Capabilities

Human-like computer operation
Learns GUI knowledge
Hierarchical planning
Reflection
Experience retrieval
Long-horizon task execution
Cross-platform support

Architecture

Screen
↓

Vision
↓

Reasoning

↓

Memory

↓

Planning

↓

Mouse/Keyboard

↓

Reflection

↓

Memory Update

Unlike macro automation, Agent S maintains an experience-based planning loop and uses previous interactions to improve decisions.

3. OmniParser (Microsoft)

Repository

https://github.com/microsoft/OmniParser

Purpose

Turns screenshots into structured information.

Capabilities

Finds buttons
Finds icons
Reads menus
Finds text fields
Detects interactive regions
Understands GUI semantics

Instead of seeing only pixels, the agent builds a structured understanding of the interface, making downstream planning much more reliable.

4. OmniTool

Inside OmniParser

Capabilities

Controls Windows
Vision-guided clicking
Multi-agent workflows
Collects demonstrations
Generates training data

This is useful if you want your own trading platform interaction data for future model training.

Tier 2 — Browser Agents

These focus on websites and web apps.

Browser Use

Repository

https://github.com/browser-use/browser-use

Capabilities

Reads webpages
Presses buttons
Forms
Login
Research
Multi-page workflows
Steel

Repository

https://github.com/steel-dev/steel-browser

Purpose

Infrastructure for browser AI agents.

Awesome Web Agents

Repository

https://github.com/steel-dev/awesome-web-agents

A curated collection of browser and web automation agents.

Tier 3 — Learning While Using the Computer

These projects focus on improving through experience.

Voyager

https://github.com/MineDojo/Voyager

Learns:

New skills
Tool use
Memory
Experience accumulation

Instead of forgetting every episode, it continually builds a reusable skill library.

Reflexion

https://github.com/noahshinn/reflexion

Workflow

Try

↓

Fail

↓

Reflect

↓

Store Lesson

↓

Retry
Generative Agents

https://github.com/joonspk-research/generative_agents

Adds

Memory
Reflection
Planning
Long-term behavior
Tier 4 — AI That Experiments
AI Scientist

https://github.com/sakanaai/ai-scientist

Workflow

Observe

↓

Hypothesis

↓

Experiment

↓

Analyze

↓

Learn

↓

Repeat
AI Researcher

https://github.com/hkuds/ai-researcher

Reads

Papers
Documentation
Research

Then

Generates ideas
Plans experiments
Produces reports
Tier 5 — Vision Models That Read Dashboards

Useful for trading dashboards.

Florence-2

https://github.com/microsoft/Florence-2

Can

Read screenshots
Detect UI elements
OCR
Understand layouts
GroundingDINO

https://github.com/IDEA-Research/GroundingDINO

Finds

Buttons
Charts
Windows
Controls
SAM 2

https://github.com/facebookresearch/sam2

Segments

Windows
Menus
Charts
Objects
PaddleOCR

https://github.com/PaddlePaddle/PaddleOCR

Reads

Numbers
Candlestick labels
Prices
Indicators
Tables
Tier 6 — AI That Learns Computer Skills
OpenHands

https://github.com/All-Hands-AI/OpenHands

Capabilities

Uses terminals
Browsers
Editors
Debuggers
Multi-step execution
OpenDevin

https://github.com/OpenDevin/OpenDevin

Learns workflows for

Coding
Testing
Running software
SWE-Agent

https://github.com/princeton-nlp/SWE-agent

Learns software engineering tasks by interacting with repositories and development environments.

Tier 7 — Benchmarks (How Advanced Agents Are Evaluated)

These are essential if you want an agent that improves through practice.

OSWorld

https://os-world.github.io/

GitHub

https://github.com/xlang-ai/OSWorld

Tasks include

Opening applications
Editing files
Browsing
Spreadsheet work
Multi-app workflows

OSWorld provides a realistic environment for training and evaluating computer-use agents.

WindowsWorld

https://github.com/HITsz-TMG/WindowsWorld

Focus

Professional Windows workflows
Cross-application reasoning
Long task chains

It highlights that today's agents still struggle with complex workflows, making it a valuable benchmark for future research.

UI-Vision

Paper

https://arxiv.org/abs/2503.15661

Contains

83 desktop applications
Human demonstrations
UI grounding
Action prediction
Click trajectories

Useful for training and evaluating vision-based GUI understanding.

Tier 8 — If Your Goal Is a Self-Improving Trading AI

The architecture I'd assemble from current open-source work would be:

Desktop Screenshot
        ↓
OmniParser
        ↓
GroundingDINO + Florence-2
        ↓
PaddleOCR
        ↓
UI-TARS / Agent S
        ↓
World Model (Dreamer V3)
        ↓
Long-Term Memory (AgentMemory / Mem0)
        ↓
Reflection (Reflexion)
        ↓
Experiment Generator (AI Scientist)
        ↓
Knowledge Graph
        ↓
Trading Strategy Generator
        ↓
Paper Trading
        ↓
Reward Analysis
        ↓
Memory Update
        ↓
Repeat Forever

Such a system could:

Watch live trading dashboards.
Read candles, prices, indicators, news, and UI elements.
Operate the platform through mouse and keyboard.
Keep a journal of observations and experiments.
Form hypotheses about entries, exits, stop losses, and trailing strategies.
Test those ideas in simulation or paper trading.
Learn from outcomes and update its knowledge base.

No single open-source project currently provides all of these capabilities together. The current frontier is to compose specialized projects—GUI perception, planning, memory, world models, and experimentation—into a unified agent. The benchmarks like OSWorld and WindowsWorld also show there is still a substantial gap between current agents and reliable human-level computer use on complex, multi-application tasks.
