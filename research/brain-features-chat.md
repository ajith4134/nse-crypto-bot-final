---
title: Brain Features Chat — Human-like Learning / Thinking / Self-Evolving Trading AI
source: pasted chat (research notes), to be used as input for implementation
saved: 2026-06-29
status: verbatim capture — do NOT treat as final spec; mine for features + OSS repos to stitch
---

# Brain Features Research Chat (verbatim)

> Captured exactly as pasted. This is the seed material for a future "human-like learning"
> brain + trading-intelligence build. Use it to extract: (a) the learn/observe/reflect/test
> loop, (b) the entry/direction/stoploss/profit-trailing learning targets, and (c) the OSS
> repos to evaluate and vendor.

---

i need you to search online on git hub projects on human like learning ,thinking researching keeping notes of what it learned or observed and try ing out what it learned and makei ai train or learn on picking entry price learn ,direction and stoploss and profit tail gating and etc

If your goal is to build an AI system that behaves more like a human trader or researcher, you will need to combine multiple categories of projects rather than relying on a single repository.

The closest architecture to "human-like learning and trading" would look like this:

Observe Environment
        ↓
Store Experiences and Notes
        ↓
Reflect on Successes and Failures
        ↓
Generate Hypotheses
        ↓
Test Hypotheses in Simulation
        ↓
Update Beliefs and Strategies
        ↓
Deploy Best Strategies
        ↓
Repeat Forever

This is very similar to how humans learn from experience and improve over time. Modern AI agent research calls this lifelong learning, agent memory, reflection, and self-evolving agents.

1. Human-like Memory and Learning Projects

These repositories focus on making agents remember, reflect, and improve.

Purpose    Repository
AI agent memory systems    https://github.com/TsinghuaC3I/Awesome-Memory-for-Agents
Long-term memory architectures    https://github.com/TeleAI-UAGI/Awesome-Agent-Memory
Self-evolving agents    https://github.com/EvoAgentX/Awesome-Self-Evolving-Agents
Agent research papers    https://github.com/VoltAgent/awesome-ai-agent-papers
Autonomous agent papers    https://github.com/luo-junyu/Awesome-Agent-Papers
AI agent ecosystem    https://github.com/jim-schwoebel/awesome_ai_agents

These systems provide:

Episodic memory
Semantic memory
Reflection memory
Skill memory
Experience replay
Failure memory
Long-term memory retrieval
Self-improvement loops

This is the closest thing currently available to human memory in AI agents.

2. Human-like Thinking Components

Humans don't immediately act.

They perform:

Observation
↓
Reasoning
↓
Planning
↓
Action
↓
Reflection

Your system should include:

Observation Layer
Market prices
Orderbook data
News
Funding rates
Open interest
Social sentiment
Correlations
Working Memory

Stores:

BTC breakout attempt failed at 106k.
Volume divergence detected.
Funding positive.
ETH outperforming BTC.
Reflection Layer
Last 20 similar setups:
Win rate = 72%
Average RR = 2.3
Best exit = ATR trailing stop
Research Layer

The AI searches:

What happened last time?
What worked?
What failed?
What is different now?

This reflection approach is becoming standard in modern agent systems.

3. Note Taking and Knowledge Base

Humans write notes.

Your AI should maintain databases such as:

Trade Journal
Trade ID
Entry
Exit
Stop Loss
Take Profit
Market Regime
Features
Confidence
Outcome
Observation Notes
BTC often sweeps Asian highs before NY open.

Nifty reacts strongly to RBI announcements.

High funding + low volume often causes liquidation events.
Strategy Notes
Trend following works during high ADX periods.

Mean reversion works in low volatility ranges.
Failure Notes
Do not short BTC when ETF inflows exceed threshold.

Avoid Nifty option buying during low IV crush periods.

This becomes the AI's equivalent of a trader's notebook.

4. Trading Learning Repositories

These are some of the strongest open-source RL trading projects.

