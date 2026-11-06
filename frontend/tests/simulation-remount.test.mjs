import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/components/Step3Simulation.vue', import.meta.url), 'utf8')
const extract = name => {
  const start = source.indexOf(`const ${name} =`)
  assert.notEqual(start, -1, name)
  return source.slice(start, source.indexOf('\n}\n', start) + 2)
}
function harness(snapshot, unavailable = false) {
  const props = { simulationId: 'sim-saved' }
  const phase = { value: 0 }, runStatus = { value: {} }, startError = { value: null }
  const prevTwitterRound = { value: 0 }, prevRedditRound = { value: 0 }
  const calls = { starts: 0, details: 0, statusPolling: 0, detailPolling: 0 }, emissions = []
  const getRunStatus = async () => {
    if (unavailable) throw new Error('status unavailable')
    return { success: true, data: snapshot }
  }
  const doStartSimulation = async () => { calls.starts++ }
  const fetchRunStatusDetail = async () => { calls.details++ }
  const startStatusPolling = () => { calls.statusPolling++ }
  const startDetailPolling = () => { calls.detailPolling++ }
  const emit = (...args) => emissions.push(args), addLog = () => {}, t = key => key
  const resume = eval(`${extract('hasRecoverableRun')}\n${extract('resumeOrStartSimulation')}; resumeOrStartSimulation`)
  return { resume, calls, emissions, phase, runStatus, startError }
}

for (const status of ['running', 'starting', 'paused', 'stopping', 'completed', 'stopped', 'failed']) {
  test(`reopening a ${status} run preserves its saved timeline and never starts again`, async () => {
    const snapshot = { runner_status: status, total_actions_count: 334, current_round: 120 }
    const h = harness(snapshot)
    await h.resume()
    assert.equal(h.calls.starts, 0)
    assert.equal(h.calls.details, 1)
    assert.equal(h.runStatus.value, snapshot)
    if (['running', 'starting', 'paused', 'stopping'].includes(status)) {
      assert.equal(h.calls.statusPolling, 1)
      assert.deepEqual(h.emissions.at(-1), ['update-status', status === 'stopping' ? 'finalizing' : 'processing'])
    } else {
      assert.equal(h.calls.statusPolling, 0)
      assert.deepEqual(h.emissions.at(-1), ['update-status', status === 'failed' ? 'error' : 'completed'])
    }
  })
}

test('only an explicit idle snapshot with no saved actions starts a fresh simulation', async () => {
  const h = harness({ runner_status: 'idle', total_actions_count: 0 })
  await h.resume()
  assert.equal(h.calls.starts, 1)
  assert.equal(h.calls.details, 0)
})

for (const snapshot of [{ runner_status: 'idle', total_actions_count: 334 }, {}]) {
  test(`uncertain or orphaned saved state is never replaced: ${JSON.stringify(snapshot)}`, async () => {
    const h = harness(snapshot)
    await h.resume()
    assert.equal(h.calls.starts, 0)
    assert.equal(h.calls.details, 1)
  })
}

test('a failed status read never starts a replacement run', async () => {
  const h = harness(null, true)
  await h.resume()
  assert.equal(h.calls.starts, 0)
  assert.equal(h.calls.details, 0)
  assert.equal(h.startError.value, 'status unavailable')
})
