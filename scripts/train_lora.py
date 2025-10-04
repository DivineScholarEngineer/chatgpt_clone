"""Fine-tune gpt-oss-20b with LoRA adapters.

This script wraps the example provided in the prompt and adds a couple of
quality-of-life improvements such as configurable arguments and a
conversation-style prompt builder that matches the chat UI exposed by this
project.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments

from peft import LoraConfig, get_peft_model


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LoRA fine-tuning for gpt-oss-20b")
    parser.add_argument("--model-name", default="openai/gpt-oss-20b", help="Base model to fine-tune")
    parser.add_argument(
        "--dataset",
        default="tatsu-lab/alpaca",
        help="Dataset identifier on the Hugging Face Hub or local path",
    )
    parser.add_argument("--output-dir", default="./gpt-oss-20b-finetuned", help="Directory for trainer output")
    parser.add_argument("--lora-r", type=int, default=16, help="LoRA rank")
    parser.add_argument("--lora-alpha", type=int, default=32, help="LoRA alpha")
    parser.add_argument("--lora-dropout", type=float, default=0.05, help="LoRA dropout")
    parser.add_argument("--learning-rate", type=float, default=2e-4, help="Learning rate")
    parser.add_argument("--batch-size", type=int, default=2, help="Per-device batch size")
    parser.add_argument("--gradient-accumulation", type=int, default=4, help="Gradient accumulation steps")
    parser.add_argument("--max-steps", type=int, default=2000, help="Maximum training steps")
    parser.add_argument("--warmup-steps", type=int, default=50, help="Warmup steps")
    parser.add_argument("--max-seq-length", type=int, default=2048, help="Maximum sequence length")
    parser.add_argument("--load-in-4bit", action="store_true", help="Load model with 4-bit quantisation")
    parser.add_argument(
        "--gradient-checkpointing",
        action="store_true",
        help="Enable gradient checkpointing to save memory",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model_name, use_fast=True)
    model_kwargs = {"device_map": "auto"}
    if args.load_in_4bit:
        model_kwargs["load_in_4bit"] = True
    model = AutoModelForCausalLM.from_pretrained(args.model_name, **model_kwargs)

    if args.gradient_checkpointing:
        model.gradient_checkpointing_enable()

    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        target_modules=["q_proj", "v_proj"],
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)

    dataset = load_dataset(args.dataset)

    def format_example(example):
        # Alpaca-style datasets usually expose instruction / input / output keys
        instruction = example.get("instruction", "")
        input_text = example.get("input", "")
        output_text = example.get("output", "")
        prompt = "User: " + instruction
        if input_text:
            prompt += "\n" + input_text
        prompt += "\nAssistant:"
        completion = output_text
        return {"text": f"{prompt} {completion}"}

    tokenized_dataset = dataset["train"].map(
        format_example,
        remove_columns=dataset["train"].column_names,
    )

    tokenized_dataset = tokenized_dataset.map(
        lambda sample: tokenizer(
            sample["text"],
            truncation=True,
            max_length=args.max_seq_length,
        ),
        batched=True,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation,
        warmup_steps=args.warmup_steps,
        max_steps=args.max_steps,
        learning_rate=args.learning_rate,
        fp16=True,
        logging_steps=10,
        output_dir=str(output_dir),
        save_strategy="steps",
        save_steps=250,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
    )

    trainer.train()

    adapter_dir = output_dir / "lora-adapter"
    adapter_dir.mkdir(exist_ok=True)
    model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)


if __name__ == "__main__":
    main()
