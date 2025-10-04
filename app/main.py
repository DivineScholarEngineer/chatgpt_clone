import os
from pathlib import Path
from threading import Lock
from typing import Generator, List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
except ImportError:  # pragma: no cover - transformers is optional at runtime
    AutoModelForCausalLM = None
    AutoTokenizer = None
    pipeline = None

from . import models, schemas
from .database import SessionLocal, init_db

app = FastAPI(title="ChatGPT Clone")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

_model_lock = Lock()
_generation_pipeline = None


@app.on_event("startup")
def startup_event() -> None:
    init_db()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def load_generation_pipeline():
    global _generation_pipeline
    if _generation_pipeline is None:
        if AutoTokenizer is None or AutoModelForCausalLM is None or pipeline is None:
            raise RuntimeError(
                "transformers must be installed to run generation. "
                "Install with `pip install transformers accelerate bitsandbytes`"
            )
        model_name = os.getenv("MODEL_NAME", "openai/gpt-oss-20b")
        quantization = os.getenv("LOAD_IN_4BIT", "true").lower() == "true"
        tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
        model_kwargs = {"device_map": "auto"}
        if quantization:
            model_kwargs["load_in_4bit"] = True
        model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs)
        _generation_pipeline = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            max_new_tokens=int(os.getenv("MAX_NEW_TOKENS", "512")),
            temperature=float(os.getenv("TEMPERATURE", "0.7")),
            top_p=float(os.getenv("TOP_P", "0.9")),
            do_sample=True,
            return_full_text=False,
        )
    return _generation_pipeline


def build_prompt(messages: List[models.Message]) -> str:
    prompt_parts = []
    for message in messages:
        role = "User" if message.role == "user" else "Assistant"
        prompt_parts.append(f"{role}: {message.content}")
    prompt_parts.append("Assistant:")
    return "\n".join(prompt_parts)


def generate_response(messages: List[models.Message]) -> str:
    prompt = build_prompt(messages)
    try:
        with _model_lock:
            generator = load_generation_pipeline()
            outputs = generator(prompt)
        if outputs and "generated_text" in outputs[0]:
            return outputs[0]["generated_text"].strip() or "(The model returned an empty response.)"
        if outputs and "summary_text" in outputs[0]:
            return outputs[0]["summary_text"].strip() or "(The model returned an empty response.)"
        return "(No response generated.)"
    except RuntimeError:
        # Provide a friendly fallback for environments without transformers
        return (
            "[Model not loaded] Configure the MODEL_NAME environment variable and install "
            "transformers to enable text generation."
        )
    except Exception as exc:  # pragma: no cover - logging placeholder
        return f"An error occurred while generating a response: {exc}"


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/conversations", response_model=List[schemas.Conversation])
def list_conversations(db: Session = Depends(get_db)):
    return db.query(models.Conversation).order_by(models.Conversation.created_at.desc()).all()


@app.get("/conversations/{conversation_id}", response_model=schemas.Conversation)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conversation = db.query(models.Conversation).filter(models.Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.post("/chat", response_model=schemas.CompletionResponse)
def create_completion(payload: schemas.MessageCreate, db: Session = Depends(get_db)):
    conversation: Optional[models.Conversation]
    if payload.conversation_id:
        conversation = (
            db.query(models.Conversation)
            .filter(models.Conversation.id == payload.conversation_id)
            .first()
        )
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = models.Conversation(title=payload.message[:80] or "New chat")
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    user_message = models.Message(
        conversation_id=conversation.id,
        role="user",
        content=payload.message,
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    if payload.attachment_ids:
        attachments = (
            db.query(models.Attachment)
            .filter(models.Attachment.id.in_(payload.attachment_ids))
            .all()
        )
        for attachment in attachments:
            attachment.message_id = user_message.id
        db.commit()

    history = (
        db.query(models.Message)
        .filter(models.Message.conversation_id == conversation.id)
        .order_by(models.Message.created_at.asc())
        .all()
    )
    reply_content = generate_response(history)

    assistant_message = models.Message(
        conversation_id=conversation.id,
        role="assistant",
        content=reply_content,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    conversation = get_conversation(conversation.id, db)  # type: ignore[arg-type]

    return schemas.CompletionResponse(conversation=conversation, reply=assistant_message)


@app.post("/upload", response_model=schemas.Attachment)
def upload_file(
    conversation_id: Optional[int] = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if conversation_id:
        conversation = (
            db.query(models.Conversation)
            .filter(models.Conversation.id == conversation_id)
            .first()
        )
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

    safe_filename = f"{Path(file.filename).stem}_{os.urandom(6).hex()}{Path(file.filename).suffix}"
    file_path = UPLOAD_DIR / safe_filename

    with file_path.open("wb") as buffer:
        buffer.write(file.file.read())

    attachment = models.Attachment(
        message_id=None,  # type: ignore[arg-type]
        filename=f"uploads/{safe_filename}",
        original_name=file.filename,
        mime_type=file.content_type or "application/octet-stream",
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    return attachment


@app.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(attachment_id: int, db: Session = Depends(get_db)):
    attachment = (
        db.query(models.Attachment)
        .filter(models.Attachment.id == attachment_id)
        .first()
    )
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")

    file_path = BASE_DIR / attachment.filename
    if file_path.exists():
        try:
            file_path.unlink()
        except OSError:
            pass

    db.delete(attachment)
    db.commit()
