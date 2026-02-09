"""Processador LLM (OpenAI GPT) para análise da transcrição e geração de ata estruturada."""

import json
import logging

from openai import OpenAI

from config import Config

logger = logging.getLogger(__name__)

client = OpenAI(api_key=Config.OPENAI_API_KEY)

# ──────────────────────────────────────────────
# JSON Schema da seção 10 do PADRAO
# ──────────────────────────────────────────────

ATA_JSON_SCHEMA = """{
  "tipo_assembleia": "AGO | AGE",
  "condominio": {
    "nome": "string",
    "endereco": "string",
    "cnpj": "string"
  },
  "cabecalho": {
    "edital_convocacao": "date (DD/MM/AAAA)",
    "data_assembleia": "date (DD/MM/AAAA)",
    "horario": "string — ex: 19:30hs, em segunda convocação.",
    "convocacao": "primeira | segunda",
    "local": "string",
    "formato": "presencial | hibrido | virtual"
  },
  "mesa": {
    "presidente": {
      "nome": "string",
      "unidade": "string"
    },
    "secretario": {
      "nome": "string",
      "cargo": "string",
      "empresa": "string | null"
    }
  },
  "ordem_do_dia": [
    {
      "numero": 1,
      "titulo": "string",
      "categoria": "prestacao_contas | previsao_orcamentaria | eleicao | ratificacao | obras | regulamento | assuntos_gerais | outro",
      "deliberativo": true
    }
  ],
  "deliberacoes": [
    {
      "item_ordem_dia": 1,
      "contextualizacao": "string — parágrafo formal DETALHADO do que foi apresentado, com valores e datas quando aplicável",
      "explanacoes": ["string — detalhes complementares, esclarecimentos prestados"],
      "opcoes_apresentadas": [
        {
          "descricao": "string — ex: Opção A: Reforma parcial das áreas comuns",
          "valor": "string | null — ex: R$ 50.000,00",
          "detalhes": "string | null — detalhes adicionais da opção"
        }
      ],
      "debates": [
        {
          "pessoa": "string",
          "unidade": "string",
          "manifestacao": "string"
        }
      ],
      "votacao": {
        "ocorreu": true,
        "resultado": "aprovado_unanimidade | aprovado_maioria | reprovado | adiado",
        "abstencoes": "string | null",
        "votos_contrarios": "number | null",
        "detalhes": "string",
        "vigencia": "string | null — ex: mandato de 01/01/2026 a 31/12/2027",
        "opcao_escolhida": "string | null — qual opção foi aprovada, quando houver múltiplas"
      },
      "condicoes": ["string — cláusulas 'Ficou consignado/registrado que...' aprovadas após votação"],
      "tabela_financeira": {
        "titulo": "string | null — ex: Prestação de Contas 2025",
        "colunas": ["string — ex: Categoria, Previsto, Realizado"],
        "linhas": [
          {
            "categoria": "string — ex: DESPESA COM PESSOAL",
            "valores": ["string — ex: R$ 130.141,93"]
          }
        ],
        "total": ["string — valores da linha de total"]
      }
    }
  ],
  "assuntos_gerais": [
    {
      "descricao": "string",
      "encaminhamento": "string | null"
    }
  ],
  "encerramento": {
    "formula": "string — fórmula formal de encerramento",
    "data_extenso": "São Paulo, [dia] de [mês] de [ano]"
  }
}"""


