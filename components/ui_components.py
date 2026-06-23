import gradio as gr
from typing import List, Optional
from services.llm_factory import get_default_model


def create_provider_dropdown(providers: List[str], default_value: str = "mistral") -> gr.Dropdown:
    """Creates a standardized LLM provider dropdown."""
    return gr.Dropdown(providers, value=default_value, label="AI 提供商")


def create_llm_config_inputs(providers: List[str], default_provider: str = "mistral", initial_api_key: str = "") -> dict:
    """Creates a 3-column AI provider configuration with Provider, Model Name, and API Key."""
    with gr.Row():
        provider_dropdown = gr.Dropdown(
            choices=providers,
            value=default_provider,
            label="AI 提供商",
            interactive=True
        )
        
        model_textbox = gr.Textbox(
            label="模型名称",
            placeholder=f"默认：{get_default_model(default_provider)}",
            value="",
            interactive=True,
        )
        
        api_key_textbox = gr.Textbox(
            label="API 密钥",
            placeholder="默认：从本地 .env 文件读取",
            value=initial_api_key, 
            type="password",
            interactive=True,
        )
    
    # Update model placeholder when provider changes
    def update_model_placeholder(provider):
        default_model = get_default_model(provider)
        return gr.update(placeholder=f"默认：{default_model}")
    
    provider_dropdown.change(
        fn=update_model_placeholder,
        inputs=[provider_dropdown],
        outputs=[model_textbox]
    )
    
    return {
        "provider": provider_dropdown,
        "model": model_textbox,
        "api_key": api_key_textbox,
        "provider_dropdown_component": provider_dropdown, 
        "api_key_textbox_component": api_key_textbox 
    }


def create_unit_dropdown(default_label: str = "Select Generated Unit") -> gr.Dropdown:
    """Creates a standardized unit selection dropdown."""
    return gr.Dropdown(
        choices=["Select Generated Unit"], 
        value="Select Generated Unit", 
        label=default_label, 
        interactive=True
    )


def create_file_upload() -> gr.File:
    """Creates a standardized file upload component."""
    return gr.File(
        label="",
        file_types=[".pdf", ".doc", ".txt", ".pptx", ".md"],
        height=200
    )


def create_text_input(label: str = "Text Input", lines: int = 4) -> gr.Textbox:
    """Creates a standardized text input component."""
    return gr.Textbox(
        placeholder="在此粘贴学习内容...",
        lines=lines,
        label=""
    )


def create_status_markdown(initial_text: str = "Ready") -> gr.Markdown:
    """Creates a standardized status display."""
    return gr.Markdown(initial_text)


def create_primary_button(text: str, size: str = "lg") -> gr.Button:
    """Creates a standardized primary button."""
    return gr.Button(text, variant="primary", size=size, elem_classes="learnflow-button-large learnflow-button-rounded")


def create_secondary_button(text: str, size: str = "lg", elem_classes: Optional[str] = None) -> gr.Button:
    """Creates a standardized secondary button."""
    classes = "learnflow-button-large learnflow-button-rounded"
    if elem_classes:
        classes += f" {elem_classes}"
    return gr.Button(text, variant="secondary", size=size, elem_classes=classes)


def create_quiz_components():
    """Creates standardized quiz UI components."""
    mcq_section = gr.Column(visible=False, elem_classes="quiz-section")
    with mcq_section:
        mcq_question = gr.Markdown("### 多选题")
        mcq_choices = gr.Radio(choices=[], label="选择你的答案", elem_classes="quiz-answer-radio")
        mcq_submit = gr.Button("提交多选题答案", elem_classes="learnflow-button-large learnflow-button-rounded")
        mcq_feedback = gr.Markdown("", elem_classes="correct-feedback")
        mcq_next = gr.Button("下一题", visible=False, elem_classes="learnflow-button-large learnflow-button-rounded")

    open_ended_section = gr.Column(visible=False, elem_classes="quiz-section")
    with open_ended_section:
        open_question = gr.Markdown("### 开放题")
        open_answer = gr.Textbox(label="你的答案", lines=4, placeholder="在此输入答案...")
        open_submit = gr.Button("提交开放题答案", elem_classes="learnflow-button-large learnflow-button-rounded")
        open_feedback = gr.Markdown("", elem_classes="correct-feedback")
        open_next = gr.Button("下一道开放题", visible=False, elem_classes="learnflow-button-large learnflow-button-rounded") 

    tf_section = gr.Column(visible=False, elem_classes="quiz-section")
    with tf_section:
        tf_question = gr.Markdown("### 判断题")
        tf_choices = gr.Radio(choices=["True", "False"], label="你的答案", elem_classes="quiz-answer-radio")
        tf_submit = gr.Button("提交判断题答案", elem_classes="learnflow-button-large learnflow-button-rounded")
        tf_feedback = gr.Markdown("", elem_classes="correct-feedback")
        tf_next = gr.Button("下一道判断题", visible=False, elem_classes="learnflow-button-large learnflow-button-rounded")

    fitb_section = gr.Column(visible=False, elem_classes="quiz-section")
    with fitb_section:
        fitb_question = gr.Markdown("### 填空题")
        fitb_answer = gr.Textbox(label="你的答案", placeholder="在此输入答案...")
        fitb_submit = gr.Button("提交填空题答案", elem_classes="learnflow-button-large learnflow-button-rounded")
        fitb_feedback = gr.Markdown("", elem_classes="correct-feedback")
        fitb_next = gr.Button("下一道填空题", visible=False, elem_classes="learnflow-button-large learnflow-button-rounded")

    return {
        "mcq_section": mcq_section,
        "mcq_question": mcq_question,
        "mcq_choices": mcq_choices,
        "mcq_submit": mcq_submit,
        "mcq_feedback": mcq_feedback,
        "mcq_next": mcq_next,
        "open_ended_section": open_ended_section,
        "open_question": open_question,
        "open_answer": open_answer,
        "open_submit": open_submit,
        "open_feedback": open_feedback,
        "open_next": open_next, 
        "tf_section": tf_section,
        "tf_question": tf_question,
        "tf_choices": tf_choices,
        "tf_submit": tf_submit,
        "tf_feedback": tf_feedback,
        "tf_next": tf_next,
        "fitb_section": fitb_section,
        "fitb_question": fitb_question,
        "fitb_answer": fitb_answer,
        "fitb_submit": fitb_submit,
        "fitb_feedback": fitb_feedback,
        "fitb_next": fitb_next
    }


