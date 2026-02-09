#!/bin/bash
# ============================================================
# RAG-Z API - Testes via cURL
# ============================================================
# Uso: bash test_api_curl.sh
# Ou execute cada bloco individualmente no terminal.
#
# Configuracao:
#   BASE_URL - Endereco da API (padrao: http://192.168.0.74:8000)
# mas tem coisas que conectam direto no gradio http://192.168.0.74:7862
# ============================================================

BASE_URL="${RAG_API_URL:-http://192.168.0.74:8000}"

echo "============================================"
echo " RAG-Z API - Testes cURL"
echo " Base URL: $BASE_URL"
echo "============================================"
echo ""

# ------------------------------------------------------------
# 1. ROOT - Info basica da API
# ------------------------------------------------------------
echo ">>> 1. GET / (Root)"
curl -s "$BASE_URL/" | python -m json.tool
echo ""
echo "--------------------------------------------"

# ------------------------------------------------------------
# 2. HEALTH CHECK
# ------------------------------------------------------------
echo ">>> 2. GET /health"
curl -s "$BASE_URL/health" | python -m json.tool
echo ""
echo "--------------------------------------------"

# ------------------------------------------------------------
# 3. LISTAR CONTEXTOS
# ------------------------------------------------------------
echo ">>> 3. GET /api/contexts"
curl -s "$BASE_URL/api/contexts" | python -m json.tool
echo ""
echo "--------------------------------------------"

# ------------------------------------------------------------
# 4. CRIAR CONTEXTO
# ------------------------------------------------------------
echo ">>> 4. POST /api/contexts (criar contexto de teste)"
curl -s -X POST "$BASE_URL/api/contexts" \
  -H "Content-Type: application/json" \
  -d '{"name": "teste_curl"}' | python -m json.tool
echo ""
echo "--------------------------------------------"

# ------------------------------------------------------------
# 5. ESTATISTICAS DE CONTEXTO
# ------------------------------------------------------------
echo ">>> 5. GET /api/contexts/teste_curl/stats"
curl -s "$BASE_URL/api/contexts/teste_curl/stats" | python -m json.tool
echo ""
echo "--------------------------------------------"

# ------------------------------------------------------------
# 6. INDEXAR DOCUMENTOS
# Descomente e ajuste o caminho do arquivo para testar
# ------------------------------------------------------------
echo ">>> 6. POST /api/index (indexar documento)"
echo "    [SKIP] Descomente a linha abaixo e ajuste o caminho do arquivo"
# curl -s -X POST "$BASE_URL/api/index" \
#   -F "files=@/caminho/para/documento.pdf" \
#   -F "context=teste_curl" \
#   -F "embedding_provider=ollama" \
#   -F "hierarchy_level=regimento_interno" | python -m json.tool
echo ""
echo "--------------------------------------------"

# ------------------------------------------------------------
# 7. QUERY SIMPLES
# ------------------------------------------------------------
echo ">>> 7. POST /api/query (consulta simples)"
curl -s -X POST "$BASE_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Quais sao as regras do condominio?",
    "context": "default",
    "llm_provider": "openai",
    "embedding_provider": "ollama",
    "top_k": 5,
    "return_sources": true,
    "fluent_mode": true,
    "show_source": false
  }' | python -m json.tool
echo ""
echo "--------------------------------------------"

# ------------------------------------------------------------
# 8. QUERY HIERARQUICA (principal para chatbots)
# ------------------------------------------------------------
echo ">>> 8. POST /api/query/hierarchical (consulta hierarquica)"
curl -s -X POST "$BASE_URL/api/query/hierarchical" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Posso ter cachorro no condominio?",
    "context": "zangari_website",
    "llm_provider": "openai",
    "embedding_provider": "ollama",
    "top_k_per_context": 3,
    "return_sources": true,
    "show_source": true,
    "fluent_mode": true,
    "is_authenticated": false,
    "is_admin": false
  }' | python -m json.tool
echo ""
echo "--------------------------------------------"

# ------------------------------------------------------------
# 9. QUERY HIERARQUICA - Com historico de conversa
# ------------------------------------------------------------
echo ">>> 9. POST /api/query/hierarchical (com historico)"
curl -s -X POST "$BASE_URL/api/query/hierarchical" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "E gatos, pode?",
    "context": "zangari_website",
    "llm_provider": "openai",
    "embedding_provider": "ollama",
    "top_k_per_context": 3,
    "return_sources": true,
    "fluent_mode": true,
    "conversation_history": [
      {"role": "user", "content": "Posso ter cachorro no condominio?"},
      {"role": "assistant", "content": "De acordo com os documentos, animais de estimacao sao permitidos desde que..."}
    ],
    "is_authenticated": true
  }' | python -m json.tool
echo ""
echo "--------------------------------------------"

# ------------------------------------------------------------
# 10. QUERY HIERARQUICA - Nivel especifico
# ------------------------------------------------------------
echo ">>> 10. POST /api/query/hierarchical (nivel especifico: codigo_civil)"
curl -s -X POST "$BASE_URL/api/query/hierarchical" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Quais os direitos do condomino?",
    "context": "zangari_website",
    "llm_provider": "openai",
    "embedding_provider": "ollama",
    "top_k_per_context": 3,
    "hierarchy_level": "codigo_civil",
    "strict_hierarchy": false,
    "fluent_mode": true,
    "is_authenticated": true
  }' | python -m json.tool
