import os
import traceback
import matplotlib.pyplot as plt

def main():
    # Determine mode: "text" for stdout/stderr, "image" for plots/tables
    tool_mode = os.environ.get("TOOL_MODE", "text")  # "text" or "image"

    # Paths
    code_path = os.environ.get("CODE_PATH", "/app/code_to_run.py")
    out_dir = os.environ.get("OUT_DIR", "/out")
    os.makedirs(out_dir, exist_ok=True)

    stdout_file = os.path.join(out_dir, "stdout.txt")
    stderr_file = os.path.join(out_dir, "stderr.txt")
    plots_dir = os.path.join(out_dir, "plots")
    os.makedirs(plots_dir, exist_ok=True)

    # Redirect stdout/stderr for text mode
    if tool_mode == "text":
        with open(stdout_file, "w") as out, open(stderr_file, "w") as err:
            try:
                with open(code_path, "r") as f:
                    code = f.read()
                exec(code, {"__name__": "__main__"})
            except Exception:
                traceback.print_exc(file=err)

    # Image mode: capture plots / tables only
    elif tool_mode == "image":
        try:
            with open(code_path, "r") as f:
                code = f.read()
            exec(code, {"__name__": "__main__"})

            # Save all open matplotlib figures
            for i, fig_num in enumerate(plt.get_fignums(), start=1):
                fig = plt.figure(fig_num)
                fig.savefig(os.path.join(plots_dir, f"plot_{i}.png"))

        except Exception:
            # For image mode, write errors to stdout/stderr as text
            with open(stderr_file, "w") as err:
                traceback.print_exc(file=err)

    # Clean up matplotlib state
    plt.close('all')

if __name__ == "__main__":
    main()
