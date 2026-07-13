// BrainPage.jsx — THE one brain page (Brain Ultra Upgrade, owner order 2026-07-12:
// "replace all the scattered brain features into one single page with graphs,
// connections etc which is as on disk without any inconsistency").
// Every brain feature that used to be scattered across the Trading view lives here,
// organized as sections with anchor navigation. Nothing decorative: every panel keeps
// its own real API polling; the new Overview panels (web of neurons / cognitive loop /
// school) read the new /api/brain/* + /api/trading/brain/flow routes that measure
// disk truth directly.
import React, { useEffect, useRef, useState } from 'react'
import { useBrainThoughts } from './useBrainThoughts.js'
import SystemMapPanel from './SystemMapPanel.jsx'
import NetworkPanel from './NetworkPanel.jsx'
import ChatPanel from './ChatPanel.jsx'
import StreamOfMind from './StreamOfMind.jsx'
import { T } from './trading/theme.js'
import NeuronWebPanel from './trading/NeuronWebPanel.jsx'
import FlowHealthPanel from './trading/FlowHealthPanel.jsx'
import BrainOsPanel from './trading/BrainOsPanel.jsx'
import SchoolPanel from './trading/SchoolPanel.jsx'
import BrainPanel from './trading/BrainPanel.jsx'
import BrainOutcomeNet from './trading/BrainOutcomeNet.jsx'
import BrainLearningPanel from './trading/BrainLearningPanel.jsx'
import BrainUltraPanel from './trading/BrainUltraPanel.jsx'
import BrainOpsPanel from './trading/BrainOpsPanel.jsx'
import GoalOpsPanel from './trading/GoalOpsPanel.jsx'
import ConceptSpacePanel from './trading/ConceptSpacePanel.jsx'
import MetacognitionPanel from './trading/MetacognitionPanel.jsx'
import DebatePanel from './trading/DebatePanel.jsx'
import DecisionMemoryPanel from './trading/DecisionMemoryPanel.jsx'
import WorldModelPanel from './trading/WorldModelPanel.jsx'
import HypothesesPanel from './trading/HypothesesPanel.jsx'
import EvolvePanel from './trading/EvolvePanel.jsx'
import ComputerUsePanel from './trading/ComputerUsePanel.jsx'
import OcularCortexPanel from './trading/OcularCortexPanel.jsx'
import BrainMirrorPanel from './trading/BrainMirrorPanel.jsx'
import AppSchoolPanel from './trading/AppSchoolPanel.jsx'
import ConnectivityPanel from './trading/ConnectivityPanel.jsx'
import LLMProvidersPanel from './trading/LLMProvidersPanel.jsx'