echo ""
echo "--------------------------------------------"

# ------------------------------------------------------------
# 11. QUERY HIERARQUICA - Modo tecnico (fluent_mode=false)
# ------------------------------------------------------------
echo ">>> 11. POST /api/query/hierarchical (modo tecnico)"
curl -s -X POST "$BASE_URL/api/query/hierarchical" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "O que diz a lei sobre barulho em condominio?",
    "context": "zangari_website",
    "llm_provider": "openai",
    "embedding_provider": "ollama",
    "top_k_per_context": 3,
    "fluent_mode": false,
    "show_source": true,
    "is_authenticated": true
  }' | python -m json.tool
echo ""
echo "--------------------------------------------"

# ------------------------------------------------------------
# 12. QUERY HIERARQUICA - Usuario admin
# ------------------------------------------------------------
echo ">>> 12. POST /api/query/hierarchical (admin)"
curl -s -X POST "$BASE_URL/api/query/hierarchical" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Quais documentos estao indexados?",
    "context": "zangari_website",
    "llm_provider": "openai",
    "embedding_provider": "ollama",
    "top_k_per_context": 3,
    "fluent_mode": true,
    "user_id": "admin_001",
    "is_authenticated": true,
    "is_admin": true
  }' | python -m json.tool
echo ""
echo "--------------------------------------------"

# ------------------------------------------------------------
# 13. VERIFICACAO - Sessoes ativas
# ------------------------------------------------------------
echo ">>> 13. GET /api/verify/sessions"
curl -s "$BASE_URL/api/verify/sessions" | python -m json.tool
echo ""
echo "--------------------------------------------"

# ------------------------------------------------------------
# 14. VERIFICACAO - Extrair referencia
# Descomente e ajuste o caminho do arquivo para testar
# ------------------------------------------------------------
echo ">>> 14. POST /api/verify/extract-reference"
echo "    [SKIP] Descomente abaixo e ajuste o caminho do arquivo"
# curl -s -X POST "$BASE_URL/api/verify/extract-reference" \
#   -F "file=@/caminho/para/documento_base.pdf" \
#   -F 'request_data={"extraction_query": "lista de nomes de funcionarios", "llm_provider": "openai", "session_ttl": 3600}' \
#   | python -m json.tool
echo ""
echo "--------------------------------------------"

# ------------------------------------------------------------
# 15. VERIFICACAO - Comparar target
# Descomente e ajuste session_id e caminho do arquivo
# ------------------------------------------------------------
echo ">>> 15. POST /api/verify/compare-target"
echo "    [SKIP] Descomente abaixo, ajuste session_id e caminho"
# curl -s -X POST "$BASE_URL/api/verify/compare-target" \
#   -F "files=@/caminho/para/documento_alvo.pdf" \
#   -F "session_id=COLOQUE_O_SESSION_ID_AQUI" \
#   -F "llm_provider=openai" \
#   -F "strictness=0.7" \
#   | python -m json.tool
echo ""
echo "--------------------------------------------"

# ------------------------------------------------------------
# 16. ADMIN - Obter prompt anonimo
# ------------------------------------------------------------
echo ">>> 16. GET /api/admin/rag/anonymous-prompt"
curl -s "$BASE_URL/api/admin/rag/anonymous-prompt" | python -m json.tool
echo ""
echo "--------------------------------------------"

# ------------------------------------------------------------
# 17. ADMIN - Atualizar prompt anonimo
# ------------------------------------------------------------
echo ">>> 17. PUT /api/admin/rag/anonymous-prompt"
curl -s -X PUT "$BASE_URL/api/admin/rag/anonymous-prompt" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Voce e o assistente virtual do Grupo Zangari.\n\nCONTEXTO ATIVO: {context_label} ({context_name})\n\nCONTEXTOS PUBLICOS:\n{available_contexts}\n\nDIRETRIZES:\n- Responda apenas com base nos documentos\n- Nao invente informacoes\n- Seja cordial e objetivo"
  }' | python -m json.tool
echo ""
echo "--------------------------------------------"

# ------------------------------------------------------------
# 18. ADMIN - Resetar prompt anonimo (volta ao padrao)
# ------------------------------------------------------------
echo ">>> 18. DELETE /api/admin/rag/anonymous-prompt"
curl -s -X DELETE "$BASE_URL/api/admin/rag/anonymous-prompt" | python -m json.tool
echo ""
echo "--------------------------------------------"

# ------------------------------------------------------------
# 19. DELETAR CONTEXTO DE TESTE
# ------------------------------------------------------------
echo ">>> 19. DELETE /api/contexts/teste_curl"
curl -s -X DELETE "$BASE_URL/api/contexts/teste_curl" | python -m json.tool
echo ""
echo "--------------------------------------------"

echo ""
echo "============================================"
echo " Testes finalizados!"
echo " Swagger UI: $BASE_URL/docs"
echo " ReDoc:      $BASE_URL/redoc"
echo "============================================"
