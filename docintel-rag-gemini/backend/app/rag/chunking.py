import re
from bisect import bisect_left, bisect_right


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> list[str]:
    """Pack passages at natural breaks and keep overlap on a readable boundary."""
    if chunk_size < 1 or not 0 <= overlap < chunk_size:
        raise ValueError("Expected a positive chunk size and 0 <= overlap < chunk size.")
    text = clean_text(text)
    words = [m.start() for m in re.finditer(r"\S+", text)]
    breaks = [m.end() for m in re.finditer(r"\n\s*|(?<=[.!?])\s+|(?=[•▪◦])", text)]
    chunks = []
    start = last_end = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            # Use the last complete line, bullet, or sentence that fits. A long
            # sentence falls back to a word break, then to a hard cut for one long token.
            for boundaries in (breaks, words):
                index = bisect_right(boundaries, end) - 1
                if index >= 0 and boundaries[index] > last_end:
                    end = boundaries[index]
                    break
        passage = text[start:end].strip()
        if passage:
            chunks.append(passage)
        if end == len(text):
            break

        next_start = end
        earliest = max(start + 1, end - overlap)
        for boundaries in (breaks, words):
            index = bisect_left(boundaries, earliest)
            if index < len(boundaries) and boundaries[index] < end:
                next_start = boundaries[index]
                break
        start, last_end = next_start, end
    return chunks
