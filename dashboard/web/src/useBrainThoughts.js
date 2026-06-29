// useBrainThoughts.js — P4.6 Stream-of-Mind transport via the AG-UI protocol.
//
// Reuse-first (blueprint-named): @ag-ui/client's HttpAgent is the exact event pipeline
// CopilotKit is built on. It POSTs a RunAgentInput to our Python /api/agui SSE route and
// decodes the typed AG-UI events; we forward each TEXT_MESSAGE_CONTENT (one real thought)
// to the existing StreamOfMind panel via onThought(), so the panel shows the brain's REAL
// state of mind (ReAct steps, pymdp surprise/curiosity, calibrated verdict) — not mock data.
import { useCallback, useRef } from 'react'
import { HttpAgent } from '@ag-ui/client'

export function useBrainThoughts(onThought) {
  const running = useRef(false)

  // Run ONE think cycle and stream its thoughts into the panel.
  const think = useCallback((query) => {
    if (running.current) return
    running.current = true
    const agent = new HttpAgent({ url: '/api/agui' })
    const sub = agent.subscribe({
      onTextMessageContentEvent: ({ event }) => onThought(event.delta),
      onRunFinishedEvent: () => { running.current = false; try { sub.unsubscribe() } catch {} },
      onRunErrorEvent: () => { running.current = false; try { sub.unsubscribe() } catch {} },
    })
    agent
      .runAgent({ messages: query ? [{ id: 'u', role: 'user', content: query }] : [] })
      .catch(() => { running.current = false })
  }, [onThought])

  return think
}
