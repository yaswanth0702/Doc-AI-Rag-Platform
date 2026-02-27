from typing import List, Dict, Any

def format_context(chunks: List[Dict[str, Any]]) -> str:
    lines = []
    for i, c in enumerate(chunks, start=1):
        page = c.get("page")
        page_str = f"p.{page}" if page else "n/a"
        lines.append(
            f"[{i}] source={c.get('source_name')} page={page_str} chunk_id={c.get('chunk_id')}\n"
            f"{c.get('text')}\n"
        )
    return "\n".join(lines)
