import json
import os
import csv
import difflib
from http.server import BaseHTTPRequestHandler, HTTPServer

# Attempt to import openai for embedding-based search. If not available or API key
# missing, the application will gracefully fall back to a simple string similarity.
# Load variables from a .env file if present. This allows users to place
# `OPENAI_API_KEY` in a .env file without having to export it manually.
def _load_env_file():
    # Look for .env in the parent directory of this file and in the current
    # working directory. The parent directory search allows placement of
    # .env at the project root when running from drift_chat/.
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'),
        os.path.join(os.getcwd(), '.env'),
    ]
    for env_path in candidates:
        if os.path.exists(env_path):
            try:
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#') or '=' not in line:
                            continue
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        # Do not override existing environment variables
                        if key and key not in os.environ:
                            os.environ[key] = value
            except Exception:
                pass

_load_env_file()

OPENAI_AVAILABLE = False
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
try:
    if OPENAI_API_KEY:
        import openai  # type: ignore
        openai.api_key = OPENAI_API_KEY
        OPENAI_AVAILABLE = True
except Exception:
    # openai library not installed or API key invalid; fallback will be used
    OPENAI_AVAILABLE = False


class DriftChatHandler(BaseHTTPRequestHandler):
    """
    A simple HTTP handler to serve a chat page and accept form submissions.
    This handler supports serving static files (HTML, CSS, JS) from the
    `static` and `templates` directories, and a POST endpoint `/submit`
    to collect lead information from the chat widget. Collected leads are
    appended to an in-memory list `stored_leads` for demonstration purposes.
    """

    # In-memory store for leads (in a real application, this would be a
    # database or external service).
    stored_leads = []

    def _set_headers(self, status_code=200, content_type="text/html; charset=utf-8"):
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        # Allow CORS for local development; in production restrict domains.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        """Handle preflight CORS requests."""
        self._set_headers()

    def do_GET(self):
        """Serve files from the templates and static directories."""
        # Serve the main page at root.
        if self.path == "/" or self.path == "/index.html":
            return self._serve_file(os.path.join("templates", "index.html"), "text/html; charset=utf-8")
        # Serve static assets (JS and CSS).
        if self.path.startswith("/static/"):
            # Remove the leading slash to get the relative path
            rel_path = self.path.lstrip("/")
            # Determine MIME type based on extension
            _, ext = os.path.splitext(rel_path)
            mime_types = {
                ".js": "application/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
            }
            mime_type = mime_types.get(ext, "application/octet-stream")
            return self._serve_file(rel_path, mime_type)

        # Anything else returns 404
        self._set_headers(404)
        self.wfile.write(b"Not Found")

    def _serve_file(self, rel_path, mime_type):
        """Serve a file given its relative path and MIME type."""
        try:
            with open(os.path.join(os.path.dirname(__file__), rel_path), "rb") as f:
                content = f.read()
            self._set_headers(200, mime_type)
            self.wfile.write(content)
        except FileNotFoundError:
            self._set_headers(404)
            self.wfile.write(b"Not Found")

    def do_POST(self):
        """Handle form submission from the chat widget."""
        if self.path == "/submit":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._set_headers(400, "application/json; charset=utf-8")
                response = {"error": "Invalid JSON"}
                self.wfile.write(json.dumps(response).encode('utf-8'))
                return
            # Validate and store data
            required_fields = ["name", "email", "phone", "company", "message"]
            missing = [field for field in required_fields if not data.get(field)]
            if missing:
                self._set_headers(400, "application/json; charset=utf-8")
                response = {"error": f"Missing fields: {', '.join(missing)}"}
                self.wfile.write(json.dumps(response).encode('utf-8'))
                return
            # Append to in-memory store
            self.stored_leads.append(data)
            # Respond with success
            self._set_headers(200, "application/json; charset=utf-8")
            response = {"message": "お問い合わせありがとうございます。担当者よりご連絡いたします。"}
            self.wfile.write(json.dumps(response).encode('utf-8'))
            return
        elif self.path == "/search":
            # Handle question search from chat widget
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._set_headers(400, "application/json; charset=utf-8")
                self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode('utf-8'))
                return
            # Extract question and optional category
            question = data.get('question', '').strip()
            category = data.get('category', None)
            if not question:
                self._set_headers(400, "application/json; charset=utf-8")
                self.wfile.write(json.dumps({"error": "Missing 'question'"}).encode('utf-8'))
                return
            # Find best answer
            answer, found = find_best_answer(question, category)
            self._set_headers(200, "application/json; charset=utf-8")
            self.wfile.write(json.dumps({"answer": answer, "found": found}).encode('utf-8'))
            return
        # Unknown POST path
        self._set_headers(404)
        self.wfile.write(b"Not Found")


