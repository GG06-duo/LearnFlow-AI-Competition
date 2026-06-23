import logging
from typing import Optional, Any, Dict, List, Tuple
import logging
import gradio as gr # Import gradio for gr.update

from components.state import SessionState
from agents.models import QuizResponse, MCQQuestion, OpenEndedQuestion, TrueFalseQuestion, FillInTheBlankQuestion
from agents.learnflow_mcp_tool.learnflow_tool import LearnFlowMCPTool
from utils.common.utils import create_new_session_copy, format_mcq_feedback # Keep format_mcq_feedback for now, might be refactored later

def generate_quiz_logic(session: SessionState, provider: str, model_name: str, api_key: str,
                        difficulty: str, num_questions: int, question_types: List[str], unit_selection_str: str):
    """Core logic for generating quiz - moved from app.py"""
    session = create_new_session_copy(session)
    
    default_return = (
        session, None, 0, "生成测验时出错。",
        False, "### 多选题", [], "### 开放题", 
        "### 判断题", "### 填空题", ""
    )

    if not (session.units and unit_selection_str and unit_selection_str != "No units available"):
        return (session, None, 0, "请先选择一个单元。", 
                False, "### 多选题", [], "### 开放题", 
                "### 判断题", "### 填空题", "")

    try:
        unit_idx = int(unit_selection_str.split(".")[0]) - 1
        if not (0 <= unit_idx < len(session.units)):
            logging.error(f"generate_quiz_logic: Invalid unit index {unit_idx}")
            return default_return
        
        unit_to_quiz = session.units[unit_idx]
        logging.info(f"generate_quiz_logic: Generating NEW quiz for '{unit_to_quiz.title}' with difficulty '{difficulty}', {num_questions} questions, types: {question_types}")

        learnflow_tool = LearnFlowMCPTool()
        quiz_data_response: QuizResponse = learnflow_tool.generate_quiz(
            unit_title=unit_to_quiz.title, 
            unit_content=unit_to_quiz.content_raw, 
            llm_provider=provider,
            model_name=model_name,
            api_key=api_key,
            difficulty=difficulty,
            num_questions=num_questions,
            question_types=question_types
        )
        
        if hasattr(unit_to_quiz, 'quiz_data'):
            unit_to_quiz.quiz_data = quiz_data_response
            session_to_return = create_new_session_copy(session) 
            logging.info(f"Stored newly generated quiz in unit '{unit_to_quiz.title}'.")
        else:
            logging.warning(f"Unit '{unit_to_quiz.title}' does not have 'quiz_data' attribute.")
            session_to_return = session

        quiz_data_to_set_in_state = quiz_data_response
        current_q_idx_update = 0
        current_open_q_idx_update = 0 
        quiz_status_update = f"已生成测验：{unit_to_quiz.title}"
        quiz_container_update = True
        mcq_question_update = "此单元没有多选题。"
        mcq_choices_update = []
        open_question_update = "此单元没有开放题。"
        true_false_question_update = "此单元没有判断题。"
        fill_in_the_blank_question_update = "此单元没有填空题。"
        open_next_button_visible = False 

        if quiz_data_response.mcqs:
            first_mcq = quiz_data_response.mcqs[0]
            mcq_question_update = f"**第 1 题（多选题）：** {first_mcq.question}"
            mcq_choices_update = [f"{k}. {v}" for k,v in first_mcq.options.items()]
        
        # If more than 1 question left
        if quiz_data_response.open_ended:
            open_question_update = f"**开放题 1：** {quiz_data_response.open_ended[0].question}"
            open_next_button_visible = len(quiz_data_response.open_ended) > 1 
        
        if quiz_data_response.true_false:
            true_false_question_update = f"**第 1 题（判断题）：** {quiz_data_response.true_false[0].question}"

        if quiz_data_response.fill_in_the_blank:
            fill_in_the_blank_question_update = f"**第 1 题（填空题）：** {quiz_data_response.fill_in_the_blank[0].question}"

        if not (quiz_data_response.mcqs or quiz_data_response.open_ended or 
                quiz_data_response.true_false or quiz_data_response.fill_in_the_blank):
             quiz_status_update = f"{unit_to_quiz.title} 的测验没有生成题目。"
             quiz_container_update = False
        
        logging.info(f"generate_quiz_logic: Returning session ID {id(session_to_return)}")

        # Set visibility flags based on presence of questions
        mcq_section_visible = bool(quiz_data_response.mcqs)
        open_section_visible = bool(quiz_data_response.open_ended)
        tf_section_visible = bool(quiz_data_response.true_false)
        fitb_section_visible = bool(quiz_data_response.fill_in_the_blank)

        return session_to_return, quiz_data_to_set_in_state, current_q_idx_update, quiz_status_update, \
               quiz_container_update, mcq_question_update, mcq_choices_update, open_question_update, \
               true_false_question_update, fill_in_the_blank_question_update, "", \
               mcq_section_visible, open_section_visible, tf_section_visible, fitb_section_visible, \
               current_open_q_idx_update, open_next_button_visible 
    except Exception as e:
        logging.error(f"Error in generate_quiz_logic: {e}", exc_info=True)
        return default_return + (False, False, False, False) + (0, False) 


