import logging
import tempfile
import re
import json
import asyncio
import threading
from typing import Optional, Any, List, Dict, Tuple

import gradio as gr

from components.state import SessionState, list_saved_sessions
from agents.models import QuizResponse, ExplanationResponse, CodeExample, MCQQuestion, LearningUnit, VisualAid, OpenEndedQuestion
from utils.common.utils import (
    create_new_session_copy,
    run_code_snippet,
    update_progress_display,
    format_unit_info_markdown,
    format_units_display_markdown,
    format_unit_dropdown_choices,
    format_mcq_feedback,
    process_explanation_for_rendering
)
from utils.content_generation.content_processing import (
    process_content_logic,
    generate_explanation_logic,
    generate_all_explanations_logic
)
from utils.quiz_submission.quiz_logic import (
    generate_quiz_logic,
    generate_all_quizzes_logic,
    submit_mcq_answer_logic,
    submit_open_answer_logic,
    submit_true_false_answer_logic,
    submit_fill_in_the_blank_answer_logic,
    prepare_and_navigate_to_quiz
)
from utils.session_management.session_management import (
    save_session_logic,
    load_session_logic
)
from utils.export.export_logic import (
    export_session_to_markdown,
    export_session_to_html,
    export_session_to_pdf,
    _delete_file_after_delay # Import the async deletion function
)

# Define TAB_IDS_IN_ORDER here as it's used by handle_tab_change
TAB_IDS_IN_ORDER = ["plan", "learn", "quiz", "progress"]

def _run_async_in_thread(coro):
    """Runs an async coroutine in a new thread with its own event loop."""
    def wrapper():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(coro)
        loop.close()
    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()

# --- Wrapper Functions for Gradio Events ---
def process_content_wrapper(session: SessionState,
                            provider: str,
                            model_name: str,
                            api_key: str,
                            pdf_file: Optional[Any],
                            text_content: str,
                            input_mode: str):
    """Wrapper to handle Gradio return format for processing content."""
    logging.info(f"process_content_wrapper called with input_mode: {input_mode}")
    session, status, display, choices, default, learn_choices, quiz_choices = process_content_logic(
        session, provider, model_name, api_key, pdf_file, text_content, input_mode
    )
    logging.info(f"process_content_logic returned status '{status}' with "
                 f"{len(choices) if choices else 0} units.")
    return (
        session,
        status,
        display,
        gr.update(choices=choices, value=default),
        gr.update(choices=learn_choices, value=default),
        gr.update(choices=quiz_choices, value=default)
    )


def navigate_to_learn(session: SessionState,
                      unit_selection_str: str):
    """Wrapper to navigate to the Learn tab."""
    session = create_new_session_copy(session)
    if not (session.units and unit_selection_str and unit_selection_str != "Select Generated Unit"):
        return "请先生成并选择一个学习单元。", gr.update(selected="plan"), session
    try:
        idx = int(unit_selection_str.split(".")[0]) - 1
        session.set_current_unit(idx)
        new_session = create_new_session_copy(session)
        logging.info(f"Navigating to Learn tab for unit: {session.units[idx].title}")
        return (
            f"正在进入学习页面：{session.units[idx].title}",
            gr.update(selected="learn"),
            new_session
        )
    except Exception as e:
        logging.error(f"navigate_to_learn error: {e}", exc_info=True)
        return f"选择单元时出错：{e}", gr.update(selected="plan"), session


def load_unit_wrapper(session: SessionState,
                      unit_selection_str: str):
    """Wrapper for loading a specific unit for learning."""
    session = create_new_session_copy(session)
    if not (session.units and unit_selection_str and unit_selection_str != "Select Generated Unit"):
        return session, "未选择可用单元。", gr.update(visible=False), None, [], "未选择单元。", None
    try:
        idx = int(unit_selection_str.split(".")[0]) - 1
        session.set_current_unit(idx)
        unit = session.units[idx]
        info_md = format_unit_info_markdown(unit, content_preview_length=300)
        dropdown_val = f"{idx+1}. {unit.title}"
        new_session = create_new_session_copy(session)
        if unit.explanation_data:
            return new_session, info_md, gr.update(visible=True), unit.explanation_data, unit.explanation_data.code_examples or [], info_md, dropdown_val
        return new_session, info_md, gr.update(visible=False), None, [], info_md, dropdown_val
    except Exception as e:
        logging.error(f"load_unit_wrapper error: {e}", exc_info=True)
        return create_new_session_copy(session), f"加载单元时出错：{e}", gr.update(visible=False), None, [], "未选择单元。", None


