"""Development entry point.

Run with:  python run.py
  - This computer        :  http://127.0.0.1:5000
  - Other home computers :  http://<this-PC-LAN-IP>:5000   (e.g. http://192.168.0.9:5000)

Env vars (optional):
  HOST         interface to bind   (default 0.0.0.0 = all interfaces, LAN-accessible)
  PORT         port                (default 5000)
  FLASK_DEBUG  "1" to enable the debugger (default off; keep OFF on a shared network)
"""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    # Debugger allows remote code execution — only enable on a trusted/local box.
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)
