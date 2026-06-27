import React, { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import { kindColor } from './useState.js'

// D3-rendered horizontal bar chart of per-node test accuracy, sorted desc,
// with a dashed naive-baseline marker. Re-renders whenever data changes.
export function AccuracyBars({ nodes, baseline }) {
  const ref = useRef()
  useEffect(() => {
    const data = nodes
      .map((n) => ({ name: n.name, kind: n.kind, acc: n.metrics?.test_accuracy ?? 0 }))
      .filter((d) => d.acc > 0)
      .sort((a, b) => b.acc - a.acc)
    const W = ref.current.clientWidth || 420
    const rowH = 20, m = { top: 8, right: 44, bottom: 18, left: 116 }
    const H = m.top + m.bottom + data.length * rowH
    const svg = d3.select(ref.current).attr('viewBox', `0 0 ${W} ${H}`).attr('width', '100%').attr('height', H)
    svg.selectAll('*').remove()
    const lo = Math.min(0.45, d3.min(data, (d) => d.acc) ?? 0.45)
    const x = d3.scaleLinear().domain([lo, 1]).range([m.left, W - m.right])
    const y = d3.scaleBand().domain(data.map((d) => d.name)).range([m.top, H - m.bottom]).padding(0.22)

    svg.append('g').selectAll('rect.bg').data(data).join('rect')
      .attr('x', m.left).attr('y', (d) => y(d.name)).attr('height', y.bandwidth())
      .attr('width', x(1) - m.left).attr('rx', 5).attr('fill', 'rgba(255,255,255,.05)')
    svg.append('g').selectAll('rect.bar').data(data).join('rect')
      .attr('x', m.left).attr('y', (d) => y(d.name)).attr('height', y.bandwidth())
      .attr('rx', 5).attr('fill', (d) => kindColor(d.kind))
      .attr('width', 0).transition().duration(700)
      .attr('width', (d) => Math.max(2, x(d.acc) - m.left))
    svg.append('g').selectAll('text.nm').data(data).join('text')
      .attr('x', m.left - 8).attr('y', (d) => y(d.name) + y.bandwidth() / 2 + 3)
      .attr('text-anchor', 'end').attr('fill', '#cbd6ee').text((d) => d.name)
    svg.append('g').selectAll('text.v').data(data).join('text')
      .attr('x', (d) => x(d.acc) + 5).attr('y', (d) => y(d.name) + y.bandwidth() / 2 + 3)
      .attr('fill', '#8ea0c0').text((d) => d.acc.toFixed(3))

    if (baseline) {
      svg.append('line').attr('x1', x(baseline)).attr('x2', x(baseline))
        .attr('y1', m.top).attr('y2', H - m.bottom)
        .attr('stroke', '#fb7185').attr('stroke-dasharray', '4 3').attr('stroke-width', 1.5)
      svg.append('text').attr('x', x(baseline)).attr('y', m.top + 2)
        .attr('text-anchor', 'middle').attr('fill', '#fb7185')
        .text(`baseline ${baseline.toFixed(2)}`)
    }
  }, [nodes, baseline])
  return <svg ref={ref} />
}

// D3 line chart of reservoir accuracy vs injected noise (when present).
export function NoiseSweep({ sweep }) {
  const ref = useRef()
  useEffect(() => {
    if (!sweep || !sweep.length) return
    const W = ref.current.clientWidth || 420, H = 180
    const m = { top: 12, right: 16, bottom: 28, left: 36 }
    const svg = d3.select(ref.current).attr('viewBox', `0 0 ${W} ${H}`).attr('width', '100%').attr('height', H)
    svg.selectAll('*').remove()
    const x = d3.scaleLinear().domain(d3.extent(sweep, (d) => d.noise)).range([m.left, W - m.right])
    const y = d3.scaleLinear().domain([0.4, 1]).range([H - m.bottom, m.top])
    svg.append('g').attr('transform', `translate(0,${H - m.bottom})`)
      .call(d3.axisBottom(x).ticks(5)).attr('color', '#56688f')
    svg.append('g').attr('transform', `translate(${m.left},0)`)
      .call(d3.axisLeft(y).ticks(4)).attr('color', '#56688f')
    const area = d3.area().x((d) => x(d.noise)).y0(H - m.bottom).y1((d) => y(d.accuracy)).curve(d3.curveMonotoneX)
    const line = d3.line().x((d) => x(d.noise)).y((d) => y(d.accuracy)).curve(d3.curveMonotoneX)
    const grad = svg.append('defs').append('linearGradient').attr('id', 'ns').attr('x1', 0).attr('x2', 0).attr('y1', 0).attr('y2', 1)
    grad.append('stop').attr('offset', '0%').attr('stop-color', '#5cc8ff').attr('stop-opacity', 0.5)
    grad.append('stop').attr('offset', '100%').attr('stop-color', '#5cc8ff').attr('stop-opacity', 0)
    svg.append('path').datum(sweep).attr('fill', 'url(#ns)').attr('d', area)
    svg.append('path').datum(sweep).attr('fill', 'none').attr('stroke', '#5cc8ff').attr('stroke-width', 2).attr('d', line)
    svg.selectAll('circle').data(sweep).join('circle')
      .attr('cx', (d) => x(d.noise)).attr('cy', (d) => y(d.accuracy)).attr('r', 3).attr('fill', '#b98cff')
  }, [sweep])
  return <svg ref={ref} />
}
