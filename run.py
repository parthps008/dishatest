import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0" if "PORT" in os.environ else "127.0.0.1"
    print(f"Starting Disha Academy Test Portal on http://{host}:{port}...")
    uvicorn.run("app.main:app", host=host, port=port, reload=False if "PORT" in os.environ else True)
