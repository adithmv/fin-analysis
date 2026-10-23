import os

os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")


class Embedder:
    def __init__(self, config, offline=True):
        from sentence_transformers import SentenceTransformer

        self.config = config
        self.key = config["model"] + "@" + config["revision"]
        self.model = SentenceTransformer(
            config["model"],
            revision=config["revision"],
            device="cpu",
            local_files_only=offline,
            trust_remote_code=False,
        )
        if self.model.get_sentence_embedding_dimension() != config["dimension"]:
            raise ValueError("Embedding dimensions differ from database configuration")

    def encode(self, texts):
        import numpy as np

        vectors = self.model.encode(texts, batch_size=16, normalize_embeddings=True, show_progress_bar=False)
        if not np.isfinite(vectors).all():
            raise ValueError("Non-finite embedding")
        return vectors.tolist()
