#!/usr/bin/env python3
"""Build the Workbench-ready AIOps training notebook."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path


def markdown(source: str) -> dict:
    text = textwrap.dedent(source).strip()
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": text.splitlines(keepends=True),
    }


def code(source: str) -> dict:
    text = textwrap.dedent(source).strip()
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.splitlines(keepends=True),
    }


cells = [
    markdown(
        """
        # OpenShift AIOps Gemma3 12B QLoRA SFT

        이 노트북은 Workbench에서 바로 실행하는 학습용입니다.

        - 학습 방식: SFT(Supervised Fine-Tuning)
        - 파라미터 효율 방식: PEFT LoRA
        - 메모리 절감 방식: 4bit QLoRA 로딩
        - 학습 데이터: `~/aiops-gemma3/data/aiops_train.jsonl`
        - 학습 중 검증 데이터: `~/aiops-gemma3/data/aiops_eval.jsonl`
        - 최종 holdout 평가 데이터: `~/aiops-gemma3/data/aiops_gold.jsonl`

        SFT와 LoRA는 경쟁 선택지가 아닙니다. 여기서는 SFTTrainer로 instruction/chat 형식 학습을 수행하고, 12B 모델 전체를 full fine-tuning하지 않기 위해 PEFT LoRA adapter만 학습합니다.
        """
    ),
    code(
        """
        import shutil
        from pathlib import Path

        total, used, free = shutil.disk_usage(str(Path.home()))
        print("total GiB:", round(total / 1024**3, 2))
        print("used GiB:", round(used / 1024**3, 2))
        print("free GiB:", round(free / 1024**3, 2))
        """
    ),
    code(
        """
        import torch

        print("cuda available:", torch.cuda.is_available())
        if torch.cuda.is_available():
            print("gpu:", torch.cuda.get_device_name(0))
            print("capability:", torch.cuda.get_device_capability(0))
        """
    ),
    markdown("## 1. Package Install"),
    code("%pip install peft trl bitsandbytes sentencepiece"),
    code(
        """
        import torch
        import transformers
        import datasets
        import peft
        import trl
        import bitsandbytes as bnb

        print("torch:", torch.__version__)
        print("cuda:", torch.cuda.is_available())
        if torch.cuda.is_available():
            print("gpu:", torch.cuda.get_device_name(0))
        print("transformers:", transformers.__version__)
        print("datasets:", datasets.__version__)
        print("peft:", peft.__version__)
        print("trl:", trl.__version__)
        """
    ),
    markdown("## 2. Model Download From MinIO"),
    code(
        """
        from pathlib import Path
        import boto3
        from botocore.client import Config

        endpoint = "http://minio.minio.svc.cluster.local:9000"
        access_key = "admin"
        secret_key = "admin123"
        bucket = "rhoai-models"
        prefix = "gemma-3-12b-it/"

        local_dir = Path.home() / "aiops-gemma3/models/gemma-3-12b-it"
        local_dir.mkdir(parents=True, exist_ok=True)

        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )

        count = 0
        total_bytes = 0

        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                size = obj["Size"]

                if key.endswith("/"):
                    continue

                rel = key[len(prefix):]
                target = local_dir / rel
                target.parent.mkdir(parents=True, exist_ok=True)

                if target.exists() and target.stat().st_size == size and size > 0:
                    print(f"skip existing {key} ({size / 1024**3:.2f} GiB)")
                else:
                    print(f"download {key} ({size / 1024**3:.2f} GiB)")
                    s3.download_file(bucket, key, str(target))

                count += 1
                total_bytes += size

        print("files:", count)
        print("remote size GiB:", round(total_bytes / 1024**3, 2))
        print("local:", local_dir)
        """
    ),
    code(
        """
        from pathlib import Path

        model_dir = Path.home() / "aiops-gemma3/models/gemma-3-12b-it"

        for p in sorted(model_dir.iterdir()):
            if p.is_file():
                print(p.name, round(p.stat().st_size / 1024**2, 2), "MiB")

        zero_files = [p for p in model_dir.rglob("*") if p.is_file() and p.stat().st_size == 0]
        if zero_files:
            raise RuntimeError(f"zero-byte model files found: {zero_files}")
        print("zero files: none")
        """
    ),
    markdown("## 3. Dataset Check"),
    code(
        """
        from pathlib import Path

        base = Path.home() / "aiops-gemma3"
        data_dir = base / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        train_path = data_dir / "aiops_train.jsonl"
        eval_path = data_dir / "aiops_eval.jsonl"
        eval_typo_path = data_dir / "aiops_eval.josnl"
        gold_path = data_dir / "aiops_gold.jsonl"

        if not eval_path.exists() and eval_typo_path.exists():
            print("using fallback eval path:", eval_typo_path)
            eval_path = eval_typo_path

        print("train:", train_path)
        print("eval:", eval_path)
        print("gold:", gold_path)
        """
    ),
    code(
        """
        import json
        from collections import Counter

        required_sections = [
            "[진단]",
            "[근거]",
            "[확인 명령어]",
            "[조치 방향]",
            "[주의사항]",
            "[추가 확인질문]",
        ]

        def validate_messages_file(path, expected_min):
            count = 0
            section_misses = Counter()
            with open(path, "r", encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    if not line.strip():
                        continue
                    obj = json.loads(line)
                    assert list(obj.keys()) == ["messages"], f"{path.name}:{i} must be messages-only"
                    assert len(obj["messages"]) == 3, f"{path.name}:{i} messages length"
                    roles = [m["role"] for m in obj["messages"]]
                    assert roles == ["system", "user", "assistant"], f"{path.name}:{i} roles={roles}"
                    assistant = obj["messages"][2]["content"]
                    for section in required_sections:
                        if section not in assistant:
                            section_misses[section] += 1
                    count += 1
            assert count >= expected_min, f"{path.name} count too small: {count}"
            assert not section_misses, f"{path.name} missing sections: {section_misses}"
            return count

        counts = {
            "train": validate_messages_file(train_path, 10_000),
            "eval": validate_messages_file(eval_path, 1_111),
            "gold": validate_messages_file(gold_path, 150),
        }
        print(counts)
        """
    ),
    markdown("## 4. Load Dataset And Tokenizer"),
    code(
        """
        from datasets import load_dataset
        from transformers import AutoTokenizer

        model_dir = base / "models/gemma-3-12b-it"
        tokenizer = AutoTokenizer.from_pretrained(str(model_dir))

        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        dataset = load_dataset(
            "json",
            data_files={
                "train": str(train_path),
                "eval": str(eval_path),
                "gold": str(gold_path),
            },
        )

        def to_text(example):
            return {
                "text": tokenizer.apply_chat_template(
                    example["messages"],
                    tokenize=False,
                    add_generation_prompt=False,
                )
            }

        text_dataset = dataset.map(to_text, remove_columns=dataset["train"].column_names)
        print(text_dataset)
        print(text_dataset["train"][0]["text"][:1000])
        """
    ),
    markdown("## 5. Load Base Model In 4bit"),
    code(
        """
        import torch
        from transformers import AutoModelForCausalLM, BitsAndBytesConfig

        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )

        model = AutoModelForCausalLM.from_pretrained(
            str(model_dir),
            quantization_config=bnb_config,
            device_map="auto",
            torch_dtype=torch.bfloat16,
        )

        model.config.use_cache = False
        print("loaded")
        print("device:", model.device)
        print("cuda memory allocated GiB:", round(torch.cuda.memory_allocated() / 1024**3, 2))
        print("cuda memory reserved GiB:", round(torch.cuda.memory_reserved() / 1024**3, 2))
        """
    ),
    markdown("## 6. Base Model Smoke Test"),
    code(
        """
        def generate_answer(active_model, user_text, max_new_tokens=768):
            messages = [{"role": "user", "content": user_text}]
            prompt = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
            inputs = tokenizer(prompt, return_tensors="pt").to(active_model.device)
            with torch.no_grad():
                output = active_model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=False,
                    pad_token_id=tokenizer.eos_token_id,
                )
            return tokenizer.decode(
                output[0][inputs["input_ids"].shape[-1]:],
                skip_special_tokens=True,
            )

        smoke_prompt = '''Route 503입니다. namespace=app-test
        Service endpoints는 <none>이고, Pod는 Running 1/1입니다.
        Service selector는 app=web이고, Pod label은 app=web-v2입니다.
        원인과 확인 명령어를 알려주세요.'''

        print(generate_answer(model, smoke_prompt))
        """
    ),
    markdown("## 7. PEFT LoRA Configuration"),
    code(
        """
        from peft import LoraConfig, prepare_model_for_kbit_training

        # Keep gradient checkpointing disabled for stable restart/retrain behavior.
        model.config.use_cache = False
        model = prepare_model_for_kbit_training(
            model,
            use_gradient_checkpointing=False,
        )

        lora_config = LoraConfig(
            r=64,
            lora_alpha=128,
            lora_dropout=0.05,
            target_modules=[
                "q_proj", "k_proj", "v_proj", "o_proj",
                "gate_proj", "up_proj", "down_proj",
            ],
            task_type="CAUSAL_LM",
        )

        print(lora_config)
        """
    ),
    markdown("## 8. SFT Training"),
    code(
        """
        import json
        from pathlib import Path
        from transformers import TrainerCallback, EarlyStoppingCallback
        from trl import SFTTrainer, SFTConfig

        output_dir = str(base / "outputs/gemma3-12b-aiops-lora-v2")
        train_logs = []

        class MetricsCallback(TrainerCallback):
            def on_log(self, args, state, control, logs=None, **kwargs):
                if logs:
                    row = dict(logs)
                    row["step"] = state.global_step
                    train_logs.append(row)
                    if "eval_loss" in row or state.global_step % 100 == 0:
                        print(row)

            def on_train_end(self, args, state, control, **kwargs):
                log_path = Path(args.output_dir) / "trainer_logs.jsonl"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(log_path, "w", encoding="utf-8") as f:
                    for row in train_logs:
                        f.write(json.dumps(row, ensure_ascii=False) + "\\n")
                print("saved logs:", log_path)

        args = SFTConfig(
            output_dir=output_dir,
            max_length=4096,
            per_device_train_batch_size=1,
            per_device_eval_batch_size=1,
            gradient_accumulation_steps=8,
            learning_rate=5e-5,
            num_train_epochs=3,
            lr_scheduler_type="cosine",
            warmup_steps=100,
            logging_steps=10,
            gradient_checkpointing=False,
            eval_strategy="steps",
            eval_steps=100,
            save_strategy="steps",
            save_steps=100,
            save_total_limit=8,
            load_best_model_at_end=True,
            metric_for_best_model="eval_loss",
            greater_is_better=False,
            bf16=True,
            report_to="none",
            packing=False,
        )

        trainer = SFTTrainer(
            model=model,
            args=args,
            train_dataset=text_dataset["train"],
            eval_dataset=text_dataset["eval"],
            processing_class=tokenizer,
            peft_config=lora_config,
            callbacks=[
                MetricsCallback(),
                EarlyStoppingCallback(early_stopping_patience=5),
            ],
        )

        trainer.train()
        best_checkpoint = trainer.state.best_model_checkpoint
        print("best checkpoint:", best_checkpoint)
        print("best eval loss:", trainer.state.best_metric)

        # With load_best_model_at_end=True, trainer.model is restored to the best checkpoint.
        trainer.save_model(output_dir)
        tokenizer.save_pretrained(output_dir)
        print("saved best adapter:", output_dir)
        """
    ),
    markdown("## 9. Evaluation Metrics And Loss Graphs"),
    code(
        """
        metrics = trainer.evaluate()
        print(metrics)
        """
    ),
    code(
        """
        import json
        from pathlib import Path
        import pandas as pd
        import matplotlib.pyplot as plt

        output_path = Path(output_dir)
        log_path = output_path / "trainer_logs.jsonl"

        rows = []
        if log_path.exists():
            with open(log_path, "r", encoding="utf-8") as f:
                rows = [json.loads(line) for line in f if line.strip()]
        else:
            rows = train_logs

        df = pd.DataFrame(rows)
        display(df)

        def save_metric_plot(df, metric, filename, title=None, smooth_window=5):
            if metric not in df.columns:
                print(f"skip: {metric} not logged")
                return None
            sub = df[["step", metric]].dropna()
            if sub.empty:
                print(f"skip: {metric} empty")
                return None
            sub["smoothed"] = sub[metric].rolling(smooth_window, min_periods=1).mean()
            plt.figure(figsize=(9, 5))
            plt.plot(sub["step"], sub[metric], alpha=0.35, label="original")
            plt.plot(sub["step"], sub["smoothed"], linewidth=2, label="smoothed")
            plt.xlabel("step")
            plt.ylabel(metric)
            plt.title(title or metric)
            plt.grid(True)
            plt.legend()
            target = output_path / filename
            plt.savefig(target, dpi=140, bbox_inches="tight")
            plt.show()
            print("saved:", target)
            return target

        save_metric_plot(df, "loss", "loss_graph.png", "training loss")
        save_metric_plot(df, "eval_loss", "eval_loss_graph.png", "eval loss")
        save_metric_plot(df, "mean_token_accuracy", "mean_token_accuracy_graph.png", "mean token accuracy")
        save_metric_plot(df, "grad_norm", "grad_norm_graph.png", "gradient norm")
        save_metric_plot(df, "learning_rate", "learning_rate_graph.png", "learning rate")
        """
    ),
    markdown("## 10. Gold Set Generation Test"),
    code(
        """
        import random
        from pathlib import Path

        sample_count = min(12, len(dataset["gold"]))
        sample_indices = random.Random(42).sample(range(len(dataset["gold"])), sample_count)

        report_path = Path(output_dir) / "sample_outputs.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("# Gold Sample Outputs\\n\\n")
            for idx in sample_indices:
                item = dataset["gold"][idx]
                user_text = item["messages"][1]["content"]
                expected = item["messages"][2]["content"]
                generated = generate_answer(model, user_text, max_new_tokens=1024)

                f.write(f"## Sample {idx}\\n\\n")
                f.write("### User\\n\\n")
                f.write(user_text + "\\n\\n")
                f.write("### Expected\\n\\n")
                f.write(expected + "\\n\\n")
                f.write("### Generated\\n\\n")
                f.write(generated + "\\n\\n")
                f.write("---\\n\\n")

        print("saved:", report_path)
        """
    ),
    markdown("## 11. Simple Rule-Based Gold Score"),
    code(
        """
        import re
        import json
        from pathlib import Path

        required_sections = ["[진단]", "[근거]", "[확인 명령어]", "[조치 방향]", "[주의사항]", "[추가 확인질문]"]
        dangerous = re.compile(r"\\boc\\s+(delete|patch|scale)\\b|\\boc\\s+rollout\\s+restart\\b")
        oc_namespaced = re.compile(r"^\\s*oc\\s+.+(\\s-n\\s+\\S+|\\s--namespace(?:=|\\s+)\\S+)", re.MULTILINE)

        def simple_score(answer):
            structure = 3 if all(section in answer for section in required_sections) else 0
            command = 3 if oc_namespaced.search(answer) else (1 if "oc " in answer else 0)
            safety = 1 if dangerous.search(answer) else 3
            evidence = min(3, sum(token in answer for token in ["spec.", "metadata.", "status.", "selector", "labels", "secretKeyRef", "targetPort", "conditions"]))
            cause = 2 if "[진단]" in answer else 0
            total = structure + command + safety + evidence + cause
            return {"structure": structure, "command": command, "safety": safety, "evidence": evidence, "cause": cause, "total": total}

        scored = []
        for idx in sample_indices:
            item = dataset["gold"][idx]
            generated = generate_answer(model, item["messages"][1]["content"], max_new_tokens=1024)
            row = {"sample_index": idx, **simple_score(generated)}
            scored.append(row)

        metric_report = Path(output_dir) / "metric_report.md"
        avg_total = sum(row["total"] for row in scored) / len(scored)
        with open(metric_report, "w", encoding="utf-8") as f:
            f.write("# Metric Report\\n\\n")
            f.write(f"- gold sample subset: {len(scored)}\\n")
            f.write(f"- average simple score: {avg_total:.2f} / 15\\n\\n")
            f.write("| Sample | Total | Structure | Evidence | Command | Safety |\\n")
            f.write("|---:|---:|---:|---:|---:|---:|\\n")
            for row in scored:
                f.write(f"| {row['sample_index']} | {row['total']} | {row['structure']} | {row['evidence']} | {row['command']} | {row['safety']} |\\n")

        print("saved:", metric_report)
        print("avg_total:", avg_total)
        """
    ),
    markdown(
        """
        ## 12. Package And Upload Adapter To MinIO

        학습 완료 후 Lightspeed 적용을 위해 LoRA adapter 산출물을 tar.gz로 묶고 MinIO에 업로드합니다.
        """
    ),
    code(
        """
        import tarfile
        from pathlib import Path

        adapter_dir = Path(output_dir)
        archive_path = adapter_dir.parent / f"{adapter_dir.name}.tar.gz"

        required_adapter_files = [
            adapter_dir / "adapter_config.json",
            adapter_dir / "adapter_model.safetensors",
        ]
        missing = [p for p in required_adapter_files if not p.exists()]
        if missing:
            raise FileNotFoundError(f"adapter files missing: {missing}")

        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(adapter_dir, arcname=adapter_dir.name)

        print("packaged:", archive_path)
        print("size MiB:", round(archive_path.stat().st_size / 1024**2, 2))
        """
    ),
    code(
        """
        import boto3
        from botocore.client import Config

        endpoint = "http://minio.minio.svc.cluster.local:9000"
        access_key = "admin"
        secret_key = "admin123"
        bucket = "rhoai-models"
        adapter_prefix = "aiops-adapters/gemma3-12b-aiops-lora-v2"

        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )

        archive_key = f"{adapter_prefix}/{archive_path.name}"
        s3.upload_file(str(archive_path), bucket, archive_key)
        print("uploaded:", f"s3://{bucket}/{archive_key}")

        for path in sorted(adapter_dir.rglob("*")):
            if path.is_file():
                rel = path.relative_to(adapter_dir)
                key = f"{adapter_prefix}/{adapter_dir.name}/{rel.as_posix()}"
                s3.upload_file(str(path), bucket, key)
        print("uploaded adapter directory prefix:", f"s3://{bucket}/{adapter_prefix}/{adapter_dir.name}/")
        """
    ),
    code(
        """
        # Optional restore/download check. Use this when another notebook or Lightspeed prep job
        # needs to pull the adapter back from MinIO.
        restore_dir = base / "outputs/restored-adapters"
        restore_dir.mkdir(parents=True, exist_ok=True)
        restored_archive = restore_dir / archive_path.name

        s3.download_file(bucket, archive_key, str(restored_archive))
        print("downloaded:", restored_archive)
        print("downloaded size MiB:", round(restored_archive.stat().st_size / 1024**2, 2))
        """
    ),
    markdown(
        """
        ## Output Files

        학습이 끝나면 기본 산출물은 `~/aiops-gemma3/outputs/gemma3-12b-aiops-lora-v2` 아래에 생성됩니다.

        - `adapter_config.json`
        - `adapter_model.safetensors`
        - tokenizer files
        - `trainer_logs.jsonl`
        - `loss_graph.png`
        - `eval_loss_graph.png`
        - `mean_token_accuracy_graph.png`
        - `grad_norm_graph.png`
        - `learning_rate_graph.png`
        - `sample_outputs.md`
        - `metric_report.md`
        - `../gemma3-12b-aiops-lora-v2.tar.gz`
        - MinIO upload prefix: `s3://rhoai-models/aiops-adapters/gemma3-12b-aiops-lora-v2/`
        """
    ),
]

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3.12",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "codemirror_mode": {"name": "ipython", "version": 3},
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.12.13",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

Path("notebooks/aiops_training.ipynb").write_text(
    json.dumps(notebook, ensure_ascii=False, indent=1) + "\n",
    encoding="utf-8",
)
print("wrote notebooks/aiops_training.ipynb")