def generate_explanation_wrapper(session: SessionState,
                                 provider: str,
                                 model_name: str,
                                 api_key: str,
                                 explanation_style: str,
                                 unit_selection_str: str):
    """Wrapper for generating an explanation for a single unit."""
    session, status, visible, expl_data, code_examples, unit_info, dropdown_val = generate_explanation_logic(
        session, provider, model_name, api_key, explanation_style, unit_selection_str
    )
    return (
        session,
        status,
        gr.update(visible=visible),
        expl_data,
        code_examples,
        unit_info,
        gr.update(value=dropdown_val)
    )


def generate_all_explanations_wrapper(session: SessionState,
                                      provider: str,
                                      model_name: str,
                                      api_key: str,
                                      explanation_style: str):
    """Wrapper for generating explanations for all units."""
    session, status, visible, expl_data, code_examples, unit_info, dropdown_val = generate_all_explanations_logic(
        session, provider, model_name, api_key, explanation_style
    )
    return (
        session,
        status,
        gr.update(visible=visible),
        expl_data,
        code_examples,
        unit_info,
        gr.update(value=dropdown_val)
    )


def generate_quiz_wrapper(session: SessionState,
                          unit_selection_str: str,
                          provider: str,
                          model_name: str,
                          api_key: str,
                          difficulty: str,
                          num_questions: int,
                          question_types: List[str]):
    """Wrapper for generating a quiz for a unit."""
    session, quiz_data, q_idx, status, visible, mcq_q, mcq_choices, open_q, tf_q, fitb_q, feedback, mcq_vis, open_vis, tf_vis, fitb_vis, open_q_idx, open_next_vis = generate_quiz_logic(
        session, provider, model_name, api_key, difficulty, num_questions, question_types, unit_selection_str
    )
    return (
        session,
        quiz_data,
        q_idx,
        status,
        gr.update(visible=visible),
        mcq_q,
        gr.update(choices=mcq_choices, value=None),
        open_q,
        tf_q,
        fitb_q,
        feedback,
        gr.update(visible=mcq_vis),
        gr.update(visible=open_vis),
        gr.update(visible=tf_vis),
        gr.update(visible=fitb_vis),
        open_q_idx,
        gr.update(visible=open_next_vis)
    )


def generate_all_quizzes_wrapper(session: SessionState,
                                 provider: str,
                                 model_name: str,
                                 api_key: str):
    """Wrapper for generating quizzes for all units."""
    session, quiz_data, q_idx, status, visible, mcq_q, mcq_choices, open_q, tf_q, fitb_q, feedback, mcq_vis, open_vis, tf_vis, fitb_vis, open_q_idx, open_next_vis = generate_all_quizzes_logic(
        session, provider, model_name, api_key
    )
    return (
        session,
        quiz_data,
        q_idx,
        status,
        gr.update(visible=visible),
        mcq_q,
        gr.update(choices=mcq_choices, value=None),
        open_q,
        tf_q,
        fitb_q,
        feedback,
        gr.update(visible=mcq_vis),
        gr.update(visible=open_vis),
        gr.update(visible=tf_vis),
        gr.update(visible=fitb_vis),
        open_q_idx,
        gr.update(visible=open_next_vis)
    )


def submit_mcq_wrapper(session: SessionState,
                        current_quiz_data: QuizResponse,
                        question_idx_val: int,
                        user_choice_str: str,
                        llm_provider: str,
                        model_name: str,
                        api_key: str):
    """Wrapper for handling MCQ answer submissions."""
    feedback, show_next = submit_mcq_answer_logic(
        session, current_quiz_data, question_idx_val, user_choice_str
    )
    return feedback, gr.update(visible=show_next)


def next_mcq_question(current_quiz_data: Optional[QuizResponse],
                      question_idx_val: int):
    """Get the next MCQ question or completion message."""
    if not (current_quiz_data and current_quiz_data.mcqs):
        return question_idx_val, "没有更多多选题。", gr.update(choices=[], value=None), "", gr.update(visible=False)
    next_idx = question_idx_val + 1
    if next_idx < len(current_quiz_data.mcqs):
        item = current_quiz_data.mcqs[next_idx]
        question_text = f"**第 {next_idx + 1} 题：** {item.question}"
        choices = [f"{k}. {v}" for k, v in item.options.items()]
        return next_idx, question_text, gr.update(choices=choices, value=None), "", gr.update(visible=False)
    return question_idx_val, "你已完成所有多选题。", gr.update(choices=[], value=None), "", gr.update(visible=False)


def submit_open_wrapper(session: SessionState,
                        current_quiz_data: QuizResponse,
                        question_idx_val: int,
                        user_answer_text: str,
                        llm_provider: str,
                        model_name: str,
                        api_key: str):
    """Wrapper for handling open-ended answer submissions."""
    feedback, show_next = submit_open_answer_logic(session, current_quiz_data, question_idx_val, user_answer_text, llm_provider, model_name, api_key)
    return feedback, gr.update(visible=show_next)


