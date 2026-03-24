"""Cliente HTTP para a API RAG-Z via Gradio (busca em documentos de condomínio).

O RAG-Z expõe endpoints Gradio em /gradio_api/call/{endpoint}.
Padrão de chamada em 2 passos:
  1. POST /gradio_api/call/{endpoint}  {"data": [...]}  → {"event_id": "..."}
  2. GET  /gradio_api/call/{endpoint}/{event_id}         → SSE com resultado
"""

import json
import logging
import re
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


def _gradio_call(endpoint: str, data: list, timeout: float = None) -> list:
    """Executa chamada Gradio em 2 passos e retorna a lista de resultados.

    Args:
        endpoint: Nome do endpoint Gradio (ex: "refresh_dropdown")
        data: Lista de parâmetros posicionais
        timeout: Timeout opcional para a chamada

    Returns:
        Lista de resultados do Gradio

    Raises:
        RuntimeError: Se a chamada falhar
    """
    client = _get_client()
    call_timeout = timeout or Config.RAG_Z_TIMEOUT

    # Passo 1: POST para iniciar a chamada
    r = client.post(
        f"/gradio_api/call/{endpoint}",
        json={"data": data},
        timeout=call_timeout,
    )
    r.raise_for_status()
    event_id = r.json().get("event_id")
    if not event_id:
        raise RuntimeError(f"RAG-Z Gradio: sem event_id para {endpoint}")

    # Passo 2: GET para obter o resultado (SSE stream)
    r2 = client.get(
        f"/gradio_api/call/{endpoint}/{event_id}",
        timeout=call_timeout,
    )
    r2.raise_for_status()

    # Parsear resposta SSE: linhas "event: complete\ndata: [...]"
    result_data = _parse_sse_response(r2.text)
    return result_data


def _parse_sse_response(text: str) -> list:
    """Parseia resposta SSE do Gradio e retorna dados."""
    for line in text.strip().split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            raw = line[6:]
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("RAG-Z: falha ao parsear SSE data: %s", raw[:200])
                return []
    return []


# ──────────────────────────────────────────────
# Funções públicas
# ──────────────────────────────────────────────


def is_available() -> bool:
    """Check if RAG-Z Gradio API is reachable."""
    if not Config.RAG_Z_ENABLED:
        return False
    try:
        result = _gradio_call("get_status", [], timeout=8.0)
        return bool(result)
    except Exception as exc:
        logger.warning("RAG-Z API indisponível: %s", exc)
        return False


def list_contexts() -> list[dict]:
    """Lista contextos de condomínio disponíveis via Gradio refresh_dropdown.

    Returns:
        Lista de dicts: [{"name": "cond_0388"}, ...]
    """
    try:
        result = _gradio_call("refresh_dropdown", [])
        # Resultado é: [{"choices": [["cond_0006", "cond_0006"], ...], "value": "...", "__type__": "update"}]
        if not result:
            return []

        dropdown_data = result[0] if isinstance(result, list) else result
        choices = dropdown_data.get("choices", []) if isinstance(dropdown_data, dict) else []

        # Buscar stats para enriquecer com contagem de docs
        stats_map = _get_all_context_stats()

        contexts = []
        for choice in choices:
            name = choice[0] if isinstance(choice, list) else choice
            ctx = {"name": name}
            if name in stats_map:
                ctx["total_docs"] = stats_map[name].get("docs", 0)
                ctx["total_files"] = stats_map[name].get("files", 0)
            contexts.append(ctx)

        return contexts

    except Exception as exc:
        logger.error("Erro ao listar contextos RAG-Z: %s", exc)
        return []


def _get_all_context_stats() -> dict:
    """Parseia o resultado de get_status para extrair stats por contexto.

    Returns:
        Dict: {"cond_0388": {"docs": 1986, "files": 10}, ...}
    """
    try:
        result = _gradio_call("get_status", [], timeout=10.0)
        if not result:
            return {}

        status_text = result[0] if isinstance(result, list) else str(result)
        if not isinstance(status_text, str):
            return {}

        # Parsear linhas como: "  • cond_0388: 1986 docs, 10 arquivos"
        stats = {}
        for line in status_text.split("\n"):
            match = re.search(r"•\s+(\S+):\s+(\d+)\s+docs?,\s+(\d+)\s+arquivos?", line)
            if match:
                name = match.group(1)
                docs = int(match.group(2))
                files = int(match.group(3))
                stats[name] = {"docs": docs, "files": files}

        return stats

    except Exception as exc:
        logger.warning("Erro ao obter stats RAG-Z: %s", exc)
        return {}


