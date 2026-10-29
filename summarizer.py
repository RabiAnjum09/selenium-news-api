import re
from collections import Counter

def summarize(text, max_sentences=4):
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return "No article text was available."

    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [
        s.strip() for s in sentences
        if len(s.strip().split()) >= 6
    ]

    if len(sentences) <= max_sentences:
        return " ".join(sentences) or text[:500]

    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    stop_words = {
        "the", "and", "for", "that", "with", "this",
        "from", "are", "was", "were", "has", "have",
        "had", "will", "into", "its", "their", "they",
        "about", "after", "said", "than", "also"
    }

    frequencies = Counter(
        word for word in words if word not in stop_words
    )

    scored = []
    for index, sentence in enumerate(sentences):
        tokens = re.findall(r"\b[a-zA-Z]{3,}\b",
                            sentence.lower())
        score = sum(frequencies[w] for w in tokens)
        score = score / max(len(tokens), 1)
        scored.append((index, score, sentence))

    selected = sorted(
        scored, key=lambda item: item[1], reverse=True
    )[:max_sentences]

    selected.sort(key=lambda item: item[0])
    return " ".join(item[2] for item in selected)
