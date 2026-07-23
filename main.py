"""Hosted-agent entrypoint for ZavaOps.

Wraps the multi-agent supervisor in Foundry's Responses protocol server.
Foundry injects FOUNDRY_PROJECT_ENDPOINT and AZURE_AI_MODEL_DEPLOYMENT_NAME into the
container; all other configuration comes from environmentVariables in azure.yaml.
"""
import os
import sys

from dotenv import load_dotenv
from agent_framework_foundry_hosting import ResponsesHostServer

# Repo root on the path so `src.agents.*` and the data/ folder resolve inside the container.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

REQUIRED_ENV = [
    "AZURE_AI_MODEL_DEPLOYMENT_NAME",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_SEARCH_ENDPOINT",
    "AZURE_SEARCH_INDEX",
    "MCP_SERVER_URL",
    "MCP_EXTENSION_KEY",
]


def main() -> None:
    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Set them via azure.yaml environmentVariables or `azd env set`."
        )

    # Imported here (not at module top) so the env check above produces a clear
    # error message before any agent tries to read configuration at import time.
    from src.agents.supervisor import build_supervisor

    agent = build_supervisor()
    server = ResponsesHostServer(agent)
    server.run()


if __name__ == "__main__":
    main()