def build_system_prompt(use_rag: bool = False) -> str:
    """Monta o system prompt com todas as regras do PADRAO."""
    prompt = """Você é um assistente especializado em redação de Atas de Assembleia Condominial no padrão brasileiro. Sua função é transformar transcrições de áudio de assembleias em atas formais estruturadas em JSON.

## REGRAS OBRIGATÓRIAS

1. Use SEMPRE terceira pessoa e voz passiva predominante: "Foi informado que...", nunca "Informamos que..."
2. Formalize toda linguagem coloquial. Elimine gírias, repetições, hesitações e interjeições.
3. Cada item da ordem do dia deve conter: contextualização, explanação, debates (se houver) e resultado da votação.
4. Identifique pessoas sempre com nome + unidade + cargo (quando aplicável).
5. Valores monetários devem ser registrados com precisão (R$ X.XXX,XX).
6. O resultado da votação é OBRIGATÓRIO para itens deliberativos.
7. Use as fórmulas padrão do universo condominial para transições e desfechos.
8. NÃO invente informações ausentes na transcrição.
9. Marque com [A CONFIRMAR] qualquer dado que não ficou claro na transcrição.
10. Quando detectar nomes próprios que parecem incorretos (erro de speech-to-text), marque como [VERIFICAR: "nome transcrito"].
11. Quando houver apresentação de opções/alternativas para votação, documente TODAS as opções no campo "opcoes_apresentadas" ANTES do resultado da votação, incluindo valores quando mencionados.
12. Após cada votação, registre condições, ressalvas ou condicionantes no campo "condicoes" usando a fórmula "Ficou consignado que:" ou "Ficou registrado que:".
13. Para prestação de contas e previsão orçamentária, estruture os valores no campo "tabela_financeira" com colunas PREVISTO e REALIZADO (ou equivalentes).
14. A contextualização de cada deliberação deve ser um parágrafo longo e formal, não apenas uma frase. Inclua datas, valores, referências a documentos e o contexto completo do que foi apresentado.
15. Eleições, reconduções e mandatos devem SEMPRE incluir o período de vigência no campo "vigencia" (ex: "mandato de 01/01/2026 a 31/12/2027").

## GLOSSÁRIO DE TERMOS (transcrição oral → ata formal)

- "o síndico" / "a síndica" → "O(A) Sr(a). [Nome], síndico(a)"
- "a administradora" → "a representante da administradora"
- "o conselho" → "o Corpo Diretivo" / "o conselho consultivo"
- "a taxa" / "o condomínio" (valor) → "a cota ordinária" / "a taxa condominial"
- "o fundo" → "o Fundo de Reserva"
- "a pasta" → "a pasta de prestação de contas"
- "rateio extra" → "arrecadação extraordinária"
- "previsão" → "previsão orçamentária"
- "votaram sim" / "todo mundo aprovou" → "aprovado por unanimidade"
- "a maioria votou" → "aprovado por maioria dos presentes"
- "alguns se abstiveram" → "com abstenção de [N] unidades"
- "foram contra" → "com [N] votos contrários"
- "AGO" → "Assembleia Geral Ordinária"
- "AGE" → "Assembleia Geral Extraordinária"
- "ficou registrado" / "ficou consignado" → "Ficou consignado que:"
- "opção A" / "opção B" / "alternativa" → "Opção A: [descrição completa com valor]"
- "comissão" → "comissão de condôminos"
- "pro forma" → "votação pro forma (sem caráter vinculante)"
- "fração ideal" → "conforme fração ideal de cada unidade"
- "mandato" → "mandato para o período de [data início] a [data fim]"

## SINAIS NA TRANSCRIÇÃO

Mudança de pauta: "Vamos para o próximo item...", "Passando ao item [N]...", "Item [N] da pauta..."
Momento de votação: "Vamos votar...", "Quem é a favor...", "Os contrários...", "Está aprovado..."
Registro formal: "Que conste em ata...", "Quero registrar que...", "Fique registrado..."
Opções para votação: "Opção 1...", "Alternativa A...", "Primeira proposta...", "Temos duas possibilidades..."
Condições pós-aprovação: "Ficou registrado...", "Com a condição de que...", "Desde que...", "Fica consignado..."
Dados financeiros: "O previsto era...", "O realizado foi...", "A receita total...", "As despesas foram..."

## ESTILO E FÓRMULAS

### Abertura
- "Em abertura dos trabalhos, foi eleito(a) para presidir a mesa o(a) Sr(a). [Nome], [unidade]."
- "Ato contínuo, procedeu-se à leitura do edital de convocação, publicado em [data], verificando-se a existência de quórum legal para realização da assembleia."
- "Em continuidade, a representante da administradora expôs a pauta da presente assembleia."

### Transições entre itens
- "Isto posto, passou-se ao [N]º item da Ordem do Dia..."
- "Na sequência, passou ao [N]º item da Ordem do Dia..."
- "Ato contínuo, passou-se ao [N]º item..."
- "Dando seguimento à Ordem do Dia..."
- "Em continuidade, foi apresentado(a)..."

### Votação
- "Submetida a matéria à votação, foi aprovada por unanimidade dos presentes."
- "Colocada em votação, ficou aprovada por maioria a [Opção/proposta]."
- "Procedeu-se à votação da candidatura do(a) Sr(a). [Nome], sendo este(a) eleito(a) por unanimidade."
- "Após ampla discussão e esclarecimento dos questionamentos, colocada em votação, a matéria foi aprovada por unanimidade."

### Condições pós-aprovação
- "Ficou consignado que:"
- "Ficou registrado que:"
- "Restou consignada a preferência unânime..."
- "Foi ressaltado que..."

### Encerramento
- "Questionado se dentre os presentes haveria mais algum item a ser tratado, e não havendo manifestações, o(a) Sr(a). Presidente determinou o encerramento dos trabalhos e a lavratura da presente ata, que segue assinada por ele(a), presidente, e por mim, secretário(a)."
- "Não havendo mais assuntos a serem tratados, o(a) Sr(a). Presidente deu por encerrada a assembleia, lavrando-se a presente ata."

## EXEMPLO DE DELIBERAÇÃO BEM ESCRITA

EXEMPLO de como estruturar uma deliberação de prestação de contas:

Contextualização:
"Em continuidade, a representante da administradora apresentou a prestação de contas do exercício de 2024, informando que a pasta contendo os demonstrativos financeiros encontrava-se à disposição dos condôminos desde o dia 10/11/2025. Foi esclarecido que as receitas totais no período foram de R$ 193.012,50, enquanto as despesas totalizaram R$ 186.478,37, resultando em superávit de R$ 6.534,13."

Tabela financeira (campo "tabela_financeira"):
{
  "titulo": "Prestação de Contas 2024",
  "colunas": ["Categoria", "Previsto", "Realizado"],
  "linhas": [
    {"categoria": "DESPESA COM PESSOAL", "valores": ["R$ 130.141,93", "R$ 119.128,84"]},
    {"categoria": "CONSUMO", "valores": ["R$ 10.880,84", "R$ 12.063,72"]},
    {"categoria": "MANUTENÇÃO", "valores": ["R$ 36.720,30", "R$ 41.508,87"]}
  ],
  "total": ["R$ 193.012,50", "R$ 186.478,37"]
}

Votação:
"Submetida a matéria à votação, as contas foram aprovadas por unanimidade dos presentes."

Condições (campo "condicoes"):
["Ficou consignado que o superávit apurado será revertido ao Fundo de Reserva."]

EXEMPLO de deliberação com opções:

Contextualização:
"Na sequência, passou ao 5º item da Ordem do Dia, referente à reforma da fachada do edifício. O(A) Sr(a). [Nome], síndico(a), apresentou três orçamentos obtidos junto a empresas especializadas, detalhando escopo, prazo e valor de cada proposta."

Opções apresentadas (campo "opcoes_apresentadas"):
[
  {"descricao": "Opção A: Empresa Alpha — reforma completa com pintura", "valor": "R$ 280.000,00", "detalhes": "Prazo de 6 meses, inclui andaimes"},
  {"descricao": "Opção B: Empresa Beta — reforma parcial (fachada frontal)", "valor": "R$ 150.000,00", "detalhes": "Prazo de 3 meses"},
  {"descricao": "Opção C: Empresa Gamma — reforma completa sem pintura", "valor": "R$ 210.000,00", "detalhes": "Prazo de 4 meses"}
]

Votação com opção escolhida:
{"resultado": "aprovado_maioria", "opcao_escolhida": "Opção A: Empresa Alpha", "detalhes": "Aprovada por maioria a proposta da Empresa Alpha, com 2 votos contrários."}

Condições:
["Ficou consignado que o síndico deverá apresentar o contrato para aprovação do Conselho em até 30 dias.", "Ficou registrado que o rateio extraordinário para custeio da obra será cobrado em 10 parcelas."]

## FORMATO DE SAÍDA

Responda EXCLUSIVAMENTE com um JSON válido no seguinte schema:

"""

    if use_rag:
        prompt += """
IMPORTANTE — CONSULTA A DOCUMENTOS (RAG):
Você tem acesso a uma ferramenta de busca nos documentos do condomínio (convenção, regimento interno, atas anteriores) e na legislação aplicável. Use esta ferramenta PROATIVAMENTE quando:
- NÃO encontrar o CNPJ do condomínio na transcrição
- NÃO encontrar o nome completo ou endereço do condomínio
- NÃO encontrar o nome do síndico, presidente da mesa ou membros do conselho
- Precisar verificar dados cadastrais do condomínio
- Quiser confirmar informações mencionadas na transcrição

ANTES de marcar qualquer dado como [A CONFIRMAR], tente consultar os documentos do condomínio. Somente marque [A CONFIRMAR] se a busca também não retornar a informação.

"""

    prompt += ATA_JSON_SCHEMA

    return prompt