def next_open_question(current_quiz_data: Optional[QuizResponse],
                       question_idx_val: int):
    """Get the next Open-Ended question or completion message."""
    if not (current_quiz_data and current_quiz_data.open_ended):
        return question_idx_val, "没有更多开放题。", "", "", gr.update(visible=False)
    next_idx = question_idx_val + 1
    if next_idx < len(current_quiz_data.open_ended):
        item = current_quiz_data.open_ended[next_idx]
        question_text = f"**开放题 {next_idx + 1}：** {item.question}"
        return next_idx, question_text, "", "", gr.update(visible=False)
    return question_idx_val, "你已完成所有开放题。", "", "", gr.update(visible=False)


def submit_true_false_wrapper(session: SessionState,
                              current_quiz_data: QuizResponse,
                              question_idx_val: int,
                              user_choice_str: str,
                              llm_provider: str,
                              model_name: str,
                              api_key: str):
    """Wrapper for handling True/False answer submissions."""
    feedback, show_next = submit_true_false_answer_logic(
        session, current_quiz_data, question_idx_val, user_choice_str
    )
    return feedback, gr.update(visible=show_next)


def next_true_false_question(current_quiz_data: Optional[QuizResponse],
                             question_idx_val: int):
    """Get the next True/False question or completion message."""
    if not (current_quiz_data and current_quiz_data.true_false):
        return question_idx_val, "没有更多判断题。", gr.update(value=None), "", gr.update(visible=False)
    next_idx = question_idx_val + 1
    if next_idx < len(current_quiz_data.true_false):
        item = current_quiz_data.true_false[next_idx]
        question_text = f"**第 {next_idx + 1} 题（判断题）：** {item.question}"
        return next_idx, question_text, gr.update(value=None), "", gr.update(visible=False)
    return question_idx_val, "你已完成所有判断题。", gr.update(value=None), "", gr.update(visible=False)


def submit_fill_in_the_blank_wrapper(session: SessionState,
                                     current_quiz_data: QuizResponse,
                                     question_idx_val: int,
                                     user_answer_text: str,
                                     llm_provider: str,
                                     model_name: str,
                                     api_key: str):
    """Wrapper for handling Fill in the Blank submissions."""
    feedback, show_next = submit_fill_in_the_blank_answer_logic(
        session, current_quiz_data, question_idx_val, user_answer_text
    )
    return feedback, gr.update(visible=show_next)


def next_fill_in_the_blank_question(current_quiz_data: Optional[QuizResponse],
                                    question_idx_val: int):
    """Get the next Fill in the Blank question or completion message."""
    if not (current_quiz_data and current_quiz_data.fill_in_the_blank):
        return question_idx_val, "没有更多填空题。", "", "", gr.update(visible=False)
    next_idx = question_idx_val + 1
    if next_idx < len(current_quiz_data.fill_in_the_blank):
        item = current_quiz_data.fill_in_the_blank[next_idx]
        question_text = f"**第 {next_idx + 1} 题（填空题）：** {item.question}"
        return next_idx, question_text, "", "", gr.update(visible=False)
    return question_idx_val, "你已完成所有填空题。", "", "", gr.update(visible=False)


def handle_tab_change(session: SessionState,
                      current_quiz_data: Optional[QuizResponse],
                      evt: gr.SelectData):
    """Wrapper for handling tab selection change."""
    selected_index = evt.index
    logging.info(f"Tab selected - Index: {selected_index}")
    if session is None:
        session = SessionState()
    session = create_new_session_copy(session)
    completed_stats, in_progress_stats, average_score_stats, overall_progress_html, details = update_progress_display(session)

    ui_learn_visible = gr.update(visible=False)
    ui_quiz_visible = gr.update(visible=False)
    ui_learn_data = None
    ui_learn_code = []
    ui_learn_info = "未选择或加载单元。"
    ui_dropdown_val = None

    if session.current_unit_index is not None and session.get_current_unit():
        ui_dropdown_val = f"{session.current_unit_index + 1}. {session.get_current_unit().title}"

    tab_id = TAB_IDS_IN_ORDER[selected_index] if 0 <= selected_index < len(TAB_IDS_IN_ORDER) else "plan"

    if tab_id == "learn":
        unit = session.get_current_unit()
        if unit:
            ui_learn_info = format_unit_info_markdown(unit)
            if unit.explanation_data:
                ui_learn_visible = gr.update(visible=True)
                ui_learn_data = unit.explanation_data
                ui_learn_code = unit.explanation_data.code_examples or []
        return session, completed_stats, in_progress_stats, average_score_stats, overall_progress_html, details, ui_learn_visible, ui_learn_data, ui_learn_code, ui_quiz_visible, ui_learn_info, gr.update(value=ui_dropdown_val), gr.update(choices=list_saved_sessions()), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)

    if tab_id == "quiz":
        mcq_vis = bool(current_quiz_data and current_quiz_data.mcqs)
        open_vis = bool(current_quiz_data and current_quiz_data.open_ended)
        tf_vis = bool(current_quiz_data and current_quiz_data.true_false)
        fitb_vis = bool(current_quiz_data and current_quiz_data.fill_in_the_blank)
        ui_quiz_visible = gr.update(visible=mcq_vis or open_vis or tf_vis or fitb_vis)
        return session, completed_stats, in_progress_stats, average_score_stats, overall_progress_html, details, ui_learn_visible, ui_learn_data, ui_learn_code, ui_quiz_visible, ui_learn_info, gr.update(value=ui_dropdown_val), gr.update(choices=list_saved_sessions()), gr.update(visible=mcq_vis), gr.update(visible=open_vis), gr.update(visible=tf_vis), gr.update(visible=fitb_vis)

    if tab_id == "progress":
        saved_choices = list_saved_sessions()
        return session, completed_stats, in_progress_stats, average_score_stats, overall_progress_html, details, ui_learn_visible, ui_learn_data, ui_learn_code, ui_quiz_visible, ui_learn_info, gr.update(value=ui_dropdown_val), gr.update(choices=saved_choices), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)

    return session, completed_stats, in_progress_stats, average_score_stats, overall_progress_html, details, ui_learn_visible, ui_learn_data, ui_learn_code, ui_quiz_visible, ui_learn_info, gr.update(value=ui_dropdown_val), gr.update(choices=list_saved_sessions()), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)


