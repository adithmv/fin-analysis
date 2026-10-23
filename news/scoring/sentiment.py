"""Pinned CPU FinBERT; probability labels come from the model, never index assumptions."""

import os

os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")


class Sentiment:
    def __init__(self, config, offline=True):
        import torch
        from transformers import AutoTokenizer, AutoModelForSequenceClassification

        self.config = config
        torch.set_num_threads(min(4, os.cpu_count() or 1))
        self.tokenizer = AutoTokenizer.from_pretrained(
            config["model"], revision=config["revision"], local_files_only=offline, trust_remote_code=False
        )
        self.model = (
            AutoModelForSequenceClassification.from_pretrained(
                config["model"],
                revision=config["revision"],
                local_files_only=offline,
                trust_remote_code=False,
            )
            .to("cpu")
            .eval()
        )
        labels = {int(k): v.lower() for k, v in self.model.config.id2label.items()}
        if set(labels.values()) != {"positive", "negative", "neutral"}:
            raise ValueError("Unexpected FinBERT label map")
        self.labels = labels

    def score(self, texts):
        import torch

        output = []
        for offset in range(0, len(texts), self.config["batch_size"]):
            inputs = self.tokenizer(
                texts[offset : offset + self.config["batch_size"]],
                padding=True,
                truncation=True,
                max_length=min(512, self.config["max_tokens"]),
                return_tensors="pt",
            )
            with torch.inference_mode():
                probabilities = torch.softmax(self.model(**inputs).logits, dim=-1).cpu().tolist()
            output.extend(decode(p, self.labels) for p in probabilities)
        return output


def decode(probabilities, labels):
    probs = {labels[i]: float(p) for i, p in enumerate(probabilities)}
    if abs(sum(probs.values()) - 1) > 1e-5 or any(not 0 <= p <= 1 for p in probs.values()):
        raise ValueError("Invalid sentiment probabilities")
    return dict(
        p_positive=probs["positive"],
        p_negative=probs["negative"],
        p_neutral=probs["neutral"],
        label=max(probs, key=probs.get),
        score=probs["positive"] - probs["negative"],
    )


def english(article):
    text = article["title"] + " " + (article.get("summary") or "")
    if article.get("language", "en") not in ("en", "eng"):
        return False
    letters = [c for c in text if c.isalpha()]
    if not letters or sum("a" <= c.lower() <= "z" for c in letters) / len(letters) < 0.85:
        return False
    from langdetect import detect, DetectorFactory

    DetectorFactory.seed = 0
    try:
        return detect(text) == "en"
    except Exception:
        return False
