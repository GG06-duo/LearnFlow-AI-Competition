import os
import re
import shutil
import sys
import time
import logging
import threading
import subprocess
import gradio as gr
from pathlib import Path
from typing import Optional, Literal

from services.llm_factory import _PROVIDER_MAP
from components.state import SessionState
from components.ui_components import (
    create_llm_config_inputs, create_unit_dropdown, create_file_upload,
    create_text_input, create_status_markdown, create_primary_button,
    create_secondary_button, create_quiz_components,
    create_session_management_components, create_export_components,
    create_difficulty_radio, create_question_number_slider,
    create_question_types_checkboxgroup,
    create_stats_card, create_overall_progress_html
)
from agents.models import ExplanationResponse

from utils.common.utils import run_code_snippet
from utils.app_wrappers import (
    process_content_wrapper,
    navigate_to_learn,
    load_unit_wrapper,
    generate_explanation_wrapper,
    generate_all_explanations_wrapper,
    prepare_and_navigate_to_quiz,
    generate_quiz_wrapper,
    generate_all_quizzes_wrapper,
    submit_mcq_wrapper, next_mcq_question,
    submit_open_wrapper, next_open_question,
    submit_true_false_wrapper, next_true_false_question,
    submit_fill_in_the_blank_wrapper, next_fill_in_the_blank_question,
    handle_tab_change,
    save_session_wrapper, load_session_wrapper,
    export_markdown_wrapper, export_html_wrapper, export_pdf_wrapper
)


# Configure essential logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s'
)

PROVIDERS = list(_PROVIDER_MAP.keys())
TAB_IDS_IN_ORDER = ["plan", "learn", "quiz", "progress"]
PROGRESS_TIMER_JS = """
() => {
    let updateScheduled = false;

    const updateProgressTimers = () => {
        document.querySelectorAll(".progress-text").forEach((element) => {
            const text = element.textContent.trim();
            const elapsedMatch = text.match(/^processing\\s*\\|\\s*([\\d.]+)/i);

            if (elapsedMatch) {
                element.dataset.progressLabel = `processing | ${elapsedMatch[1]}s`;
            } else {
                delete element.dataset.progressLabel;
            }
        });
    };

    const scheduleUpdate = () => {
        if (updateScheduled) return;
        updateScheduled = true;
        requestAnimationFrame(() => {
            updateScheduled = false;
            updateProgressTimers();
        });
    };

    new MutationObserver(scheduleUpdate).observe(document.body, {
        childList: true,
        characterData: true,
        subtree: true,
    });
    updateProgressTimers();
}
"""


