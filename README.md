# 🚀 LearnFlow AI: Revolutionizing Learning with AI Agents & MCP

LearnFlow AI transforms any document into a comprehensive, interactive learning experience through an innovative multi-agent system. Built with cutting-edge AI technologies and designed for the future of personalized education, it seamlessly integrates advanced RAG capabilities, MCP server functionality, and intelligent content generation.

## 🎯 Video Demo & Overview
🎬 Watch our comprehensive demo: [LearnFlow AI in Action](https://youtu.be/_AsLnPB8pN0)
Experience how LearnFlow AI revolutionizes document-based learning through intelligent agent orchestration and seamless user experience.

---
## ✨ Core Innovation & Features

LearnFlow AI's architecture and features are meticulously designed to excel according to the Hackathon guidelines, demonstrating innovation, performance, and practical utility, aligning with key award criteria:

### 🤖 Multi-Agent Intelligence System
Our sophisticated multi-agent system orchestrates the entire learning process, showcasing a robust and extensible AI framework.
*   **Planner Agent:** Employs an innovative "LLM-first" document understanding strategy, prioritizing native large language model comprehension for superior content summarization and unit generation. This approach, powered by leading LLMs like **Mistral AI** and others via our unified interface, ensures highly relevant and structured learning paths.
*   **Explainer Agent:** Generates contextual explanations with interactive visualizations and code execution. This agent's deep integration with **LlamaIndex Tool Integration** allows it to dynamically generate interactive code blocks and relevant visualizations, enhancing engagement and practical understanding.
*   **Examiner Agent:** Creates comprehensive assessments with instant evaluation capabilities. The optimized non-LLM evaluation for immediate feedback demonstrates high efficiency and responsiveness, aligning with **performance focus**.
*   **Unified Orchestration:** Central MCP tool coordination ensures seamless agent interaction, a core component of our novel approach to multi-agent coordination through the MCP protocol.

### 🔗 Model Context Protocol (MCP) Server
LearnFlow AI functions as a dedicated MCP server, exposing its core functionalities as accessible tools for external AI agents and systems. This integration is a prime example of **Innovative MCP Usage**.
*   **First-Class MCP Integration:** Our complete Node.js/TypeScript MCP server implementation exposes all learning capabilities, enabling other AI agents to programmatically access LearnFlow's intelligence.
*   **Automatic Background Launch:** Seamless Node.js server integration with the Python application, featuring a bidirectional Python-Node.js communication bridge with automatic lifecycle management, contributes to a production-ready architecture.
*   **Cross-Platform Compatibility:** Designed to work across local development, containers, and cloud deployment environments.

### 🔍 Advanced RAG & Document Processing
Our robust Retrieval-Augmented Generation (RAG) foundation is a key innovation, for powering LearnFlow AI.
*   **Smart Processing Strategy:** Features an LLM-native understanding with sophisticated semantic chunking fallback, ensuring comprehensive content ingestion.
*   **Vector-Enhanced Context:** Utilizes FAISS-powered semantic search with sentence transformers for efficient and accurate document retrieval.
*   **Cross-Reference Intelligence:** Contextual unit generation prevents overlap and builds intelligent connections between learning topics, enhancing the overall learning flow.
*   **Multi-Format Support:** Supports PDF, DOCX, PPTX, and TXT documents with seamless **LlamaIndex** integration for diverse content processing.

### 🎨 Rich Content Generation
LearnFlow AI delivers a superior learning experience through its ability to generate diverse and high-quality content.
*   **Interactive Visualizations:** AI-generated Plotly charts offer both interactive and static export options, providing dynamic data representation.
*   **Executable Code Blocks:** Live code generation with syntax highlighting and execution capabilities allows for hands-on learning.
*   **Perfect LaTeX Rendering:** Achieves professional mathematical notation in both web and PDF exports, crucial for technical and academic content.
*   **Professional PDF Export:** Our headless browser rendering ensures publication-quality PDF documents, a significant technical achievement.

### ⚡ Performance & User Experience
LearnFlow AI prioritizes a responsive and intuitive user experience, demonstrating high performance and practical utility, keeping a **User First** design in mind.
*   **Instantaneous Quiz Evaluation:** Optimized non-LLM evaluation for immediate feedback on multiple-choice, true/false, and fill-in-the-blank questions, showcasing efficient AI.
*   **Multi-Provider LLM Support:** Our unified interface supports **OpenAI**, **Mistral AI**, **Gemini**, and local models, offering flexibility and advanced utilization of cutting-edge language models. This multi-provider architecture, highlights flexible and advanced utilization of cutting-edge language models for diverse content generation tasks.
*   **Session Persistence:** Users can save and load learning sessions with comprehensive progress tracking, ensuring continuity and a seamless learning journey.
*   **Responsive UI:** A modern Gradio interface with real-time updates and status indicators provides an intuitive and engaging user experience.
*   **Scalability Foundation:** The multi-agent architecture is designed for horizontal scaling with independent agent processes, async processing for non-blocking content generation, and efficient resource optimization, reflecting a focus on **efficient and scalable AI solutions**.

---
## 🚀 Quick Start

### Prerequisites
*   Python 3.9+
*   Node.js 16+ (for MCP server)
*   4GB+ RAM recommended

### Installation
1.  **Open the project directory**
    ```bash
    cd LearnFlow-AI
    ```
2.  **Set up Python environment**
    ```bash
    python -m venv .venv

    # Windows
    .venv\Scripts\activate

    # macOS/Linux
    source .venv/bin/activate

    pip install -r requirements.txt
    ```
3.  **Configure MCP Server**
    ```bash
    cd mcp_server/learnflow-mcp-server
    npm install
    npm run build
    ```
4.  **Environment Configuration**
    ```bash
    # Copy example environment file
    cp .env.example .env

    # Add your API keys
    OPENAI_API_KEY=your_openai_key
    MISTRAL_API_KEY=your_mistral_key
    GEMINI_API_KEY=your_gemini_key
    ```
5.  **Launch Application**
    ```bash
    python app.py
    ```
    The application will automatically launch the MCP server in the background and open the Gradio interface.

---
## 📋 Usage Guide

### Basic Workflow
1.  📄 **Plan:** Upload documents and generate structured learning units.
2.  📚 **Learn:** Access detailed explanations with interactive content.
3.  📝 **Quiz:** Take comprehensive assessments with instant feedback.
4.  📊 **Progress:** Track learning progress and export results.

### Advanced Features
*   **Multi-Format Export:** JSON, Markdown, HTML, and professional PDF.
*   **Session Management:** Save and resume learning sessions.
*   **Custom AI Models:** Configure different LLM providers per task.
*   **Interactive Content:** Execute code blocks and view dynamic visualizations.

---
## 🏗️ Architecture Overview

```
LearnFlow AI/
├── agents/                 # Multi-agent system core
│   ├── planner/               # Document processing & unit generation
│   ├── explainer/             # Content explanation & visualization
│   ├── examiner/              # Quiz generation & evaluation
│   └── learnflow_mcp_tool/    # Central orchestration
├── mcp_server/                # Node.js MCP server wrapped on the orchestrator
├── services/                  # LLM factory & vector store
├── components/                # UI components & state management
└── utils/                     # Modular helper functions
```

### Key Technologies
*   **Frontend:** Gradio 5.32.0 with custom CSS
*   **AI/ML:** LlamaIndex, sentence-transformers, FAISS
*   **LLM Integration:** LiteLLM with multi-provider support
*   **MCP Server:** Node.js/TypeScript with MCP SDK
*   **Export:** Plotly, pyppeteer for PDF generation
*   **State Management:** Pydantic models for type safety

---
## 🚀 Deployment

### Docker Deployment
```dockerfile
FROM python:3.9-slim

# Install Node.js and Chromium
RUN apt-get update && apt-get install -y nodejs npm chromium

# Copy and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Build MCP server
RUN cd mcp_server/learnflow-mcp-server && npm install && npm run build

EXPOSE 7860

CMD ["python", "app.py"]
```

---
## 🤝 Contributing

We welcome contributions! 
### Development Setup
1.  Fork the repository.
2.  Create a feature branch
3.  Make your changes and ensure all features are tested.
4.  Submit a pull request.

### Reporting Issues
Please report bugs or request features if encountered.

---
## 📄 License

This project is licensed under the Apache License 2.0 - see the license file for details.

    http://www.apache.org/licenses/LICENSE-2.0



---
## 🙏 Acknowledgments

*   **LlamaIndex Team** for the powerful RAG framework.
*   **Mistral AI** for advanced language model capabilities.
*   **Gradio Team** for the excellent UI framework.
*   **MCP Community** for the innovative protocol specification.
*   **Generous API Credits from:**
    *   Anthropic
    *   OpenAI
    *   Nebius
    *   Hyperbolic Labs
    *   Sambanova

*   Open Source Contributors who make projects like this possible.

---
<div align="center">
Built with ❤️ for the future of AI-powered education
🌟 Star this repo • 🐛 Report Bug • 💡 Request Feature
</div>