# Load Q&A data from CSV once at module import time
QA_DATA: list[dict] = []
QA_FILE = os.path.join(os.path.dirname(__file__), 'qa_data.csv')
if os.path.exists(QA_FILE):
    try:
        with open(QA_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                QA_DATA.append({
                    'question': row.get('質問', '').strip(),
                    'answer': row.get('回答', '').strip(),
                    'category': row.get('対応カテゴリー', '').strip(),
                    'source': row.get('根拠資料', '').strip(),
                    # Placeholder for embedding vector; will be populated if OpenAI available
                    'embedding': None,
                })
    except Exception as e:
        print(f"Error loading QA data: {e}")

# Precompute embeddings for questions if OpenAI is available
if OPENAI_AVAILABLE and QA_DATA:
    try:
        # Gather all question texts
        texts = [entry['question'] for entry in QA_DATA]
        # Call OpenAI embeddings API in one batch to minimize requests
        response = openai.Embedding.create(model="text-embedding-ada-002", input=texts)  # type: ignore
        # Map returned embeddings back to QA_DATA entries
        for i, data in enumerate(response['data']):  # type: ignore
            QA_DATA[i]['embedding'] = data['embedding']
    except Exception as e:
        print(f"Error computing embeddings: {e}")
        OPENAI_AVAILABLE = False


def find_best_answer(user_question: str, selected_category: str | None = None, threshold: float = 0.35):
    """
    Find the most relevant answer for the user's question. The search uses two
    strategies:

    1. If OpenAI embeddings are available and embeddings for QA entries have
       been precomputed, compute an embedding for the user's question and
       measure cosine similarity to each QA entry's embedding. If the highest
       similarity exceeds the threshold, return that answer.
    2. Otherwise, or if no high similarity is found, fall back to a simple
       string similarity (difflib.SequenceMatcher) to find the closest match.

    If `selected_category` is provided, candidate entries are first filtered
    to those whose category contains the selected category. If no confident
    match is found among the filtered entries, the search is repeated across
    all entries.
    Returns (answer, found) where `found` indicates whether a confident match
    was found.
    """

    def cosine_similarity(vec1, vec2):
        # Compute cosine similarity between two numeric vectors
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        return dot / (norm1 * norm2) if norm1 and norm2 else 0.0

    def embedding_search(candidates):
        # Compute embedding for user's question
        try:
            result = openai.Embedding.create(model="text-embedding-ada-002", input=[user_question])  # type: ignore
            question_embedding = result['data'][0]['embedding']  # type: ignore
        except Exception:
            return None, 0.0
        best_score = 0.0
        best_answer = None
        for entry in candidates:
            if not entry.get('embedding'):
                continue
            score = cosine_similarity(question_embedding, entry['embedding'])
            if score > best_score:
                best_score = score
                best_answer = entry['answer']
        return best_answer, best_score

    def simple_search(candidates):
        # Use difflib to find similar question text
        best_score = 0.0
        best_answer = None
        for entry in candidates:
            sim = difflib.SequenceMatcher(None, user_question, entry['question']).ratio()
            if sim > best_score:
                best_score = sim
                best_answer = entry['answer']
        return best_answer, best_score

    # Filter by category if provided
    if selected_category:
        filtered = [e for e in QA_DATA if selected_category in e['category']]
    else:
        filtered = list(QA_DATA)

    # Use embedding search if available
    if OPENAI_AVAILABLE and QA_DATA:
        answer, score = embedding_search(filtered if filtered else QA_DATA)
        # If answer found and above threshold, return
        # For embeddings, use a higher threshold (e.g. 0.8) because similarity is between 0 and 1
        if answer and score >= max(0.8, threshold):
            return answer, True
    # Fallback to simple string similarity search
    answer_simple, score_simple = simple_search(filtered if filtered else QA_DATA)
    if answer_simple and score_simple >= threshold:
        return answer_simple, True
    # If no match above threshold and category was applied, search across all
    if selected_category and filtered and len(filtered) != len(QA_DATA):
        # Attempt embedding search across all
        if OPENAI_AVAILABLE and QA_DATA:
            ans_all, score_all = embedding_search(QA_DATA)
            if ans_all and score_all >= max(0.8, threshold):
                return ans_all, True
        # Otherwise simple search across all
        ans_all_simple, score_all_simple = simple_search(QA_DATA)
        if ans_all_simple and score_all_simple >= threshold:
            return ans_all_simple, True
    # No confident match found
    return None, False



def run(server_class=HTTPServer, handler_class=DriftChatHandler, port=8000):
    """Run the HTTP server."""
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Server started at http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()


if __name__ == '__main__':
    run()