import uvicorn
import os
import sys


def main():
    host = os.environ.get("CT_HOST", "0.0.0.0")
    port = int(os.environ.get("CT_PORT", "8090"))
    debug = os.environ.get("CT_DEBUG", "false").lower() in ("true", "1", "yes")

    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info",
    )


if __name__ == "__main__":
    main()
