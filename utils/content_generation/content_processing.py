import logging
from typing import List, Optional, Any, Tuple, Literal

from components.state import SessionState
from agents.models import LearningUnit, ExplanationResponse, QuizResponse
from agents.learnflow_mcp_tool.learnflow_tool import LearnFlowMCPTool
from utils.common.utils import create_new_session_copy, format_units_display_markdown, \
    format_unit_dropdown_choices, format_unit_info_markdown, process_explanation_for_rendering

def process_content_logic(session: SessionState, provider: str, model_name: str, api_key: str, pdf_file: Optional[Any], text_content: str, input_mode: Literal["PDF", "File", "Text"]):
    """Core logic for processing content - moved from app.py"""
    session = create_new_session_copy(session)
    session.provider = provider
    
    content_to_process = ""
    if input_mode.upper() in ("PDF", "FILE") and pdf_file is not None:
        content_to_process = pdf_file if isinstance(pdf_file, str) else pdf_file.name
    elif input_mode == "Text" and text_content.strip():
        content_to_process = text_content.strip()
    else:
        no_units_msg = "No units available"
        return session, "请提供 PDF 文件或文本内容。", "尚未生成学习单元。", \
               [no_units_msg], None, [no_units_msg], [no_units_msg]
    try:
        learnflow_tool = LearnFlowMCPTool()
        units_data: List[LearningUnit] = learnflow_tool.plan_learning_units(
            content=content_to_process, 
            input_type=input_mode, 
            llm_provider=provider,
            model_name=model_name,
            api_key=api_key
        )
        
        if not units_data:
            no_units_msg = "No units available"
            return session, "无法处理内容，请检查你的输入。", "尚未生成学习单元。", \
                   [no_units_msg], None, [no_units_msg], [no_units_msg]
        
        session.clear_units() # Clear existing units before adding new ones
        session.add_units(units_data)
        
        display_text = format_units_display_markdown(session.units)
        dropdown_choices, default_value = format_unit_dropdown_choices(session.units)
        
        new_session = create_new_session_copy(session)
        return new_session, f"已成功生成 {len(units_data)} 个学习单元！", display_text, \
               dropdown_choices, default_value, dropdown_choices, dropdown_choices
    except Exception as e:
        logging.error(f"Error processing content: {e}", exc_info=True)
        original_session_on_error = create_new_session_copy(session)
        no_units_msg = "No units available"
        return original_session_on_error, f"处理内容时出错：{str(e)}", "尚未生成学习单元。", \
               [no_units_msg], None, [no_units_msg], [no_units_msg]


def load_unit_for_learn_logic(session: SessionState, unit_selection_str: str):
    """Core logic for loading a unit for learning - moved from app.py"""
    session = create_new_session_copy(session)
    if not (session.units and unit_selection_str and unit_selection_str != "No units available"):
        return session, "未选择可用单元。", False, None, [], "未选择单元。", None
    try:
        unit_idx = int(unit_selection_str.split(".")[0]) - 1
        session.set_current_unit(unit_idx)
        unit = session.units[unit_idx]
        
        unit_info_md = format_unit_info_markdown(unit, content_preview_length=300)
        learn_unit_dropdown_val = (
            f"{session.current_unit_index + 1}. {unit.title}" 
            if session.current_unit_index is not None else unit.title
        )

        new_session_load = create_new_session_copy(session)
        logging.info(f"Loaded unit '{unit.title}' for learn tab.")

        if unit.explanation_data:
            logging.info(f"Found existing explanation data for {unit.title}.")
            # Ensure explanation_data is passed as ExplanationResponse type
            return new_session_load, unit_info_md, True, unit.explanation_data, \
                   (unit.explanation_data.code_examples or []), unit_info_md, learn_unit_dropdown_val
        else:
            logging.info(f"No existing explanation data for {unit.title}")
            return new_session_load, unit_info_md, False, None, [], \
                   unit_info_md, learn_unit_dropdown_val
    except Exception as e:
        logging.error(f"Error in load_unit_for_learn: {e}", exc_info=True)
        original_session_on_error = create_new_session_copy(session)
        return original_session_on_error, f"加载单元时出错：{str(e)}", False, None, [], "未选择单元。", None