def _build_user_prompt(transcricao: dict, participantes_json: str = None, dados_condominio: str = None) -> str:
    """Monta o user prompt com a transcrição e dados complementares."""
    parts = []

    if dados_condominio:
        parts.append(f"## Dados do Condomínio\n{dados_condominio}\n")

    if participantes_json:
        parts.append(f"## Lista de Participantes\n{participantes_json}\n")

    parts.append("## Transcrição Bruta da Assembleia\n")

    # Incluir utterances com speaker labels e timestamps
    utterances = transcricao.get("utterances", [])
    if utterances:
        for utt in utterances:
            speaker = utt.get("speaker", "?")
            text = utt.get("text", "")
            start = utt.get("start", 0)
            # Formatar timestamp
            minutes = start // 60000
            seconds = (start % 60000) // 1000
            parts.append(f"[{minutes:02d}:{seconds:02d}] Speaker {speaker}: {text}")
    else:
        # Fallback: texto completo
        parts.append(transcricao.get("texto_completo", ""))

    # Incluir chapters se disponíveis
    chapters = transcricao.get("chapters", [])
    if chapters:
        parts.append("\n## Capítulos/Tópicos Identificados Automaticamente")
        for ch in chapters:
            parts.append(f"- {ch.get('headline', 'Item')}: {ch.get('summary', '')}")

    parts.append("\n---\nAnalise a transcrição acima e gere a ata estruturada em JSON conforme o schema definido. Se houver dados faltantes (CNPJ, endereço, nome completo do síndico/presidente) e a ferramenta de busca estiver disponível, consulte os documentos do condomínio ANTES de marcar [A CONFIRMAR].")

    return "\n".join(parts)


