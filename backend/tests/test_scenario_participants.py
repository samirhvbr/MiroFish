import io
import time

import pytest

from app import create_app
from app.api import graph as graph_api
from app.api import simulation as simulation_api
from app.config import Config
from app.models.project import ProjectManager, ProjectStatus
from app.services import simulation_manager as simulation_manager_module
from app.services.oasis_profile_generator import OasisProfileGenerator
from app.services.simulation_config_generator import SimulationConfigGenerator
from app.services.simulation_manager import SimulationManager
from app.services.zep_entity_reader import EntityNode, FilteredEntities

REQUESTED_ROLES = [
    "Small-business owner",
    "IT manager",
    "Residential user",
    "Existing customer",
    "Competing provider",
    "Consumer advocate",
]
SOURCE_ACTORS = ["Provider", "Provider Internet", "Corporate Internet", "Network Services"]


@pytest.fixture
def client(tmp_path, monkeypatch):
    class FakeOntologyGenerator:
        def generate(self, **kwargs):
            return {
                "entity_types": [],
                "edge_types": [],
                "scenario_participants": [
                    *REQUESTED_ROLES, "it manager", " Provider ", None,
                ],
            }

    class SourceGraphReader:
        def filter_defined_entities(self, **kwargs):
            return FilteredEntities(
                [
                    EntityNode(f"source-{index}", name, ["Organization"], "Provider", {})
                    for index, name in enumerate(SOURCE_ACTORS)
                ],
                {"Organization"},
                len(SOURCE_ACTORS),
                len(SOURCE_ACTORS),
            )

    monkeypatch.setattr(Config, "LLM_API_KEY", "unused-in-tests")
    monkeypatch.setattr(Config, "ZEP_API_KEY", "")
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(tmp_path / "projects"))
    monkeypatch.setattr(SimulationManager, "SIMULATION_DATA_DIR", str(tmp_path / "simulations"))
    monkeypatch.setattr(Config, "OASIS_SIMULATION_DATA_DIR", str(tmp_path / "simulations"))
    monkeypatch.setattr(graph_api, "OntologyGenerator", FakeOntologyGenerator)
    monkeypatch.setattr(simulation_api, "ZepEntityReader", SourceGraphReader)
    monkeypatch.setattr(simulation_manager_module, "ZepEntityReader", SourceGraphReader)
    monkeypatch.setattr(OasisProfileGenerator, "_build_entity_context", lambda self, entity: "")
    monkeypatch.setattr(SimulationConfigGenerator, "_call_llm_with_retry", lambda *args, **kwargs: {})

    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


@pytest.mark.parametrize("manual,expected_roles", [
    ("", REQUESTED_ROLES),
    ("IT manager\nSkeptical customer\nIT MANAGER", ["IT manager", "Skeptical customer"]),
])
def test_scenario_roles_reach_both_platform_profiles_and_agent_config(client, manual, expected_roles):
    response = client.post("/api/graph/ontology/generate", data={
        "files": (io.BytesIO(b"Public marketing text from a provider."), "source.txt"),
        "simulation_requirement": "Compare reactions from " + ", ".join(REQUESTED_ROLES),
        "scenario_participants": manual,
    })
    assert response.status_code == 200, response.json
    project = ProjectManager.get_project(response.json["data"]["project_id"])
    # A synthetic role must not be stored as a graph type or a source fact.
    assert project.ontology == {"entity_types": [], "edge_types": []}
    project.status = ProjectStatus.GRAPH_COMPLETED
    project.graph_id = "graph_example"
    ProjectManager.save_project(project)
    simulation = SimulationManager().create_simulation(project.project_id, project.graph_id)
    sid = simulation.simulation_id

    response = client.post("/api/simulation/prepare", json={
        "simulation_id": sid, "use_llm_for_profiles": False,
    })
    assert response.status_code == 200, response.json
    task = response.json["data"]
    expected = [*SOURCE_ACTORS, *expected_roles]
    assert task["expected_entities_count"] == len(expected)

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.post("/api/simulation/prepare/status", json={
            "simulation_id": sid, "task_id": task["task_id"],
        })
        status = response.json["data"]
        if status["status"] in {"completed", "ready", "failed"}:
            break
        time.sleep(0.02)
    assert status["status"] in {"completed", "ready"}, status

    manager = SimulationManager()
    for platform in ("twitter", "reddit"):
        profiles = manager.get_profiles(sid, platform)
        assert [profile["name"] for profile in profiles] == expected
        assert [int(profile["user_id"]) for profile in profiles] == list(range(len(expected)))
        if platform == "reddit":
            assert [profile["profession"] for profile in profiles[len(SOURCE_ACTORS):]] == expected_roles
        persona_field = "user_char" if platform == "twitter" else "persona"
        for profile in profiles[len(SOURCE_ACTORS):]:
            assert "fictional participant" in profile[persona_field]
            assert profile["name"] in profile[persona_field]

    config = manager.get_simulation_config(sid)["agent_configs"]
    assert [agent["entity_name"] for agent in config] == expected
    assert [agent["agent_id"] for agent in config] == list(range(len(expected)))
    assert all(agent["entity_type"] == "ScenarioParticipant" for agent in config[len(SOURCE_ACTORS):])


def test_excessive_manual_role_list_is_rejected_before_project_creation(client):
    response = client.post("/api/graph/ontology/generate", data={
        "simulation_requirement": "Compare stakeholders.",
        "scenario_participants": "\n".join(f"Role {i}" for i in range(13)),
    }, headers={"Accept-Language": "pt-BR"})
    assert response.status_code == 400
    assert "até 12 papéis" in response.json["error"]
    assert ProjectManager.list_projects() == []