Project    Purpose
https://github.com/AI4Finance-Foundation/FinRL    RL trading framework
https://github.com/AI4Finance-Foundation/FinRL-Trading    Production trading infrastructure
https://github.com/TradeMaster-NTU/TradeMaster    RL research platform
https://github.com/stefan-jansen/machine-learning-for-trading    Complete ML trading ecosystem
https://github.com/HarshiniAiyyer/RLTrader    RL + LSTM trading
https://github.com/rezakarbasi/RL-agent-trader    RL stoploss optimization
https://github.com/roblen001/reinforcement_learning_trading_agent    PPO crypto trading
https://github.com/D3F4LT4ST/RL-trading    Forex RL
https://github.com/zero-was-here/tradingbot    Deep RL production bot

These repositories already contain:

PPO
SAC
TD3
DDPG
A2C
Actor-Critic methods
Experience replay
Reward optimization

5. Learning Entry Price

Instead of hardcoding entries:

RSI < 30 -> Buy

The AI learns:

State:
RSI=24
ADX=38
Volume Spike=Yes
Funding=Negative
Trend=Bullish

Action:
Enter Long

Reward:
+3R

After millions of examples:

AI learns optimal entry locations.
6. Learning Direction

Input features:

OHLCV
Orderflow
Volume Profile
Funding
Open Interest
Correlations
News
Sentiment
Regime

Output:

Long probability = 0.74
Short probability = 0.19
No Trade = 0.07
7. Learning Stop Loss

Human traders evolve stop losses.

The AI can learn:

Structure stop
ATR stop
Volatility stop
Orderbook stop
Liquidity stop
Dynamic stop

Recent research suggests adaptive stop losses outperform static percentages.

8. Learning Profit Targets

Instead of fixed targets:

TP = 2%

The AI learns:

Trend strength high:
hold longer

Momentum fading:
take profit

Liquidity zone ahead:
partial exit
9. Tail Gating Profits

This is essentially dynamic trailing exits.

Examples:

Move SL to breakeven after +1R.

Trail using ATR after +2R.

Switch to structure trailing after +4R.

Scale out 25%-25%-50%.

Research increasingly shows exit optimization is as important as entry optimization.

10. Closest Architecture To Human Traders
Perception Module
    ↓
Memory System
    ↓
Research Agent
    ↓
Reasoning Agent
    ↓
Risk Agent
    ↓
Execution Agent
    ↓
Reflection Agent
    ↓
Memory Update

This resembles:

Human observation
Human memory
Human reflection
Human experimentation
Human improvement

Modern research refers to this as a lifelong self-evolving autonomous agent system.

For your trading project, the strongest combination would likely be:

Memory Layer:
Awesome-Memory-for-Agents

Thinking Layer:
Reflection + Debate Agents

Learning Layer:
FinRL + TradeMaster

Research Layer:
RAG + Vector Database

Trading Layer:
PPO + SAC + Transformer Forecast Models

Experience Layer:
Trade Journal + Market Notes + Failure Database

Evolution Layer:
Self-Evolving Agents

This combination is probably the closest open-source approach currently available to an AI system that learns and improves in a way that resembles how experienced human traders build intuition over years of trading experience.

---

Yes. There are a few projects and research directions that are significantly more advanced than traditional machine learning models. These are attempting to move from pattern recognition AI toward human-like learning, reasoning, memory, planning, and self-improvement.

Tier 1 — World Models (Closest to Human Imagination)

Humans can imagine future outcomes before acting.

Example:

If I buy here,
price may go up.

If volume disappears,
price may reverse.

If news arrives,
the trend may accelerate.

World Models try to do exactly this by building an internal simulation of reality and testing actions before taking them. This is currently one of the hottest research areas in AGI and robotics.

Major Projects
Awesome World Models for Robotics
Tsinghua World Model Collection
Awesome World Models Repository
World Models Original Project

These systems learn:

Environment dynamics
Cause and effect
Future state prediction
Counterfactual reasoning
Internal simulations

