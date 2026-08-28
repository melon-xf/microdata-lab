/**
 * microdata-lab — desktop plugin.
 * Pane: repo health (branch, contract checks) + run buttons for gates/tests.
 * Chip: one-click PASS/FAIL summary. Commands: run gates/check/tests.
 */
import {
  Button,
  EmptyState,
  ErrorState,
  PALETTE_AREA,
  Tip,
  cn,
  haptic,
  host,
  useQuery
} from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'

const ID = 'microdata-lab'
let CTX = null // set in register(); used by api()

async function api(path, body) {
  return CTX.rest(path, body ? { method: 'POST', body } : undefined)
}

function Dot(props) {
  return jsx('span', {
    className: cn(
      'inline-block h-2 w-2 rounded-full',
      props.ok === true
        ? 'bg-(--ui-accent)'
        : props.ok === false
          ? 'bg-red-500'
          : 'bg-(--ui-stroke-secondary)'
    )
  })
}

function Row(props) {
  return jsxs('div', {
    className: 'flex items-center justify-between gap-2 py-1',
    children: [
      jsxs('span', {
        className: 'flex items-center gap-2 text-sm',
        children: [jsx(Dot, { ok: props.ok }), props.label]
      }),
      jsx('span', { className: 'text-(--ui-text-tertiary)', children: props.detail ?? '' })
    ]
  })
}

function useStatus() {
  return useQuery(['microdata-status'], async () => {
    const r = await api('/status')
    return r.result
  })
}

function runCommand(which) {
  haptic('tap')
  api('/run', { which }).then(r =>
    host.notify({
      kind: r.exit === 0 ? 'success' : 'error',
      message: `${which}: exit ${r.exit}${r.error ? ` (${r.error})` : ''}`
    })
  )
}

function Pane() {
  const status = useStatus()
  if (status.isPending) return jsx(EmptyState, { label: 'loading…' })
  if (status.isError)
    return jsx(ErrorState, { label: 'backend unreachable', onRetry: () => status.refetch() })

  const s = status.data
  return jsxs('div', {
    className: 'flex h-full flex-col gap-2 overflow-auto p-3 text-sm',
    children: [
      jsx('div', { className: 'font-medium', children: 'microdata-lab' }),
      jsx(Row, {
        label: 'contract checks',
        ok: s.contract_failed === 0 && s.ok,
        detail: `${s.contract_passed} passed / ${s.contract_failed} failed`
      }),
      jsx('div', { className: 'text-(--ui-text-tertiary)', children: s.branch_tip }),
      jsxs('div', {
        className: 'mt-2 flex flex-wrap gap-2',
        children: [
          jsx(Button, {
            variant: 'secondary',
            type: 'button',
            onClick: () => runCommand('gates'),
            children: 'run gates'
          }),
          jsx(Button, {
            variant: 'secondary',
            type: 'button',
            onClick: () => runCommand('tests'),
            children: 'run tests'
          })
        ]
      }),
      jsx('pre', {
        className:
          'mt-2 max-h-48 overflow-auto rounded bg-(--chrome-action-hover) p-2 text-xs text-(--ui-text-secondary)',
        children: s.raw_tail || ''
      })
    ]
  })
}

function Chip() {
  const status = useStatus()
  const data = status.data
  const ok = data ? data.contract_failed === 0 && data.ok : undefined
  return jsx(Tip, {
    label:
      ok === undefined
        ? 'microdata-lab — checking…'
        : ok
          ? 'microdata-lab — all checks pass'
          : 'microdata-lab — checks failing',
    children: jsx('button', {
      type: 'button',
      className: cn(
        'inline-flex h-full items-center gap-1 px-1.5 text-[0.6875rem] transition-colors',
        'text-(--ui-text-tertiary) hover:bg-(--chrome-action-hover) hover:text-foreground'
      ),
      onClick: () => {
        haptic('tap')
        status.refetch()
        host.notify({
          kind: ok ? 'info' : 'warning',
          message: ok
            ? `microdata-lab OK — ${data.contract_passed} analyses pass`
            : 'microdata-lab: some checks failing'
        })
      },
      children: jsxs('span', {
        className: 'flex items-center gap-1',
        children: [jsx(Dot, { ok }), 'mdlab']
      })
    })
  })
}

export default {
  id: ID,
  name: 'Microdata Lab',
  register(ctx) {
    CTX = ctx
    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'microdata-lab',
      data: { placement: 'right', width: '280px' },
      render: () => jsx(Pane, {})
    })
    ctx.register({ id: 'chip', area: 'statusBar.right', order: 130, render: () => jsx(Chip, {}) })
    const commands = [
      ['mdlab-gates', 'Run microdata viz gates', 'gates'],
      ['mdlab-check', 'Run microdata check-analysis', 'check'],
      ['mdlab-tests', 'Run microdata tests', 'tests']
    ]
    for (const cmd of commands) {
      ctx.register({
        id: cmd[0],
        area: PALETTE_AREA,
        label: cmd[1],
        run: () => runCommand(cmd[2])
      })
    }
  }
}