def generate_all_quizzes_logic(session: SessionState, provider: str, model_name: str, api_key: str):
    """
    Generates quizzes for all learning units in the session.
    Does not change the currently displayed unit/quiz in the UI.
    """
    session = create_new_session_copy(session)
    if not session.units:
        return session, None, 0, "没有可生成测验的学习单元。", \
               False, "### 多选题", [], "### 开放题", \
               "### 判断题", "### 填空题", "", \
               False, False, False, False, 0, False 

    status_messages = []
    
    # Preserve current quiz data and index if a quiz is active
    current_quiz_data_before_loop = None
    current_question_idx_before_loop = 0
    current_open_question_idx_before_loop = 0 # Preserve open-ended index
    if session.current_unit_index is not None and session.units[session.current_unit_index].quiz_data:
        current_quiz_data_before_loop = session.units[session.current_unit_index].quiz_data
        # Note: current_question_idx is not stored in session state, so we assume 0 for re-display
        # if the user was mid-quiz, they'd restart from Q1 for the current unit.

    learnflow_tool = LearnFlowMCPTool()

    for i, unit in enumerate(session.units):
        if not unit.quiz_data: # Only generate if not already present
            try:
                logging.info(f"Generating quiz for unit {i+1}: {unit.title}")
                # For generate_all_quizzes, use default quiz settings including new types
                quiz_data_response: QuizResponse = learnflow_tool.generate_quiz(
                    unit_title=unit.title, 
                    unit_content=unit.content_raw, 
                    llm_provider=provider,
                    model_name=model_name,
                    api_key=api_key,
                    difficulty="Medium", 
                    num_questions=8, 
                    question_types=["Multiple Choice", "Open-Ended",   # Multiple choice not MCQ
                                    "True/False", "Fill in the Blank"] # All types 
                )
                session.update_unit_quiz_data(i, quiz_data_response)
                status_messages.append(f"✅ 已生成测验：{unit.title}")
            except Exception as e:
                logging.error(f"Error generating quiz for unit {i+1} ({unit.title}): {e}", exc_info=True)
                status_messages.append(f"❌ 生成测验失败：{unit.title}（{str(e)}）")
        else:
            status_messages.append(f"ℹ️ 已存在测验：{unit.title}")

    final_status_message = "所有测验处理完成：\n" + "\n".join(status_messages)
    new_session_all_gen = create_new_session_copy(session)

    # Restore quiz display for the currently selected unit, if any
    quiz_container_update = False
    mcq_question_update = "### 多选题"
    mcq_choices_update = []
    open_question_update = "### 开放题"
    true_false_question_update = "### 判断题"
    fill_in_the_blank_question_update = "### 填空题"
    quiz_data_to_return = None
    open_next_button_visible = False # Default to hidden

    mcq_section_visible = False
    open_section_visible = False
    tf_section_visible = False
    fitb_section_visible = False

    if new_session_all_gen.current_unit_index is not None:
        current_unit_after_loop = new_session_all_gen.units[new_session_all_gen.current_unit_index]
        if current_unit_after_loop.quiz_data:
            quiz_data_to_return = current_unit_after_loop.quiz_data
            quiz_container_update = True
            
            mcq_section_visible = bool(quiz_data_to_return.mcqs)
            open_section_visible = bool(quiz_data_to_return.open_ended)
            tf_section_visible = bool(quiz_data_to_return.true_false)
            fitb_section_visible = bool(quiz_data_to_return.fill_in_the_blank)

            if quiz_data_to_return.mcqs:
                first_mcq = quiz_data_to_return.mcqs[0]
                mcq_question_update = f"**第 1 题（多选题）：** {first_mcq.question}"
                mcq_choices_update = [f"{k}. {v}" for k,v in first_mcq.options.items()]
            if quiz_data_to_return.open_ended: # Changed from elif to if
                open_question_update = f"**开放题 1：** {quiz_data_to_return.open_ended[0].question}"
                open_next_button_visible = len(quiz_data_to_return.open_ended) > 1
            if quiz_data_to_return.true_false: # Changed from elif to if
                true_false_question_update = f"**第 1 题（判断题）：** {quiz_data_to_return.true_false[0].question}"
            if quiz_data_to_return.fill_in_the_blank: # Changed from elif to if
                fill_in_the_blank_question_update = f"**第 1 题（填空题）：** {quiz_data_to_return.fill_in_the_blank[0].question}"
            
            if not (quiz_data_to_return.mcqs or quiz_data_to_return.open_ended or
                    quiz_data_to_return.true_false or quiz_data_to_return.fill_in_the_blank):
                quiz_container_update = False

    return new_session_all_gen, quiz_data_to_return, current_question_idx_before_loop, final_status_message, \
           quiz_container_update, mcq_question_update, mcq_choices_update, open_question_update, \
           true_false_question_update, fill_in_the_blank_question_update, "", \
           mcq_section_visible, open_section_visible, tf_section_visible, fitb_section_visible, \
           current_open_question_idx_before_loop, open_next_button_visible # Added open-ended index and next button visibility


