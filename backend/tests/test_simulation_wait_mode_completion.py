"""The simulation script stays alive after ``simulation_end`` to serve
interviews. Finished rounds must still publish a terminal status, without
waiting for that process to exit."""

import pytest

from app.services import simulation_runner as runner_module
from app.services.simulation_runner import (
    RunnerStatus,
    SimulationRunState,
    SimulationRunner,
)


class _IdleInterviewProcess:
    """A simulation process idling in wait-for-commands mode."""

    pid = 4242

    def __init__(self):
        self.exit_code = None

    def poll(self):
        return self.exit_code

    @property
    def returncode(self):
        return self.exit_code


def _write_simulation_end(tmp_path, simulation_id, platforms):
    for platform in platforms:
        platform_dir = tmp_path / simulation_id / platform
        platform_dir.mkdir(parents=True)
        (platform_dir / "actions.jsonl").write_text(
            '{"event_type":"simulation_end","total_rounds":3,"total_actions":7}\n',
            encoding="utf-8",
        )


def _patch_state_io(monkeypatch, tmp_path, state, synced):
    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(tmp_path))
    monkeypatch.setattr(
        SimulationRunner,
        "get_run_state",
        classmethod(lambda _cls, _simulation_id: state),
    )
    monkeypatch.setattr(
        SimulationRunner,
        "_save_run_state",
        classmethod(lambda _cls, _state: None),
    )
    monkeypatch.setattr(
        SimulationRunner,
        "_sync_simulation_status",
        classmethod(lambda _cls, _sim_id, status, *_args: synced.append(status)),
    )


def _run_monitor_until_completed(monkeypatch, simulation_id, process, state):
    """Drive the monitor loop, then close the interview environment.

    The process exits on the first tick after a terminal status, or after a
    few idle ticks otherwise, as a user closing the environment would.
    """
    ticks = []

    def fake_sleep(_seconds):
        ticks.append(state.runner_status)
        terminal = state.runner_status in {
            RunnerStatus.COMPLETED,
            RunnerStatus.FAILED,
        }
        if terminal or len(ticks) >= 3:
            process.exit_code = 0

    monkeypatch.setattr(runner_module.time, "sleep", fake_sleep)
    SimulationRunner._processes[simulation_id] = process
    try:
        SimulationRunner._monitor_simulation(simulation_id)
    finally:
        SimulationRunner._processes.pop(simulation_id, None)
        SimulationRunner._graph_memory_enabled.pop(simulation_id, None)
        SimulationRunner._manual_stop_requests.discard(simulation_id)


def test_should_complete_while_process_still_serves_interviews(
    monkeypatch, tmp_path
):
    simulation_id = "sim-wait-mode"
    _write_simulation_end(tmp_path, simulation_id, ["twitter", "reddit"])
    state = SimulationRunState(
        simulation_id=simulation_id,
        runner_status=RunnerStatus.RUNNING,
        twitter_running=True,
        reddit_running=True,
    )
    synced = []
    _patch_state_io(monkeypatch, tmp_path, state, synced)
    process = _IdleInterviewProcess()

    statuses_while_alive = []
    original = SimulationRunner._publish_terminal_status.__func__

    def recording_publish(cls, *args, **kwargs):
        original(cls, *args, **kwargs)
        statuses_while_alive.append((state.runner_status, process.poll()))

    monkeypatch.setattr(
        SimulationRunner, "_publish_terminal_status", classmethod(recording_publish)
    )

    _run_monitor_until_completed(monkeypatch, simulation_id, process, state)

    # COMPLETED was published while the process was still alive (poll None),
    # and the later clean exit did not rewrite it.
    assert statuses_while_alive == [(RunnerStatus.COMPLETED, None)]
    assert state.runner_status == RunnerStatus.COMPLETED
    assert state.completed_at is not None
    assert synced == [RunnerStatus.COMPLETED]


def test_should_drain_graph_ingestion_before_completing(monkeypatch, tmp_path):
    simulation_id = "sim-wait-mode-zep"
    _write_simulation_end(tmp_path, simulation_id, ["twitter"])
    state = SimulationRunState(
        simulation_id=simulation_id,
        runner_status=RunnerStatus.RUNNING,
        twitter_running=True,
    )
    synced = []
    _patch_state_io(monkeypatch, tmp_path, state, synced)
    drained = []
    monkeypatch.setattr(
        runner_module.ZepGraphMemoryManager,
        "get_updater",
        classmethod(lambda _cls, _simulation_id: None),
    )
    process = _IdleInterviewProcess()
    monkeypatch.setattr(
        runner_module.ZepGraphMemoryManager,
        "stop_updater",
        classmethod(lambda _cls, sim_id: drained.append((sim_id, process.poll()))),
    )
    SimulationRunner._graph_memory_enabled[simulation_id] = True

    _run_monitor_until_completed(monkeypatch, simulation_id, process, state)

    assert drained == [(simulation_id, None)]
    assert synced == [RunnerStatus.STOPPING, RunnerStatus.COMPLETED]
    assert state.runner_status == RunnerStatus.COMPLETED