This is probably the closest open-source equivalent of imagination today.

Tier 2 — Self-Evolving AI Agents

These systems don't just learn once.

They:

Observe
↓
Act
↓
Measure Result
↓
Reflect
↓
Improve Strategy
↓
Repeat
Leading repositories
Awesome Self Evolving Agents
Agent OS Collection

Capabilities include:

Reflection
Self-correction
Skill accumulation
Memory formation
Strategy evolution
Autonomous experimentation

These are among the closest things to "learning from experience" in open-source AI.

Tier 3 — Memory-Based AI

Humans remember failures and successes.

Modern agent memory systems attempt to reproduce:

Episodic Memory
Trade #1921:
BTC breakout at 104k failed.
Semantic Memory
BTC breakouts fail frequently during negative ETF flows.
Procedural Memory
When volatility expands:
use wider stop losses.

Projects in this category include:

Awesome Memory for Agents
Awesome Agent Memory Collection

These systems are trying to replicate long-term human memory structures.

Tier 4 — Embodied AI

Humans learn by interacting with the world.

Embodied AI attempts the same idea.

Examples include:

Robots learning to manipulate objects.
AI learning through exploration.
AI learning from trial and error.

Examples:

CARLA Simulator
CarDreamer Project

These systems combine:

Reinforcement learning
World models
Planning
Memory
Exploration

Tier 5 — Recursive Self-Improvement

This is where the AI:

Writes code
↓
Tests code
↓
Measures performance
↓
Improves itself
↓
Repeats

Projects approaching this include:

RepoMaster
GenAI Agents Repository

These systems can:

Explore repositories
Understand dependencies
Reuse knowledge
Improve solutions autonomously

Tier 6 — Ultra Advanced Trading Intelligence Architecture

For your use case (learning entries, exits, stop losses, profit trailing), an advanced architecture could look like:

Market Data
     ↓
Observation Agent
     ↓
Memory System
     ↓
Research Agent
     ↓
World Model Simulator
     ↓
Strategy Generator
     ↓
Risk Agent
     ↓
Execution Agent
     ↓
Reflection Agent
     ↓
Knowledge Database Update

The AI would store experiences such as:

Entry:
BTC breakout above resistance

Context:
High volume
Positive funding
ETF inflows positive

Outcome:
+4.2R profit

Conclusion:
Increase confidence in similar setups.

Over thousands of trades the system gradually learns:

Optimal entry locations
Market direction probabilities
Dynamic stop losses
Profit trailing rules
Regime-dependent behavior
Position sizing

This resembles how experienced discretionary traders build intuition over many years.

Tier 7 — Frontier Research Areas

The most advanced active areas in AI research right now are:

World Models
Self-Evolving Agents
Memory-Augmented Agents
Embodied AI
Multi-Agent Societies
Long-Horizon Reasoning
Autonomous Scientific Discovery
Self-Improving Code Agents
Lifelong Learning Systems
Neuro-Symbolic AI

These are widely considered among the key ingredients required for more general intelligence systems.

If you want the closest currently achievable open-source stack to "human-like learning", it would likely be:

World Model
+
Long-Term Memory
+
Reflection Engine
+
Reinforcement Learning
+
Self-Evolving Agents
+
Vector Memory Database
+
Multi-Agent Reasoning

That combination is currently much closer to human-style learning than a conventional LSTM, transformer, or supervised trading model alone.

---

If we move beyond trading and look at quantum physics, theoretical physics, finance, and scientific discovery, there are projects that are trying to build AI systems that do much more than prediction.

These systems attempt to:

Observe
↓
Learn
↓
Build internal models of reality
↓
Imagine possibilities
↓
Generate hypotheses
↓
Design experiments
↓
Test ideas
↓
Learn from failures
↓
Discover new knowledge
↓
Repeat forever

This is the direction often called Agentic Science, AI Scientists, and Autonomous Discovery Systems.

