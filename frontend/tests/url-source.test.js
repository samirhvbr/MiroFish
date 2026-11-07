import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { clearPendingUpload, getPendingUpload, pendingUploadFormData, setPendingUpload } from '../src/store/pendingUpload.js'

afterEach(clearPendingUpload)

test('URL handoff uses the reviewed snapshot and edited prompt without files', () => {
  setPendingUpload([], 'My edited question', {
    sourceId: 'snapshot-id', horizonHours: 48, scenarioParticipants: 'IT manager\nExisting customer'
  })
  const form = pendingUploadFormData(getPendingUpload())
  assert.equal(form.get('source_id'), 'snapshot-id')
  assert.equal(form.get('simulation_requirement'), 'My edited question')
  assert.equal(form.get('simulation_horizon_hours'), '48')
  assert.deepEqual(form.getAll('files'), [])
  assert.equal(form.get('scenario_participants'), 'IT manager\nExisting customer')
  clearPendingUpload()
  assert.equal(getPendingUpload().sourceId, null)
  assert.equal(getPendingUpload().scenarioParticipants, '')
  assert.equal(getPendingUpload().isPending, false)
})

test('file upload clears stale URL metadata and still sends the document', () => {
  setPendingUpload([], 'URL prompt', { sourceId: 'old', horizonHours: 48 })
  const file = new File(['Document text'], 'source.txt', { type: 'text/plain' })
  setPendingUpload([file], 'Manual question', { scenarioParticipants: 'Small-business owner' })
  const form = pendingUploadFormData(getPendingUpload())
  assert.equal(form.get('source_id'), null)
  assert.equal(form.get('simulation_horizon_hours'), null)
  assert.equal(form.get('files').name, 'source.txt')
  assert.equal(form.get('scenario_participants'), 'Small-business owner')
  assert.equal(form.get('simulation_requirement'), 'Manual question')
})
