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
      "descricao": "string — parágrafo detalhado do assunto levantado, quem levantou e a discussão que gerou. OBRIGATÓRIO: capture TODOS os assuntos do final da assembleia.",
      "encaminhamento": "string | null — o que ficou decidido ou prometido sobre este assunto"
    }
  ],
  "encerramento": {
    "formula": "string — fórmula formal de encerramento COMPLETA. OBRIGATÓRIO. Ex: 'Questionado se dentre os presentes haveria mais algum item a ser tratado, e não havendo manifestações, o Sr. [Nome], Presidente da Mesa, determinou o encerramento dos trabalhos e a lavratura da presente ata, que segue assinada por ele, presidente, e por mim, [Nome], secretário(a).'",
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
4. Identifique pessoas sempre com nome completo + unidade + cargo (quando aplicável). Para eleições, inclua RG e CPF se mencionados.
5. Valores monetários devem ser registrados com precisão (R$ X.XXX,XX) e, quando relevantes (valores de cota, rateio, totais), também POR EXTENSO: "R$ 102.527,59 (cento e dois mil quinhentos e vinte e sete reais e cinquenta e nove centavos)".
6. O resultado da votação é OBRIGATÓRIO para itens deliberativos.
7. Use as fórmulas padrão do universo condominial para transições e desfechos (veja seção ESTILO E FÓRMULAS).
8. NÃO invente informações ausentes na transcrição.
9. Marque com [A CONFIRMAR] qualquer dado que não ficou claro na transcrição.
10. Quando detectar nomes próprios que parecem incorretos (erro de speech-to-text), marque como [VERIFICAR: "nome transcrito"].
11. Quando houver apresentação de opções/alternativas para votação, documente TODAS as opções no campo "opcoes_apresentadas" ANTES do resultado da votação, incluindo valores quando mencionados.
12. Após cada votação, registre condições, ressalvas ou condicionantes no campo "condicoes" usando a fórmula "Ficou consignado que:" ou "Ficou registrado que:".
13. Para prestação de contas e previsão orçamentária, estruture os valores no campo "tabela_financeira" com colunas PREVISTO e REALIZADO (ou equivalentes). No texto da contextualização, referencie a tabela: "conforme quadro abaixo:" ou "conforme demonstrativo apresentado:".
14. A contextualização de cada deliberação deve ser um parágrafo LONGO e formal (mínimo 4-6 frases). Inclua datas, valores, nomes, referências a documentos e o contexto completo do que foi apresentado. Mesmo itens não-deliberativos (esclarecimentos, informes) devem ter contextualização detalhada com TODOS os dados mencionados na transcrição.
15. Eleições, reconduções e mandatos devem SEMPRE incluir: período de vigência no campo "vigencia", nomes completos, unidades, e quando mencionados RG/CPF. Se houver menção a autorização bancária para a administradora, registre em explanacoes.
16. TODOS os itens da ordem do dia devem ter um "titulo" DESCRITIVO — copie o mesmo texto que aparece na pauta anunciada na transcrição. Exemplos: "Aprovação da Prestação de Contas do Período de Julho/2023 a Junho/2024", "Eleição de Síndico, Subsíndico e Membros do Conselho para Mandato de 2 (Dois) Anos".
17. O campo "assuntos_gerais" é OBRIGATÓRIO. Capture CADA assunto individual levantado no final da assembleia: reclamações, sugestões, pedidos, esclarecimentos. Cada assunto é uma entrada separada com descrição detalhada e encaminhamento. Se 5 temas diferentes foram discutidos, gere 5 entradas.
18. O campo "encerramento.formula" é OBRIGATÓRIO e deve ser UMA ÚNICA fórmula de encerramento formal (1-2 frases). NÃO RESUMA a assembleia no encerramento — use apenas a fórmula padrão: "Não havendo mais nada a ser tratado, os trabalhos foram encerrados, sendo lavrada a presente ata, a qual vai assinada pelo Sr. [Presidente] e por mim, [Secretário(a)]."
19. Para esclarecimentos e informes (itens não-deliberativos), use as "explanacoes" para registrar TODOS os detalhes discutidos, incluindo perguntas dos moradores e respostas da administradora/síndico. Não resuma — desenvolva.
20. Capture TODAS as deliberações discutidas na assembleia, sem pular nenhum item da pauta. Se a transcrição menciona 6+ itens, a ata deve ter 6+ deliberações. Cada item DEVE aparecer na ordem do dia e ter sua deliberação correspondente.
21. A PRIMEIRA deliberação DEVE começar com a fórmula de abertura dos trabalhos, mencionando a eleição do presidente da mesa e do secretário. Inclua esta abertura na contextualização do primeiro item.
22. Quando uma deliberação resulta em múltiplas decisões distintas, enumere com alíneas: "(i) ...; (ii) ...; e (iii) ..." no campo "detalhes" da votação.
23. NÃO duplique conteúdo. Cada informação aparece APENAS no campo correto do JSON. Não repita deliberações nos assuntos_gerais. Não repita a ata inteira no encerramento.

## GLOSSÁRIO DE TERMOS (transcrição oral → ata formal)

- "o síndico" / "a síndica" → "O(A) Sr(a). [Nome Completo], síndico(a)"
- "a administradora" / "a Camila" / "a gerente" → "a representante da administradora" ou "Com a palavra, a Sra. [Nome], representante da Administradora [Nome]"
- "o conselho" → "o Corpo Diretivo" / "o conselho consultivo"
- "a taxa" / "o condomínio" (valor) → "a cota ordinária" / "a taxa condominial"
- "o fundo" → "o Fundo de Reserva" / "o Fundo de Melhorias"
- "a pasta" → "a pasta de prestação de contas" / "a pasta contendo os demonstrativos financeiros"
- "rateio extra" → "arrecadação extraordinária"
- "previsão" → "previsão orçamentária"
- "votaram sim" / "todo mundo aprovou" → "aprovado por unanimidade dos presentes"
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
- "mandato" → "mandato de [N] ([extenso]) anos, a partir de [data início] até [data fim]"
- "o balancete" → "os balancetes mensais encaminhados aos condôminos por e-mail"
- "a ação" / "o processo" → "a ação judicial" / "a demanda judicial em curso"

## SINAIS NA TRANSCRIÇÃO

Mudança de pauta: "Vamos para o próximo item...", "Passando ao item [N]...", "Item [N] da pauta..."
Momento de votação: "Vamos votar...", "Quem é a favor...", "Os contrários...", "Está aprovado..."
Registro formal: "Que conste em ata...", "Quero registrar que...", "Fique registrado..."
Opções para votação: "Opção 1...", "Alternativa A...", "Primeira proposta...", "Temos duas possibilidades..."
Condições pós-aprovação: "Ficou registrado...", "Com a condição de que...", "Desde que...", "Fica consignado..."
Dados financeiros: "O previsto era...", "O realizado foi...", "A receita total...", "As despesas foram..."
Eleição/candidatura: "Alguém se candidata...", "Eu me candidato...", "Gostaria de continuar..."
Assuntos gerais: "Alguém tem mais alguma coisa...", "Quero falar sobre...", "Eu queria perguntar..."

## ESTILO E FÓRMULAS

### Abertura (OBRIGATÓRIA — incluir na contextualização do Item 1)
- "Iniciados os trabalhos, foi eleito(a), para presidir a mesa da Assembleia, o(a) Sr(a). [Nome Completo], do apto [N] e, para secretariá-lo(a), a Sra. [Nome], representante da Administradora [Nome]. Na sequência foi anunciada a matéria do primeiro item da ordem do dia:"
- Se houver segunda convocação: "em segunda convocação, por falta de quórum legal na primeira"

### Introdução de falas e apresentações
- "Com a palavra, a Sra. [Nome], representante da Administradora, esclareceu aos presentes que..."
- "Com a palavra, o Sr. [Nome], síndico, informou que..."
- "Foi apresentada a projeção financeira dos últimos 12 (doze) meses, em que o condomínio apresentou..."
- "A Sra. [Nome] apresentou proposta para..."
- "Após esses esclarecimentos, foi apresentada..."

### Transições entre itens
- "Na sequência, foi anunciada a matéria do [N]º item da ordem do dia:"
- "Dando sequência, foi apresentado(a)..."
- "Ato contínuo, a Sra. [Nome] apresentou..."
- "Isto posto, passou-se ao [N]º item da Ordem do Dia..."

### Referência a dados financeiros
- "conforme quadro abaixo:" (quando há tabela_financeira)
- "conforme demonstrativo apresentado:"
- "Fica, portanto, a arrecadação composta da seguinte forma: Ordinária R$ [valor] ([extenso]), [Fundo] R$ [valor] ([extenso])..."

### Votação
- "Após alguns esclarecimentos, colocada a matéria em votação, foram aprovadas por unanimidade dos presentes..."
- "Após sanadas todas as dúvidas, colocada a matéria em votação, fica aprovado por maioria dos presentes, com [N] votos contrários que: (i) ...; e (ii) ..."
- "Foi questionado aos presentes se havia algum candidato ao cargo de Síndico, se apresentando e sendo reeleito por unanimidade dos votos, o Sr. [Nome], apto [N], portador do RG nº [RG] e CPF nº [CPF]..."
- "Submetida a matéria à votação, foi aprovada por unanimidade dos presentes."

### Condições pós-aprovação
- "Ficou consignado que:"
- "Ficou registrado que:"
- "A regra anteriormente aprovada para [assunto] permanece inalterada."
- "sendo mantida a isenção de [%] sobre a cota ordinária" (para síndico reeleito)

### Encerramento (fórmula curta — NÃO RESUMA a assembleia)
- "Não havendo mais nada a ser tratado, os trabalhos foram encerrados, sendo lavrada a presente ata, a qual vai assinada pelo Sr. Presidente e por mim, Secretário(a)."
- "Questionado se dentre os presentes haveria mais algum item a ser tratado, e não havendo mais assuntos, determinou o presidente da mesa o encerramento dos trabalhos e a lavratura da presente ata, que segue assinada por ele presidente e por mim, secretário(a)."

## EXEMPLOS DE DELIBERAÇÕES BEM ESCRITAS

### EXEMPLO 1 — Prestação de contas

Contextualização:
"Com a palavra, a Sra. Camila, representante da Administradora Zangari, esclareceu aos presentes que a dinâmica desse item é representada pelo envio das pastas de prestações de contas mensalmente ao conselho e síndico, que são devidamente analisadas, e na mesma periodicidade os balancetes são encaminhados aos condôminos por e-mail para que possam ter ciência da prestação de contas através de toda movimentação financeira descrita neles. Após esses esclarecimentos, foi apresentada a projeção financeira dos últimos 12 (doze) meses, em que o condomínio apresentou um déficit de 0,56% entre o que foi previsto e o que foi realizado, conforme quadro abaixo:"

Tabela financeira:
{"titulo": "Prestação de Contas Jul/2023 a Jun/2024", "colunas": ["Categoria", "Previsto", "Realizado"], "linhas": [{"categoria": "DESPESA COM PESSOAL", "valores": ["R$ 130.141,93", "R$ 119.128,84"]}, {"categoria": "TERCEIRIZAÇÃO", "valores": ["R$ 200.000,00", "R$ 210.500,00"]}], "total": ["R$ 1.137.156,56", "R$ 1.143.600,00"]}

Explanações:
["Apresentou também o índice de inadimplência do condomínio que atualmente é de 0,65%, com uma única unidade em atraso.", "Dando sequência, foi apresentada a evolução financeira das contas do Condomínio referente ao período de aprovação e saldo final.", "Ato contínuo, a Sra. Camila apresentou proposta para unificação das contas destinadas a melhorias e obras, informando que após a quitação da obra de retrofit da fachada, a conta Benfeitorias será extinta, e o valor de arrecadação mensal da conta Locação será também destinado ao Fundo de Melhorias."]

Votação:
{"resultado": "aprovado_unanimidade", "detalhes": "Após alguns esclarecimentos, colocada a matéria em votação, foram aprovadas por unanimidade dos presentes as contas do período e a unificação das contas destinadas a melhorias e obras conforme proposta."}

### EXEMPLO 2 — Eleição com detalhes completos

Contextualização:
"Foi questionado aos presentes se havia algum candidato ao cargo de Síndico, se apresentando e sendo reeleito por unanimidade dos votos, o Sr. Ricardo Nogueira Duarte, apto 101, portador do RG nº 9.400.230-7 e CPF nº 040.089.868-39, sendo mantida a isenção de 100% sobre a cota ordinária. Para o cargo de Subsíndico se apresentou e foi eleito por unanimidade dos votos o Sr. Marcelo Bianchi, apto 34. Para os cargos de conselheiros se candidataram e foram eleitos: Sr. Paulo Antonio Cabanas Capani, apto 204; Sr. Domingos Acácio Rodrigues, apto 171; e Sra. Flávia Leonato Machado Livero, apto 104."

Votação:
{"resultado": "aprovado_unanimidade", "vigencia": "mandato de 2 (dois) anos, a partir de 05/09/2024 até 04/09/2026", "detalhes": "Todos os eleitos cumprirão o mandato de 2 (dois) anos. Foi ratificado que a movimentação bancária será realizada pela administradora."}

### EXEMPLO 3 — Deliberação com múltiplas alíneas

Contextualização:
"Com a palavra, o Sr. Ricardo, síndico, informou que recebeu algumas solicitações de pais moradores, que menores de 13 anos não fizessem o uso da academia mesmo que acompanhados de seus responsáveis, pois as crianças ficam correndo dentro do espaço ou até mesmo utilizar os equipamentos de forma irregular, podendo assim ocasionar acidentes."

Votação:
{"resultado": "aprovado_maioria", "votos_contrarios": 2, "detalhes": "Após sanadas todas as dúvidas, colocada a matéria em votação, fica aprovado por maioria dos presentes, com dois votos contrários que: (i) adolescentes menores de 13 (treze) anos estão proibidos de frequentar a academia, mesmo que acompanhados de seus responsáveis; e (ii) adolescentes de 13 (treze) e 14 (catorze) anos de idade podem frequentar e utilizar a academia, desde que acompanhados de seu pai ou mãe durante todo o período em que permanecerem no espaço."}

Condições:
["A regra anteriormente aprovada para adolescentes a partir de 15 (quinze) anos frequentarem a academia sozinhos, desde que autorizados por escrito por seus pais, permanece inalterada."]

## DESENVOLVIMENTO DO TEXTO

A ata deve ser COMPLETA e DETALHADA. Siga estas diretrizes RIGOROSAMENTE:

1. **Contextualização**: Cada deliberação deve ter MÍNIMO 4-6 frases formais. Use "Com a palavra" para introduzir quem fala. Inclua:
   - Quem apresentou (nome completo + cargo/unidade)
   - O que foi apresentado (assunto + detalhes)
   - Valores, datas, períodos mencionados
   - Referências a documentos, pastas, balancetes, relatórios
   - Antecedentes relevantes mencionados na transcrição
   - "conforme quadro abaixo:" quando houver tabela financeira

2. **Explanações**: Registre TODOS os esclarecimentos, perguntas e respostas. Cada ponto separado na lista.

3. **Debates**: Capture manifestações individuais com nome, unidade e argumento DESENVOLVIDO.

4. **Assuntos Gerais**: OBRIGATÓRIO. Cada assunto é UMA ENTRADA SEPARADA. Se falaram sobre pintura, quadra, app e elevador = 4 entradas separadas. Cada uma com "descricao" detalhada e "encaminhamento".

5. **Encerramento**: APENAS a fórmula de encerramento (1-2 frases). NÃO inclua resumo da assembleia. Exemplo: "Não havendo mais nada a ser tratado, os trabalhos foram encerrados, sendo lavrada a presente ata, a qual vai assinada pelo Sr. [Nome], Presidente, e por mim, [Nome], Secretário(a). São Paulo, [data por extenso]."

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

    parts.append("""
---
## INSTRUÇÕES FINAIS

Analise a transcrição acima e gere a ata estruturada em JSON conforme o schema definido.

CHECKLIST OBRIGATÓRIO — verifique ANTES de enviar o JSON:
1. Cada item da "ordem_do_dia" tem "titulo" copiado da pauta anunciada na transcrição
2. Cada "deliberacoes" tem "contextualizacao" com MÍNIMO 4-6 frases formais (não resumos curtos)
3. A contextualização do PRIMEIRO item inclui a abertura: "Iniciados os trabalhos, foi eleito(a)..."
4. Valores importantes estão em numeral + extenso: "R$ 8.000,00 (oito mil reais)"
5. "assuntos_gerais" lista CADA assunto individual do final da assembleia como entrada separada
6. "encerramento.formula" é UMA fórmula de encerramento (1-2 frases) — NÃO um resumo da assembleia
7. NÃO há duplicação — cada informação aparece apenas no campo correto
8. TODOS os itens da pauta da transcrição estão presentes nas deliberações
9. Tabelas financeiras são referenciadas no texto com "conforme quadro abaixo:"
10. Eleições incluem nomes completos, unidades, período de vigência

Se houver dados faltantes (CNPJ, endereço, nome completo do síndico/presidente) e a ferramenta de busca estiver disponível, consulte os documentos do condomínio ANTES de marcar [A CONFIRMAR].""")

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
            "max_tokens": 16000,
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
                    max_tokens=16000,
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
        max_tokens=16000,
    )
    content = final_response.choices[0].message.content or ""
    ata_data = json.loads(content)

    return {"ata": ata_data, "fontes_rag": collected_sources}
