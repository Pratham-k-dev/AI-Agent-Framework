from .workspace import Workspace
from .tools import RunPythonTool, ReadFileTool,WriteFileTool,AppendFileTool,DeleteFileTool,LocalRuntime
from .prompt_builder import PromptBuilder
import time
from google.genai.errors import ClientError,ServerError
import json
from dataclasses import dataclass
from typing import Any, Callable, Optional
from enum import Enum
from .Memory.memory import ConversationMemory
from .Memory.store import SQLiteStore
from .Memory.context import ContextBuilder
from .Memory.optimizer import ContextOptimizer,Summarizer
import sys
from yaspin import yaspin
# class MockAction:
#     def __init__(self):
#         self.thought = "Write fibonacci to code.py"
#         self.tool = "write_file"
#         self.arguments = {
#             "path": "code.py",
#             "content": """def fibonacci(n):
#     a, b = 0, 1
#     for _ in range(n):
#         print(a, end=" ")
#         a, b = b, a + b
#     print()

# if __name__ == "__main__":
#     fibonacci(10)
# """
#         }
#         self.final_answer = None

from .schemas import AgentAction
class ToolResult:
    def __init__(
        self,
        success: bool,
        output: str,
    ):
        self.success = success
        self.output = output

class EventType(str, Enum):
    THOUGHT = "thought"
    TOOL_CALL = "tool_call"
    OBSERVATION = "observation"
    FINAL_ANSWER = "final_answer"
    ERROR = "error"


@dataclass
class AgentEvent:
    type: EventType
    data: Any


class ToolAgent:
    def __init__(
        self,
        model,
        tools,
        max_iterations=2,
        cli_stream=False,
        callback=None,
        description=None,
        session_id="abc"
    ):
        self.model = model
        self.workspace = Workspace("./myagents/WorkSpace")
        
        self.max_iterations = max_iterations
        self.runtime=LocalRuntime()
        builtin_tools = [
            ReadFileTool(self.workspace),
            WriteFileTool(self.workspace),
            AppendFileTool(self.workspace),
            DeleteFileTool(self.workspace),
            RunPythonTool(self.workspace,self.runtime),
        ]
        self.tools = {}
        for tool in builtin_tools:
            self.tools[tool.name] = tool

        for tool in (tools or []):
            if tool.name in self.tools:
                raise ValueError(f"Tool '{tool.name}' already exists.")
            self.tools[tool.name] = tool

        self.system_prompt = PromptBuilder.build_system_prompt(
            self.tools
        )
        self.session_id=session_id
        self.cli_stream=cli_stream
        self.callback = callback
        self.memory = ConversationMemory(
            store=SQLiteStore(db_path="./myagents/memory.db"),
            builder=ContextBuilder(),
            optimizer=ContextOptimizer(),
            summarizer=Summarizer(),
            session_id=self.session_id
        )
        self.description=description
        
    def _emit(self, event_type: EventType, data: Any):
            """
            Sends an event to whoever is listening.
            If no callback is registered, nothing happens.
            """
            if(self.cli_stream):
                event = AgentEvent(
                type=event_type,
                data=data,
                )
                self.cli_callback(event)



            if self.callback is None:
                return

            event = AgentEvent(
                type=event_type,
                data=data,
            )

            self.callback(event)
    def cli_callback(self,event: AgentEvent):

        match event.type:

            case EventType.THOUGHT:
                print(f"💭 {event.data}")

            case EventType.TOOL_CALL:
                print(f"🔧 {event.data['tool']}")
                print(f"   args: {event.data['arguments']}")

            case EventType.OBSERVATION:
                print(f"📥 {event.data}")

            case EventType.FINAL_ANSWER:
                print(f"\n✅ {event.data}")

            case EventType.ERROR:
                print(f"❌ {event.data}")

    def run(self, task: str):
        if sys.stdout.isatty():
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

        self.memory.add_user_message(
                
                task
            )
        for iteration in range(self.max_iterations):
            # gemini_messages = []

                # for msg in messages:
                #     gemini_messages.append(
                #         {
                #             "role": "user" if msg["role"] == "user" else "user",
                #             "parts": [
                #                 {
                #                     "text": msg["content"]
                #                 }
                #             ]
                #         }
                #     )
            gemini_messages = self.memory.build_context(
                self.system_prompt
            )
            action=None
            MAX_RETRIES = 3

            for attempt in range(MAX_RETRIES):

                try:
                    spinner=None
                    if sys.stdout.isatty():
                        spinner = yaspin(text="Thinking...", color="cyan")
                    if spinner:
                        spinner.start()
                    action = self.model.generate(
                        gemini_messages,
                        AgentAction
                    )
                    if spinner:
                        spinner.stop()
                    break

                except ServerError:
                    if attempt == MAX_RETRIES - 1:
                        raise

                    wait = 2 ** attempt
                    
                    print(f"Server error. Retrying in {wait}s...")
                    time.sleep(wait)
                    
            if(not action):
                continue
            self._emit(
                EventType.THOUGHT,
                action.thought
            )
            if action.final_answer:
                self.memory.add_assistant_message(
                    
                    action.final_answer
                )
                self.memory.optimize(self.model)
                return action.final_answer

            tool = self.tools.get(action.tool)
            

            
            if tool is None:
                observation = f"Unknown tool '{action.tool}'"
            else:            
                try:
                    args=None
                    self._emit(
                        EventType.TOOL_CALL,
                        {
                            "tool": action.tool,
                            "arguments": action.arguments,
                        }
                    )
                    if action.arguments is not None: 
                        args = json.loads(action.arguments)
                    observation = tool.execute(** args)
                    self._emit(
                        EventType.OBSERVATION,
                        observation,
                    )
                    observation="toolresult: "+ observation.output
                except Exception as e:
                    observation = str(e)
                    self._emit(
                        EventType.ERROR,
                        str(e),
                    )
            self.memory.add_assistant_message(
                
                action.thought
            )
            self.memory.add_user_message(
                observation
            )
            self.memory.optimize(self.model)
            
            # messages.append({
            #     "role":"assistant",
            #     "content":action.thought
            # })

            # messages.append({
            #     "role":"user",
            #     "content":f"Observation:\n{observation}"
            # })
            # print(messages)
            