# ──────────────────────────────────────────────
# Assistente de editor de texto
# ──────────────────────────────────────────────

ASSISTENTE_SYSTEM_PROMPT = """Você é um assistente especializado em redação e edição de Atas de Assembleia Condominial no padrão brasileiro. Você auxilia o editor humano a redigir, corrigir, formalizar e completar trechos de ata.

## REGRAS DE ESTILO

1. Use SEMPRE terceira pessoa e voz passiva predominante: "Foi informado que...", nunca "Informamos que..."
2. Formalize toda linguagem coloquial. Elimine gírias, repetições, hesitações e interjeições.
3. Identifique pessoas sempre com nome + unidade + cargo (quando aplicável).
4. Valores monetários devem ser registrados com precisão (R$ X.XXX,XX).
5. O resultado da votação é OBRIGATÓRIO para itens deliberativos.
6. Use as fórmulas padrão do universo condominial para transições e desfechos.
7. NÃO invente informações. Se algo não estiver claro, marque com [A CONFIRMAR].
8. Nomes próprios duvidosos: marque com [VERIFICAR: "nome"].

## GLOSSÁRIO (oral → formal)

- "o síndico"/"a síndica" → "O(A) Sr(a). [Nome], síndico(a)"
- "a administradora" → "a representante da administradora"
- "o conselho" → "o Corpo Diretivo" / "o conselho consultivo"
- "a taxa"/"o condomínio" (valor) → "a cota ordinária" / "a taxa condominial"
- "o fundo" → "o Fundo de Reserva"
- "rateio extra" → "arrecadação extraordinária"
- "previsão" → "previsão orçamentária"
- "votaram sim"/"todo mundo aprovou" → "aprovado por unanimidade"
- "a maioria votou" → "aprovado por maioria dos presentes"
- "AGO" → "Assembleia Geral Ordinária"
- "AGE" → "Assembleia Geral Extraordinária"

## FÓRMULAS PADRÃO

- Transições: "Em continuidade...", "Após esclarecimentos...", "Dando seguimento...", "Submetida a matéria...", "Diante disso..."
- Presentes: "Conforme lista de presença, parte integrante desta ata"
- Encerramento: "Questionado se dentre os presentes haveria mais algum item a ser tratado, e não havendo mais assuntos, determinou o(a) presidente da mesa o encerramento dos trabalhos e a lavratura da presente ata, que segue assinada por ele(a) presidente e por mim, secretário(a)."

## COMPORTAMENTO

- Responda DIRETAMENTE com o texto solicitado (não use blocos de código markdown).
- Se o editor pedir para formalizar, retorne o texto formalizado.
- Se pedir para completar, continue o texto no mesmo tom.
- Se pedir para corrigir, retorne o texto corrigido.
- Se pedir sugestões, liste as sugestões de forma clara.
- Mantenha o contexto da conversa para edições incrementais.

## CONSULTA A DOCUMENTOS (RAG)

Quando disponível, você tem acesso a uma ferramenta de busca nos documentos do condomínio
(convenção, regimento interno, atas anteriores) e na legislação aplicável (Lei de Condomínios 4.591/64,
Código Civil). Use esta ferramenta quando:
- O editor pedir para validar ou fundamentar algo legalmente
- Precisar verificar quóruns, prazos ou regras específicas
- A instrução mencionar leis, artigos, convenção ou regimento
- Quiser enriquecer o texto da ata com referências legais corretas

Ao citar informações obtidas da busca, SEMPRE indique a fonte entre parênteses.
Exemplo: "(conforme art. 1.335 do Código Civil)" ou "(conforme art. 12 da Convenção do Condomínio)".
Se a busca não retornar resultados relevantes, não invente — indique com [VERIFICAR FONTE]."""