Quantum AI Discovery Systems
1. The AI learns quantum mechanics and discovers new algorithms

This is one of the most advanced directions currently.

Example workflow:

Observe quantum experiments
↓
Learn qubit interactions
↓
Simulate future states
↓
Generate new circuit designs
↓
Run experiments
↓
Keep successful discoveries
↓
Discard failures

Projects:

Quantum AI GitHub Collection
Awesome Quantum Machine Learning
World Models Project

These systems explore:

Quantum reinforcement learning
Quantum neural networks
Quantum optimization
Quantum circuit discovery
Quantum error correction learning

2. AI imagining quantum experiments before running them

Humans perform thought experiments:

What happens if gravity bends light?
What happens if these particles interact?

Advanced AI systems attempt:

Simulate experiment
↓
Predict outcome
↓
Estimate uncertainty
↓
Choose best experiment
↓
Run experiment

This dramatically reduces experimental cost.

Recent systems are already performing autonomous experiment planning and optimization.

Physics AI Scientists
3. Autonomous AI Physicists

The frontier of physics AI currently looks like:

Read papers
↓
Generate hypotheses
↓
Write simulations
↓
Run experiments
↓
Analyze results
↓
Write conclusions
↓
Generate new hypotheses

Leading projects:

The AI Scientist
The AI Scientist v2
AI Researcher
Awesome AI Scientists
Agent Scientists Survey

These projects are moving toward fully autonomous scientific research systems.

4. Autonomous AI Physicist Projects

Two of the most advanced examples are:

PhysMaster
AHOIS

Capabilities include:

Hypothesis generation
Counterexample generation
Falsification tests
Experiment planning
Result validation
Theory revision

These are surprisingly close to how human physicists work.

Finance Discovery Systems

Traditional finance AI asks:

Will price rise tomorrow?

Ultra advanced finance AI asks:

Why did this happen?
What market regime caused it?
What conditions repeat?
What if stop loss changes?
What if position sizing changes?
What if entry timing changes?
5. Finance World Models

Architecture:

Market Observation
↓
Memory
↓
Market Simulator
↓
Experiment Generator
↓
Strategy Evolution
↓
Risk Evaluation
↓
Execution
↓
Reflection

Projects:

FinRL
Machine Learning for Trading
Awesome AI4Finance
Awesome AI in Finance

These support:

PPO
SAC
TD3
DDPG
Multi-agent trading
Strategy evolution
Autonomous experimentation

6. AI experimenting with trading ideas

Example:

Hypothesis:
ATR trailing stop improves profits.

Experiment:
Run 50,000 simulations.

Result:
Improves Sharpe ratio by 14%.

Store result in memory.

Generate next hypothesis.

This is very similar to how quantitative researchers operate.

The Ultimate Architecture

If you combined the best ideas from physics, quantum research, and finance:

Observation Agent
        ↓
Long-Term Memory
        ↓
World Model
        ↓
Imagination Engine
        ↓
Hypothesis Generator
        ↓
Experiment Planner
        ↓
Simulator
        ↓
Result Analyzer
        ↓
Knowledge Graph
        ↓
Self Improvement Engine
        ↓
Memory Update

This architecture attempts to reproduce:

Human learning
Human imagination
Human experimentation
Human scientific discovery
Human intuition formation
The Most Advanced Open Research Directions Today

Ranked roughly by how close they are to human-style discovery:

Autonomous AI Scientists
World Models
Agentic Science
Long-Term Memory Agents
Self-Evolving Agents
Physics Discovery Agents
Quantum Discovery Systems
Multi-Agent Research Societies
Scientific Debate Agents
Recursive Self-Improving Systems

These are increasingly becoming the building blocks of next-generation research systems rather than isolated machine learning models.

I can also build a detailed "Artificial Scientist Architecture" specifically for trading and finance, where the AI behaves more like a quantitative researcher than a conventional trading bot—maintaining notebooks, forming hypotheses, running experiments, and updating beliefs based on evidence.

