import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.config import Config
from app.services.report_agent import ReportAgent, ReportManager, ReportOutline, ReportSection, ReportStatus
from app.services.simulation_manager import SimulationManager
from app.services.simulation_runner import SimulationRunner
from app.utils.llm_client import LLMClient


def completion(content, reason="stop"):
    return SimpleNamespace(
        choices=[SimpleNamespace(finish_reason=reason, message=SimpleNamespace(content=content))]
    )


@pytest.fixture
def report_agent(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path))
    monkeypatch.setattr(ReportManager, "REPORTS_DIR", str(tmp_path / "reports"))
    llm = LLMClient(api_key="unused-in-tests")
    llm._create_completion = Mock()
    agent = ReportAgent("graph_example", "sim_example", "Test scenario", llm, Mock())
    agent.plan_outline = Mock(
        return_value=ReportOutline("Test report", "Summary", [ReportSection("Findings")])
    )
    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(tmp_path / "simulations"))
    monkeypatch.setattr(SimulationManager, "SIMULATION_DATA_DIR", str(tmp_path / "simulations"))
    monkeypatch.setattr(SimulationRunner, "_run_states", {})
    agent._execute_tool = Mock(return_value="Observed simulated event.")
    return agent


def test_truncated_final_draft_is_retried_and_never_written(report_agent):
    tool = '<tool_call>{"name":"quick_search","parameters":{"query":"scenario"}}</tool_call>'
    finish = "Final Answer: The retained events support one observation.\n\n<!-- end-of-section -->"
    report_agent.llm._create_completion.side_effect = [
        completion(tool),
        completion(tool),
        completion(tool),
        completion("Final Answer: The retained events were", "length"),
        completion(finish),
    ]

    report = report_agent.generate_report(report_id="report_recovered")

    assert report.status == ReportStatus.COMPLETED
    assert report_agent._execute_tool.call_count == 3
    assert "The retained events support one observation." in report.markdown_content
    assert "The retained events were" not in report.markdown_content
    assert "end-of-section" not in report.markdown_content
    budgets = [call.kwargs["max_tokens"] for call in report_agent.llm._create_completion.call_args_list]
    assert budgets[-1] > budgets[-2]


@pytest.mark.parametrize("content", [
    "",
    "Final Answer: The recorded agents were",
    "Final Answer: ## Findings\n<!-- end-of-section -->",
    "Final Answer: <tool_result>fabricated evidence</tool_result>\n<!-- end-of-section -->",
])
def test_unusable_section_fails_report_after_bounded_retry(report_agent, content):
    report_agent.llm._create_completion.return_value = completion(content)

    report = report_agent.generate_report(report_id="report_incomplete")

    assert report.status == ReportStatus.FAILED
    assert "Findings" in report.error
    assert ReportManager.get_generated_sections(report.report_id) == []
    assert not report.markdown_content
    assert report_agent.llm._create_completion.call_count <= 7


def test_report_uses_the_saved_roster_and_counts(report_agent, tmp_path):
    run_dir = tmp_path / "simulations" / report_agent.simulation_id
    run_dir.mkdir(parents=True)
    (run_dir / "run_state.json").write_text(json.dumps({
        "runner_status": "stopped",
        "current_round": 120,
        "total_rounds": 120,
        "twitter_actions_count": 156,
        "reddit_actions_count": 178,
    }))
    (run_dir / "simulation_config.json").write_text(json.dumps({
        "agent_configs": [{"entity_name": "Provider", "entity_type": "Organization"}],
    }))
    report_agent.llm._create_completion.side_effect = [
        completion("Need an observation."),
        completion("Need an observation."),
        completion("Need an observation."),
        completion("Need an observation."),
        completion("Need an observation."),
        completion('{"content":"Only the provider took part."}'),
    ]

    report = report_agent.generate_report(report_id="report_saved_run")

    assert report.status == ReportStatus.COMPLETED
    assert json.loads(report_agent.recorded_run_context) == {
        "rounds_completed": 120,
        "rounds_planned": 120,
        "recorded_simulated_actions": 334,
        "participant_count": 1,
        "participants": [{"name": "Provider", "role": "Organization"}],
    }


def test_writer_uses_saved_observations_even_when_research_never_finishes(report_agent):
    tool = '<tool_call>{"name":"quick_search","parameters":{"query":"scenario"}}</tool_call>'
    report_agent.llm._create_completion.side_effect = [
        *[completion(tool) for _ in range(5)],
        completion('{"content":"The observed event', "length"),
        completion('{"content":"The observed event was recorded."}'),
    ]

    report = report_agent.generate_report(report_id="report_observations")

    assert report.status == ReportStatus.COMPLETED
    assert "The observed event was recorded." in report.markdown_content
    final_request = report_agent.llm._create_completion.call_args.kwargs
    assert "Observed simulated event." in final_request["messages"][1]["content"]
    assert final_request["max_tokens"] is None