def create_app():
    with gr.Blocks(
        theme=gr.themes.Base(),
        title="AI学习平台",
        css_paths=["static/style.css"],
        js=PROGRESS_TIMER_JS,
    ) as app:
        gr.HTML("""
        <div class="learnflow-hero">
            <h1>
                🎓 AI 学习平台
            </h1>
            <p>
                人工智能驱动的个性化学习体验
            </p>
        </div>
        """)

        # Global states
        global_session = gr.State(SessionState())
        explanation_data_state = gr.State(None)
        current_code_examples = gr.State([])
        quiz_data_state = gr.State(None)
        current_question_idx = gr.State(0)
        current_open_question_idx = gr.State(0)
        current_tf_question_idx = gr.State(0)
        current_fitb_question_idx = gr.State(0)
        api_keys_store = gr.State({}) 

        # Function to update the API key store and propagate changes to all API key textboxes
        def propagate_api_keys(api_keys_store_val, plan_provider_val, learn_provider_val, quiz_provider_val):
            return (
                api_keys_store_val,
                gr.update(value=api_keys_store_val.get(plan_provider_val, "")),
                gr.update(value=api_keys_store_val.get(learn_provider_val, "")),
                gr.update(value=api_keys_store_val.get(quiz_provider_val, ""))
            )

        # Function to handle API key input changes
        def handle_api_key_input(current_provider, new_api_key, api_keys_store_val):
            api_keys_store_val[current_provider] = new_api_key
            return api_keys_store_val

        # Function to handle provider dropdown changes
        def handle_provider_change(new_provider, api_keys_store_val):
            # When provider changes, retrieve the stored key for the new provider
            new_api_key_for_current_tab = api_keys_store_val.get(new_provider, "")
            return new_api_key_for_current_tab, api_keys_store_val


        with gr.Tabs() as tabs:
            # Plan Tab
            with gr.Tab("📋 规划", id="plan", elem_classes="panel"):
                gr.Markdown("## 规划你的学习旅程")
                gr.Markdown("上传内容，让 AI 为你生成结构化学习单元")
                
                gr.Markdown("### AI 提供商配置")
                plan_llm_config = create_llm_config_inputs(PROVIDERS, "custom", initial_api_key=api_keys_store.value.get("custom", ""))
                ai_provider_plan = plan_llm_config["provider"]
                model_name_plan = plan_llm_config["model"]
                api_key_plan = plan_llm_config["api_key"]
                
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 📄 上传文档")
                        file_in = create_file_upload()
                        gr.Markdown("*支持 PDF、DOC、TXT、PPTX、MD 格式*")
                    with gr.Column(scale=1):
                        gr.Markdown("### ✍️ 粘贴内容")
                        text_in = create_text_input(lines=8)
                with gr.Row():
                    input_type = gr.Radio(
                        choices=["File", "Text"],
                        value="Text",
                        label="内容类型",
                        elem_classes="content-type-radio-group",
                    )
                plan_btn = create_primary_button("🚀 使用 AI 处理")
                plan_status = create_status_markdown(
                    "上传内容并点击“使用 AI 处理”以生成学习单元。"
                )
                with gr.Row():
                    unit_dropdown = create_unit_dropdown("已生成的学习单元")
                    navigate_btn = create_secondary_button("继续学习 →")
                units_display = gr.Markdown("尚未生成学习单元。")

            # Learn Tab
            with gr.Tab("📚 学习", id="learn", elem_classes="panel"):
                gr.Markdown("## 互动学习")
                gr.Markdown("AI 根据你的学习风格量身定制讲解")
                
                gr.Markdown("### AI 提供商配置")
                learn_llm_config = create_llm_config_inputs(PROVIDERS, "custom", initial_api_key=api_keys_store.value.get("custom", ""))
                learn_provider_dd = learn_llm_config["provider"]
                model_name_learn = learn_llm_config["model"]
                api_key_learn = learn_llm_config["api_key"]
                
                with gr.Row():
                    with gr.Column():
                        learn_unit_dropdown = create_unit_dropdown("学习单元")
                    with gr.Column():
                        load_unit_btn = create_secondary_button("📖 加载单元")
                current_unit_info = gr.Markdown("未选择单元。")
                gr.Markdown("### 学习风格")
                with gr.Row():
                    explanation_style_radio = gr.Radio(
                        choices=["Concise", "Detailed"],
                        value="Concise",
                        label="",
                        elem_classes="learning-style-radio-group",
                    )
                with gr.Row():
                    explain_btn = create_primary_button("✨ 生成讲解")
                    generate_all_explanations_btn = create_secondary_button(
                        "生成所有章节", elem_classes="secondary-btn"
                    )
                explanation_status = create_status_markdown("")
                explanation_container = gr.Column(visible=False)
                with explanation_container:
                    pass
                quiz_nav_btn = create_secondary_button("📝 进行单元测验", elem_classes="danger-btn")

            # Quiz Tab
            with gr.Tab("❓ 测验", id="quiz", elem_classes="panel"):
                gr.Markdown("## 知识评估")
                gr.Markdown("用 AI 生成的测验检验你的理解")
                quiz_unit_dropdown = create_unit_dropdown("选择测试单元")
                gr.Markdown("### 题目类型")
                with gr.Row():
                    with gr.Column():
                        question_types_checkboxgroup = create_question_types_checkboxgroup()
                    with gr.Column():
                        pass
                gr.Markdown("### 难度级别")
                difficulty_radio = create_difficulty_radio()
                gr.Markdown("### 题目数量")
                question_number_slider = create_question_number_slider()
                
                gr.Markdown("### AI 提供商配置")
                quiz_llm_config = create_llm_config_inputs(PROVIDERS, "custom", initial_api_key=api_keys_store.value.get("custom", ""))
                ai_provider_quiz = quiz_llm_config["provider"]
                model_name_quiz = quiz_llm_config["model"]
                api_key_quiz = quiz_llm_config["api_key"]
                
                generate_quiz_btn = create_primary_button("🎯 生成测验")
                generate_all_quizzes_btn = create_secondary_button(
                    "生成所有测验", elem_classes="secondary-btn"
                )
                quiz_status = create_status_markdown(
                    "选择单元并配置偏好以开始测验。"
                )
                quiz_container = gr.Column(visible=False)
                with quiz_container:
                    quiz_components = create_quiz_components()
                    (mcq_section, mcq_question, mcq_choices, mcq_submit,
                     mcq_feedback, mcq_next) = (
                        quiz_components["mcq_section"],
                        quiz_components["mcq_question"],
                        quiz_components["mcq_choices"],
                        quiz_components["mcq_submit"],
                        quiz_components["mcq_feedback"],
                        quiz_components["mcq_next"]
                     )
                    (open_ended_section, open_question, open_answer,
                     open_submit, open_feedback, open_next) = (
                        quiz_components["open_ended_section"],
                        quiz_components["open_question"],
                        quiz_components["open_answer"],
                        quiz_components["open_submit"],
                        quiz_components["open_feedback"],
                        quiz_components["open_next"]
                     )
                    (tf_section, tf_question, tf_choices, tf_submit,
                     tf_feedback, tf_next) = (
                        quiz_components["tf_section"],
                        quiz_components["tf_question"],
                        quiz_components["tf_choices"],
                        quiz_components["tf_submit"],
                        quiz_components["tf_feedback"],
                        quiz_components["tf_next"]
                     )
                    (fitb_section, fitb_question, fitb_answer, fitb_submit,
                     fitb_feedback, fitb_next) = (
                        quiz_components["fitb_section"],
                        quiz_components["fitb_question"],
                        quiz_components["fitb_answer"],
                        quiz_components["fitb_submit"],
                        quiz_components["fitb_feedback"],
                        quiz_components["fitb_next"]
                     )

            # Progress Tab
            with gr.Tab("📊 进度", id="progress", elem_classes="panel"):
                gr.Markdown("## 学习分析")
                with gr.Row():
                    overall_stats = create_stats_card("已完成", "0", "已掌握单元", "✅", "#10b981")
                    in_progress_stats = create_stats_card("进行中", "0", "学习中单元", "📈", "#3b82f6")
                    average_score_stats = create_stats_card("平均分", "0%", "测验成绩", "🎯", "#f59e0b")
                progress_chart = gr.Plot(label="学习进度", visible=False)
                gr.Markdown("### 📋 详细进度")
                progress_df = gr.Dataframe(
                    headers=["学习单元", "状态", "测验分数", "进度"],
                    datatype=["str", "str", "str", "number"],
                    interactive=False
                )
                gr.Markdown("### 🎯 总体学习进度")
                overall_progress = create_overall_progress_html(progress_percentage=0)
                gr.Markdown("### 💾 会话管理")
                session_components = create_session_management_components()
                with gr.Row():
                    session_name_input = session_components["session_name_input"]
                with gr.Row():
                    save_session_btn = session_components["save_session_btn"]
                    load_session_btn = session_components["load_session_btn"]
                saved_sessions_dropdown = session_components["saved_sessions_dropdown"]
                session_status = session_components["session_status"]
                gr.Markdown("### 📤 导出与分享")
                export_components = create_export_components()
                with gr.Row():
                    export_markdown_btn = export_components["export_markdown_btn"]
                    export_html_btn = export_components["export_html_btn"]
                    export_pdf_btn = export_components["export_pdf_btn"]
                export_file = export_components["export_file"]
                export_status = export_components["export_status"]

        # --- Dynamic Explanation Renderer ---
        @gr.render(inputs=[explanation_data_state])
        def render_dynamic_explanation(explanation_data: Optional[ExplanationResponse]):
            if not explanation_data:
                gr.Markdown("<!-- Explanation will appear here once generated. -->")
                return
            processed_markdown = explanation_data.markdown
            parts = re.split(r'\[CODE_INSERTION_POINT_(\d+)\]', processed_markdown)
            for i, part_content in enumerate(parts):
                if i % 2 == 0 and part_content.strip():
                    gr.Markdown(
                        part_content,
                        latex_delimiters=[{"left": "$$", "right": "$$", "display": True},
                                          {"left": "$", "right": "$", "display": False}]
                    )
                elif i % 2 == 1:
                    try:
                        idx = int(part_content)
                        if 0 <= idx < len(explanation_data.code_examples or []):
                            code_example = explanation_data.code_examples[idx]
                            with gr.Column():
                                gr.Markdown(f"### 💻 {code_example.description or f'代码示例 {idx+1}'}")
                                # Ensure language is one of the literal types expected by gr.Code
                                allowed_languages = ["python", "javascript", "html", "css", "json", "markdown", "latex"]
                                lang: Literal["python", "javascript", "html", "css", "json", "markdown", "latex"] = \
                                    code_example.language if code_example.language in allowed_languages else "python" # type: ignore
                                code_block = gr.Code(language=lang, value=code_example.code)
                                run_btn = gr.Button("▶ 运行代码", size="sm")
                                run_btn.click(run_code_snippet, inputs=[code_block], outputs=[gr.Textbox(label="输出", lines=3, interactive=False)])
                    except ValueError:
                        gr.Markdown(f"*(Error: Invalid code placeholder '{part_content}')*")

        # --- Event Handlers ---
        # Explicitly type Gradio components to help Pylint
        plan_btn_typed: gr.Button = plan_btn
        navigate_btn_typed: gr.Button = navigate_btn
        load_unit_btn_typed: gr.Button = load_unit_btn
        explain_btn_typed: gr.Button = explain_btn
        generate_all_explanations_btn_typed: gr.Button = generate_all_explanations_btn
        quiz_nav_btn_typed: gr.Button = quiz_nav_btn
        generate_quiz_btn_typed: gr.Button = generate_quiz_btn
        generate_all_quizzes_btn_typed: gr.Button = generate_all_quizzes_btn
        mcq_submit_typed: gr.Button = mcq_submit
        mcq_next_typed: gr.Button = mcq_next
        open_submit_typed: gr.Button = open_submit
        open_next_typed: gr.Button = open_next
        tf_submit_typed: gr.Button = tf_submit
        tf_next_typed: gr.Button = tf_next
        fitb_submit_typed: gr.Button = fitb_submit
        fitb_next_typed: gr.Button = fitb_next
        save_session_btn_typed: gr.Button = save_session_btn
        load_session_btn_typed: gr.Button = load_session_btn
        export_markdown_btn_typed: gr.Button = export_markdown_btn
        export_html_btn_typed: gr.Button = export_html_btn
        export_pdf_btn_typed: gr.Button = export_pdf_btn
        tabs_typed: gr.Tabs = tabs

        # API Key sharing logic
        # When provider dropdown changes, update current tab's API key textbox and then propagate
        plan_llm_config["provider_dropdown_component"].change(
            fn=handle_provider_change,
            inputs=[plan_llm_config["provider_dropdown_component"], api_keys_store],
            outputs=[plan_llm_config["api_key_textbox_component"], api_keys_store]
        ).then(
            fn=propagate_api_keys,
            inputs=[api_keys_store, plan_llm_config["provider_dropdown_component"], learn_llm_config["provider_dropdown_component"], quiz_llm_config["provider_dropdown_component"]],
            outputs=[api_keys_store, plan_llm_config["api_key_textbox_component"], learn_llm_config["api_key_textbox_component"], quiz_llm_config["api_key_textbox_component"]]
        )
        # When API key textbox changes, update the store and then propagate
        plan_llm_config["api_key_textbox_component"].change(
            fn=handle_api_key_input,
            inputs=[plan_llm_config["provider_dropdown_component"], plan_llm_config["api_key_textbox_component"], api_keys_store],
            outputs=[api_keys_store]
        ).then(
            fn=propagate_api_keys,
            inputs=[api_keys_store, plan_llm_config["provider_dropdown_component"], learn_llm_config["provider_dropdown_component"], quiz_llm_config["provider_dropdown_component"]],
            outputs=[api_keys_store, plan_llm_config["api_key_textbox_component"], learn_llm_config["api_key_textbox_component"], quiz_llm_config["api_key_textbox_component"]]
        )

        learn_llm_config["provider_dropdown_component"].change(
            fn=handle_provider_change,
            inputs=[learn_llm_config["provider_dropdown_component"], api_keys_store],
            outputs=[learn_llm_config["api_key_textbox_component"], api_keys_store]
        ).then(
            fn=propagate_api_keys,
            inputs=[api_keys_store, plan_llm_config["provider_dropdown_component"], learn_llm_config["provider_dropdown_component"], quiz_llm_config["provider_dropdown_component"]],
            outputs=[api_keys_store, plan_llm_config["api_key_textbox_component"], learn_llm_config["api_key_textbox_component"], quiz_llm_config["api_key_textbox_component"]]
        )
        learn_llm_config["api_key_textbox_component"].change(
            fn=handle_api_key_input,
            inputs=[learn_llm_config["provider_dropdown_component"], learn_llm_config["api_key_textbox_component"], api_keys_store],
            outputs=[api_keys_store]
        ).then(
            fn=propagate_api_keys,
            inputs=[api_keys_store, plan_llm_config["provider_dropdown_component"], learn_llm_config["provider_dropdown_component"], quiz_llm_config["provider_dropdown_component"]],
            outputs=[api_keys_store, plan_llm_config["api_key_textbox_component"], learn_llm_config["api_key_textbox_component"], quiz_llm_config["api_key_textbox_component"]]
        )

        quiz_llm_config["provider_dropdown_component"].change(
            fn=handle_provider_change,
            inputs=[quiz_llm_config["provider_dropdown_component"], api_keys_store],
            outputs=[quiz_llm_config["api_key_textbox_component"], api_keys_store]
        ).then(
            fn=propagate_api_keys,
            inputs=[api_keys_store, plan_llm_config["provider_dropdown_component"], learn_llm_config["provider_dropdown_component"], quiz_llm_config["provider_dropdown_component"]],
            outputs=[api_keys_store, plan_llm_config["api_key_textbox_component"], learn_llm_config["api_key_textbox_component"], quiz_llm_config["api_key_textbox_component"]]
        )
        quiz_llm_config["api_key_textbox_component"].change(
            fn=handle_api_key_input,
            inputs=[quiz_llm_config["provider_dropdown_component"], quiz_llm_config["api_key_textbox_component"], api_keys_store],
            outputs=[api_keys_store]
        ).then(
            fn=propagate_api_keys,
            inputs=[api_keys_store, plan_llm_config["provider_dropdown_component"], learn_llm_config["provider_dropdown_component"], quiz_llm_config["provider_dropdown_component"]],
            outputs=[api_keys_store, plan_llm_config["api_key_textbox_component"], learn_llm_config["api_key_textbox_component"], quiz_llm_config["api_key_textbox_component"]]
        )


        plan_btn_typed.click(
            process_content_wrapper,
            inputs=[global_session, ai_provider_plan, model_name_plan, api_key_plan, file_in, text_in, input_type],
            outputs=[global_session, plan_status, units_display, unit_dropdown,
                     learn_unit_dropdown, quiz_unit_dropdown]
        )
        navigate_btn_typed.click(
            navigate_to_learn,
            inputs=[global_session, unit_dropdown],
            outputs=[plan_status, tabs, global_session]
        )
        load_unit_btn_typed.click(
            load_unit_wrapper,
            inputs=[global_session, learn_unit_dropdown],
            outputs=[global_session, current_unit_info, explanation_container,
                     explanation_data_state, current_code_examples, current_unit_info, learn_unit_dropdown]
        )
        explain_btn_typed.click(
            generate_explanation_wrapper,
            inputs=[global_session, learn_provider_dd, model_name_learn, api_key_learn, explanation_style_radio, learn_unit_dropdown],
            outputs=[global_session, explanation_status, explanation_container,
                     explanation_data_state, current_code_examples, current_unit_info, learn_unit_dropdown]
        )
        generate_all_explanations_btn_typed.click(
            generate_all_explanations_wrapper,
            inputs=[global_session, learn_provider_dd, model_name_learn, api_key_learn, explanation_style_radio],
            outputs=[global_session, explanation_status, explanation_container,
                     explanation_data_state, current_code_examples, current_unit_info, learn_unit_dropdown]
        )
        quiz_nav_btn_typed.click(
            prepare_and_navigate_to_quiz,
            inputs=[global_session, learn_provider_dd, model_name_learn, api_key_learn, gr.State(TAB_IDS_IN_ORDER)],
            outputs=[global_session, explanation_status, tabs, explanation_container,
                     explanation_data_state, current_code_examples, current_unit_info,
                     quiz_status, quiz_container, mcq_question, mcq_choices, open_question, quiz_data_state, current_question_idx,
                     tf_question, fitb_question, mcq_section, open_ended_section,
                     tf_section, fitb_section, current_open_question_idx, open_next]
        )
        generate_quiz_btn_typed.click(
            generate_quiz_wrapper,
            inputs=[global_session, quiz_unit_dropdown, ai_provider_quiz, model_name_quiz, api_key_quiz,
                    difficulty_radio, question_number_slider, question_types_checkboxgroup],
            outputs=[global_session, quiz_data_state, current_question_idx, quiz_status,
                     quiz_container, mcq_question, mcq_choices, open_question,
                     tf_question, fitb_question, mcq_feedback, mcq_section,
                     open_ended_section, tf_section, fitb_section, current_open_question_idx, open_next]
        )
        generate_all_quizzes_btn_typed.click(
            generate_all_quizzes_wrapper,
            inputs=[global_session, ai_provider_quiz, model_name_quiz, api_key_quiz],
            outputs=[global_session, quiz_data_state, current_question_idx, quiz_status,
                     quiz_container, mcq_question, mcq_choices, open_question,
                     tf_question, fitb_question, mcq_feedback, mcq_section,
                     open_ended_section, tf_section, fitb_section, current_open_question_idx, open_next]
        )
        mcq_submit_typed.click(
            submit_mcq_wrapper,
            inputs=[global_session, quiz_data_state, current_question_idx,
                    mcq_choices, ai_provider_quiz, model_name_quiz, api_key_quiz],
            outputs=[mcq_feedback, mcq_next]
        )
        mcq_next_typed.click(
            next_mcq_question,
            inputs=[quiz_data_state, current_question_idx],
            outputs=[current_question_idx, mcq_question, mcq_choices,
                     mcq_feedback, mcq_next]
        )
        open_submit_typed.click(
            submit_open_wrapper,
            inputs=[global_session, quiz_data_state, current_open_question_idx, open_answer, ai_provider_quiz, model_name_quiz, api_key_quiz],
            outputs=[open_feedback, open_next]
        )
        open_next_typed.click(
            next_open_question,
            inputs=[quiz_data_state, current_open_question_idx],
            outputs=[current_open_question_idx, open_question, open_answer,
                     open_feedback, open_next]
        )
        tf_submit_typed.click(
            submit_true_false_wrapper,
            inputs=[global_session, quiz_data_state, current_tf_question_idx,
                    tf_choices, ai_provider_quiz, model_name_quiz, api_key_quiz],
            outputs=[tf_feedback, tf_next]
        )
        tf_next_typed.click(
            next_true_false_question,
            inputs=[quiz_data_state, current_tf_question_idx],
            outputs=[current_tf_question_idx, tf_question, tf_choices,
                     tf_feedback, tf_next]
        )
        fitb_submit_typed.click(
            submit_fill_in_the_blank_wrapper,
            inputs=[global_session, quiz_data_state, current_fitb_question_idx,
                    fitb_answer, ai_provider_quiz, model_name_quiz, api_key_quiz],
            outputs=[fitb_feedback, fitb_next]
        )
        fitb_next_typed.click(
            next_fill_in_the_blank_question,
            inputs=[quiz_data_state, current_fitb_question_idx],
            outputs=[current_fitb_question_idx, fitb_question, fitb_answer,
                     fitb_feedback, fitb_next]
        )
        save_session_btn_typed.click(
            save_session_wrapper,
            inputs=[global_session, session_name_input],
            outputs=[global_session, session_status, saved_sessions_dropdown]
        )
        load_session_btn_typed.click(
            load_session_wrapper,
            inputs=[saved_sessions_dropdown],
            outputs=[global_session, session_status,
                     unit_dropdown, learn_unit_dropdown, quiz_unit_dropdown,
                     units_display, overall_stats, in_progress_stats, average_score_stats, overall_progress, progress_df]
        )
        export_markdown_btn_typed.click(
            export_markdown_wrapper,
            inputs=[global_session],
            outputs=[export_file, export_status, export_file]
        )
        export_html_btn_typed.click(
            export_html_wrapper,
            inputs=[global_session],
            outputs=[export_file, export_status, export_file]
        )
        export_pdf_btn_typed.click(
            export_pdf_wrapper,
            inputs=[global_session],
            outputs=[export_file, export_status, export_file]
        )
        tabs_typed.select(
            handle_tab_change,
            inputs=[global_session, quiz_data_state],
            outputs=[
                global_session, overall_stats, in_progress_stats, average_score_stats, overall_progress, progress_df,
                explanation_container, explanation_data_state, current_code_examples,
                quiz_container, current_unit_info, learn_unit_dropdown,
                saved_sessions_dropdown, mcq_section, open_ended_section,
                tf_section, fitb_section
            ]
        )

    return app



