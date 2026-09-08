def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end == length:
            break
        start = end - overlap

    return chunks