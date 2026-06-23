#!/usr/bin/env node
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ErrorCode,
  ListToolsRequestSchema,
  McpError,
} from '@modelcontextprotocol/sdk/types.js';
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Adjust this path to the root of your LearnFlow AI project
const LEARNFLOW_AI_ROOT = process.env.LEARNFLOW_AI_ROOT || path.resolve(__dirname, '../../../../'); // Assuming learnflow-mcp-server is in C:\Users\kaido\Documents\Cline\MCP

// Determine the correct Python executable path within the virtual environment
const PYTHON_EXECUTABLE = process.platform === 'win32'
  ? path.join(LEARNFLOW_AI_ROOT, '.venv', 'Scripts', 'python.exe')
  : path.join(LEARNFLOW_AI_ROOT, '.venv', 'bin', 'python');

class LearnFlowMCPWrapperServer {
  private server: Server;

  constructor() {
    this.server = new Server(
      {
        name: 'learnflow-mcp-server',
        version: '0.1.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.setupToolHandlers();

    this.server.onerror = (error) => console.error('[MCP Error]', error);
    process.on('SIGINT', async () => {
      await this.server.close();
      process.exit(0);
    });
  }

  private async callPythonTool(toolName: string, args: any): Promise<any> {
    return new Promise((resolve, reject) => {
      const pythonScriptPath = path.join(LEARNFLOW_AI_ROOT, 'mcp_tool_runner.py'); // A new Python script to act as an intermediary
      const packagedExecutable = process.env.LEARNFLOW_MCP_EXECUTABLE;
      const command = packagedExecutable || PYTHON_EXECUTABLE;
      const pythonArgs = packagedExecutable
        ? ['--mcp-tool', toolName, JSON.stringify(args)]
        : [pythonScriptPath, toolName, JSON.stringify(args)];

      const pythonProcess = spawn(command, pythonArgs, {
        cwd: LEARNFLOW_AI_ROOT, // Ensure Python script runs from the LearnFlow AI root
        env: { ...process.env, PYTHONPATH: LEARNFLOW_AI_ROOT }, // Add LearnFlow AI root to PYTHONPATH
      });

      let stdout = '';
      let stderr = '';

      pythonProcess.stdout.on('data', (data) => {
        stdout += data.toString();
      });

      pythonProcess.stderr.on('data', (data) => {
        stderr += data.toString();
      });

      pythonProcess.on('close', (code) => {
        if (code === 0) {
          try {
            resolve(JSON.parse(stdout));
          } catch (e: unknown) { // Explicitly type 'e' as unknown
            const errorMessage = e instanceof Error ? e.message : String(e);
            console.error(`[MCP Wrapper] Failed to parse JSON from Python stdout: ${stdout}`);
            reject(new McpError(ErrorCode.InternalError, `Failed to parse Python output: ${errorMessage}`));
          }
        } else {
          console.error(`[MCP Wrapper] Python script exited with code ${code}`);
          console.error(`[MCP Wrapper] Python stdout: ${stdout}`);
          console.error(`[MCP Wrapper] Python stderr: ${stderr}`);
          reject(new McpError(ErrorCode.InternalError, `Python script error: ${stderr || 'Unknown error'}`));
        }
      });

      pythonProcess.on('error', (err) => {
        console.error(`[MCP Wrapper] Failed to start Python subprocess: ${err.message}`);
        reject(new McpError(ErrorCode.InternalError, `Failed to start Python subprocess: ${err.message}`));
      });
    });
  }

  private setupToolHandlers() {
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: [
        {
          name: 'plan_learning_units',
          description: 'Generates a list of learning units from the provided content.',
          inputSchema: {
            type: 'object',
            properties: {
              content: { type: 'string', description: 'The content to process (raw text or PDF file path).' },
              input_type: { type: 'string', enum: ['PDF', 'Text'], description: 'The type of the input content.' },
              llm_provider: { type: 'string', description: 'The LLM provider to use for planning.' },
              model_name: { type: 'string', description: 'The specific model name to use. Defaults to None.' },
              api_key: { type: 'string', description: 'The API key to use. Defaults to None.' },
            },
            required: ['content', 'input_type', 'llm_provider'],
          },
        },
        {
          name: 'generate_explanation',
          description: 'Generates an explanation for a given learning unit.',
          inputSchema: {
            type: 'object',
            properties: {
              unit_title: { type: 'string', description: 'The title of the learning unit.' },
              unit_content: { type: 'string', description: 'The raw content of the learning unit.' },
              explanation_style: { type: 'string', enum: ['Concise', 'Detailed'], description: 'The desired style of explanation.' },
              llm_provider: { type: 'string', description: 'The LLM provider to use for explanation generation.' },
              model_name: { type: 'string', description: 'The specific model name to use. Defaults to None.' },
              api_key: { type: 'string', description: 'The API key to use. Defaults to None.' },
            },
            required: ['unit_title', 'unit_content', 'explanation_style', 'llm_provider'],
          },
        },
        {
          name: 'generate_quiz',
          description: 'Generates a quiz for a given learning unit.',
          inputSchema: {
            type: 'object',
            properties: {
              unit_title: { type: 'string', description: 'The title of the learning unit.' },
              unit_content: { type: 'string', description: 'The raw content of the learning unit.' },
              llm_provider: { type: 'string', description: 'The LLM provider to use for quiz generation.' },
              model_name: { type: 'string', description: 'The specific model name to use. Defaults to None.' },
              api_key: { type: 'string', description: 'The API key to use. Defaults to None.' },
              difficulty: { type: 'string', description: 'The desired difficulty level of the quiz (e.g., "Easy", "Medium", "Hard").', default: 'Medium' },
              num_questions: { type: 'number', description: 'The total number of questions to generate.', default: 8 },
              question_types: { type: 'array', items: { type: 'string', enum: ["Multiple Choice", "Open-Ended", "True/False", "Fill in the Blank"] }, description: 'A list of desired question types (e.g., ["MCQ", "Open-Ended"]).', default: ["Multiple Choice", "Open-Ended", "True/False", "Fill in the Blank"] },
            },
            required: ['unit_title', 'unit_content', 'llm_provider'],
          },
        },
        {
          name: 'evaluate_mcq_response',
          description: 'Evaluates a user\'s response to a multiple-choice question.',
          inputSchema: {
            type: 'object',
            properties: {
              mcq_question: { type: 'object', description: 'The MCQ question object.' },
              user_answer_key: { type: 'string', description: 'The key corresponding to the user\'s selected answer.' },
              llm_provider: { type: 'string', description: 'The LLM provider.' },
              model_name: { type: 'string', description: 'The specific model name to use. Defaults to None.' },
              api_key: { type: 'string', description: 'The API key to use. Defaults to None.' },
            },
            required: ['mcq_question', 'user_answer_key', 'llm_provider'],
          },
        },
        {
          name: 'evaluate_true_false_response',
          description: 'Evaluates a user\'s response to a true/false question.',
          inputSchema: {
            type: 'object',
            properties: {
              tf_question: { type: 'object', description: 'The True/False question object.' },
              user_answer: { type: 'boolean', description: 'The user\'s true/false answer.' },
              llm_provider: { type: 'string', description: 'The LLM provider.' },
              model_name: { type: 'string', description: 'The specific model name to use. Defaults to None.' },
              api_key: { type: 'string', description: 'The API key to use. Defaults to None.' },
            },
            required: ['tf_question', 'user_answer', 'llm_provider'],
          },
        },
        {
          name: 'evaluate_fill_in_the_blank_response',
          description: 'Evaluates a user\'s response to a fill-in-the-blank question.',
          inputSchema: {
            type: 'object',
            properties: {
              fitb_question: { type: 'object', description: 'The FillInTheBlank question object.' },
              user_answer: { type: 'string', description: 'The user\'s answer for the blank.' },
              llm_provider: { type: 'string', description: 'The LLM provider.' },
              model_name: { type: 'string', description: 'The specific model name to use. Defaults to None.' },
              api_key: { type: 'string', description: 'The API key to use. Defaults to None.' },
            },
            required: ['fitb_question', 'user_answer', 'llm_provider'],
          },
        },
        {
          name: 'evaluate_open_ended_response',
          description: 'Evaluates a user\'s response to an open-ended question.',
          inputSchema: {
            type: 'object',
            properties: {
              open_ended_question: { type: 'object', description: 'The open-ended question object.' },
              user_answer_text: { type: 'string', description: 'The user\'s free-form answer.' },
              llm_provider: { type: 'string', description: 'The LLM provider.' },
              model_name: { type: 'string', description: 'The specific model name to use. Defaults to None.' },
              api_key: { type: 'string', description: 'The API key to use. Defaults to None.' },
            },
            required: ['open_ended_question', 'user_answer_text', 'llm_provider'],
          },
        },
      ],
    }));

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      try {
        const result = await this.callPythonTool(request.params.name, request.params.arguments);
        // Convert the JSON result to a string to satisfy the 'text' type expectation
        return {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
        };
      } catch (error: unknown) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        console.error(`[MCP Wrapper] Error calling Python tool ${request.params.name}:`, error);
        if (error instanceof McpError) {
          throw error;
        }
        throw new McpError(ErrorCode.InternalError, `Failed to execute tool: ${errorMessage}`);
      }
    });
  }

  async run() {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error('LearnFlow MCP wrapper server running on stdio');
  }
}

const server = new LearnFlowMCPWrapperServer();
server.run().catch(console.error);
