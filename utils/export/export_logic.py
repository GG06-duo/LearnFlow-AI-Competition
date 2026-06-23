import logging
import tempfile
import markdown
import os
import shutil
import re
import urllib.parse
import base64
import asyncio
import pathlib
from components.state import SessionState, get_unit_status_emoji

try:
    import pyppeteer
    from pyppeteer.launcher import DEFAULT_ARGS
    PYPPETEER_AVAILABLE = True
except ImportError:
    logging.warning("pyppeteer not installed. PDF export will be disabled. "
                    "Please run 'pip install pyppeteer'.")
    PYPPETEER_AVAILABLE = False
except Exception as e:
    logging.error(f"Error importing pyppeteer: {e}. PDF export will be disabled.", exc_info=True)
    PYPPETEER_AVAILABLE = False

async def _delete_file_after_delay(file_path: str, delay: int = 60):
    """Deletes a file after a specified delay."""
    await asyncio.sleep(delay)
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
            logging.info(f"Deleted temporary export file: {file_path}")
        else:
            logging.warning(f"File not found for deletion: {file_path}")
    except Exception as e:
        logging.error(f"Error deleting file {file_path}: {e}", exc_info=True)

def _convert_markdown_to_html(md_content: str) -> str:
    """Converts markdown to HTML, preserving LaTeX for MathJax."""
    return markdown.markdown(md_content, extensions=['fenced_code', 'tables', 'sane_lists'])

def _image_to_base64_uri(image_path: str) -> str:
    """Converts an image file to a Base64 data URI."""
    if not os.path.exists(image_path):
        logging.warning(f"Image not found at path: {image_path}. Skipping embedding.")
        return ""
    
    try:
        ext = os.path.splitext(image_path)[1][1:].lower()
        if ext == 'jpg': ext = 'jpeg'
        if ext not in ['jpeg', 'png', 'gif', 'svg']:
            logging.warning(f"Unsupported image type '{ext}' for base64 embedding.")
            return image_path 

        mime_type = f"image/{ext}" if ext != 'svg' else "image/svg+xml"

        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        
        return f"data:{mime_type};base64,{encoded_string}"
    except Exception as e:
        logging.error(f"Could not convert image {image_path} to base64: {e}")
        return "" 

def export_session_to_markdown(session: SessionState) -> str:
    """Exports the entire session content to a single Markdown string."""
    markdown_content = "# LearnFlow AI Session Export\n\n"
    markdown_content += f"**LLM Provider:** {session.provider}\n\n"
    
    summary = session.get_progress_summary()
    markdown_content += "## Progress Summary\n"
    markdown_content += f"- Total Units: {summary.get('total_units', 0)}\n"
    markdown_content += f"- Completed: {summary.get('completed_units', 0)} ✅\n"
    markdown_content += f"- In Progress: {summary.get('in_progress_units', 0)} 🕑\n"
    markdown_content += f"- Not Started: {summary.get('not_started_units', 0)} 📘\n"
    markdown_content += f"- Completion Rate: {summary.get('completion_rate', 0):.1f}%\n\n"

    markdown_content += "## Learning Units\n\n"
    for i, unit in enumerate(session.units, 1):
        emoji = get_unit_status_emoji(unit)
        markdown_content += f"### {emoji} Unit {i}: {unit.title}\n\n"
        markdown_content += f"**Status:** {unit.status.replace('_', ' ').title()}\n\n"
        markdown_content += f"**Summary:** {unit.summary}\n\n"

        if unit.explanation_data:
            markdown_content += "#### Explanation\n"
            markdown_content += unit.explanation_data.markdown + "\n\n"
            for visual_aid in unit.explanation_data.visual_aids:
                markdown_content += (f"![{visual_aid.caption}]"
                                     f"({visual_aid.path})\n\n")
            for code_example in unit.explanation_data.code_examples:
                markdown_content += f"##### 💻 {code_example.description}\n"
                markdown_content += (f"```{code_example.language}\n"
                                     f"{code_example.code}\n```\n\n")
        
        if unit.quiz_data:
            markdown_content += "#### Quiz\n"
            if unit.quiz_data.mcqs:
                markdown_content += "##### Multiple Choice Questions\n"
                for q_idx, mcq in enumerate(unit.quiz_data.mcqs, 1):
                    markdown_content += f"**Q{q_idx}:** {mcq.question}\n"
                    for key, value in mcq.options.items():
                        markdown_content += f"- {key}. {value}\n"
                    markdown_content += (f"**Correct Answer:** {mcq.correct_answer}. "
                                         f"{mcq.options.get(mcq.correct_answer, '')}\n")
                    markdown_content += f"**Explanation:** {mcq.explanation}\n\n"
            if unit.quiz_data.open_ended:
                markdown_content += "##### Open-Ended Questions\n"
                for q_idx, open_q in enumerate(unit.quiz_data.open_ended, 1):
                    markdown_content += f"**Q{q_idx}:** {open_q.question}\n"
                    markdown_content += f"**Model Answer:** {open_q.model_answer}\n\n"
        
        markdown_content += "---\n\n"
    
    return markdown_content

