# ChatGPT Clone

A minimal self-hosted ChatGPT-style interface backed by Django, SQLite, and an optional Hugging Face transformers text-generation pipeline. The project includes:

- ✅ A ChatGPT-inspired web UI with conversation history, file uploads, and attachment previews.
- ✅ A Django backend that stores conversations/messages/attachments in SQLite.
- ✅ REST endpoints for chatting, managing conversations, and uploading or deleting attachments.
- ✅ A LoRA training script for `openai/gpt-oss-20b` that mirrors the configuration provided in the prompt but is fully configurable via CLI flags.

> **Note:** The default backend response is a placeholder until a transformer model is configured. Install `transformers`, `accelerate`, and `bitsandbytes`, then export `MODEL_NAME=openai/gpt-oss-20b` (or another compatible model) to enable generation.

## Getting started

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Apply migrations and launch the development server

```bash
python manage.py migrate
python manage.py runserver
```

The UI is served at [http://localhost:8000](http://localhost:8000). Conversations are persisted to `db.sqlite3` in the project root.

### 3. Configure a model (optional)

If `transformers` is installed, you can configure the inference model via environment variables:

```bash
export MODEL_NAME="openai/gpt-oss-20b"
export LOAD_IN_4BIT=true  # optional
export MAX_NEW_TOKENS=512
export TEMPERATURE=0.7
export TOP_P=0.9
```

The first request will lazily download and load the model.

### REST endpoints

| Method | Path                       | Description |
| ------ | -------------------------- | ----------- |
| `GET`  | `/`                        | Serve the ChatGPT clone UI |
| `GET`  | `/conversations`           | List saved conversations |
| `GET`  | `/conversations/{id}`      | Retrieve a single conversation with messages |
| `POST` | `/chat`                    | Submit a message and receive the assistant reply |
| `POST` | `/upload`                  | Upload a file attachment (optionally bound to a conversation) |
| `DELETE` | `/attachments/{id}`      | Delete an attachment and its stored file |

### Fine-tuning with LoRA

The `scripts/train_lora.py` module can fine-tune `openai/gpt-oss-20b` (or any compatible causal LM) using the Alpaca-style dataset specified in the prompt.

Example invocation mirroring the original parameters:

```bash
python scripts/train_lora.py \
  --model-name openai/gpt-oss-20b \
  --dataset tatsu-lab/alpaca \
  --load-in-4bit \
  --batch-size 2 \
  --gradient-accumulation 4 \
  --warmup-steps 50 \
  --max-steps 2000 \
  --learning-rate 2e-4
```

The resulting LoRA adapter weights and tokenizer are stored in `gpt-oss-20b-finetuned/lora-adapter`.

## Project structure

```
app/
  admin.py        # Django admin registrations
  apps.py         # App configuration
  generation.py   # Text generation helpers
  models.py       # Django ORM models
  urls.py         # Application URL routes
  views.py        # HTML + JSON endpoints
config/
  settings.py     # Django project settings
  urls.py         # URL configuration
  wsgi.py         # WSGI entrypoint
  asgi.py         # ASGI entrypoint
scripts/
  train_lora.py   # LoRA fine-tuning script
static/
  app.js          # Frontend behaviour
  style.css       # ChatGPT-inspired styling
templates/
  index.html      # UI shell
uploads/           # Stored files (gitignored)
db.sqlite3         # SQLite database (created at runtime)
```

## Requirements

See [`requirements.txt`](requirements.txt) for the complete list. At a minimum you will need:

- Django
- (Optional) transformers, accelerate, bitsandbytes, datasets, peft for model loading and fine-tuning

Enjoy customising the clone! Feel free to adapt the UI, hook up a different model, or extend the database schema as needed.
