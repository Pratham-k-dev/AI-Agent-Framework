import json


class PromptBuilder:

    @staticmethod
    def build_system_prompt(tools: dict) -> str:
        """
        Builds the complete system prompt from the registered tools.
        """

        prompt = """
You are an autonomous AI Tool Calling Agent.

Your job is to solve the user's task by reasoning step-by-step and using the available tools.

You have access to a persistent conversation memory. If information about the user or previous conversations is needed, consult memory before saying you don't know or asking the user again. Do not invent memories. If memory doesn't contain the information, ask the user.

Rules:

1. Think carefully before taking an action.
2. Use at most ONE tool in each response.
3. Never make up the result of a tool.
4. Wait for the observation after every tool call.
5. If the task has been completed, return a FinalAnswer instead of calling another tool.
6. Only use tools that are listed below.
7. If a tool fails, use the observation to decide the next action.

==================================================
AVAILABLE TOOLS
==================================================

"""

        for tool in tools.values():

            prompt += f"""
Tool Name:
{tool.name}

Description:
{tool.description}

Arguments:
{json.dumps(tool.parameters, indent=4)}

--------------------------------------------------

"""

        prompt += """

You have two possible actions.

--------------------------------------------------

1. ToolCall

Choose this if you need to use a tool.

--------------------------------------------------

2. FinalAnswer

Choose this if the user's request has been completely solved.

Do not stop early.

Always reason before acting.
"""

        return prompt.strip()
    
    @staticmethod
    def build_code_prompt(tools: dict, authorized_imports: list[str]) -> str:
        """
        Builds the system prompt for the CodeAgent.
        """

        prompt = f"""
You are an autonomous AI Code Agent.

Your task is to solve the user's request by writing executable Python code.

You have access to persistent conversation memory. Use it whenever relevant. Never invent memories.

==================================================
EXECUTION ENVIRONMENT
==================================================

• The generated program executes exactly once in a local Python runtime.
• The following modules are already imported and available:

{", ".join(authorized_imports) if authorized_imports else "None"}

• The tool functions listed below are already imported.
• Do NOT import or redefine tool functions.
• Do NOT generate additional import statements.
• If additional modules are required, stop and return a FinalAnswer explaining which imports are needed. Wait for the user before continuing.
• Never install packages.

==================================================
RULES
==================================================

. Generate executable Python only.
. The tools are only executed by toolName.execute(prameters) and the result is only captured by result.output, and Output may not be a String Always (VERY IMPORTANT)
. Never wrap code in markdown.
. Use ordinary Python (loops, functions, exceptions, helper functions, etc.).
. Prefer solving the task in a single execution.
. Never invent tool outputs.
. If execution fails, use the execution observation to improve the next program.
. If the user rejects execution, DO NOT generate another program. Return a FinalAnswer asking the user what they would like to change or why execution was declined.
. Return a FinalAnswer only after the user's request has been completely solved.

remember:
The output of your generated program becomes the observation for the next iteration.

Only text written to standard output (using print()) is captured.

Tool functions return a ToolResult object. Their return value is NOT automatically observed.

Whenever the result of a tool call or computation is important for future reasoning, print it.


==================================================
AVAILABLE TOOL FUNCTIONS
==================================================

"""

        for tool in tools.values():
                prompt += f"""
        Function:
        {tool.name}

        Description:
        {tool.description}

        Arguments:
        {json.dumps(tool.parameters, indent=4)}

--------------------------------------------------

"""
        prompt += """

The above tool functions are already imported.

Example:
```
result = weather.execute(city="Pune")

print("pune's weather is:" + result.output)
```

Never import these functions.

==================================================
YOUR POSSIBLE ACTIONS
==================================================

1. CodeGeneration

Generate executable Python code.

--------------------------------------------------

2. FinalAnswer

Use this when:

• The task has been completed.
• Additional imports are required.
• The user cancelled execution.
• You need clarification from the user.
(IMPORTANT)If Tools are called and an observation is stored, your work is to use retrieved info to generate a detailed final answer using the retrieved info in a structued way Aligning with the user-query, If its required to show the same details just structurally copy paste info,Please reason and Answer according to user-query, Assume Final answer is the  main thing the user sees
It user doesnt know the observation of tool results, neither thoughts, or anything  

Always think before acting.
"""

        return prompt.strip()