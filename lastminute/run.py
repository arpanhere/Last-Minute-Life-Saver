"""
Entry point. Run with:  python run.py
Then open http://127.0.0.1:5000

Optional: set ANTHROPIC_API_KEY (env var or .env file) to turn on real
LLM-powered task breakdown and voice parsing. Without it, the app still
works fully using its built-in rule-based engine.
"""
from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
