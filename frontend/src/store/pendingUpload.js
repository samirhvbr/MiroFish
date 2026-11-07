/**
 * 临时存储待上传的文件和需求
 * 用于首页点击启动引擎后立即跳转，在Process页面再进行API调用
 */
import { reactive } from 'vue'

const state = reactive({
  files: [],
  sourceId: null,
  horizonHours: null,
  simulationRequirement: '',
  scenarioParticipants: '',
  isPending: false
})

export function setPendingUpload(files, requirement, { sourceId = null, horizonHours = null, scenarioParticipants = '' } = {}) {
  state.sourceId = sourceId
  state.horizonHours = horizonHours
  state.files = files
  state.simulationRequirement = requirement
  state.scenarioParticipants = scenarioParticipants
  state.isPending = true
}

export function getPendingUpload() {
  return {
    files: state.files,
    sourceId: state.sourceId,
    horizonHours: state.horizonHours,
    simulationRequirement: state.simulationRequirement,
    scenarioParticipants: state.scenarioParticipants,
    isPending: state.isPending
  }
}

export function clearPendingUpload() {
  state.sourceId = null
  state.horizonHours = null
  state.files = []
  state.simulationRequirement = ''
  state.scenarioParticipants = ''
  state.isPending = false
}

export default state

export function pendingUploadFormData(pending) {
  const formData = new FormData()
  pending.files.forEach(file => formData.append('files', file))
  if (pending.sourceId) {
    formData.append('source_id', pending.sourceId)
    formData.append('simulation_horizon_hours', String(pending.horizonHours))
  }
  formData.append('simulation_requirement', pending.simulationRequirement)
  if (pending.scenarioParticipants) formData.append('scenario_participants', pending.scenarioParticipants)
  return formData
}