def get_context_stats(context_name: str) -> Optional[dict]:
    """Retorna stats de um contexto específico."""
    try:
        all_stats = _get_all_context_stats()
        if context_name not in all_stats:
            return None

        stats = all_stats[context_name]
        return {
            "name": context_name,
            "total_docs": stats.get("docs", 0),
            "total_files": stats.get("files", 0),
        }
    except Exception as exc:
        logger.error("Erro ao buscar stats do contexto '%s': %s", context_name, exc)
        return None


def query_hierarchical(
    question: str,
    context: str,
    hierarchy_level: Optional[str] = None,
    top_k_per_context: int = 3,
) -> dict:
    """Consulta RAG-Z via Gradio: switch_context → query_rag.

    O RAG-Z Gradio requer que o contexto seja selecionado antes da query.

    Args:
        question: Pergunta em linguagem natural
        context: Nome do contexto (ex: "cond_0388")
        hierarchy_level: Nível hierárquico (não usado no Gradio, mantido por compatibilidade)
        top_k_per_context: Não usado no Gradio, mantido por compatibilidade

    Returns:
        dict: {"answer": str, "sources": list, "contexts_searched": list}
    """
    try:
        # Passo 1: Selecionar contexto
        _gradio_call("switch_context", [context], timeout=10.0)
        logger.info("RAG-Z: contexto selecionado: %s", context)

        # Passo 2: Fazer a query
        llm_choice = "GPT-4o (OpenAI)"
        result = _gradio_call("query_rag", [question, llm_choice], timeout=Config.RAG_Z_TIMEOUT)

        if not result:
            return {"answer": "", "sources": [], "contexts_searched": [context]}

        # Resultado: [resposta_text, fontes_text]
        answer = result[0] if len(result) > 0 else ""
        sources_text = result[1] if len(result) > 1 else ""

        # Parsear fontes
        sources = _parse_sources(sources_text) if sources_text else []

        logger.info(
            "RAG-Z query '%s' no contexto '%s': %d chars resposta, %d fontes",
            question[:50],
            context,
            len(answer) if answer else 0,
            len(sources),
        )

        return {
            "answer": answer or "",
            "sources": sources,
            "contexts_searched": [context],
        }

    except httpx.TimeoutException:
        logger.error("Timeout ao consultar RAG-Z (pergunta: '%s')", question[:80])
        return {"answer": "", "sources": [], "error": "RAG-Z API timeout"}
    except Exception as exc:
        logger.error("Erro ao consultar RAG-Z: %s", exc)
        return {"answer": "", "sources": [], "error": str(exc)}


def _parse_sources(sources_text: str) -> list[dict]:
    """Parseia texto de fontes retornado pelo Gradio query_rag.

    Formato Gradio típico:
        📚 **Fontes consultadas:**

        **[1] nome_arquivo.pdf** (chunk 1/3)
        > conteúdo do trecho...

        **[2] outro_arquivo.pdf** (chunk 2/5)
        > conteúdo...
    """
    if not sources_text or not isinstance(sources_text, str):
        return []

    sources = []
    current_source = {}

    for line in sources_text.split("\n"):
        line = line.strip()

        # Ignorar linhas de cabeçalho
        if not line or "Fontes consultadas" in line:
            continue

        # Detectar nova fonte: **[1] nome_arquivo.pdf** (chunk 1/3)
        header_match = re.search(
            r"\*\*\[(\d+)\]\s+(.+?)\*\*(?:\s*\(chunk\s+(\d+)/(\d+)\))?",
            line,
        )
        if header_match:
            if current_source:
                sources.append(current_source)
            current_source = {
                "file": header_match.group(2).strip(),
                "chunk": f"{header_match.group(3)}/{header_match.group(4)}" if header_match.group(3) else "",
                "content": "",
            }
            continue

        # Acumular conteúdo (linhas > ou texto normal)
        if current_source:
            clean = line.lstrip("> ").strip()
            if clean:
                prev = current_source.get("content", "")
                current_source["content"] = f"{prev}\n{clean}".strip() if prev else clean

    if current_source:
        sources.append(current_source)

    return sources


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
