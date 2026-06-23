import logging
from typing import Optional, List, Tuple

from components.state import SessionState, list_saved_sessions
from utils.common.utils import create_new_session_copy, format_units_display_markdown, \
    format_unit_dropdown_choices, update_progress_display

def save_session_logic(session: SessionState, session_name: str):
    """Core logic for saving sessions - moved from app.py"""
    if not session_name.strip():
        return session, "请输入会话名称。", list_saved_sessions()
    
    session_copy = create_new_session_copy(session)
    message = session_copy.save_session(session_name.strip())
    return session_copy, message, list_saved_sessions()


def load_session_logic(session_name: str):
    """Core logic for loading sessions - moved from app.py"""
    # Default return values for error cases or initial state (11 outputs)
    default_session_state = SessionState()
    default_units_dropdown_choices = ["No units available"]
    default_units_display_text = "尚未生成学习单元。"
    default_progress_stats = "暂无会话数据。"
    default_progress_bar_html = ""
    default_progress_df = [] 

    if not session_name.strip():
        return default_session_state, "请选择要加载的会话。", \
               default_units_dropdown_choices, None, default_units_dropdown_choices, default_units_dropdown_choices, \
               default_units_display_text, default_progress_stats, default_progress_bar_html, default_progress_df
    try:
        loaded_session = SessionState.load_session(session_name.strip())
        
        units_display_text = format_units_display_markdown(loaded_session.units)
        dropdown_choices, default_value = format_unit_dropdown_choices(loaded_session.units)
        
        # Unpack all 5 values from update_progress_display
        completed_stats, in_progress_stats, average_score_stats, overall_progress_html, progress_df_value = update_progress_display(loaded_session)

        return loaded_session, f"会话“{session_name}”已成功加载！", \
               dropdown_choices, default_value, dropdown_choices, dropdown_choices, \
               units_display_text, completed_stats, in_progress_stats, average_score_stats, overall_progress_html, progress_df_value
    except FileNotFoundError as e:
        return default_session_state, str(e), \
               default_units_dropdown_choices, None, default_units_dropdown_choices, default_units_dropdown_choices, \
               default_units_display_text, default_progress_stats, default_progress_bar_html, default_progress_df
    except Exception as e:
        logging.error(f"Error loading session: {e}", exc_info=True)
        return default_session_state, f"加载会话时出错：{str(e)}", \
               default_units_dropdown_choices, None, default_units_dropdown_choices, default_units_dropdown_choices, \
               default_units_display_text, default_progress_stats, default_progress_bar_html, default_progress_df