# ──────────────────────────────────────────────
# Tools para OpenAI Function Calling (RAG-Z)
# ──────────────────────────────────────────────

RAG_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_condominium_docs",
            "description": (
                "Pesquisa documentos do condomínio (convenção, regimento interno, atas anteriores) "
                "e legislação aplicável (Lei de Condomínios, Código Civil). "
                "Use esta ferramenta quando precisar verificar informações legais, "
                "regras do condomínio, artigos de lei, ou validar o conteúdo de uma ata "
                "contra a documentação existente. "
                "Exemplos de quando usar: "
                "- Verificar quórum necessário para votação "
                "- Consultar regras sobre obras, animais, barulho "
                "- Buscar artigos específicos da convenção ou código civil "
                "- Validar se uma deliberação está de acordo com a lei"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "A pergunta ou busca em linguagem natural. "
                            "Seja específico. Ex: 'Qual o quórum necessário para aprovação de obras?' "
                            "ou 'O que diz o artigo 1.335 do Código Civil sobre direitos do condômino?'"
                        ),
                    },
                    "hierarchy_level": {
                        "type": "string",
                        "enum": [
                            "convencao",
                            "regimento_interno",
                            "codigo_civil",
                            "lei_condominios",
                            "ata_assembleia",
                        ],
                        "description": (
                            "Nível hierárquico específico para buscar. "
                            "Se omitido, busca em cascata: documentos do condomínio → lei de condomínios → código civil. "
                            "Use 'convencao' para regras específicas do condomínio, "
                            "'regimento_interno' para regras de convivência, "
                            "'codigo_civil' para lei geral, "
                            "'lei_condominios' para Lei 4.591/64, "
                            "'ata_assembleia' para atas anteriores."
                        ),
                    },
                },
                "required": ["query"],
            },
        },
    },
]


def _should_use_rag_tools(condominio_context: str = None) -> bool:
    """RAG tools são oferecidas quando há contexto de condomínio e RAG está habilitado."""
    if not condominio_context:
        return False
    if not Config.RAG_Z_ENABLED:
        return False
    return True


