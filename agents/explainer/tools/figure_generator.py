import tempfile
from typing import Dict, Any
import plotly.graph_objects as go
from llama_index.core.tools import FunctionTool

def make_figure(
    title: str, 
    content: str, 
    chart_type: str, 
    data: Dict[str, Any]
) -> str:
    """Create a Plotly figure based on chart_type and data, save it as a PNG,
    and return the filepath to the generated image.
    
    Args:
        title (str): The main title of the learning unit.
        content (str): The raw content of the learning unit.
        chart_type (str): The type of chart to generate (e.g., "bar_chart", 
                          "line_graph", "pie_chart", "scatter_plot", "histogram").
        data (Dict[str, Any]): A dictionary containing the data for the chart. 
                                Expected keys depend on chart_type:
                                - "bar_chart": {"labels": List[str], "values": List[float], 
                                                "x_label": str, "y_label": str}
                                - "line_graph": {"x": List[float], "y": List[float], 
                                                 "x_label": str, "y_label": str}
                                - "pie_chart": {"sizes": List[float], "labels": List[str]}
                                - "scatter_plot": {"x": List[float], "y": List[float], 
                                                  "x_label": str, "y_label": str}
                                - "histogram": {"values": List[float], "bins": int, 
                                               "x_label": str, "y_label": str}
    Returns:
        str: The filepath to the generated image file.
    """
    fig = go.Figure()
    
    try:
        if chart_type == "bar_chart":
            labels = data.get("labels", [])
            values = data.get("values", [])
            fig.add_trace(go.Bar(x=labels, y=values, marker_color='skyblue'))
            fig.update_layout(title_text=f"Bar Chart for {title}",
                              xaxis_title=data.get("x_label", "Category"),
                              yaxis_title=data.get("y_label", "Value"))
        elif chart_type == "line_graph":
            x = data.get("x", [])
            y = data.get("y", [])
            fig.add_trace(go.Scatter(x=x, y=y, mode='lines+markers', 
                                     marker_color='purple'))
            fig.update_layout(title_text=f"Line Graph for {title}",
                              xaxis_title=data.get("x_label", "X-axis"),
                              yaxis_title=data.get("y_label", "Y-axis"))
        elif chart_type == "pie_chart":
            sizes = data.get("sizes", [])
            labels = data.get("labels", [])
            fig.add_trace(go.Pie(labels=labels, values=sizes, hole=.3))
            fig.update_layout(title_text=f"Pie Chart for {title}")
        elif chart_type == "scatter_plot":
            x = data.get("x", [])
            y = data.get("y", [])
            fig.add_trace(go.Scatter(x=x, y=y, mode='markers', marker_color='red'))
            fig.update_layout(title_text=f"Scatter Plot for {title}",
                              xaxis_title=data.get("x_label", "X-axis"),
                              yaxis_title=data.get("y_label", "Y-axis"))
        elif chart_type == "histogram":
            values = data.get("values", [])
            bins = data.get("bins", 10) 
            fig.add_trace(go.Histogram(x=values, nbinsx=bins, 
                                       marker_color='green'))
            fig.update_layout(title_text=f"Histogram for {title}",
                              xaxis_title=data.get("x_label", "Value"),
                              yaxis_title=data.get("y_label", "Frequency"))
        else:
            # Handle unsupported chart types
            fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode='text', 
                                     text=[f"Figure for {title}", 
                                           f"(Unsupported Chart Type: {chart_type})"], 
                                     textfont_size=12))
            fig.update_layout(xaxis_visible=False, yaxis_visible=False, 
                              title_text=f"Figure for {title}")
            
    except Exception as e:
        fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode='text', 
                                 text=[f"Figure for {title}", 
                                       f"(Error generating figure: {e})"], 
                                 textfont_size=12))
        fig.update_layout(xaxis_visible=False, yaxis_visible=False, 
                          title_text=f"Figure for {title}")

    # Save the figure to a temporary file and return its path
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png', prefix='plotly_figure_')
    fig.write_image(temp_file.name, format='png', width=800, height=500, scale=2)
    temp_file.close()
    
    return temp_file.name

make_figure_tool = FunctionTool.from_defaults(fn=make_figure, name="make_figure")