def submit_mcq_answer_logic(session: SessionState, current_quiz_data: Optional[QuizResponse], 
                          question_idx_val: int, user_choice_str: Optional[str]):
    """Core logic for submitting MCQ answers - now performs direct comparison."""
    logging.info(f"submit_mcq_answer_logic called with q_idx: {question_idx_val}, choice: {user_choice_str}")
    if not (current_quiz_data and current_quiz_data.mcqs and 0 <= question_idx_val < len(current_quiz_data.mcqs)):
        logging.warning("submit_mcq_answer_logic: Invalid quiz data or question index.")
        return "错误：未找到测验数据或题目。", False
    
    current_mcq_item: MCQQuestion = current_quiz_data.mcqs[question_idx_val]
    user_answer_key = user_choice_str.split(".")[0] if user_choice_str else ""
    
    is_correct = (user_answer_key == current_mcq_item.correct_answer)
    
    # Update the MCQ item's is_correct and user_answer status
    current_mcq_item.is_correct = is_correct
    current_mcq_item.user_answer = user_answer_key 
    
    # Update the unit status in the session if all questions are answered
    if session.current_unit_index is not None:
        session.update_unit_quiz_data(session.current_unit_index, current_quiz_data)

    feedback_text = ""
    if is_correct:
        feedback_text = f"✅ **回答正确！** {current_mcq_item.explanation}"
    else:
        correct_ans_display = f"{current_mcq_item.correct_answer}. {current_mcq_item.options.get(current_mcq_item.correct_answer, '')}"
        feedback_text = f"❌ **回答错误。** 正确答案是 {correct_ans_display}。{current_mcq_item.explanation}"
    
    show_next_button = question_idx_val + 1 < len(current_quiz_data.mcqs)
    return feedback_text, show_next_button

