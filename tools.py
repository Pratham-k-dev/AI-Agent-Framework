from abc import ABC, abstractmethod
from pydantic import BaseModel

import inspect
from typing import get_origin, get_args,Any


import subprocess
import sys


class ToolResult(BaseModel):
    success: bool
    output: Any

    def __str__(self):
        return self.output


class BaseTool(ABC):
    name: str
    description: str
    parameters: dict = {}

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        pass

    def to_prompt(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }




class LocalRuntime:

    def execute(self, workspace, entry):

        process = subprocess.run(
            [sys.executable, entry],
            cwd=workspace.root,
            capture_output=True,
            text=True,
        )

        return {
            "exit_code": process.returncode,
            "output": process.stdout + process.stderr,
        }


class RunPythonTool(BaseTool):
    name = "run_python"
    description = "Execute a Python file locally."

    parameters = {
        "type": "object",
        "properties": {
            "entry": {
                "type": "string",
                "description": "Python file to execute.",
                "default": "main.py",
            }
        },
        "required": [],
    }

    def __init__(self, workspace, runtime):
        self.workspace = workspace
        self.runtime = runtime

    def execute(self, entry="main.py") -> ToolResult:

        result = self.runtime.execute(
            self.workspace,
            entry,
        )

        return ToolResult(
            success=result["exit_code"] == 0,
            output=result["output"],
        )
class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Create or overwrite a file."

    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Destination file path."
            },
            "content": {
                "type": "string",
                "description": "Content to write."
            }
        },
        "required": ["path", "content"]
    }

    def __init__(self, workspace):
        self.workspace = workspace

    def execute(self, path: str, content: str) -> ToolResult:
        self.workspace.write(path, content)

        return ToolResult(
            success=True,
            output=f"Successfully wrote '{path}'."
        )


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read a file."

    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path to read."
            }
        },
        "required": ["path"]
    }

    def __init__(self, workspace):
        self.workspace = workspace

    def execute(self, path: str) -> ToolResult:
        content = self.workspace.read(path)

        return ToolResult(
            success=True,
            output=content
        )


class AppendFileTool(BaseTool):
    name = "append_file"
    description = "Append content to a file."

    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path."
            },
            "content": {
                "type": "string",
                "description": "Content to append."
            }
        },
        "required": ["path", "content"]
    }

    def __init__(self, workspace):
        self.workspace = workspace

    def execute(self, path: str, content: str) -> ToolResult:
        self.workspace.append(path, content)

        return ToolResult(
            success=True,
            output=f"Successfully appended to '{path}'."
        )


class DeleteFileTool(BaseTool):
    name = "delete_file"
    description = "Delete a file."

    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File to delete."
            }
        },
        "required": ["path"]
    }

    def __init__(self, workspace):
        self.workspace = workspace

    def execute(self, path: str) -> ToolResult:
        self.workspace.delete(path)

        return ToolResult(
            success=True,
            output=f"Successfully deleted '{path}'."
        )
    
class DecoratedTool(BaseTool):

    def __init__(self, func):
        self.func = func

        self.name = func.__name__
        self.description = inspect.getdoc(func) or ""

        self.signature = inspect.signature(func)

        self.parameters = self._build_schema()

    def execute(self, **kwargs) -> ToolResult:

        result = self.func(**kwargs)

        if isinstance(result, ToolResult):
            return result

        return ToolResult(
            success=True,
            output=(result),
        )

    def _build_schema(self):

        properties = {}
        required = []

        for name, parameter in self.signature.parameters.items():

            annotation = parameter.annotation

            properties[name] = {
                "type": self._python_to_json(annotation),
                "description": f"{name} parameter"
            }

            if parameter.default is inspect.Parameter.empty:
                required.append(name)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    def _python_to_json(self, annotation):

        mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }

        return mapping.get(annotation, "string")


def _tool(func):
    return DecoratedTool(func)

class AgentTool(BaseTool):

    def __init__(self, agent):
        self.agent = agent

        self.name = agent.name
        self.description = agent.description

        self.parameters = {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Task to delegate to the agent."
                }
            },
            "required": ["task"],
        }

    def execute(self, task: str) -> ToolResult:

        result = self.agent.run(task)

        if isinstance(result, ToolResult):
            return result

        return ToolResult(
            success=True,
            output=result,
        )
    
class AgentTool(BaseTool):

    def __init__(self, agent):
        self.agent = agent

        self.name = agent.name
        self.description = agent.description

        self.parameters = {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Task to delegate to the agent."
                }
            },
            "required": ["task"],
        }

    def execute(self, task: str) -> ToolResult:

        result = self.agent.run(task)

        if isinstance(result, ToolResult):
            return result

        return ToolResult(
            success=True,
            output=result,
        )


def agent_tool(agent):
    return AgentTool(agent)
from ddgs import DDGS

import requests
import trafilatura


@_tool
def web_search(
    query: str,
    max_results: int = 3,
):
    """
    Search the web and return synthesized information from the top pages.
    """

    output = []

    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))

    for result in results:
        url = result["href"]

        try:
            html = requests.get(
                url,
                timeout=10,
                headers={
                    "User-Agent": "Mozilla/5.0"
                },
            ).text

            text = trafilatura.extract(html)

            output.append({
                "title": result["title"],
                "url": url,
                "content": text[:2500] if text else ""
            })

        except Exception:
            continue

    return output

import requests
from bs4 import BeautifulSoup

@_tool
def web_scrape(url: str):
    """
    Download and extract readable text from a webpage.
    """

    response = requests.get(
        url,
        timeout=10,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    soup = BeautifulSoup(response.text, "html.parser")

    return soup.get_text(
        separator="\n",
        strip=True
    )