def create_progress_components():
    """Creates standardized progress display components."""
    return {
        "overall_stats": gr.Markdown("暂无会话数据。"),
        "progress_bar": gr.HTML(""),
        "unit_details": gr.Dataframe(
            headers=["单元", "状态", "测验分数", "完成度"], 
            datatype=["str", "str", "str", "str"], 
            interactive=False
        )
    }


def create_session_management_components():
    """Creates standardized session management components."""
    return {
        "session_name_input": gr.Textbox(placeholder="输入会话名称以保存或加载...", label="会话名称"),
        "save_session_btn": gr.Button("💾 保存当前会话", elem_classes="learnflow-button-large learnflow-button-rounded"),
        "load_session_btn": gr.Button("📂 加载会话", elem_classes="learnflow-button-large learnflow-button-rounded"),
        "saved_sessions_dropdown": gr.Dropdown(choices=["Choose from saved sessions..."], value="Choose from saved sessions...", label="历史会话", interactive=True),
        "session_status": gr.Markdown("")
    }


def create_export_components():
    """Creates standardized export components."""
    return {
        "export_markdown_btn": gr.Button("📝 导出 Markdown", elem_classes="learnflow-button-large learnflow-button-rounded"),
        "export_html_btn": gr.Button("🌐 导出 HTML", elem_classes="learnflow-button-large learnflow-button-rounded"),
        "export_pdf_btn": gr.Button("📄 导出 PDF", elem_classes="learnflow-button-large learnflow-button-rounded"),
        "export_file": gr.File(label="下载导出文件", visible=False),
        "export_status": gr.Markdown("")
    }

def create_difficulty_radio() -> gr.Radio:
    """Creates a radio group for difficulty level."""
    return gr.Radio(
        choices=["Easy", "Medium", "Hard"],
        value="Medium",
        label="难度级别",
        interactive=True,
        container=False,
        elem_classes="difficulty-radio-group"
    )

def create_question_number_slider(min_val: int = 3, max_val: int = 30, default_val: int = 8) -> gr.Slider:
    """Creates a slider for number of questions."""
    return gr.Slider(
        minimum=min_val,
        maximum=max_val,
        value=default_val,
        step=1,
        label="题目数量",
        interactive=True
    )

def create_question_types_checkboxgroup() -> gr.CheckboxGroup:
    """Creates a checkbox group for question types."""
    return gr.CheckboxGroup(
        choices=["Multiple Choice", "Open-Ended", "True/False", "Fill in the Blank"],
        value=["Multiple Choice", "Open-Ended", "True/False"],
        label="题目类型",
        interactive=True,
        elem_classes="question-types-checkbox-group"
    )

def create_ai_provider_dropdown(providers: List[str], default_value: str = "mistral") -> gr.Dropdown: 
    """Creates a dropdown for AI provider."""
    return gr.Dropdown(
        choices=providers,
        value=default_value,
        label="AI 提供商",
        interactive=True
    )

def create_stats_card(title: str, value: str, description: str, icon: str, color: str) -> gr.Markdown:
    """Creates a standardized statistics card."""
    return gr.Markdown(f"""
    <div class="stats-card" style="--stats-accent: {color};">
        <h3>{icon} {title}</h3>
        <p class="stats-value">{value}</p>
        <p class="stats-description">{description}</p>
    </div>
    """)

def create_overall_progress_html(progress_percentage: int = 53) -> gr.HTML:
    """Creates the HTML for the overall learning progress bar."""
    return gr.HTML(f"""
        <div class="overall-progress-card">
            <h3>总课程进度：{progress_percentage}%</h3>
            <div class="progress-track">
                <div class="progress-fill" style="width: {progress_percentage}%;"></div>
            </div>
            <p>继续加油！你正在取得很好的进步。</p>
        </div>
    """)