def submit_true_false_answer_logic(session: SessionState, current_quiz_data: Optional[QuizResponse],
                                   question_idx_val: int, user_choice_str: str):
    """Core logic for submitting True/False answers - now performs direct comparison."""
    logging.info(f"submit_true_false_answer_logic called with q_idx: {question_idx_val}, choice: {user_choice_str}")
    if not (current_quiz_data and current_quiz_data.true_false and 0 <= question_idx_val < len(current_quiz_data.true_false)):
        logging.warning("submit_true_false_answer_logic: Invalid quiz data or question index.")
        return "错误：未找到测验数据或题目。", False

    current_tf_item: TrueFalseQuestion = current_quiz_data.true_false[question_idx_val]
    
    # Convert user_choice_str to boolean
    user_choice_bool = user_choice_str.lower() == "true"
    
    is_correct = (user_choice_bool == current_tf_item.correct_answer)
    current_tf_item.is_correct = is_correct 
    current_tf_item.user_answer = user_choice_bool 

    # Update the unit status in the session if all questions are answered
    if session.current_unit_index is not None:
        session.update_unit_quiz_data(session.current_unit_index, current_quiz_data)
    
    feedback_text = ""
    if is_correct:
        feedback_text = f"✅ **回答正确！** {current_tf_item.explanation}"
    else:
        feedback_text = f"❌ **回答错误。** 正确答案是 {current_tf_item.correct_answer}。{current_tf_item.explanation}"
    
    show_next_button = question_idx_val + 1 < len(current_quiz_data.true_false)
    return feedback_text, show_next_button

def submit_fill_in_the_blank_answer_logic(session: SessionState, current_quiz_data: Optional[QuizResponse],
                                          question_idx_val: int, user_answer_text: str):
    """Core logic for submitting Fill in the Blank answers - now performs direct comparison."""
    logging.info(f"submit_fill_in_the_blank_answer_logic called with q_idx: {question_idx_val}, answer: {user_answer_text}")
    if not (current_quiz_data and current_quiz_data.fill_in_the_blank and 0 <= question_idx_val < len(current_quiz_data.fill_in_the_blank)):
        logging.warning("submit_fill_in_the_blank_answer_logic: Invalid quiz data or question index.")
        return "错误：未找到测验数据或题目。", False

    current_fitb_item: FillInTheBlankQuestion = current_quiz_data.fill_in_the_blank[question_idx_val]
    
    # Simple case-insensitive comparison for now
    is_correct = (user_answer_text.strip().lower() == current_fitb_item.correct_answer.strip().lower())
    current_fitb_item.is_correct = is_correct 
    current_fitb_item.user_answer = user_answer_text 

    # Update the unit status in the session if all questions are answered
    if session.current_unit_index is not None:
        session.update_unit_quiz_data(session.current_unit_index, current_quiz_data)
    
    feedback_text = ""
    if is_correct:
        feedback_text = f"✅ **回答正确！** {current_fitb_item.explanation}"
    else:
        feedback_text = f"❌ **回答错误。** 正确答案是“{current_fitb_item.correct_answer}”。{current_fitb_item.explanation}"
    
    show_next_button = question_idx_val + 1 < len(current_quiz_data.fill_in_the_blank)
    return feedback_text, show_next_button