def assistente_editor(
    instrucao: str,
    texto: str,
    contexto: str = None,
    historico: list[dict] = None,
    stream: bool = False,
    condominio_context: str = None,
):
    """Assistente LLM para edição interativa de atas, com RAG via function calling.

    Args:
        instrucao: O que o editor quer fazer (ex: "formalize este parágrafo")
        texto: O texto sendo editado
        contexto: Contexto adicional (transcrição, dados da ata, etc.)
        historico: Histórico de mensagens anteriores [{role, content}, ...]
        stream: Se True, retorna um generator de chunks (SSE)
        condominio_context: Nome do contexto RAG-Z (ex: "cond_0388")

    Returns:
        dict: {"resultado": str, "fontes_rag": list} ou generator de dicts
    """
    logger.info(
        "Assistente editor chamado (stream=%s, condominio=%s)",
        stream,
        condominio_context,
    )

    messages = [{"role": "system", "content": ASSISTENTE_SYSTEM_PROMPT}]

    # Adicionar histórico se fornecido
    if historico:
        for msg in historico:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    # Montar mensagem do usuário
    user_parts = []
    if contexto:
        user_parts.append(f"## Contexto\n{contexto}\n")
    user_parts.append(f"## Texto atual\n{texto}\n")
    user_parts.append(f"## Instrução\n{instrucao}")

    messages.append({"role": "user", "content": "\n".join(user_parts)})

    # Determinar se RAG tools devem ser oferecidas
    use_tools = _should_use_rag_tools(condominio_context)
    tools = RAG_TOOLS if use_tools else None

    # --- FUNCTION CALLING LOOP (sempre síncrono) ---
    # Resolve todos os tool calls primeiro, depois opcionalmente faz stream da resposta final.
    collected_sources = []
    max_tool_rounds = 3

    for _round in range(max_tool_rounds):
        call_kwargs = {
            "model": Config.OPENAI_MODEL,
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": 4000,
        }
        if tools:
            call_kwargs["tools"] = tools
            call_kwargs["tool_choice"] = "auto"

        response = client.chat.completions.create(**call_kwargs)
        choice = response.choices[0]

        # Se não há tool calls, temos a resposta final
        if not choice.message.tool_calls:
            if stream:
                # Adiciona a mensagem do assistant ao histórico e re-faz com stream
                messages.append({"role": "assistant", "content": choice.message.content or ""})
                return _assistente_stream_final(messages, collected_sources)

            content = choice.message.content or ""
            logger.info(
                "Assistente editor respondeu (%d chars, %d fontes RAG)",
                len(content),
                len(collected_sources),
            )
            return {"resultado": content, "fontes_rag": collected_sources}

        # --- Processar tool calls ---
        messages.append(choice.message)

        for tool_call in choice.message.tool_calls:
            if tool_call.function.name == "search_condominium_docs":
                args = json.loads(tool_call.function.arguments)
                query = args.get("query", "")
                hierarchy_level = args.get("hierarchy_level", None)

                logger.info(
                    "RAG tool call: query='%s', level=%s, context=%s",
                    query[:80],
                    hierarchy_level,
                    condominio_context,
                )

                from processors.rag_client import format_rag_result_for_llm, query_hierarchical

                rag_result = query_hierarchical(
                    question=query,
                    context=condominio_context,
                    hierarchy_level=hierarchy_level,
                )

                for src in rag_result.get("sources", []):
                    collected_sources.append(src)

                tool_response_text = format_rag_result_for_llm(rag_result)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_response_text,
                })
            else:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": f"Ferramenta desconhecida: {tool_call.function.name}",
                })

    # Limite de rodadas atingido
    logger.warning("Assistente atingiu limite de %d rodadas de tool calling", max_tool_rounds)
    last_content = response.choices[0].message.content or ""
    return {"resultado": last_content, "fontes_rag": collected_sources}


