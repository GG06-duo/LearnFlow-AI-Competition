import logging
import os
import subprocess
import sys
import tempfile # Import tempfile
from typing import List, Tuple, Optional
import gradio as gr
from components.state import SessionState, LearningUnit, ExplanationResponse, get_unit_status_emoji
from agents.models import CodeExample

# Configure logging for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def create_new_session_copy(session: SessionState) -> SessionState:
    """Creates a deep copy of the session state to ensure immutability for Gradio."""
    return session.model_copy()

def run_code_snippet(code: str) -> str:
    """Executes a Python code snippet and returns its output."""
    try:
        # Create a temporary file to write the code
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py', encoding='utf-8') as tmp_file:
            tmp_file.write(code)
            tmp_file_path = tmp_file.name

        # Execute the temporary file using a subprocess
        process = subprocess.run(
            [sys.executable, tmp_file_path],
            capture_output=True,
            text=True,
            check=False,
            encoding='utf-8'
        )

        # Clean up the temporary file
        os.remove(tmp_file_path)

        if process.returncode == 0:
            return process.stdout.strip()
        else:
            return f"Error:\n{process.stderr.strip()}"
    except Exception as e:
        return f"Execution failed: {e}"

def update_progress_display(session: SessionState) -> Tuple[gr.Markdown, gr.Markdown, gr.Markdown, gr.HTML, gr.Dataframe]:
    """Updates the progress display components based on the current session state."""
    summary = session.get_progress_summary()
    total_units = summary["total_units"]
    completed_units = summary["completed_units"]
    in_progress_units = summary["in_progress_units"]
    
    average_score = session.get_average_quiz_score()

    # Overall Stats Cards
    completed_stats_card = gr.Markdown(f"""
    <div class="stats-card" style="--stats-accent: #10b981;">
        <h3>✅ 已完成</h3>
        <p class="stats-value">{completed_units}</p>
        <p class="stats-description">已掌握单元</p>
    </div>
    """)

    in_progress_stats_card = gr.Markdown(f"""
    <div class="stats-card" style="--stats-accent: #3b82f6;">
        <h3>📈 进行中</h3>
        <p class="stats-value">{in_progress_units}</p>
        <p class="stats-description">学习中单元</p>
    </div>
    """)

    average_score_stats_card = gr.Markdown(f"""
    <div class="stats-card" style="--stats-accent: #f59e0b;">
        <h3>🎯 平均分</h3>
        <p class="stats-value">{average_score:.0f}%</p>
        <p class="stats-description">测验成绩</p>
    </div>
    """)

    # Detailed Progress Table
    data = []
    for i, unit in enumerate(session.units):
        status_emoji = get_unit_status_emoji(unit)
        quiz_score_display = "N/A"
        unit_total_questions = 0
        unit_answered_questions = 0

        if unit.quiz_data:
            # Calculate score for display in table
            unit_correct_questions = 0
            
            if unit.quiz_data.mcqs:
                unit_correct_questions += sum(1 for q in unit.quiz_data.mcqs if q.is_correct)
                unit_total_questions += len(unit.quiz_data.mcqs)
                unit_answered_questions += sum(1 for q in unit.quiz_data.mcqs if q.user_answer is not None)
            
            if unit.quiz_data.true_false:
                unit_correct_questions += sum(1 for q in unit.quiz_data.true_false if q.is_correct)
                unit_total_questions += len(unit.quiz_data.true_false)
                unit_answered_questions += sum(1 for q in unit.quiz_data.true_false if q.user_answer is not None)
            
            if unit.quiz_data.fill_in_the_blank:
                unit_correct_questions += sum(1 for q in unit.quiz_data.fill_in_the_blank if q.is_correct)
                unit_total_questions += len(unit.quiz_data.fill_in_the_blank)
                unit_answered_questions += sum(1 for q in unit.quiz_data.fill_in_the_blank if q.user_answer is not None)
            
            if unit.quiz_data.open_ended:
                unit_correct_questions += sum(1 for q in unit.quiz_data.open_ended if q.score is not None and q.score >= 5)
                unit_total_questions += len(unit.quiz_data.open_ended)
                unit_answered_questions += sum(1 for q in unit.quiz_data.open_ended if q.user_answer is not None)

            if unit_total_questions > 0:
                quiz_score_display = f"{int((unit_correct_questions / unit_total_questions) * 100)}%"
        
        progress_percentage = 0
        if unit.status == "completed":
            progress_percentage = 100
        elif unit.status == "in_progress":
            if unit_total_questions > 0:
                progress_percentage = int((unit_answered_questions / unit_total_questions) * 100)
            else:
                # If in progress but no questions generated yet
                progress_percentage = 0 
        
        data.append([
            f"{i+1}. {unit.title}",
            f"{status_emoji} {unit.status.replace('_', ' ').title()}",
            quiz_score_display,
            progress_percentage
        ])

    # Overall Learning Progress Bar
    overall_progress_percentage = 0
    if total_units > 0:
        overall_progress_percentage = int((completed_units / total_units) * 100)

    overall_progress_html = gr.HTML(f"""
        <div class="overall-progress-card">
            <h3>总课程进度：{overall_progress_percentage}%</h3>
            <div class="progress-track">
                <div class="progress-fill" style="width: {overall_progress_percentage}%;"></div>
            </div>
            <p>继续加油！你正在取得很好的进步。</p>
        </div>
    """)

    return (
        completed_stats_card,
        in_progress_stats_card,
        average_score_stats_card,
        overall_progress_html,
        gr.Dataframe(value=data, 
                     headers=["学习单元", "状态", "测验分数", "进度"], 
                     datatype=["str", "str", "str", "number"], 
                     interactive=False)
    )

