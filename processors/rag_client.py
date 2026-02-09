"""Cliente HTTP para a API RAG-Z (busca em documentos de condomínio)."""

import logging
from typing import Optional

import httpx

from config import Config

logger = logging.getLogger(__name__)

_client: Optional[httpx.Client] = None


def _get_client() -> httpx.Client:
    """Lazy-initialize persistent httpx client with connection pooling."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(
            base_url=Config.RAG_Z_API_URL,
            timeout=httpx.Timeout(Config.RAG_Z_TIMEOUT),
            headers={"Content-Type": "application/json"},
        )
    return _client


def is_available() -> bool:
    """Check if RAG-Z API is reachable."""
    if not Config.RAG_Z_ENABLED:
        return False
    try:
        r = _get_client().get("/health", timeout=5.0)
        return r.status_code == 200
    except Exception as exc:
        logger.warning("RAG-Z API indisponível: %s", exc)
        return False


def list_contexts() -> list[dict]:
    """GET /api/contexts — lista contextos de condomínio disponíveis."""
    try:
        r = _get_client().get("/api/contexts")
        r.raise_for_status()
        data = r.json()
        return data.get("contexts", [])
    except Exception as exc:
        logger.error("Erro ao listar contextos RAG-Z: %s", exc)
        return []


def get_context_stats(context_name: str) -> Optional[dict]:
    """GET /api/contexts/{name}/stats — stats de um contexto."""
    try:
        r = _get_client().get(f"/api/contexts/{context_name}/stats")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logger.error("Erro ao buscar stats do contexto '%s': %s", context_name, exc)
        return None


def query_hierarchical(
    question: str,
    context: str,
    hierarchy_level: Optional[str] = None,
    top_k_per_context: int = 3,
) -> dict:
    """POST /api/query/hierarchical — busca hierárquica em documentos do condomínio.

    Cascata: Docs do condomínio → Lei de Condomínios → Código Civil.
    """
    payload = {
        "question": question,
        "context": context,
        "llm_provider": "openai",
        "embedding_provider": "ollama",
        "top_k_per_context": top_k_per_context,
        "return_sources": True,
        "show_source": True,
        "fluent_mode": True,
        "is_authenticated": True,
        "strict_hierarchy": False,
    }

    if hierarchy_level:
        payload["hierarchy_level"] = hierarchy_level

    try:
        r = _get_client().post("/api/query/hierarchical", json=payload)
        r.raise_for_status()
        return r.json()
    except httpx.TimeoutException:
        logger.error("Timeout ao consultar RAG-Z (pergunta: '%s')", question[:80])
        return {"answer": "", "sources": [], "error": "RAG-Z API timeout"}
    except Exception as exc:
        logger.error("Erro ao consultar RAG-Z: %s", exc)
        return {"answer": "", "sources": [], "error": str(exc)}


def format_rag_result_for_llm(result: dict) -> str:
    """Formata resultado RAG-Z como bloco de texto para tool response do LLM."""
    parts = []

    answer = result.get("answer", "")
    if answer:
        parts.append(f"Resposta encontrada:\n{answer}")

    sources = result.get("sources", [])
    if sources:
        parts.append("\nFontes documentais:")
        for i, src in enumerate(sources, 1):
            file_name = src.get("file", "desconhecido")
            chunk_info = src.get("chunk", "")
            content = src.get("content", "")
            parts.append(f"  [{i}] Arquivo: {file_name} (trecho {chunk_info})")
            if content:
                truncated = content[:500] + "..." if len(content) > 500 else content
                parts.append(f"      Conteúdo: {truncated}")

    contexts_searched = result.get("contexts_searched", [])
    if contexts_searched:
        parts.append(f"\nContextos pesquisados: {', '.join(contexts_searched)}")

    if result.get("error"):
        parts.append(f"\n[AVISO: {result['error']}]")

    if not parts:
        return "Nenhuma informação relevante encontrada nos documentos do condomínio."

    return "\n".join(parts)