if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--mcp-tool":
        from mcp_tool_runner import run_tool
        import asyncio

        asyncio.run(run_tool(sys.argv[2], sys.argv[3]))
        sys.exit(0)

    # Build the MCP server automatically for a self-contained local launch.
    APP_ROOT = Path(__file__).resolve().parent
    MCP_DIR = APP_ROOT / 'mcp_server' / 'learnflow-mcp-server'
    BUILD_DIR = MCP_DIR / 'build'
    MCP_SERVER_PATH = BUILD_DIR / 'index.js'
    LEARNFLOW_AI_ROOT = str(APP_ROOT)

    # === MCP Build ===
    def build_mcp_server():
        if BUILD_DIR.exists():
            logging.info(f"MCP build already exists at {BUILD_DIR}")
            return True

        logging.info(f"MCP build not found at {BUILD_DIR}, starting build process...")

        try:
            subprocess.run(["npm", "install"], cwd=str(MCP_DIR), check=True)
            subprocess.run(["npm", "run", "build"], cwd=str(MCP_DIR), check=True)
            logging.info("MCP server built successfully.")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"MCP build failed: {e}")
            return False
        except FileNotFoundError:
            logging.error("npm not found. Ensure Node.js is installed in your environment.")
            return False

    # === MCP Launch ===
    def launch_mcp_server():
        logging.info(f"Attempting to launch MCP server from: {MCP_SERVER_PATH}")
        logging.info(f"Setting LEARNFLOW_AI_ROOT to: {LEARNFLOW_AI_ROOT}")

        if not BUILD_DIR.exists():
            logging.error(f"MCP server build directory not found: {BUILD_DIR}")
            return

        env = os.environ.copy()
        env['LEARNFLOW_AI_ROOT'] = LEARNFLOW_AI_ROOT
        node_executable = APP_ROOT / 'node' / 'node.exe'
        if not node_executable.exists():
            node_executable = Path(shutil.which('node') or 'node')
        if getattr(sys, 'frozen', False):
            env['LEARNFLOW_MCP_EXECUTABLE'] = sys.executable

        try:
            process = subprocess.Popen(
                [str(node_executable), str(MCP_SERVER_PATH)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            logging.info(f"MCP server process started with PID: {process.pid}")

            def log_stdout():
                for line in process.stdout:
                    logging.info(f"MCP STDOUT: {line.strip()}")

            def log_stderr():
                for line in process.stderr:
                    logging.error(f"MCP STDERR: {line.strip()}")

            threading.Thread(target=log_stdout, daemon=True).start()
            threading.Thread(target=log_stderr, daemon=True).start()

            global mcp_server_process
            mcp_server_process = process

        except FileNotFoundError:
            logging.error("Node.js executable not found. Please ensure Node.js is installed and in your PATH.")
        except Exception as e:
            logging.error(f"Failed to launch MCP server: {e}")
    if not build_mcp_server():
        logging.error("Build failed. Aborting.")
        sys.exit(1)

    # Launch the MCP server in a separate thread 
    mcp_thread = threading.Thread(target=launch_mcp_server, daemon=True)
    mcp_thread.start()
    time.sleep(5) 

    app = create_app()
    app.launch(inbrowser=True)