---

I did a deeper search focusing specifically on individual projects, not just collections or "awesome lists". I prioritized projects related to:

Human-like memory
Learning from experience
Reflection
Discovery
Experimentation
Imagination and world models
Autonomous research
Self-improvement
Scientific discovery
Learning from failures
Building internal models of the world

Below are some of the most interesting projects currently available.

1. Sakana AI Scientist

The closest open-source project to an autonomous researcher.

Capabilities:

Generates hypotheses
Writes code
Runs experiments
Analyzes results
Creates graphs
Writes papers
Reviews its own work
Iterates on failures

Repository:

https://github.com/sakanaai/ai-scientist

Version 2:

https://github.com/sakanaai/ai-scientist-v2

Research page:

https://sakana.ai/ai-scientist/

This is currently one of the strongest examples of AI attempting scientific discovery rather than simple prediction.

2. AI Researcher

An autonomous scientific innovation system.

Capabilities:

Literature review
Idea generation
Research planning
Experiment proposal
Scientific writing
Research workflow automation

Repository:

https://github.com/hkuds/ai-researcher

This project attempts to create a complete AI research assistant rather than a chatbot.

3. AgentMemory

Persistent memory for AI agents.

Capabilities:

Long-term memory
Semantic search
Experience retrieval
Memory ranking
Memory persistence across sessions

Repository:

https://github.com/rohitg00/agentmemory

This is one of the better projects for giving agents something closer to memory instead of just context windows.

4. MindForge

Human-inspired memory system for AI agents.

Capabilities:

Short-term memory
Long-term memory
User memory
Session memory
Concept graphs
Associative recall

Repository:

https://github.com/aiopsforce/mindforge

This is one of the closest implementations of layered memory systems inspired by human cognition.

5. World Models

One of the most important projects in AGI research.

Project:

https://worldmodels.github.io/

Paper implementation:

https://github.com/ctallec/world-models

The core idea:

Observe world
↓
Build internal simulator
↓
Imagine futures
↓
Choose best action
↓
Learn from result

This resembles imagination and mental simulation in humans.

6. Dreamer

Perhaps the most important world-model reinforcement learning project.

Project:

https://github.com/danijar/dreamerv3

Capabilities:

Learns environment dynamics
Simulates futures internally
Trains from imagined experiences
Plans before acting

Dreamer is one of the closest existing systems to "thinking before acting."

7. MuZero

One of the most influential learning systems ever created.

Paper:

https://arxiv.org/abs/1911.08265

Open implementation:

https://github.com/werner-duvaud/muzero-general

Capabilities:

Learns rules of environments automatically
Learns planning
Learns search
Learns strategies without explicit rules

It learned games like Chess, Go, and Atari without being given the rules beforehand.

8. OpenAI Procgen

Project:

https://github.com/openai/procgen

Purpose:

Generalization learning
Transfer learning
Learning abstract concepts rather than memorization

This was designed to test whether agents truly understand environments.

9. Voyager

One of the most human-like learning systems built so far.

Repository:

https://github.com/MineDojo/Voyager

Capabilities:

Learns skills automatically
Stores successful strategies
Reuses knowledge
Builds increasingly complex abilities

In Minecraft it continuously accumulated knowledge instead of resetting every episode.

This resembles procedural memory in humans.

10. Generative Agents

Repository:

https://github.com/joonspk-research/generative_agents

Capabilities:

Memories
Reflection
Planning
Social interactions
Goal formation

Agents remember conversations and past events and use them to guide future behavior.

This project became famous because the agents developed emergent social behaviors.

11. CAMEL AI

Repository:

https://github.com/camel-ai/camel

Capabilities:

Multi-agent societies
Collaboration
Debate
Shared knowledge
Specialization

Useful for creating research teams made entirely of AI agents.

12. MetaGPT

Repository:

https://github.com/FoundationAgents/MetaGPT

Capabilities:

AI company simulation
Researchers
Architects
Engineers
Testers