def format_unit_info_markdown(unit: LearningUnit, content_preview_length: int = 300) -> str:
    """Formats the current unit's information into a Markdown string."""
    content_preview = unit.content_raw[:content_preview_length] + "..." if len(unit.content_raw) > content_preview_length else unit.content_raw
    return f"""
    ### 当前单元：{unit.title}
    **状态：** {get_unit_status_emoji(unit)} {unit.status.replace('_', ' ').title()} \n
    **摘要：** {unit.summary}
    """

def format_units_display_markdown(units: List[LearningUnit]) -> str:
    """Formats a list of learning units into a Markdown string for display."""
    if not units:
        return "尚未生成学习单元。"
    
    markdown_output = "### 已生成的学习单元：\n\n"
    for i, unit in enumerate(units):
        status_emoji = get_unit_status_emoji(unit)
        markdown_output += f"- {status_emoji} **{i+1}. {unit.title}**\n"
        markdown_output += f"  *摘要*：{unit.summary}\n"
        if unit.explanation:
            markdown_output += f"  *已生成讲解*：是\n"
        if unit.quiz_data:
            markdown_output += f"  *已生成测验*：是\n"
            # Calculate quiz score for display in units list
            unit_correct_questions = 0
            unit_total_questions = 0
            if unit.quiz_data.mcqs:
                unit_correct_questions += sum(1 for q in unit.quiz_data.mcqs if q.is_correct)
                unit_total_questions += len(unit.quiz_data.mcqs)
            if unit.quiz_data.true_false:
                unit_correct_questions += sum(1 for q in unit.quiz_data.true_false if q.is_correct)
                unit_total_questions += len(unit.quiz_data.true_false)
            if unit.quiz_data.fill_in_the_blank:
                unit_correct_questions += sum(1 for q in unit.quiz_data.fill_in_the_blank if q.is_correct)
                unit_total_questions += len(unit.quiz_data.fill_in_the_blank)
            if unit.quiz_data.open_ended:
                unit_correct_questions += sum(1 for q in unit.quiz_data.open_ended if q.score is not None and q.score >= 5)
                unit_total_questions += len(unit.quiz_data.open_ended)

            if unit_total_questions > 0:
                markdown_output += f"  *测验分数*：{int((unit_correct_questions / unit_total_questions) * 100)}%\n"
        markdown_output += "\n"
    return markdown_output

def format_unit_dropdown_choices(units: List[LearningUnit]) -> Tuple[List[str], Optional[str]]:
    """Formats a list of learning units for dropdown choices and returns a default value."""
    if not units:
        return ["No units available"], None
    choices = [f"{i+1}. {unit.title}" for i, unit in enumerate(units)]
    default_value = choices[0] if choices else None
    return choices, default_value

def format_mcq_feedback(is_correct: bool, correct_answer: str, explanation: str) -> str:
    """Formats the feedback for an MCQ question."""
    feedback_class = "correct-feedback" if is_correct else "incorrect-feedback"
    status = "回答正确！" if is_correct else "回答错误。"
    return f"""
    <div class="{feedback_class}">
        <p><strong>{status}</strong></p>
        <p>正确答案：<strong>{correct_answer}</strong></p>
        <p>讲解：{explanation}</p>
    </div>
    """

def process_explanation_for_rendering(explanation_data: ExplanationResponse) -> Tuple[str, List[CodeExample]]:
    """
    Processes the explanation data to prepare it for Gradio Markdown rendering,
    inserting placeholders for code blocks.
    """
    processed_markdown = explanation_data.markdown
    code_examples_for_ui = []

    # Replace [FIGURE: {...}] with actual image tags if paths are available
    # This assumes visual_aid are already handled and their paths are valid
    for i, visual_aid in enumerate(explanation_data.visual_aids):
        if visual_aid.type == "image" and visual_aid.path:
            # Assuming visual_aid.path is a URL or a Gradio-accessible path
            processed_markdown = processed_markdown.replace(
                f"[FIGURE: {i}]",
                f"![{visual_aid.caption or 'Figure'}]({visual_aid.path})"
            )

    # Replace [CODE: {...}] with placeholders for Gradio's dynamic rendering
    for i, code_example in enumerate(explanation_data.code_examples):
        # Use a unique placeholder that can be split later
        processed_markdown = processed_markdown.replace(
            f"[CODE: {i}]",
            f"[CODE_INSERTION_POINT_{i}]"
        )
        code_examples_for_ui.append(code_example)

    return processed_markdown, code_examples_for_ui
