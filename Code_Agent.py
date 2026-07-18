from .workspace import  Workspace
from .prompt_builder import PromptBuilder
import time
from google.genai.errors import ClientError,ServerError
from dataclasses import dataclass
from typing import Any
from enum import Enum

from .Memory.memory import ConversationMemory
from .Memory.store import SQLiteStore
from .Memory.context import ContextBuilder
from .Memory.optimizer import ContextOptimizer, Summarizer
from .schemas import CodeAgentAction
from .tools import WriteFileTool,LocalRuntime, RunPythonTool
from pathlib import Path
from yaspin import yaspin
import sys

ROOT=Path(__file__).resolve().parent




class EventType(str, Enum):
    BANNER="banner"
    THINKING_STARTED="TH1"
    THINKING_ENDED="TH2"
    THOUGHT = "thought"
    CODE = "code"
    OBSERVATION = "observation"
    FINAL_ANSWER = "final_answer"
    ERROR = "error"
    CODE_GENERATED = "code_generated"
    EXECUTION_REQUEST = "execution_request"


@dataclass
class AgentEvent:
    type: EventType
    data: Any



def build_runtime(code, tool_modules=None, authorized_imports=None):

    tool_modules = tool_modules or []
    authorized_imports = authorized_imports or []

    runtime = []
   
    runtime.append("import sys")
   
    
    # Add tool module directories
    for module_path in tool_modules:
        module_path = Path(module_path)

        runtime.append(
            f'sys.path.insert(0, r"{module_path.parent}")'
        )
    framework_root = Path(__file__).resolve().parents[2]
    runtime.append(f'sys.path.insert(0, r"{framework_root}")')

    runtime.append("")

    # Import authorized modules
    for module in authorized_imports:
        runtime.append(f"import {module}")

    if authorized_imports:
        runtime.append("")

    # Import tool modules
    for module_path in tool_modules:
        module_name = Path(module_path).stem
        runtime.append(f"from {module_name} import *")
    runtime.append(f"from myagents.tools import *")
    runtime.append("")
    runtime.append(code)

    return "\n".join(runtime)