def save_session_wrapper(session: SessionState,
                         session_name: str):
    """Wrapper for saving the current session."""
    session, message, choices = save_session_logic(session, session_name)
    return session, message, gr.update(choices=choices, value=session_name.strip() if session_name.strip() else None)


def load_session_wrapper(session_name: str):
    """Wrapper for loading a saved session."""
    session_state, status_message, unit_dd_choices, unit_dd_default_value, learn_dd_choices, quiz_dd_choices, units_display_md, completed_stats_md, in_progress_stats_md, avg_score_stats_md, overall_progress_html_val, progress_df_val = load_session_logic(session_name)
    return (
        session_state,
        status_message,
        gr.update(choices=unit_dd_choices, value=unit_dd_default_value),
        gr.update(choices=learn_dd_choices, value=unit_dd_default_value),
        gr.update(choices=quiz_dd_choices, value=unit_dd_default_value),
        units_display_md,
        completed_stats_md,
        in_progress_stats_md,
        avg_score_stats_md,
        overall_progress_html_val,
        progress_df_val
    )


def export_markdown_wrapper(session: SessionState):
    """Wrapper for exporting session to Markdown."""
    if not session.units:
        return None, "当前会话没有可导出的单元。", gr.update(visible=False)
    try:
        content = export_session_to_markdown(session)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".md", prefix="LearnFlow_Export_")
        with open(tmp.name, "w", encoding="utf-8") as f:
            f.write(content)
        tmp.close()
        _run_async_in_thread(_delete_file_after_delay(tmp.name)) 
        return tmp.name, "已成功导出 Markdown！", gr.update(visible=True, value=tmp.name)
    except Exception as e:
        logging.error(f"export_markdown_wrapper error: {e}", exc_info=True)
        return None, f"导出 Markdown 时出错：{e}", gr.update(visible=False)


def export_html_wrapper(session: SessionState):
    """Wrapper for exporting session to HTML."""
    if not session.units:
        return None, "当前会话没有可导出的单元。", gr.update(visible=False)
    try:
        content = export_session_to_html(session)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html", prefix="LearnFlow_Export_")
        with open(tmp.name, "w", encoding="utf-8") as f:
            f.write(content)
        tmp.close()
        _run_async_in_thread(_delete_file_after_delay(tmp.name)) 
        return tmp.name, "已成功导出 HTML！", gr.update(visible=True, value=tmp.name)
    except Exception as e:
        logging.error(f"export_html_wrapper error: {e}", exc_info=True)
        return None, f"导出 HTML 时出错：{e}", gr.update(visible=False)


def export_pdf_wrapper(session: SessionState):
    """Wrapper for exporting session to PDF."""
    if not session.units:
        return None, "当前会话没有可导出的单元。", gr.update(visible=False)
    try:
        path = export_session_to_pdf(session)
        if path.startswith("Error:"):
            return None, path, gr.update(visible=False)
        _run_async_in_thread(_delete_file_after_delay(path)) 
        return path, "已成功导出 PDF！", gr.update(visible=True, value=path)
    except Exception as e:
        logging.error(f"export_pdf_wrapper error: {e}", exc_info=True)
        return None, f"导出 PDF 时出错：{e}", gr.update(visible=False)
