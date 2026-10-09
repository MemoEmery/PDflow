def pdf_metadata(doc) -> dict:
    m = doc.metadata or {}
    return {k: (m.get(k) or "")[:120] for k in ("title", "author", "producer", "creationDate") if m.get(k)}