def submit_open_answer_logic(session: SessionState, current_quiz_data: Optional[QuizResponse], 
                           question_idx_val: int, user_answer_text: str, llm_provider: str,
                           model_name: str, api_key: str):
    """Core logic for submitting open-ended answers - now handles multiple questions."""
    logging.info(f"submit_open_answer_logic called with q_idx: {question_idx_val}, answer: {user_answer_text}")
    if not (current_quiz_data and current_quiz_data.open_ended and 0 <= question_idx_val < len(current_quiz_data.open_ended)):
        logging.warning("submit_open_answer_logic: Invalid quiz data or question index.")
        return "错误：未找到测验数据或题目。", False 

    try:
        open_question_data = current_quiz_data.open_ended[question_idx_val]
        learnflow_tool = LearnFlowMCPTool()
        result = learnflow_tool.evaluate_open_ended_response(
            open_question_data, user_answer_text, llm_provider, model_name, api_key
        )
        
        open_question_data.user_answer = user_answer_text 
        open_question_data.score = result.get('score') 

        # Update the unit status in the session if all questions are answered
        if session.current_unit_index is not None:
            session.update_unit_quiz_data(session.current_unit_index, current_quiz_data)

        feedback_text = f"""
        **你的分数：** {result.get('score', 'N/A')}/10（注：AI 评估仅供参考）\n
        **反馈：** {result.get('feedback', '暂无反馈。')}\n
        **参考答案：** {result.get('model_answer', '暂无参考答案。')} 
        """
        show_next_button = question_idx_val + 1 < len(current_quiz_data.open_ended)
        return feedback_text, show_next_button
    except Exception as e:
        logging.error(f"Error evaluating open answer: {e}", exc_info=True)
        return f"评估答案时出错：{str(e)}", False # Return feedback and show_next

