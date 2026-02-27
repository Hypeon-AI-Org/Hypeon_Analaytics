import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import InsightsList from './InsightsList'

const mockInsights = {
  items: [
    {
      insight_id: 'ins-1',
      summary: 'Campaign c1 has spend but zero revenue.',
      confidence: 0.85,
      created_at: '2025-02-22T10:00:00Z',
      explanation: 'Spend = 100.',
      recommendation: 'Pause c1.',
      detected_by: ['waste_zero_revenue'],
      entity_id: 'c1_a1',
      client_id: 1,
    },
  ],
  count: 1,
}

beforeEach(() => {
  global.fetch = vi.fn()
})

test('shows loading then list of insights', async () => {
  fetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(mockInsights) })
  render(<InsightsList />)
  expect(screen.getByRole('button', { name: /Refresh/ })).toBeInTheDocument()
  await waitFor(() => {
    expect(screen.getByText(/Campaign c1 has spend but zero revenue/)).toBeInTheDocument()
  })
  expect(screen.getByText(/85% confidence/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Approve/ })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Reject/ })).toBeInTheDocument()
})

test('Details toggles provenance block', async () => {
  fetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(mockInsights) })
  render(<InsightsList />)
  await waitFor(() => {
    expect(screen.getByText(/Campaign c1/)).toBeInTheDocument()
  })
  expect(screen.queryByText(/Explanation:/)).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: /Details/ }))
  expect(screen.getByText(/Explanation:/)).toBeInTheDocument()
  expect(screen.getByText(/Spend = 100/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: /Collapse/ }))
  expect(screen.queryByText(/Explanation:/)).not.toBeInTheDocument()
})