def test_should_fail_when_graph_drain_fails_after_rounds(monkeypatch, tmp_path):
    simulation_id = "sim-wait-mode-drain-fail"
    _write_simulation_end(tmp_path, simulation_id, ["reddit"])
    state = SimulationRunState(
        simulation_id=simulation_id,
        runner_status=RunnerStatus.RUNNING,
        reddit_running=True,
    )
    synced = []
    _patch_state_io(monkeypatch, tmp_path, state, synced)
    process = _IdleInterviewProcess()
    drained_while = []

    def failing_drain(_cls, _sim_id):
        drained_while.append(process.poll())
        raise RuntimeError("drain broke")

    monkeypatch.setattr(
        runner_module.ZepGraphMemoryManager,
        "get_updater",
        classmethod(lambda _cls, _simulation_id: None),
    )
    monkeypatch.setattr(
        runner_module.ZepGraphMemoryManager,
        "stop_updater",
        classmethod(failing_drain),
    )
    SimulationRunner._graph_memory_enabled[simulation_id] = True

    _run_monitor_until_completed(monkeypatch, simulation_id, process, state)

    # The drain ran once, while the interview process was still alive.
    assert drained_while == [None]
    assert state.runner_status == RunnerStatus.FAILED
    assert "drain broke" in state.error


def test_should_not_complete_until_every_enabled_platform_ends(
    monkeypatch, tmp_path
):
    simulation_id = "sim-wait-mode-partial"
    _write_simulation_end(tmp_path, simulation_id, ["twitter"])
    reddit_dir = tmp_path / simulation_id / "reddit"
    reddit_dir.mkdir(parents=True)
    (reddit_dir / "actions.jsonl").write_text(
        '{"event_type":"round_end","round":1}\n', encoding="utf-8"
    )
    state = SimulationRunState(
        simulation_id=simulation_id,
        runner_status=RunnerStatus.RUNNING,
        twitter_running=True,
        reddit_running=True,
    )
    synced = []
    _patch_state_io(monkeypatch, tmp_path, state, synced)
    state.twitter_completed = True

    returned = SimulationRunner._complete_if_rounds_finished(simulation_id, state)

    assert returned.runner_status == RunnerStatus.RUNNING
    assert synced == []


def test_should_not_complete_when_manual_stop_is_pending(monkeypatch, tmp_path):
    simulation_id = "sim-wait-mode-stopping"
    _write_simulation_end(tmp_path, simulation_id, ["twitter"])
    state = SimulationRunState(
        simulation_id=simulation_id,
        runner_status=RunnerStatus.RUNNING,
        twitter_completed=True,
    )
    synced = []
    _patch_state_io(monkeypatch, tmp_path, state, synced)
    SimulationRunner._manual_stop_requests.add(simulation_id)
    try:
        SimulationRunner._complete_if_rounds_finished(simulation_id, state)
    finally:
        SimulationRunner._manual_stop_requests.discard(simulation_id)

    assert state.runner_status == RunnerStatus.RUNNING
    assert synced == []


def _patch_restart_state(monkeypatch, status):
    state = SimulationRunState(simulation_id="sim-restart", runner_status=status)
    monkeypatch.setattr(
        SimulationRunner,
        "get_run_state",
        classmethod(lambda _cls, _simulation_id: state),
    )
    return state


def test_should_close_interview_process_of_finished_run_before_restart(
    monkeypatch,
):
    _patch_restart_state(monkeypatch, RunnerStatus.COMPLETED)
    process = _IdleInterviewProcess()
    events = []

    class Monitor:
        alive = True

        def join(self, timeout):
            events.append(("join", process.poll()))
            self.alive = False

        def is_alive(self):
            return self.alive

    def terminate(_cls, proc, _simulation_id, **_kwargs):
        events.append("terminate")
        proc.exit_code = 0

    monkeypatch.setattr(SimulationRunner, "_terminate_process", classmethod(terminate))
    SimulationRunner._processes["sim-restart"] = process
    SimulationRunner._monitor_threads["sim-restart"] = Monitor()
    try:
        SimulationRunner._close_finished_interview_process("sim-restart")
    finally:
        SimulationRunner._processes.pop("sim-restart", None)
        SimulationRunner._monitor_threads.pop("sim-restart", None)

    # The old process is gone before its monitor is awaited.
    assert events == ["terminate", ("join", 0)]


def test_should_refuse_restart_while_old_monitor_is_still_alive(monkeypatch):
    _patch_restart_state(monkeypatch, RunnerStatus.COMPLETED)

    class StuckMonitor:
        def join(self, timeout):
            pass

        def is_alive(self):
            return True

    SimulationRunner._processes.pop("sim-restart", None)
    SimulationRunner._monitor_threads["sim-restart"] = StuckMonitor()
    try:
        with pytest.raises(ValueError, match="still shutting down"):
            SimulationRunner._close_finished_interview_process("sim-restart")
    finally:
        SimulationRunner._monitor_threads.pop("sim-restart", None)