def prepare_and_navigate_to_quiz(session: SessionState, provider: str, model_name: str, api_key: str, TAB_IDS_IN_ORDER: List[str]):
    """
    Prepares quiz data and navigation to the quiz tab.
    Moved from app.py to reduce its length.
    """
    session = create_new_session_copy(session) 
    
    # Default return values for error cases
    default_error_return = (
        session, "发生错误。", gr.update(selected="learn"), 
        gr.update(visible=False), None, [], "正在进入测验页面...", 
        "生成测验时出错。", gr.update(visible=False), "此单元没有多选题。", 
        gr.update(choices=[], value=None), "此单元没有开放题。", 
        None, 0, "此单元没有判断题。", "此单元没有填空题。", 
        gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
        0, gr.update(visible=False) # Added open-ended index and next button visibility
    )

    if not session.units:
        return session, "没有可测验的学习单元。", gr.update(selected="plan"), \
               gr.update(visible=False), None, [], "正在进入测验页面...", \
               "正在加载测验...", gr.update(visible=False), "此单元没有多选题。", \
               gr.update(choices=[], value=None), "此单元没有开放题。", None, 0, \
               "此单元没有判断题。", "此单元没有填空题。", \
               gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), \
               0, gr.update(visible=False) # Added open-ended index and next button visibility

    current_unit_to_quiz = session.get_current_unit()
    if not current_unit_to_quiz:
        return session, "尚未选择要测验的当前单元。", gr.update(selected="learn"), \
               gr.update(visible=False), None, [], "正在进入测验页面...", \
               "正在加载测验...", gr.update(visible=False), "此单元没有多选题。", \
               gr.update(choices=[], value=None), "此单元没有开放题。", None, 0, \
               "此单元没有判断题。", "此单元没有填空题。", \
               gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), \
               0, gr.update(visible=False) # Added open-ended index and next button visibility

    quiz_data_to_set_in_state = None
    if hasattr(current_unit_to_quiz, 'quiz_data') and current_unit_to_quiz.quiz_data is not None:
        quiz_data_to_set_in_state = current_unit_to_quiz.quiz_data
    else:
        try:
            learnflow_tool = LearnFlowMCPTool()
            default_difficulty = "Medium"
            default_num_questions = 8
            default_question_types = ["Multiple Choice", "Open-Ended", "True/False", "Fill in the Blank"]
            
            logging.debug(f"Calling generate_quiz with: "
                          f"unit_title='{current_unit_to_quiz.title}', "
                          f"unit_content_len={len(current_unit_to_quiz.content_raw)}, "
                          f"llm_provider='{provider}', "
                          f"difficulty='{default_difficulty}', "
                          f"num_questions={default_num_questions}, "
                          f"question_types={default_question_types}")

            newly_generated_quiz_data: QuizResponse = learnflow_tool.generate_quiz(
                unit_title=current_unit_to_quiz.title, 
                unit_content=current_unit_to_quiz.content_raw, 
                llm_provider=provider,
                model_name=model_name,
                api_key=api_key,
                difficulty=default_difficulty, 
                num_questions=default_num_questions, 
                question_types=default_question_types 
            )
            quiz_data_to_set_in_state = newly_generated_quiz_data
            if hasattr(current_unit_to_quiz, 'quiz_data'):
                current_unit_to_quiz.quiz_data = newly_generated_quiz_data
                session = create_new_session_copy(session)
        except Exception as e:
            logging.error(f"Error during quiz generation: {e}", exc_info=True)
            return default_error_return
    
    quiz_status_update = f"测验：{current_unit_to_quiz.title}"
    quiz_container_update = gr.update(visible=True)
    current_q_idx_update = 0 
    current_open_q_idx_update = 0 # Initialize open-ended question index
    mcq_question_update = "此单元没有多选题。"
    mcq_choices_update = gr.update(choices=[], value=None)
    open_question_update = "此单元没有开放题。"
    true_false_question_update = "此单元没有判断题。"
    fill_in_the_blank_question_update = "此单元没有填空题。"
    open_next_button_visible = gr.update(visible=False) # Default to hidden

    # Set visibility flags based on presence of questions
    mcq_section_visible = bool(quiz_data_to_set_in_state and quiz_data_to_set_in_state.mcqs)
    open_section_visible = bool(quiz_data_to_set_in_state and quiz_data_to_set_in_state.open_ended)
    tf_section_visible = bool(quiz_data_to_set_in_state and quiz_data_to_set_in_state.true_false)
    fitb_section_visible = bool(quiz_data_to_set_in_state and quiz_data_to_set_in_state.fill_in_the_blank)

    if quiz_data_to_set_in_state and (quiz_data_to_set_in_state.mcqs or quiz_data_to_set_in_state.open_ended or
                                      quiz_data_to_set_in_state.true_false or quiz_data_to_set_in_state.fill_in_the_blank):
        if quiz_data_to_set_in_state.mcqs:
            first_mcq = quiz_data_to_set_in_state.mcqs[0]
            mcq_question_update = f"**第 1 题（多选题）：** {first_mcq.question}"
            mcq_choices_update = gr.update(choices=[f"{k}. {v}" for k,v in first_mcq.options.items()], value=None)
        if quiz_data_to_set_in_state.open_ended: 
            open_question_update = f"**开放题 1：** {quiz_data_to_set_in_state.open_ended[0].question}"
            open_next_button_visible = gr.update(visible=len(quiz_data_to_set_in_state.open_ended) > 1)
        if quiz_data_to_set_in_state.true_false: 
            true_false_question_update = f"**第 1 题（判断题）：** {quiz_data_to_set_in_state.true_false[0].question}"
        if quiz_data_to_set_in_state.fill_in_the_blank: 
            fill_in_the_blank_question_update = f"**第 1 题（填空题）：** {quiz_data_to_set_in_state.fill_in_the_blank[0].question}"
    else:
        quiz_status_update = f"{current_unit_to_quiz.title} 的测验没有题目。"
        quiz_container_update = gr.update(visible=False)

    return session, "", gr.update(selected="quiz"), \
           gr.update(visible=False), None, [], "正在进入测验页面...", \
           quiz_status_update, quiz_container_update, mcq_question_update, mcq_choices_update, open_question_update, \
           quiz_data_to_set_in_state, current_q_idx_update, \
           true_false_question_update, fill_in_the_blank_question_update, \
           gr.update(visible=mcq_section_visible), gr.update(visible=open_section_visible), \
           gr.update(visible=tf_section_visible), gr.update(visible=fitb_section_visible), \
           current_open_q_idx_update, open_next_button_visible 