class CodeAgent:

    def __init__(
        self,
        model,
        tools,
        tool_paths=[],
        authorized_imports=[],
        max_iterations=2,
        cli_stream=False,
        callback=None,
        description=None,
        session_id="my_id",
        name=""
    ):

        self.model = model
        WorkDir=ROOT/"Workspace"
        self.workspace = Workspace("./myagents/Workspace")
        
        self.tools = {}
        for tool in tools:
            self.tools[tool.name] = tool
        self.tool_paths = tool_paths
        self.max_iterations = max_iterations

        self.authorized_imports=authorized_imports

        self.system_prompt = PromptBuilder.build_code_prompt(
            self.tools,
            self.authorized_imports
        )

        self.cli_stream = cli_stream
        self.callback = callback
        self.session_id=session_id
        storedir=ROOT/"memory.db"
        self.memory = ConversationMemory(
            store=SQLiteStore(db_path=str(storedir)),
            builder=ContextBuilder(),
            optimizer=ContextOptimizer(),
            summarizer=Summarizer(),
            session_id=self.session_id
        )
        self.runtime=LocalRuntime()
        self.write_tool=WriteFileTool(self.workspace)
        self.run_tool=RunPythonTool(self.workspace,self.runtime )
        self.description=description
        self.name=name
        

    # -------------------------------------------------------

    def _emit(self, event_type: EventType, data: Any):

        if self.cli_stream:
            self.cli_callback(
                AgentEvent(event_type, data)
            )

        if self.callback is not None:
            self.callback(
                AgentEvent(event_type, data)
            )

    # -------------------------------------------------------

    def cli_callback(self, event: AgentEvent):

        match event.type:
            case EventType.BANNER:
                print("="*75)
                BANNER = r"""
███╗   ███╗██╗   ██╗     █████╗  ██████╗ ███████╗███╗   ██╗████████╗███████╗
████╗ ████║╚██╗ ██╔╝    ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██╔════╝
██╔████╔██║ ╚████╔╝     ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ███████╗
██║╚██╔╝██║  ╚██╔╝      ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ╚════██║
██║ ╚═╝ ██║   ██║       ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ███████║
╚═╝     ╚═╝   ╚═╝       ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝

          Autonomous Agent Framework
"""

                print(BANNER)
                print("="*75)
            case EventType.THINKING_STARTED:
                if event.data and sys.stdout.isatty():
                    spinner=event.data
                    spinner.start()
            case EventType.THINKING_ENDED:
                if event.data and sys.stdout.isatty():
                    spinner = event.data
                    spinner.stop()

            case EventType.THOUGHT:
                print(f"💭 {event.data}")

            case EventType.EXECUTION_REQUEST:
                print(
                    "\nℹ️  Review the agent-generated code below."
                )
                print(
                    "    Before execution, the framework automatically prepares the runtime by:"
                )
                print(
                    "      • Importing all authorized modules."
                )
                print(
                    "      • Loading all registered tool modules."
                )
                print(
                    "      • Adapting tool calls to the framework's execution interface when required."
                )
                print(
                    "    The logic shown below is exactly what the agent wrote; only the execution environment is prepared automatically.\n"
                )
                print("\n📜 Generated Code ")
                print("-" * 60)
                print(event.data)
                print("-" * 60)

                while True:
                    choice = input("\nExecute this code? (yes/no): ").strip().lower()

                    if choice in ("yes", "y"):
                        return True

                    if choice in ("no", "n"):
                        return False

                    print("Please enter 'yes' or 'no'.")

            case EventType.OBSERVATION:
                print(f"📥 {event.data}")

            case EventType.FINAL_ANSWER:
                print(f"\n✅ {event.data}")

            case EventType.ERROR:
                print(f"❌ {event.data}")

    # -------------------------------------------------------
    def _request_execution(self, code):

        event = AgentEvent(
            EventType.EXECUTION_REQUEST,
            code
        )

        if self.callback is not None:
            return self.callback(event)

        if self.cli_stream:
            return self.cli_callback(event)

        return True

    def run(self, task: str):
        self._emit(EventType.BANNER,"")

        self.memory.add_user_message("user-query: "+ task)

        for _ in range(self.max_iterations):

            gemini_messages = self.memory.build_context(
                self.system_prompt
            )
            MAX_RETRIES = 3

            for attempt in range(MAX_RETRIES):

                try:
                    spinner=None
                    if sys.stdout.isatty():
                        spinner = yaspin(text="Thinking...", color="cyan")
                    self._emit(EventType.THINKING_STARTED,spinner)
                    action = self.model.generate(
                        gemini_messages,
                        CodeAgentAction
                    )
                    self._emit(EventType.THINKING_ENDED,spinner)
                    
                    break

                except ServerError:
                    if attempt == MAX_RETRIES - 1:
                        raise

                    wait = 2 ** attempt
                    
                    print(f"Server error. Retrying in {wait}s...")
                    time.sleep(wait)
                except Exception as e:
                    print(f"Unexpected {type(e).__name__}: {e}")
                    raise
            
            if not action:
                continue
            # ---------------------------------------------

            self._emit(
                EventType.THOUGHT,
                action.thought
            )

            # ---------------------------------------------
            # Final Answer
            # ---------------------------------------------

            if action.final_answer:
            
                self.memory.add_assistant_message(
                    action.final_answer
                )
            
                self.memory.optimize(self.model)
            
                return action.final_answer

            # ---------------------------------------------
            # Code Generation
            # ---------------------------------------------
            if(not action.code):
                continue

            approved = self._request_execution(action.code)
            

            if not approved:
                observation = (
                    "Execution cancelled by the user. "
                    "Generate a different solution or explain why execution is required."
                )
            else:
                # spinner = yaspin(text="Executing...", color="cyan")
                # spinner.start()
                spinner=None
                if sys.stdout.isatty():
                    spinner = yaspin(text="Executing...", color="cyan")
                if spinner:
                    spinner.start()
                runtime = build_runtime(
                    action.code,
                    self.tool_paths,
                    self.authorized_imports
                    
                )

                self.write_tool.execute(
                    path="runtime.py",
                    content=runtime,
                )

                observation = self.run_tool.execute(
                    entry="runtime.py",
                )
                observation="Code's result is:\n"+observation.output
                if spinner:
                    spinner.stop()
                
                # spinner.stop()
            self._emit(
                EventType.OBSERVATION,
                observation
            )

            # ---------------------------------------------

            self.memory.add_assistant_message(
                action.thought
            )

            self.memory.add_user_message(
                "Execution Result:\n" + observation
            )

            # self.memory.optimize(self.model)