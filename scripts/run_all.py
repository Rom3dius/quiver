"""Launch both the Discord bot and C2 web dashboard."""

from __future__ import annotations

import os
import signal
import subprocess
import sys

from quiver.config import load_config
from quiver.logging_config import setup_logging


def main() -> None:
    setup_logging()
    config = load_config()

    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    python = sys.executable

    bot_proc = subprocess.Popen(
        [python, os.path.join(scripts_dir, "run_bot.py")],
        env=os.environ.copy(),
    )
    web_proc = subprocess.Popen(
        [python, os.path.join(scripts_dir, "run_web.py")],
        env=os.environ.copy(),
    )

    print(f"Bot PID: {bot_proc.pid}")
    print(f"Web PID: {web_proc.pid}")
    print(f"Dashboard: http://{config.flask_host}:{config.flask_port}")
    print("Press Ctrl+C to stop both processes.")

    def shutdown(signum, frame):
        print("\nShutting down...")
        bot_proc.terminate()
        web_proc.terminate()
        bot_proc.wait(timeout=10)
        web_proc.wait(timeout=10)
        print("Both processes stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Wait for either process to exit
    while True:
        bot_exit = bot_proc.poll()
        web_exit = web_proc.poll()

        if bot_exit is not None:
            print(f"Bot exited with code {bot_exit}. Stopping web...")
            web_proc.terminate()
            web_proc.wait(timeout=10)
            sys.exit(bot_exit)

        if web_exit is not None:
            print(f"Web exited with code {web_exit}. Stopping bot...")
            bot_proc.terminate()
            bot_proc.wait(timeout=10)
            sys.exit(web_exit)

        try:
            bot_proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass


if __name__ == "__main__":
    main()
