import React, { useEffect, useRef, useState } from 'react'

// P4.2 — Brain Chat with STREAMING. Plain React + fetch, no extra deps.
// Honest-wiring: only renders what the API actually returns.
// Primary contract (NDJSON stream):
//   POST /api/chat/stream  { message, history:[{role,content}...] }
//   -> application/x-ndjson, one JSON object per line:
//      {type:"thought", text}   {type:"sources", sources:[{title,snippet}]}
//      {type:"token", text}     {type:"done"}     {type:"error", error}
// Fallback (non-streaming):
//   POST /api/chat  { message } -> { reply, sources, thoughts, error }
//
// Thoughts are lifted OUT of this panel via the onThought(text) prop so the
// shared <StreamOfMind/> can render the brain's live state of mind.

export default function ChatPanel({ onThought }) {
  const [messages, setMessages] = useState([]) // {role:'user'|'assistant'|'system', text, sources?}
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false) // true until first token arrives
  const listRef = useRef(null)

  // auto-scroll to newest message / as tokens stream in
  useEffect(() => {
    const el = listRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, loading])

  const emitThought = (text) => {
    if (text && typeof onThought === 'function') onThought(text)
  }

  // Append a streamed token delta to the trailing in-progress assistant bubble.
  const appendToken = (delta) => {
    setMessages((m) => {
      const last = m[m.length - 1]
      if (last && last.role === 'assistant' && last.streaming) {
        const next = m.slice(0, -1)
        next.push({ ...last, text: (last.text || '') + delta })
        return next
      }
      return [...m, { role: 'assistant', text: delta, sources: [], streaming: true }]
    })
  }

  const attachSources = (sources) => {
    if (!Array.isArray(sources) || sources.length === 0) return
    setMessages((m) => {
      const last = m[m.length - 1]
      if (last && last.role === 'assistant' && last.streaming) {
        const next = m.slice(0, -1)
        next.push({ ...last, sources })
        return next
      }
      // sources arrived before any token — seed an empty streaming bubble
      return [...m, { role: 'assistant', text: '', sources, streaming: true }]
    })
  }

  const finalizeStream = () => {
    setMessages((m) => m.map((x) => (x.streaming ? { ...x, streaming: false } : x)))
  }

  const handleEvent = (evt) => {
    switch (evt.type) {
      case 'thought':
        emitThought(evt.text)
        break
      case 'sources':
        attachSources(evt.sources)
        break
      case 'token':
        setLoading(false)
        appendToken(evt.text || '')
        break
      case 'done':
        finalizeStream()
        break
      case 'error':
        finalizeStream()
        setMessages((m) => [...m, { role: 'system', text: `⚠ ${evt.error}` }])
        break
      default:
        break
    }
  }

  // Non-streaming fallback used if the stream fetch fails outright.
  const fallback = async (text, history) => {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, history }),
    })
    const j = await r.json()
    if (Array.isArray(j.thoughts)) j.thoughts.forEach(emitThought)
    setLoading(false)
    if (j.error) {
      setMessages((m) => [...m, { role: 'system', text: `⚠ ${j.error}` }])
    } else {
      setMessages((m) => [...m, {
        role: 'assistant',
        text: j.reply ?? '',
        sources: Array.isArray(j.sources) ? j.sources : [],
      }])
    }
  }

  const send = async () => {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    // history = prior turns (exclude system notices) before this user message
    const history = messages
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .map((m) => ({ role: m.role, content: m.text }))
    setMessages((m) => [...m, { role: 'user', text }])
    setLoading(true)
    emitThought('user: ' + text.slice(0, 40))

    try {
      const r = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, history }),
      })
      if (!r.ok || !r.body) throw new Error(`stream unavailable (${r.status})`)

      const reader = r.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let nl
        while ((nl = buffer.indexOf('\n')) >= 0) {
          const line = buffer.slice(0, nl).trim()
          buffer = buffer.slice(nl + 1)
          if (!line) continue
          try { handleEvent(JSON.parse(line)) } catch { /* skip malformed line */ }
        }
      }
      // flush any trailing buffered object (stream may end without newline)
      const tail = buffer.trim()
      if (tail) { try { handleEvent(JSON.parse(tail)) } catch { /* ignore */ } }
      finalizeStream()
    } catch (e) {
      // stream path failed entirely — try the non-streaming fallback
      try {
        await fallback(text, history)
      } catch (e2) {
        setMessages((m) => [...m, { role: 'system', text: `⚠ chat request failed: ${String(e2 || e)}` }])
      }
    } finally {
      setLoading(false)
    }
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="chat">
      <div className="chat-list" ref={listRef}>
        {messages.length === 0 && !loading && (
          <div className="chat-empty">Ask the brain about the network, nodes, or results.</div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-msg ${m.role}`}>
            <div className="chat-bubble">
              {m.text}
              {m.streaming && <span className="stream-cursor" aria-hidden="true" />}
            </div>
            {m.role === 'assistant' && m.sources && m.sources.length > 0 && (
              <div className="chat-sources">
                {m.sources.map((s, j) => (
                  <div className="chat-source" key={j}>
                    <div className="src-title">{s.title}</div>
                    {s.snippet && <div className="src-snippet">{s.snippet}</div>}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="chat-msg assistant">
            <div className="chat-bubble typing"><span /><span /><span /></div>
          </div>
        )}
      </div>

      <div className="chat-input">
        <textarea
          rows={1}
          value={input}
          placeholder="Message the brain…  (Enter to send · Shift+Enter for newline)"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={loading}
        />
        <button onClick={send} disabled={loading || !input.trim()}>Send</button>
      </div>
    </div>
  )
}
