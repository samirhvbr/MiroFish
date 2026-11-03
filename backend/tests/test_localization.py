import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

from app import create_app
from app.utils.locale import (
    get_language_instruction,
    get_locale,
    get_output_language,
    resolve_locale,
    set_locale,
    t,
)
from scripts.simulation_locale import apply_output_language, interview_prompt


@pytest.fixture(autouse=True)
def restore_thread_locale():
    previous = get_locale()
    yield
    set_locale(previous)


def flatten(value, prefix=''):
    if isinstance(value, dict):
        return {key: text for name, child in value.items()
                for key, text in flatten(child, f'{prefix}.{name}').items()}
    if isinstance(value, list):
        return {key: text for index, child in enumerate(value)
                for key, text in flatten(child, f'{prefix}.{index}').items()}
    return {prefix: value}


def test_brazilian_catalog_has_all_keys_and_interpolation_parameters():
    directory = Path(__file__).resolve().parents[2] / 'locales'
    catalogs = {language: flatten(json.loads((directory / f'{language}.json').read_text(encoding='utf-8')))
                for language in ('en', 'zh', 'pt-BR')}
    assert catalogs['en'].keys() == catalogs['zh'].keys() == catalogs['pt-BR'].keys()
    for key, translated in catalogs['pt-BR'].items():
        assert isinstance(translated, str) and translated.strip(), key
        parameters = lambda text: sorted(re.findall(r'\{\w+\}', text))
        assert parameters(translated) == parameters(catalogs['en'][key]), key
        assert not re.search(r'[\u3400-\u9fff]', translated), key


@pytest.mark.parametrize('tag', ['pt-BR', 'pt-br', 'PT_br', 'pt', 'pt-PT'])
def test_portuguese_tags_resolve_to_the_installed_brazilian_catalog(tag):
    assert resolve_locale(tag) == 'pt-BR'


@pytest.mark.parametrize(('header', 'expected'), [
    ('pt-BR,pt;q=0.9,en;q=0.8', 'pt-BR'),
    ('fr-FR;q=1,pt-BR;q=0.8,en;q=0.5', 'pt-BR'),
    ('pt-BR;q=0,en-US;q=0.9', 'en'),
    ('en;q=0.5,pt-BR;q=0.9', 'pt-BR'),
    ('en-US', 'en'),
    ('zh-CN', 'zh'),
    ('de-DE', 'en'),
    ('', 'en'),
])
def test_accept_language_negotiates_available_catalogs(header, expected):
    with Flask(__name__).test_request_context(headers={'Accept-Language': header}):
        assert get_locale() == expected


def test_background_tasks_use_brazilian_messages_and_ai_instructions():
    set_locale('pt-BR')
    assert t('log.prepareComplete') == '✓ Preparação concluída'
    assert t('api.projectNotFound', id='example') == 'Projeto não encontrado: example'
    assert 'português do Brasil' in get_language_instruction()
    assert 'chaves JSON' in get_language_instruction()
    assert get_output_language() == 'Brazilian Portuguese'


def test_api_validation_is_localized_without_changing_status_or_fields():
    app = create_app()
    client = app.test_client()
    response = client.post('/api/simulation/create', json={}, headers={'Accept-Language': 'pt-BR,pt;q=0.9'})
    assert response.status_code == 400
    assert response.json['success'] is False
    assert response.json['error'] == 'Informe o identificador do projeto (project_id)'


def test_new_oasis_agents_receive_the_requested_output_language(monkeypatch):
    agents = [SimpleNamespace(output_language=None), SimpleNamespace(output_language=None)]
    graph = SimpleNamespace(get_agents=lambda: enumerate(agents))
    monkeypatch.setenv('MIROFISH_OUTPUT_LANGUAGE', 'Brazilian Portuguese')
    apply_output_language(graph)
    assert all(agent.output_language == 'Brazilian Portuguese' for agent in agents)


def test_unconfigured_output_language_preserves_existing_agent_behavior(monkeypatch):
    agent = SimpleNamespace(output_language='existing')
    graph = SimpleNamespace(get_agents=lambda: [(0, agent)])
    monkeypatch.delenv('MIROFISH_OUTPUT_LANGUAGE', raising=False)
    apply_output_language(graph)
    assert agent.output_language == 'existing'


def test_interviews_retain_the_question_and_request_brazilian_portuguese(monkeypatch):
    monkeypatch.setenv('MIROFISH_OUTPUT_LANGUAGE', 'Brazilian Portuguese')
    assert interview_prompt('What changed?') == 'What changed?\n\nRespond in Brazilian Portuguese.'


def test_unconfigured_interviews_preserve_the_original_prompt(monkeypatch):
    monkeypatch.delenv('MIROFISH_OUTPUT_LANGUAGE', raising=False)
    assert interview_prompt('Original question') == 'Original question'


@pytest.mark.parametrize('platform', ['twitter', 'reddit', 'parallel'])
def test_requested_language_reaches_each_simulation_subprocess(monkeypatch, tmp_path, platform):
    from app.services import simulation_runner as module

    runner = module.SimulationRunner
    simulation_id = 'sim-locale'
    sim_dir = tmp_path / simulation_id
    sim_dir.mkdir()
    (sim_dir / 'simulation_config.json').write_text(json.dumps({
        'time_config': {'total_simulation_hours': 1, 'minutes_per_round': 60},
    }), encoding='utf-8')
    scripts_dir = tmp_path / 'scripts'
    scripts_dir.mkdir()
    (scripts_dir / f'run_{platform}_simulation.py').write_text('', encoding='utf-8')
    monkeypatch.setattr(runner, 'RUN_STATE_DIR', str(tmp_path))
    monkeypatch.setattr(runner, 'SCRIPTS_DIR', str(scripts_dir))
    for name in ('_run_states', '_processes', '_monitor_threads', '_action_queues',
                 '_stdout_files', '_stderr_files', '_graph_memory_enabled', '_finalization_locks'):
        monkeypatch.setattr(runner, name, {})
    monkeypatch.setattr(runner, '_sync_simulation_status', lambda *_args: None)
    monkeypatch.setattr(module.threading, 'Thread', lambda **_kwargs: SimpleNamespace(start=lambda: None))
    captured = {}

    def fake_process(_command, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(pid=123, poll=lambda: None)

    monkeypatch.setattr(module.subprocess, 'Popen', fake_process)
    # A browser's normal compound language header must survive the subprocess boundary.
    with Flask(__name__).test_request_context(headers={'Accept-Language': 'pt-BR,pt;q=0.9'}):
        try:
            runner.start_simulation(simulation_id, platform=platform, enable_graph_memory_update=False)
            assert captured['env']['MIROFISH_OUTPUT_LANGUAGE'] == 'Brazilian Portuguese'
        finally:
            if simulation_id in runner._stdout_files:
                runner._stdout_files[simulation_id].close()
