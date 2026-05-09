import sys
import traceback
import contextlib
import base64
import io
from io import StringIO
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Biomni Sandbox Executor")

class ExecuteRequest(BaseModel):
    code: str
    reset_namespace: bool = False

class ExecuteResponse(BaseModel):
    stdout: str
    stderr: str
    error: str | None
    success: bool
    plots: list[str] = []

_persistent_namespace = {}
_captured_plots = []

def _capture_matplotlib_plots():
    """Capture any matplotlib plots that might have been generated during execution."""
    global _captured_plots
    try:
        import matplotlib.pyplot as plt

        # Check if there are any active figures
        if plt.get_fignums():
            for fig_num in plt.get_fignums():
                fig = plt.figure(fig_num)

                # Save figure to base64
                buffer = io.BytesIO()
                fig.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
                buffer.seek(0)

                # Convert to base64
                image_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
                plot_data = f"data:image/png;base64,{image_data}"

                # Add to captured plots if not already there
                if plot_data not in _captured_plots:
                    _captured_plots.append(plot_data)

                # Close the figure to free memory
                plt.close(fig)
    except ImportError:
        pass
    except Exception as e:
        print(f"Warning: Could not capture matplotlib plots: {e}")

def _apply_matplotlib_patches():
    """Apply simple monkey patches to matplotlib functions to automatically capture plots."""
    try:
        import matplotlib.pyplot as plt

        if hasattr(plt, "_biomni_patched"):
            return

        original_show = plt.show
        original_savefig = plt.savefig

        def show_with_capture(*args, **kwargs):
            _capture_matplotlib_plots()
            print("Plot generated and displayed")
            return original_show(*args, **kwargs)

        def savefig_with_capture(*args, **kwargs):
            filename = args[0] if args else kwargs.get("fname", "unknown")
            result = original_savefig(*args, **kwargs)
            _capture_matplotlib_plots()
            print(f"Plot saved to: {filename}")
            return result

        plt.show = show_with_capture
        plt.savefig = savefig_with_capture
        plt._biomni_patched = True

    except ImportError:
        pass
    except Exception as e:
        print(f"Warning: Could not apply matplotlib patches: {e}")


@app.post("/execute", response_model=ExecuteResponse)
async def execute_code(req: ExecuteRequest):
    global _persistent_namespace
    global _captured_plots
    
    if req.reset_namespace:
        _persistent_namespace.clear()
        _captured_plots.clear()

    stdout_capture = StringIO()
    stderr_capture = StringIO()
    
    success = True
    error_message = None
    
    try:
        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
            _apply_matplotlib_patches()
            exec(req.code, _persistent_namespace)
            _capture_matplotlib_plots()
    except Exception as e:
        success = False
        error_message = traceback.format_exc()
        
    return ExecuteResponse(
        stdout=stdout_capture.getvalue(),
        stderr=stderr_capture.getvalue(),
        error=error_message,
        success=success,
        plots=_captured_plots.copy()
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8081)
