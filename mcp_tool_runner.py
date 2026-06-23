import sys
import json
import os
import asyncio
import inspect
import logging

# Configure logging for the runner script and add current working dir
# Acts as an intermediary script by Node.js MCP server
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [MCP_RUNNER] - %(message)s')
sys.path.insert(0, os.getcwd())

try:
    from agents.learnflow_mcp_tool.learnflow_tool import LearnFlowMCPTool
    from agents.models import LearningUnit, ExplanationResponse, QuizResponse, MCQQuestion, OpenEndedQuestion, TrueFalseQuestion, FillInTheBlankQuestion
except ImportError as e:
    logging.error(f"Failed to import LearnFlow AI modules: {e}")
    logging.error(f"Current working directory: {os.getcwd()}")
    logging.error(f"Python path: {sys.path}")
    sys.exit(1)

# Initialize the LearnFlowMCPTool once
learnflow_tool_instance = LearnFlowMCPTool()

async def run_tool(tool_name=None, json_args=None):
    if tool_name is None and len(sys.argv) < 3:
        logging.error("Usage: python mcp_tool_runner.py <tool_name> <json_args>")
        sys.exit(1)

    tool_name = tool_name or sys.argv[1]
    json_args = json_args or sys.argv[2]

    try:
        args = json.loads(json_args)
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON arguments: {e}")
        sys.exit(1)

    logging.info(f"Received tool call: {tool_name} with args: {args}")

    # Convert dictionary arguments back to Pydantic models where necessary
    if tool_name == 'evaluate_mcq_response' and 'mcq_question' in args:
        args['mcq_question'] = MCQQuestion(**args['mcq_question'])
    elif tool_name == 'evaluate_open_ended_response' and 'open_ended_question' in args:
        args['open_ended_question'] = OpenEndedQuestion(**args['open_ended_question'])
    elif tool_name == 'evaluate_true_false_response' and 'tf_question' in args:
        args['tf_question'] = TrueFalseQuestion(**args['tf_question'])
    elif tool_name == 'evaluate_fill_in_the_blank_response' and 'fitb_question' in args:
        args['fitb_question'] = FillInTheBlankQuestion(**args['fitb_question'])

    tool_method = getattr(learnflow_tool_instance, tool_name, None)

    if not tool_method:
        logging.error(f"Tool '{tool_name}' not found in LearnFlowMCPTool.")
        sys.exit(1)

    try:
        if inspect.iscoroutinefunction(tool_method):
            result = await tool_method(**args)
        else:
            result = tool_method(**args)

        if isinstance(result, list) and all(isinstance(item, LearningUnit) for item in result):
            output = [item.model_dump() for item in result]
        elif isinstance(result, (ExplanationResponse, QuizResponse)):
            output = result.model_dump()
        else:
            output = result 

        print(json.dumps(output))
        logging.info(f"Successfully executed tool '{tool_name}'.")
    except Exception as e:
        logging.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_tool())