function Card({ title, hint, children }) {
  return (
    <div data-card style={{ background: T.panel, border: `1px solid ${T.border}`,
                            borderRadius: 10, padding: 14 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
        <h2 style={{ margin: 0, fontSize: 15, color: T.text, fontWeight: 700,
                     letterSpacing: 0.2 }}>{title}</h2>
        {hint && <span style={{ color: T.muted, fontSize: 12 }}>{hint}</span>}
      </div>
      <div style={{ marginTop: 10 }}>{children}</div>
    </div>
  )
}

const SECTIONS = [
  { id: 'overview', label: '🧠 Intelligence' },
  { id: 'map', label: '🗺 System Map' },
  { id: 'mind', label: '💭 Mind' },
  { id: 'memory', label: '📚 Memory & Learning' },
  { id: 'cognition', label: '⚖️ Cognition' },
  { id: 'embodiment', label: '🦾 Embodiment' },
  { id: 'wiring', label: '🔌 Wiring' },
]

function Section({ id, label, children }) {
  return (
    <section id={`brain-${id}`} style={{ scrollMarginTop: 64 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '18px 0 10px' }}>
        <span style={{ fontSize: 14, fontWeight: 800, color: T.text }}>{label}</span>
        <div style={{ flex: 1, height: 1, background: T.border }} />
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>{children}</div>
    </section>
  )
}

export default function BrainPage() {
  // Stream-of-Mind state (moved here from App.jsx with the rest of the brain view).
  const [thoughts, setThoughts] = useState([])
  const thoughtSeq = useRef(0)                        // ref, not state: two thoughts in
  const onThought = (text) => {                       // one tick must get distinct ids
    if (!text) return
    const id = `${Date.now()}-${thoughtSeq.current++}`
    setThoughts((t) => [{ id, text, ts: Date.now() }, ...t].slice(0, 40))
  }
  const think = useBrainThoughts(onThought)

  // Outcome-net prediction (was fed by useTrading in the Trading view; here it has a
  // lean poll of its own so the brain page stays independent of the trading hook).
  const [predict, setPredict] = useState(null)
  useEffect(() => {
    let alive = true
    const tick = () => fetch('/api/trading/brain/predict').then((r) => r.json())
      .then((j) => alive && setPredict(j)).catch(() => {})
    tick()
    const t = setInterval(tick, 30000)   // outcome-net training is heavy server-side —
    return () => { alive = false; clearInterval(t) }   // keep the old ~30s cadence
  }, [])

  return (
    <div style={{ padding: '0 16px 24px' }}>
      {/* sticky section nav — the single-page index of the whole brain */}
      <div style={{ position: 'sticky', top: 0, zIndex: 10, background: 'rgba(11,15,22,0.92)',
                    backdropFilter: 'blur(4px)', padding: '8px 0', display: 'flex', gap: 8,
                    flexWrap: 'wrap', borderBottom: `1px solid ${T.border}` }}>
        {SECTIONS.map((s) => (
          <a key={s.id} href={`#brain-${s.id}`}
             style={{ fontSize: 12, color: T.accent, textDecoration: 'none',
                      border: `1px solid ${T.border}`, borderRadius: 14, padding: '3px 10px' }}>
            {s.label}</a>
        ))}
      </div>

      <Section id="overview" label="🧠 Intelligence — web of neurons · one loop · the school">
        <NeuronWebPanel />
        <FlowHealthPanel />
        <BrainOsPanel />
        <SchoolPanel />
      </Section>

      <Section id="map" label="🗺 System Map — the living cortex">
        <SystemMapPanel />
        <NetworkPanel />
      </Section>

      <Section id="mind" label="💭 Mind — stream, chat, boss, goal">
        <div className="grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <div className="card mind-card" style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 10, padding: 14 }}>
            <h2 style={{ marginTop: 0 }}>Stream of Mind
              <button className="think-btn" onClick={() => think('How does the brain decide when to ask for help?')}
                style={{ marginLeft: 10, fontSize: 12, padding: '2px 10px', cursor: 'pointer',
                  background: '#1b2433', color: '#4cc2ff', border: '1px solid #1e2837', borderRadius: 8 }}>
                ⚡ Think
              </button>
            </h2>
            <div className="hint">The brain's live state of mind (AG-UI stream) — thoughts fire, glow, then fade; salient ones consolidate to memory.</div>
            <StreamOfMind thoughts={thoughts} />
          </div>
          <div className="card chat-card" style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 10, padding: 14 }}>
            <h2 style={{ marginTop: 0 }}>Brain Chat</h2>
            <div className="hint">Chat with the brain about the network, nodes and results.</div>
            <ChatPanel onThought={onThought} />
          </div>
        </div>
        <Card title="Brain Ops — boss directives · R&D · mind event bus" hint="real boss/R&D/mind-bus + honest real/demo catalog of subsystems">
          <BrainOpsPanel />
        </Card>
        <Card title="Goal & Rails — the owner's evidence spine" hint="goal scoreboard · watchdogs+autonomy gates · one-variable rails · smart-money consensus · track records · UI-only data coverage">
          <GoalOpsPanel />
        </Card>
      </Section>

      <Section id="memory" label="📚 Memory & Learning">
        <Card title="Brain Learning & Web — reads, browses, self-evaluates" hint="reads books/papers → KnowledgeBrain · read-only web screening · continuous learn loop">
          <BrainLearningPanel />
        </Card>
        <Card title="Brain Ultra — associative memory · micro-LLM · perception · continual" hint="HippoRAG+A-MEM recall · Claude-style file memory · cloned nanoGPT/llama2.c · Docling · Avalanche no-forgetting">
          <BrainUltraPanel />
        </Card>
        <Card title="Decision Memory — episodes · attribution · reflections" hint="FinMem layered episodes · SHAP 'which data drove it' · outcome-closure lessons recalled before new entries">
          <DecisionMemoryPanel />
        </Card>
        <Card title="Concept Discovery — pure-self feature invention" hint="self-supervised encoder invents features → sparse-autoencoder probe → LLM naming → concept manifold">
          <ConceptSpacePanel />
        </Card>
      </Section>

      <Section id="cognition" label="⚖️ Cognition — decide, imagine, debate, evolve">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <Card title="AI Brain (T8)" hint="evolution · self-eval · skills · end-to-end decision">
            <BrainPanel />
          </Card>
          <Card title="Brain Outcome Net" hint="trade rows → node network → win-prob / verdict">
            <BrainOutcomeNet data={predict} />
          </Card>
        </div>
        <Card title="Metacognition — calibrated uncertainty & abstention (Pillar 17)" hint="conformal p_up + coverage-guaranteed intervals · reliability diagram · abstention log">
          <MetacognitionPanel />
        </Card>
        <Card title="Adversarial Debate + Verifier (Pillar 18)" hint="bull/bear/risk debate + process-reward step verifier — verified reasoning, not just PnL">
          <DebatePanel />
        </Card>
        <Card title="Imagination — World-Model + MuZero planning" hint="learned market dynamics · MCTS plans entry/direction/stop/trailing in imagined R">
          <WorldModelPanel />
        </Card>
        <Card title="Hypothesis Ledger — AI-Scientist research loop" hint="propose → experiment on the journal → Bayesian credence → confirm/refute">
          <HypothesesPanel />
        </Card>
        <Card title="Self-Evolving Loop — lifelong strategy evolution" hint="evolve → admit guardrail-passed winners into the skill library">
          <EvolvePanel />
        </Card>
      </Section>

      <Section id="embodiment" label="🦾 Embodiment — eyes and hands on the apps">
        <Card title="Computer-Use Agent — sees & operates the dashboards" hint="reads panels/charts/buttons, presses them paper-first, reflects (Reflexion) & grows a skill library (Voyager)">
          <ComputerUsePanel />
        </Card>
        <Card title="Ocular Cortex — the brain's eyes & visual memory" hint="FREE vision reads each broker screen · fuses pixels+DOM+OCR+app JSON · learns golden paths">
          <OcularCortexPanel />
        </Card>
        <Card title="Brain Screen Mirror — watch the brain operate the apps" hint="READ-ONLY live mirror of the browser the BRAIN drives · watching never steers the hand">
          <BrainMirrorPanel />
        </Card>
        <Card title="App Driving School — Binance (crypto)" hint="explores the logged-in BINANCE app read-only · learns the golden route to each market-data kind">
          <AppSchoolPanel broker="binance" />
        </Card>
        <Card title="App Driving School — Upstox (NSE)" hint="a SEPARATE school for the logged-in UPSTOX app · learns NSE routes from Upstox's own traffic · read-only">
          <AppSchoolPanel broker="upstox" />
        </Card>
      </Section>

      <Section id="wiring" label="🔌 Wiring — connectivity & providers">
        <Card title="Wiring watchdog — self-healing connectivity" hint="flags any module/endpoint that WAS wired coming unwired (a regression)">
          <ConnectivityPanel />
        </Card>
        <Card title="LLM Providers — cloud-LLM failover telemetry" hint="per-provider hit-rate · free calls used · failures/rate-limits · last latency — real core.llm.chat stats">
          <LLMProvidersPanel />
        </Card>
      </Section>
    </div>
  )
}