def test_should_leave_active_runs_to_the_start_guard(monkeypatch):
    _patch_restart_state(monkeypatch, RunnerStatus.RUNNING)
    process = _IdleInterviewProcess()
    monkeypatch.setattr(
        SimulationRunner,
        "_terminate_process",
        classmethod(lambda *_args, **_kwargs: pytest.fail("terminated a live run")),
    )
    SimulationRunner._processes["sim-restart"] = process
    try:
        SimulationRunner._close_finished_interview_process("sim-restart")
    finally:
        SimulationRunner._processes.pop("sim-restart", None)

    assert process.poll() is None


@pytest.mark.parametrize('first_platform', ['twitter', 'reddit'])
def test_parallel_run_does_not_finish_before_second_platform_creates_its_log(monkeypatch, tmp_path, first_platform):
    simulation_id = 'sim-late-platform'
    _write_simulation_end(tmp_path, simulation_id, [first_platform])
    state = SimulationRunState(
        simulation_id=simulation_id,
        runner_status=RunnerStatus.RUNNING,
        twitter_completed=first_platform == 'twitter',
        reddit_completed=first_platform == 'reddit',
    )
    state.platform = 'parallel'
    synced = []
    _patch_state_io(monkeypatch, tmp_path, state, synced)

    SimulationRunner._complete_if_rounds_finished(simulation_id, state)

    assert state.runner_status == RunnerStatus.RUNNING
    assert state.completed_at is None
    assert synced == []


@pytest.mark.parametrize('platform', ['twitter', 'reddit', 'parallel'])
def test_enabled_platform_survives_run_state_reload(monkeypatch, tmp_path, platform):
    import json
    simulation_id = 'sim-platform-persisted'
    directory = tmp_path / simulation_id
    directory.mkdir()
    state = SimulationRunState(simulation_id=simulation_id, platform=platform)
    (directory / 'run_state.json').write_text(json.dumps(state.to_dict()), encoding='utf-8')
    monkeypatch.setattr(SimulationRunner, 'RUN_STATE_DIR', str(tmp_path))
    assert SimulationRunner._load_run_state(simulation_id).platform == platform


@pytest.mark.parametrize('platform', ['twitter', 'reddit'])
def test_single_platform_completion_ignores_an_unselected_platform_log(monkeypatch, tmp_path, platform):
    simulation_id = 'sim-single-platform'
    _write_simulation_end(tmp_path, simulation_id, ['twitter', 'reddit'])
    state = SimulationRunState(
        simulation_id=simulation_id,
        runner_status=RunnerStatus.RUNNING,
        platform=platform,
        twitter_completed=platform == 'twitter',
        reddit_completed=platform == 'reddit',
    )
    synced = []
    _patch_state_io(monkeypatch, tmp_path, state, synced)
    SimulationRunner._complete_if_rounds_finished(simulation_id, state)
    assert state.runner_status == RunnerStatus.COMPLETED
    assert synced == [RunnerStatus.COMPLETED]


def test_force_restart_closes_resident_process_before_log_cleanup(monkeypatch):
    from types import SimpleNamespace
    from flask import Flask
    from app.api import simulation as api
    from app.services.simulation_manager import SimulationStatus

    events = []
    simulation = SimpleNamespace(status=SimulationStatus.COMPLETED, graph_id='graph', project_id='project')
    monkeypatch.setattr(api, 'SimulationManager', lambda: SimpleNamespace(
        get_simulation=lambda simulation_id: simulation,
        _save_simulation_state=lambda state: events.append('save'),
    ))
    monkeypatch.setattr(api, '_check_simulation_prepared', lambda simulation_id: (True, {}))
    monkeypatch.setattr(SimulationRunner, 'get_run_state', lambda simulation_id: SimulationRunState(simulation_id=simulation_id, runner_status=RunnerStatus.COMPLETED))
    monkeypatch.setattr(runner_module.ZepGraphMemoryManager, 'get_updater', lambda simulation_id: None)
    monkeypatch.setattr(SimulationRunner, '_close_finished_interview_process', lambda simulation_id: events.append('close'))
    monkeypatch.setattr(SimulationRunner, 'cleanup_simulation_logs', lambda simulation_id: (events.append('cleanup') or {'success': True}))
    monkeypatch.setattr(SimulationRunner, 'start_simulation', lambda **kwargs: (events.append('start') or SimpleNamespace(to_dict=lambda: {})))
    with Flask(__name__).test_request_context('/api/simulation/start', method='POST', json={'simulation_id': 'sim-force', 'force': True}):
        response = api.start_simulation()
    assert response.status_code == 200
    assert events.index('close') < events.index('cleanup') < events.index('start')