def export_session_to_html(session: SessionState, embed_images_for_pdf: bool = False) -> str:
    """
    Exports the entire session content to a single HTML string.
    
    Args:
        session: The SessionState object.
        embed_images_for_pdf: If True, embeds images as Base64 data URIs, which is
                              necessary for self-contained PDF generation.
    """
    html_parts = []

    html_parts.append("<h1>LearnFlow AI Session Export</h1>\n\n")
    html_parts.append(f"<p><strong>LLM Provider:</strong> {session.provider}</p>\n\n")
    
    summary = session.get_progress_summary()
    html_parts.append("<h2>Progress Summary</h2>\n")
    html_parts.append("<div class='progress-summary'><ul>\n")
    html_parts.append(f"<li>Total Units: {summary.get('total_units', 0)}</li>\n")
    html_parts.append(f"<li>Completed: {summary.get('completed_units', 0)} ✅</li>\n")
    html_parts.append(f"<li>In Progress: {summary.get('in_progress_units', 0)} 🕑</li>\n")
    html_parts.append(f"<li>Not Started: {summary.get('not_started_units', 0)} 📘</li>\n")
    html_parts.append(f"<li>Completion Rate: {summary.get('completion_rate', 0):.1f}%</li>\n")
    html_parts.append("</ul></div>\n\n")

    html_parts.append("<h2>Learning Units</h2>\n\n")
    for i, unit in enumerate(session.units, 1):
        emoji = get_unit_status_emoji(unit)
        html_parts.append(f"<h3>{emoji} Unit {i}: {unit.title}</h3>\n\n")
        html_parts.append(f"<p><strong>Status:</strong> {unit.status.replace('_', ' ').title()}</p>\n\n")
        html_parts.append(f"<p><strong>Summary:</strong> {unit.summary}</p>\n\n")

        if unit.explanation_data:
            html_parts.append("<h4>Explanation</h4>\n")
            html_parts.append(_convert_markdown_to_html(unit.explanation_data.markdown) + "\n\n")
            for visual_aid in unit.explanation_data.visual_aids:
                # If generating for PDF, embed the image. Otherwise, use the path.
                img_src = _image_to_base64_uri(visual_aid.path) if embed_images_for_pdf else visual_aid.path
                if img_src:
                    html_parts.append(f'<img src="{img_src}" alt="{visual_aid.caption}" style="max-width: 100%; height: auto; display: block; margin: 1.2em auto; border-radius: 6px; box-shadow: 0 2.4px 6px rgba(0,0,0,0.3);">\n\n')
            for code_example in unit.explanation_data.code_examples:
                html_parts.append(f"<h5>💻 {code_example.description}</h5>\n")
                html_parts.append(f"<pre><code class='language-{code_example.language}'>{code_example.code}</code></pre>\n\n")
        
        if unit.quiz_data:
            html_parts.append("<h4>Quiz</h4>\n")
            if unit.quiz_data.mcqs:
                html_parts.append("<h5>Multiple Choice Questions</h5>\n")
                for q_idx, mcq in enumerate(unit.quiz_data.mcqs, 1):
                    html_parts.append(f"<div class='quiz-question'>\n")
                    html_parts.append(f"<strong>Q{q_idx}:</strong> {_convert_markdown_to_html(mcq.question)}\n")
                    html_parts.append("<ol class='quiz-options'>\n")
                    for key, value in mcq.options.items():
                        html_parts.append(f"<li>{key}. {_convert_markdown_to_html(value)}</li>\n")
                    html_parts.append("</ol>\n")
                    html_parts.append(f"<div class='correct-answer'><strong>Correct Answer:</strong> {mcq.correct_answer}. {_convert_markdown_to_html(mcq.options.get(mcq.correct_answer, ''))}</div>\n")
                    html_parts.append(f"<div class='explanation'><strong>Explanation:</strong> {_convert_markdown_to_html(mcq.explanation)}</div>\n")
                    html_parts.append("</div>\n\n")
            if unit.quiz_data.open_ended:
                html_parts.append("<h5>Open-Ended Questions</h5>\n")
                for q_idx, open_q in enumerate(unit.quiz_data.open_ended, 1):
                    html_parts.append(f"<div class='quiz-question'>\n")
                    html_parts.append(f"<strong>Q{q_idx}:</strong> {_convert_markdown_to_html(open_q.question)}\n")
                    html_parts.append(f"<div class='model-answer'><strong>Model Answer:</strong> {_convert_markdown_to_html(open_q.model_answer)}</div>\n")
                    html_parts.append("</div>\n\n")
        
        html_parts.append("<hr>\n\n")
    
    html_body = "".join(html_parts)

    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>LearnFlow AI Session Export</title>
        <!-- MathJax for LaTeX rendering. This is crucial for pyppeteer. -->
        <script type="text/javascript" async
            src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.7/MathJax.js?config=TeX-MML-AM_CHTML">
        </script>
        <script type="text/x-mathjax-config">
          MathJax.Hub.Config({{
            "HTML-CSS": {{ linebreaks: {{ automatic: true }} }},
            SVG: {{ linebreaks: {{ automatic: true }} }},
            showProcessingMessages: false,
            messageStyle: "none"
          }});
          MathJax.Hub.Register.StartupHook("End", function() {{
            document.body.classList.add("MathJax_Processed");
          }});
        </script>
        <style>
            body {{ 
                font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif; 
                line-height: 1.6; 
                background-color: #ffffff; /* Use white background for better printing */
                color: #1f1f1f; /* Dark text for readability */
                max-width: 900px;
                margin: 40px auto;
                padding: 20px;
                font-size: 1.1em;
            }}
            /* Add a print-specific style to remove shadows and ensure dark text on white */
            @media print {{
                body {{
                    box-shadow: none;
                    margin: 0;
                    padding: 0;
                    background-color: #ffffff !important;
                    color: #000000 !important;
                }}
                .progress-summary, .quiz-question, .correct-answer, .explanation, .model-answer {{
                    box-shadow: none;
                    border: 1px solid #ddd;
                    background-color: #f9f9f9 !important;
                }}
            }}
            
            h1, h2, h3, h4, h5 {{ 
                color: #0056b3; 
                margin-top: 1.8em;
                margin-bottom: 0.6em;
            }}
            h1 {{ font-size: 2.2em; border-bottom: 2px solid #ccc; padding-bottom: 12px; }} 
            h2 {{ font-size: 1.8em; border-bottom: 1px solid #ddd; padding-bottom: 6px; }} 
            h3 {{ font-size: 1.4em; }} 
            h4 {{ font-size: 1.1em; }} 
            h5 {{ font-size: 0.9em; }} 

            p {{ margin-bottom: 1.2em; }} 
            ul, ol {{ margin-bottom: 1.2em; padding-left: 24px; }} 
            li {{ margin-bottom: 0.6em; }} 

            pre {{ 
                background-color: #f4f5f7;
                padding: 18px; 
                border-radius: 8px; 
                overflow-x: auto; 
                margin-bottom: 1.8em; 
                font-family: 'Consolas', 'Monaco', 'Andale Mono', 'Ubuntu Mono', monospace;
                font-size: 0.85em; 
                border: 1px solid #e1e4e8;
                color: #24292e;
            }}
            code {{ 
                background-color: #f4f5f7;
                padding: 2.4px 6px; 
                border-radius: 4px; 
                font-family: 'Consolas', 'Monaco', 'Andale Mono', 'Ubuntu Mono', monospace;
                font-size: 0.85em;
            }}
            
            .progress-summary {{
                background-color: #e6f7ff;
                border-left: 6px solid #1890ff;
                padding: 18px 24px; 
                margin-bottom: 2.4em; 
                border-radius: 6px; 
            }}
            .progress-summary ul {{ list-style: none; padding: 0; margin: 0; }}
            .progress-summary li {{ margin-bottom: 0.6em; }}

            .quiz-question {{
                margin-top: 1.8em; 
                margin-bottom: 1.2em; 
                padding: 18px; 
                border: 1px solid #e1e4e8;
                border-radius: 9.6px; 
                background-color: #fcfcfc;
            }}
            .quiz-question strong {{ color: #0056b3; }}
            .quiz-options {{ list-style-type: upper-alpha; padding-left: 30px; margin-top: 0.6em; }}

            .correct-answer, .explanation, .model-answer {{
                padding: 12px; 
                margin-top: 1.2em; 
                border-radius: 6px; 
            }}
            .correct-answer {{ background-color: #e6ffed; border-left: 4.8px solid #52c41a; }}
            .explanation {{ background-color: #e6f7ff; border-left: 4.8px solid #1890ff; }}
            .model-answer {{ background-color: #fffbe6; border-left: 4.8px solid #faad14; }}

            hr {{ border: 0; height: 1.2px; background: #e1e4e8; margin: 3.6em 0; }}
        </style>
    </head>
    <body>
        {}
    </body>
    </html>
    """
    return html_template.format(html_body)

# --- PDF ---
async def find_browser_executable_path() -> str | None:
    """
    Finds a usable Chrome or Chromium executable path on the system.
    This is more robust than pyppeteer's default download.
    """
    # 1. For Debian/Ubuntu systems and container deployments
    for path in ["/usr/bin/chromium", "/usr/bin/chromium-browser"]:
        if os.path.exists(path):
            logging.info(f"Found system-installed Chromium at: {path}")
            return path
    
    # 2. For Windows systems
    if os.name == 'nt':
        for path in [
            os.path.join(os.environ["ProgramFiles"], "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ["ProgramFiles(x86)"], "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ["LOCALAPPDATA"], "Google", "Chrome", "Application", "chrome.exe"),
        ]:
            if os.path.exists(path):
                logging.info(f"Found system-installed Chrome at: {path}")
                return path

    # 3. For macOS systems
    mac_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if os.path.exists(mac_path):
        logging.info(f"Found system-installed Chrome at: {mac_path}")
        return mac_path

    # 4. Fallback to pyppeteer's own downloaded version if it exists
    try:
        from pyppeteer import launcher
        pyppeteer_path = launcher.executablePath()
        if os.path.exists(pyppeteer_path):
            logging.info(f"Found pyppeteer-managed Chromium at: {pyppeteer_path}")
            return pyppeteer_path
    except Exception:
        pass 

    logging.warning("Could not find a pre-installed Chrome/Chromium browser.")
    return None

async def _export_session_to_pdf_async(session: SessionState, filename: str) -> str:
    """
    The core asynchronous function to export the session to PDF using Pyppeteer.
    It renders the full HTML with MathJax in a headless browser and prints to PDF.
    This version uses a temporary file and page.goto for robust resource loading.
    """
    if not PYPPETEER_AVAILABLE:
        return "Error: PDF export is disabled because pyppeteer is not installed."

    logging.info("Starting PDF export process...")
    
    # The HTML generation is correct, no changes needed there.
    html_content = export_session_to_html(session, embed_images_for_pdf=True)
    
    browser = None
    temp_html_path = None
    
    try:
        # 1. Write the self-contained HTML to a temporary file.
        with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.html', encoding='utf-8') as f:
            f.write(html_content)
            temp_html_path = f.name
        
        file_url = pathlib.Path(temp_html_path).as_uri()
        logging.info(f"Generated temporary HTML for rendering: {file_url}")

        executable_path = await find_browser_executable_path()
        args = DEFAULT_ARGS.copy()
        if '--enable-automation' in args:
            args.remove('--enable-automation')
        required_args = ['--no-sandbox', '--disable-setuid-sandbox', '--disable-infobars']
        for arg in required_args:
            if arg not in args:
                args.append(arg)
        
        launch_options = {
            'args': args,
            'handleSIGINT': False,
            'handleSIGTERM': False,
            'handleSIGHUP': False
        }
        if executable_path:
            launch_options['executablePath'] = executable_path

        logging.info("Launching headless browser...")
        browser = await pyppeteer.launch(launch_options)
        page = await browser.newPage()
        await page.setViewport({'width': 1200, 'height': 800})
    
        logging.info("Navigating to temporary HTML file...")
        await page.goto(file_url, waitUntil='networkidle0')

        logging.info("Waiting for MathJax to complete rendering...")
        await page.waitForSelector('body.MathJax_Processed', timeout=60000)
        
        # ----------------------------------------
        
        logging.info("Generating PDF file...")
        await page.pdf({
            'path': filename,
            'format': 'A4',
            'printBackground': True,
            'margin': {'top': '20mm', 'bottom': '20mm', 'left': '20mm', 'right': '20mm'}
        })
        
        logging.info(f"Session successfully exported to PDF: {filename}")
        # Removed asyncio.create_task(_delete_file_after_delay(filename))
        return filename

    except Exception as e:
        logging.error(f"An error occurred during PDF export with Pyppeteer: {e}", exc_info=True)
        error_message = (
            f"Error exporting to PDF: {e}. Ensure Chromium is installed in the deployment "
            "environment or Google Chrome is installed on the local machine."
        )
        return error_message
    
    finally:
        # 4. Clean up everything.
        if browser:
            logging.info("Closing headless browser.")
            await browser.close()
        if temp_html_path and os.path.exists(temp_html_path):
            os.unlink(temp_html_path)
            logging.info("Cleaned up temporary HTML file.")

def export_session_to_pdf(session: SessionState, filename: str = "LearnFlow_Session.pdf") -> str:
    """
    Exports the session to a PDF with perfectly rendered LaTeX.

    This is a synchronous wrapper around the asynchronous Pyppeteer logic,
    making it easy to call from standard synchronous code.
    """
    try:
        # This runs the async function and waits for it to complete.
        result = asyncio.run(_export_session_to_pdf_async(session, filename))
        return result
    except RuntimeError as e:
        if "cannot run loop while another loop is running" in str(e):
             logging.error("Asyncio loop conflict. This can happen in environments like Jupyter. "
                           "Try running 'await _export_session_to_pdf_async(...)' directly.")
             return "Error: Asyncio loop conflict. Cannot generate PDF in this environment."
        else:
             logging.error(f"A runtime error occurred: {e}", exc_info=True)
             return f"Error: A runtime error occurred during PDF export: {e}"
    except Exception as e:
        logging.error(f"An unexpected error occurred in the sync wrapper for PDF export: {e}", exc_info=True)
        return f"An unexpected error occurred: {e}"