def generate_explanation_logic(session: SessionState, provider: str, model_name: str, api_key: str, explanation_style: Literal["Concise", "Detailed"], unit_selection_string: str):
    """Core logic for generating explanations - moved from app.py"""
    session = create_new_session_copy(session)
    if not (session.units and unit_selection_string and unit_selection_string != "No units available"):
        return session, "没有可用单元，或尚未选择单元。", False, None, [], "未选择单元。", None

    try:
        target_unit_idx = int(unit_selection_string.split(".")[0]) - 1
        if not (0 <= target_unit_idx < len(session.units)):
            raise ValueError("Invalid unit index from selection string.")
        target_unit = session.units[target_unit_idx]
        
        unit_info_md = format_unit_info_markdown(target_unit, content_preview_length=150)
        dropdown_val = f"{target_unit_idx + 1}. {target_unit.title}"

        if target_unit.explanation_data:
            logging.info(f"Re-using existing explanation for {target_unit.title}")
            session.set_current_unit(target_unit_idx)
            new_session_reuse = create_new_session_copy(session)
            return new_session_reuse, f"已重新加载讲解：{target_unit.title}", True, \
                   target_unit.explanation_data, (target_unit.explanation_data.code_examples or []), \
                   unit_info_md, dropdown_val

        logging.info(f"Generating new explanation for {target_unit.title}")
        learnflow_tool = LearnFlowMCPTool()
        raw_explanation_response: ExplanationResponse = learnflow_tool.generate_explanation(
            unit_title=target_unit.title, 
            unit_content=target_unit.content_raw, 
            explanation_style=explanation_style,
            llm_provider=provider,
            model_name=model_name,
            api_key=api_key
        )
        
        processed_markdown, code_examples_for_ui = process_explanation_for_rendering(raw_explanation_response)
        final_explanation_data = ExplanationResponse(
            markdown=processed_markdown,
            visual_aids=raw_explanation_response.visual_aids,
            code_examples=code_examples_for_ui
        )
        
        session.update_unit_explanation_data(target_unit_idx, final_explanation_data)
        session.set_current_unit(target_unit_idx)
        new_session_gen = create_new_session_copy(session)
        
        logging.info(f"Generated new explanation for {target_unit.title}")
        return new_session_gen, f"已生成讲解：{target_unit.title}（{explanation_style}）", True, \
               final_explanation_data, (final_explanation_data.code_examples or []), \
               unit_info_md, dropdown_val
    except Exception as e:
        logging.error(f"Error in generate_explanation: {e}", exc_info=True)
        original_session_on_error = create_new_session_copy(session)
        return original_session_on_error, f"生成讲解时出错：{str(e)}", False, \
               None, [], "发生错误。", unit_selection_string

def generate_all_explanations_logic(session: SessionState, provider: str, model_name: str, api_key: str, explanation_style: Literal["Concise", "Detailed"]):
    """
    Generates explanations for all learning units in the session.
    Does not change the currently displayed unit in the UI.
    """
    session = create_new_session_copy(session)
    if not session.units:
        return session, "没有可生成讲解的学习单元。", False, None, [], "未选择单元。", None

    status_messages = []
    current_unit_idx_before_loop = session.current_unit_index 

    learnflow_tool = LearnFlowMCPTool()

    for i, unit in enumerate(session.units):
        if not unit.explanation_data: # Only generate if not already present
            try:
                logging.info(f"Generating explanation for unit {i+1}: {unit.title}")
                raw_explanation_response: ExplanationResponse = learnflow_tool.generate_explanation(
                    unit_title=unit.title, 
                    unit_content=unit.content_raw, 
                    explanation_style=explanation_style,
                    llm_provider=provider,
                    model_name=model_name,
                    api_key=api_key
                )
                processed_markdown, code_examples_for_ui = process_explanation_for_rendering(raw_explanation_response)
                final_explanation_data = ExplanationResponse(
                    markdown=processed_markdown,
                    visual_aids=raw_explanation_response.visual_aids,
                    code_examples=code_examples_for_ui
                )
                session.update_unit_explanation_data(i, final_explanation_data)
                status_messages.append(f"✅ 已生成讲解：{unit.title}")
            except Exception as e:
                logging.error(f"Error generating explanation for unit {i+1} ({unit.title}): {e}", exc_info=True)
                status_messages.append(f"❌ 生成讲解失败：{unit.title}（{str(e)}）")
        else:
            status_messages.append(f"ℹ️ 已存在讲解：{unit.title}")

    # Restore the current unit index to avoid changing the UI's current view
    if current_unit_idx_before_loop is not None and 0 <= current_unit_idx_before_loop < len(session.units):
        session.set_current_unit(current_unit_idx_before_loop)
        current_unit = session.units[current_unit_idx_before_loop]
        unit_info_md = format_unit_info_markdown(current_unit, content_preview_length=150)
        dropdown_val = f"{current_unit_idx_before_loop + 1}. {current_unit.title}"
        explanation_visible = True if current_unit.explanation_data else False
        explanation_data = current_unit.explanation_data
        code_examples = current_unit.explanation_data.code_examples if current_unit.explanation_data else []
    else:
        unit_info_md = "未选择单元。"
        dropdown_val = None
        explanation_visible = False
        explanation_data = None
        code_examples = []

    final_status_message = "所有讲解处理完成：\n" + "\n".join(status_messages)
    new_session_all_gen = create_new_session_copy(session)

    return new_session_all_gen, final_status_message, explanation_visible, explanation_data, \
           code_examples, unit_info_md, dropdown_val
