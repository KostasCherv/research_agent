/**
 * Unit tests for graphEventReducer.
 * Run with: npx vitest (requires vitest to be installed).
 */
import { describe, it, expect } from 'vitest'
import {
  initialGraphState,
  graphEventReducer,
  applyEvents,
  DAG_MAIN_PATH,
} from './graphEventReducer'
import type { ResearchStreamEvent } from '../types'

function makeEvent(node: string, status = 'completed', error?: string): ResearchStreamEvent {
  return {
    node,
    node_status: status,
    ts: new Date().toISOString(),
    metrics: { duration_ms: 42 },
    data: { error },
  }
}

describe('initialGraphState', () => {
  it('marks all nodes as idle', () => {
    const state = initialGraphState()
    for (const node of DAG_MAIN_PATH) {
      expect(state[node].status).toBe('idle')
    }
    expect(state['abort'].status).toBe('idle')
    expect(state['empty'].status).toBe('idle')
  })
})

describe('graphEventReducer', () => {
  it('marks a completed node as completed', () => {
    const state = graphEventReducer(initialGraphState(), makeEvent('search'))
    expect(state['search'].status).toBe('completed')
  })

  it('promotes the next node to running after a completion', () => {
    const state = graphEventReducer(initialGraphState(), makeEvent('search'))
    expect(state['retrieve'].status).toBe('running')
  })

  it('marks node as failed when node_status is failed', () => {
    const state = graphEventReducer(initialGraphState(), makeEvent('search', 'failed'))
    expect(state['search'].status).toBe('failed')
    // Next node should NOT be promoted to running
    expect(state['retrieve'].status).toBe('idle')
  })

  it('marks node as failed when data.error is set', () => {
    const state = graphEventReducer(initialGraphState(), makeEvent('search', 'completed', 'boom'))
    expect(state['search'].status).toBe('failed')
  })

  it('stores metrics and ts on the node', () => {
    const event = makeEvent('search')
    const state = graphEventReducer(initialGraphState(), event)
    expect(state['search'].metrics?.duration_ms).toBe(42)
    expect(state['search'].ts).toBeTruthy()
  })

  it('does not promote past the last node', () => {
    const state = graphEventReducer(initialGraphState(), makeEvent('vector_store'))
    expect(state['vector_store'].status).toBe('completed')
    // No out-of-bounds promotion
  })

  it('ignores __end__ events', () => {
    const initial = initialGraphState()
    const state = graphEventReducer(initial, makeEvent('__end__'))
    expect(state).toEqual(initial)
  })

  it('ignores __error__ events', () => {
    const initial = initialGraphState()
    const state = graphEventReducer(initial, makeEvent('__error__'))
    expect(state).toEqual(initial)
  })
})

describe('applyEvents', () => {
  it('processes a full happy-path sequence', () => {
    const events = DAG_MAIN_PATH.map((n) => makeEvent(n))
    const state = applyEvents(initialGraphState(), events)
    for (const node of DAG_MAIN_PATH) {
      expect(state[node].status).toBe('completed')
    }
  })

  it('stops promoting at the failed node', () => {
    const events = [makeEvent('search'), makeEvent('retrieve', 'failed')]
    const state = applyEvents(initialGraphState(), events)
    expect(state['search'].status).toBe('completed')
    expect(state['retrieve'].status).toBe('failed')
    expect(state['memory_context'].status).toBe('idle')
  })
})