Multiple agents work together similarly to a human organization.

13. AutoGPT

Repository:

https://github.com/Significant-Gravitas/AutoGPT

Capabilities:

Goal decomposition
Autonomous planning
Task execution
Self-directed workflows

One of the earliest autonomous agent projects.

14. BabyAGI

Repository:

https://github.com/yoheinakajima/babyagi

Capabilities:

Task generation
Prioritization
Memory
Continuous learning loops

This introduced many concepts later used by modern agents.

15. OpenDevin

Repository:

https://github.com/OpenDevin/OpenDevin

Capabilities:

Coding
Experimentation
Testing
Debugging
File manipulation

Attempts to behave like a software engineer rather than a chatbot.

16. Devin-inspired SWE agents

Repository:

https://github.com/princeton-nlp/SWE-agent

Capabilities:

Reads repositories
Understands bugs
Creates fixes
Tests solutions
Learns from failures
17. Reflection Agents

Repository:

https://github.com/noahshinn/reflexion

Core idea:

Attempt task
↓
Fail
↓
Reflect
↓
Store lesson
↓
Retry

This is extremely similar to human learning.

18. Tree of Thoughts

Repository:

https://github.com/princeton-nlp/tree-of-thought-llm

Instead of:

Think once

It performs:

Generate ideas
↓
Explore branches
↓
Evaluate branches
↓
Choose best path

Very similar to human deliberation.

19. Graph of Thoughts

Repository:

https://github.com/spcl/graph-of-thoughts

Extension of Tree of Thoughts.

Allows:

Revisiting ideas
Merging concepts
Exploring multiple hypotheses

Closer to how human reasoning networks operate.

20. OpenCog Hyperon

Repository:

https://github.com/opencog/hyperon-experimental

This is probably the closest open-source AGI project currently in existence.

Capabilities:

Symbolic reasoning
Probabilistic reasoning
Knowledge graphs
Memory
Concept formation
Self-modification

OpenCog has been pursuing AGI research for over a decade.

21. NARS

Non-Axiomatic Reasoning System.

Repository:

https://github.com/opennars/OpenNARS-for-Applications

Capabilities:

Reasoning under uncertainty
Learning from experience
Incremental learning
Resource-bounded intelligence

Very different from modern LLMs.

22. SOAR Cognitive Architecture

Repository:

https://github.com/SoarGroup/Soar

One of the oldest human cognition architectures.

Capabilities:

Episodic memory
Procedural memory
Reinforcement learning
Decision making
Goal hierarchy
23. ACT-R

Project:

https://act-r.psy.cmu.edu/

Attempts to model actual human cognition.

Capabilities:

Human memory simulation
Learning
Attention
Decision making
Skill acquisition

Used heavily in cognitive science research.

24. Sigma Cognitive Architecture

Project:

https://github.com/sigmacog/sigma

Goal:

Unified architecture for:

Perception
Memory
Planning
Learning
Action
25. LeCun's Joint Embedding Predictive Architecture (JEPA)

Project:

https://github.com/facebookresearch/ijepa

Idea:

Predict missing information
↓
Build world understanding
↓
Learn representations

Meta AI Research believes this type of architecture may become a major building block for future human-level AI systems.

If I had to rank them by "human-like intelligence"
Rank    Project    Human-like Score
1    AI Scientist v2    9.5/10
2    OpenCog Hyperon    9.3/10
3    ACT-R    9.2/10
4    Soar    9.1/10
5    Dreamer V3    9.0/10
6    Voyager    8.9/10
7    Generative Agents    8.8/10
8    Reflexion    8.7/10
9    MuZero    8.6/10
10    JEPA    8.5/10

The projects closest to human-like intelligence generally combine five ingredients:

Memory
+
World Model
+
Planning
+
Reflection
+
Experimentation

Current frontier research increasingly views these components as necessary for systems that can learn continuously, discover new ideas, and improve from experience rather than simply fitting patterns from static datasets.
