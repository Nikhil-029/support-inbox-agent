"""
Loads markdown FAQ/policy docs from knowledge_base/, splits them into
sections, and indexes them with TF-IDF for retrieval.

Deliberately lightweight: at the scale of a few dozen FAQ docs, TF-IDF
retrieval is fast, has zero heavy ML dependencies (no torch/transformers),
and is easy to reason about. A larger, more semantically varied corpus
would be a good reason to swap in neural embeddings instead -- the
`search()` interface below is the only thing a caller depends on, so that
swap wouldn't touch any other file.
"""
import os
import re
from dataclasses import dataclass
from typing import List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

KB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge_base")


@dataclass
class KBSection:
    doc_title: str
    heading: str
    text: str


class KnowledgeBase:
    def __init__(self):
        self.sections: List[KBSection] = []
        self.vectorizer = None
        self.matrix = None

    def build(self):
        self.sections = self._load_and_split()
        if not self.sections:
            raise RuntimeError(
                f"No knowledge base documents found in {KB_DIR}. "
                "Add at least one .md file."
            )

        texts = [f"{s.heading}\n{s.text}" for s in self.sections]
        self.vectorizer = TfidfVectorizer(stop_words="english", max_df=0.9)
        self.matrix = self.vectorizer.fit_transform(texts)

    def _load_and_split(self) -> List[KBSection]:
        sections = []
        if not os.path.isdir(KB_DIR):
            return sections

        for filename in sorted(os.listdir(KB_DIR)):
            if not filename.endswith(".md"):
                continue
            path = os.path.join(KB_DIR, filename)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            doc_title = filename.replace(".md", "").replace("_", " ").title()

            parts = re.split(r"\n(?=## )", content)
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                heading_match = re.match(r"^#+\s*(.+)", part)
                heading = heading_match.group(1).strip() if heading_match else doc_title
                sections.append(KBSection(doc_title=doc_title, heading=heading, text=part))

        return sections

    def search(self, query: str, top_k: int = 3) -> List[KBSection]:
        if self.vectorizer is None:
            raise RuntimeError("Knowledge base not built yet -- call .build() first.")

        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.matrix)[0]
        top_indices = scores.argsort()[::-1][:top_k]

        return [self.sections[i] for i in top_indices if scores[i] > 0]


knowledge_base = KnowledgeBase()