def _assistente_stream_final(messages: list[dict], sources: list[dict]):
    """Generator que faz stream da resposta final e emite fontes RAG no final.

    Yields dicts:
    - {"content": "chunk de texto"}
    - {"fontes_rag": [...]} como último evento
    """
    response = client.chat.completions.create(
        model=Config.OPENAI_MODEL,
        messages=messages,
        temperature=0.4,
        max_tokens=4000,
        stream=True,
    )

    for chunk in response:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            yield {"content": delta.content}

    if sources:
        yield {"fontes_rag": sources}


def analyze_transcription(
    transcricao: dict,
    participantes_json: str = None,
    dados_condominio: str = None,
    condominio_context: str = None,
) -> dict:
    """Envia transcrição ao OpenAI GPT e retorna ata estruturada como dict.

    Args:
        transcricao: Dados da transcrição (utterances, texto_completo, chapters, etc.)
        participantes_json: JSON com mapeamento de participantes
        dados_condominio: Dados complementares do condomínio
        condominio_context: Nome do contexto RAG-Z para auto-completar dados faltantes

    Returns:
        dict: {"ata": dict, "fontes_rag": list}
    """
    use_rag = _should_use_rag_tools(condominio_context)
    logger.info(
        "Iniciando análise LLM da transcrição (modelo: %s, rag: %s)",
        Config.OPENAI_MODEL,
        condominio_context if use_rag else "desabilitado",
    )

    system_prompt = build_system_prompt(use_rag=use_rag)
    user_prompt = _build_user_prompt(transcricao, participantes_json, dados_condominio)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    tools = RAG_TOOLS if use_rag else None
    collected_sources = []
    max_tool_rounds = 3

    for _round in range(max_tool_rounds):
        call_kwargs = {
            "model": Config.OPENAI_MODEL,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 8000,
        }

        if tools:
            call_kwargs["tools"] = tools
            call_kwargs["tool_choice"] = "auto"
        else:
            call_kwargs["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**call_kwargs)
        choice = response.choices[0]

        # Se não há tool calls, temos a resposta final
        if not choice.message.tool_calls:
            content = choice.message.content or ""

            # Se usou tools nas rodadas anteriores, precisa pedir JSON na resposta final
            if tools and _round > 0:
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": "Agora retorne EXCLUSIVAMENTE o JSON da ata estruturada conforme o schema definido, incorporando as informações obtidas nas consultas.",
                })
                final_response = client.chat.completions.create(
                    model=Config.OPENAI_MODEL,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.3,
                    max_tokens=8000,
                )
                content = final_response.choices[0].message.content or ""

            ata_data = json.loads(content)

            logger.info(
                "Análise LLM concluída: %d deliberações, %d assuntos gerais, %d fontes RAG",
                len(ata_data.get("deliberacoes", [])),
                len(ata_data.get("assuntos_gerais", [])),
                len(collected_sources),
            )

            return {"ata": ata_data, "fontes_rag": collected_sources}

        # --- Processar tool calls ---
        messages.append(choice.message)

        for tool_call in choice.message.tool_calls:
            if tool_call.function.name == "search_condominium_docs":
                args = json.loads(tool_call.function.arguments)
                query = args.get("query", "")
                hierarchy_level = args.get("hierarchy_level", None)

                logger.info(
                    "RAG tool call (análise): query='%s', level=%s, context=%s",
                    query[:80],
                    hierarchy_level,
                    condominio_context,
                )

                from processors.rag_client import format_rag_result_for_llm, query_hierarchical

                rag_result = query_hierarchical(
                    question=query,
                    context=condominio_context,
                    hierarchy_level=hierarchy_level,
                )

                for src in rag_result.get("sources", []):
                    collected_sources.append(src)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": format_rag_result_for_llm(rag_result),
                })
            else:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": f"Ferramenta desconhecida: {tool_call.function.name}",
                })

    # Limite de rodadas atingido — forçar resposta JSON
    logger.warning("Análise atingiu limite de %d rodadas de tool calling", max_tool_rounds)
    messages.append({
        "role": "user",
        "content": "Retorne EXCLUSIVAMENTE o JSON da ata estruturada conforme o schema definido.",
    })
    final_response = client.chat.completions.create(
        model=Config.OPENAI_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=8000,
    )
    content = final_response.choices[0].message.content or ""
    ata_data = json.loads(content)

    return {"ata": ata_data, "fontes_rag": collected_sources}
