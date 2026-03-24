# Padrão Estrutural — Ata de Assembleia Condominial

> Documento de referência para construção de IA assistente de redação de atas a partir de transcrições (AssemblyAI).

---

## 1. Visão Geral da Estrutura

Uma Ata de Assembleia Condominial segue uma estrutura rígida e previsível, composta por **5 blocos sequenciais obrigatórios**. Essa previsibilidade é a principal vantagem para automação via IA.

```
┌──────────────────────────────────────┐
│  BLOCO 1 — CABEÇALHO INSTITUCIONAL   │  ← Dados fixos, preenchidos antes da assembleia
├──────────────────────────────────────┤
│  BLOCO 2 — ORDEM DO DIA              │  ← Lista de pautas, também pré-definida
├──────────────────────────────────────┤
│  BLOCO 3 — DELIBERAÇÕES              │  ← Corpo principal — extraído da transcrição
├──────────────────────────────────────┤
│  BLOCO 4 — ASSUNTOS GERAIS           │  ← Itens avulsos discutidos no final
├──────────────────────────────────────┤
│  BLOCO 5 — ENCERRAMENTO E ASSINATURAS│  ← Fórmula fixa de fechamento
└──────────────────────────────────────┘
```

---

## 2. BLOCO 1 — Cabeçalho Institucional

### Campos obrigatórios (sempre presentes, sempre nesta ordem):

| Campo | Formato | Exemplo |
|---|---|---|
| `EDITAL DE CONVOCAÇÃO` | Data (DD/MM/AAAA ou DD.MM.AAAA) | `12/11/2025` |
| `DATA DA ASSEMBLEIA` | Data | `25/11/2025` |
| `HORÁRIO` | Hora + justificativa de convocação | `19:30hs, em segunda convocação.` |
| `LOCAL` | Endereço ou descrição do local | `No salão de festas do próprio condomínio.` |
| `PRESENTES OU REPRESENTADOS` | Referência à lista ou enumeração | `Conforme lista de presença, parte integrante desta ata.` |
| `PRESIDENTE` | Nome completo + unidade | `Sr. Vanderlei Sergio Bergamaschi – APTO 92 A` |
| `SECRETÁRIO(A)` | Nome completo + cargo/empresa | `Sra. Carla Plaça de Souza` |

### Padrões linguísticos do cabeçalho:

- **Horário** sempre inclui a convocação: `"em segunda convocação"` ou `"em segunda chamada por falta de quórum legal na primeira"`
- **Local** pode ser físico (`"No salão de festas do próprio condomínio"`) ou híbrido (`"Realizada no formato Híbrido"`)
- **Presentes** quase sempre usa a fórmula: `"Conforme lista de presença, parte integrante desta ata"`
- **Secretário(a)** quando é da Zangari, inclui: `"Representante da Zangari Administradora"` ou `"Zangari Administradora de Bens S/S Ltda."`

### Variações encontradas:

```
# Formato 1 — Campos em linhas separadas (mais comum)
EDITAL DE CONVOCAÇÃO: 12/11/2025
DATA DA ASSEMBLEIA: 25/11/2025

# Formato 2 — Presentes + Presidente na mesma linha
PRESENTES OU REPRESENTADOS: Conforme lista de inscritos anexa. PRESIDENTE: Sr. Fábio Dallacqua, unidade 201 Aroeira.
```

---

## 3. BLOCO 2 — Ordem do Dia

### Estrutura:

- Título: `ORDEM DO DIA` (centralizado ou como heading)
- Itens numerados, cada um sendo o título resumido da pauta
- Tipicamente 3–7 itens
- Último item frequentemente: `OUTROS ASSUNTOS DE INTERESSE GERAL, NÃO PASSÍVEIS DE DELIBERAÇÃO`

### Categorias recorrentes de pautas (por frequência):

| Categoria | Exemplo de título | Frequência |
|---|---|---|
| **Prestação de contas** | `APROVAÇÃO DAS CONTAS DO PERÍODO DE OUT/2024 A SET/2025` | Obrigatório em AGO |
| **Previsão orçamentária** | `APRESENTAÇÃO E APROVAÇÃO DA PREVISÃO ORÇAMENTÁRIA PARA O PRÓXIMO EXERCÍCIO` | Obrigatório em AGO |
| **Eleição** | `ELEIÇÃO DE SÍNDICO E CONSELHO PARA O PRÓXIMO BIÊNIO` | A cada biênio |
| **Ratificação de administradora** | `APRESENTAÇÃO E RATIFICAÇÃO DA NOVA ADMINISTRADORA` | Quando há troca |
| **Obras e benfeitorias** | `DELIBERAÇÃO E APROVAÇÃO DA PINTURA DOS HALLS INTERNOS` | Quando necessário |
| **Regulamento/convenção** | `ADEQUAÇÃO DOS BICICLETÁRIOS E DEFINIÇÃO DE CRITÉRIOS` | Quando necessário |
| **Assuntos gerais** | `OUTROS ASSUNTOS DE INTERESSE GERAL` | Quase sempre presente |

### Padrão de nomenclatura dos itens:

Os títulos seguem o padrão: **`[VERBO DE AÇÃO] + [OBJETO] + [ESCOPO/PERÍODO]`**

Verbos mais comuns: `APRESENTAÇÃO`, `APROVAÇÃO`, `DELIBERAÇÃO`, `ELEIÇÃO`, `VOTAÇÃO`, `DISCUSSÃO`, `RATIFICAÇÃO`, `SORTEIO`

Conectores: `E`, `PARA`, `DO/DA/DOS/DAS`, `REFERENTE AO`, `COM A POSSIBILIDADE DE`

---

## 4. BLOCO 3 — Deliberações (CORPO PRINCIPAL)

Este é o bloco mais complexo e o principal alvo da IA. Cada item da ordem do dia gera um **sub-bloco de deliberação** com estrutura interna própria.

### Estrutura de cada item deliberado:

```
[TÍTULO DO ITEM];
  → Contextualização (quem falou, o que apresentou)
  → Explanação/Esclarecimentos (detalhes técnicos, valores, opções)
  → Debates e questionamentos (perguntas dos condôminos, respostas)
  → Votação e resultado (forma de votação + resultado)
```

### 4.1 Padrões de Contextualização (abertura de cada item)

Frases-modelo que iniciam a discussão de cada pauta:

```
"Com a palavra, a representante da administradora, informou que..."
"A representante da administradora informou que..."
"A Síndica informou que..."
"Foi questionado aos presentes se..."
"Foi esclarecido aos presentes que..."
"A representante da administradora esclareceu que..."
```

**Padrão geral:** `[SUJEITO] + [VERBO DE COMUNICAÇÃO] + que + [CONTEÚDO]`

Verbos de comunicação: `informou`, `esclareceu`, `explicou`, `apresentou`, `destacou`, `ressaltou`, `relatou`, `salientou`, `mencionou`

### 4.2 Padrões de Referência a Pessoas

| Tipo | Padrão | Exemplo |
|---|---|---|
| Condômino | `O(A) Sr(a). [Nome] – unidade [Nº]` | `O Sr. Jorge – unidade 142-B` |
| Síndico(a) | `O(A) Sr(a). [Nome] – unidade [Nº], síndico(a)` | `A Sra. Silvana Gercke, Apto 163B (atual síndica)` |
| Conselheiro | `O(A) Sr(a). [Nome] – unidade [Nº], conselheiro(a)` | `O Sr. Paulo – unidade 82, conselheiro` |
| Representante admin. | `A Sra. [Nome], representante da administradora` | `A Sra. Carla, representante da administradora` |
| Membro comissão | `O(A) Sr(a). [Nome] – unidade [Nº], membro da comissão [X]` | — |

**Regra:** Na primeira menção, usar nome completo + unidade + cargo. Nas seguintes, pode abreviar.

### 4.3 Padrões de Explanação Financeira

Quando o item envolve valores, a estrutura segue:

```
1. Apresentação dos saldos/valores atuais
2. Explicação da composição dos gastos
3. Comparação com períodos anteriores (se aplicável)
4. Proposta de reajuste com percentuais e valores
5. Opções para votação (quando há alternativas)
```

Frases recorrentes:

```
"...passando a arrecadação de R$ [X] para R$ [Y]"
"...com reajuste de [N]% a partir de [mês/ano]"
"Desta forma a arrecadação ficou composta por: Ordinária R$ [X] e Fundo de Reserva: R$ [Y]"
"...foram elaboradas [N] propostas de previsão orçamentária..."
"1ª Opção) Reajuste de [N]% passando a arrecadação de [X] para [Y]"
"2ª Opção) Reajuste de [N]% passando a arrecadação de [X] para [Y]"
```

### 4.4 Padrões de Votação e Resultado

Esta é a parte mais crítica — toda deliberação DEVE terminar com o resultado da votação.

**Fórmulas de transição para votação:**

```
"Após esclarecimentos e colocado em votação..."
"Após ampla discussão e considerações, foi colocado em votação..."
"Submetida a matéria à votação..."
"Após os esclarecimentos, procedeu-se à votação..."
"Após debates, foi colocado em votação..."
"A proposta foi submetida à votação..."
```

**Fórmulas de resultado:**

| Resultado | Fórmula |
|---|---|
| Unanimidade | `"...foi aprovado(a) por unanimidade..."` |
| Maioria simples | `"...aprovado(a) por maioria dos presentes..."` ou `"...por maioria de votos..."` |
| Maioria com abstenções | `"...aprovado(a) por maioria de votos, com abstenção de [N] unidades"` |
| Com especificação | `"...tendo sido aprovado(a) pela maioria dos presentes a [Opção X] com reajuste de [N]%..."` |

### 4.5 Padrões de Debate/Questionamentos

```
"O(A) Sr(a). [Nome] foi questionado(a) sobre..."
"[Nome] expressou seu descontentamento por..."
"Foi mencionado que em outras assembleias já houve discussão sobre..."
"A comissão financeira salientou que..."
"Foi solicitado que constasse em ata que..."
"Foi ressaltado que..."
```

### 4.6 Padrões de Eleição

```
"Foi questionado aos presentes se havia algum condômino presente interessado na candidatura ao cargo de [Cargo]..."
"...apresentou-se somente o(a) Sr(a). [Nome], [Unidade] (atual [cargo])..."
"...portador(a) da cédula de identidade RG [nº] e inscrito(a) sob o CPF [nº]..."
"...sendo reeleito(a) por unanimidade de votos dos presentes para o cargo de [CARGO] do CONDOMÍNIO [NOME]."
"O mandato terá validade de [data_início] a [data_fim]."
"Colocada a matéria em votação, foram eleitos por maioria dos presentes o seguinte corpo diretivo..."
```

---

## 5. BLOCO 4 — Assuntos Gerais

Itens não deliberativos mencionados ao final. Seguem padrão mais livre, mas com estrutura:

```
"Foi sugerido pelos condôminos a realização de [ação]..."
"A Síndica esclareceu que, assim que houver definição..., será efetuado..."
"Também foi ressaltada a importância de..."
"Adicionalmente, registrou-se a orientação para que..."
```

---

## 6. BLOCO 5 — Encerramento e Assinaturas

### Fórmula de encerramento (praticamente invariável):

```
"Questionado se dentre os presentes haveria mais algum item a ser tratado,
e não havendo mais assuntos, determinou o(a) presidente da mesa o encerramento
dos trabalhos e a lavratura da presente ata, que segue assinada por ele(a)
presidente e por mim, secretário(a). São Paulo, [dia] de [mês] de [ano]."
```

**Variação encontrada:**

```
"Não havendo mais assuntos a serem tratados, a Sra. Presidente deu por encerrada
a assembleia, da qual lavrei a ata que será assinada por mim e pela Sra. Presidente.
São Paulo, [dia] de [mês] de [ano]."
```

### Bloco de assinaturas:

```
________________________          ________________________
[Nome do Presidente]              [Nome do Secretário(a)]
PRESIDENTE                        SECRETÁRIO(A)
```

---

## 7. Glossário de Termos Recorrentes

Termos que a IA deve reconhecer na transcrição e mapear corretamente:

| Termo oral (transcrição) | Termo formal (ata) |
|---|---|
| "o síndico" / "a síndica" | `O(A) Sr(a). [Nome], síndico(a)` |
| "a administradora" | `a representante da administradora` |
| "o conselho" | `o Corpo Diretivo` / `o conselho consultivo` |
| "a taxa" / "o condomínio" (valor) | `a cota ordinária` / `a taxa condominial` |
| "o fundo" | `o Fundo de Reserva` |
| "a pasta" | `a pasta de prestação de contas` |
| "o boleto" | `o boleto de condomínio` |
| "rateio extra" | `arrecadação extraordinária` |
| "previsão" | `previsão orçamentária` |
| "votaram sim" / "todo mundo aprovou" | `aprovado por unanimidade` |
| "a maioria votou" | `aprovado por maioria dos presentes` |
| "alguns se abstiveram" | `com abstenção de [N] unidades` |
| "foram contra" | `com [N] votos contrários` |
| "o salão" | `o salão de festas` |
| "a churrasqueira" | `a área da churrasqueira` |
| "AGO" | `Assembleia Geral Ordinária` |
| "AGE" | `Assembleia Geral Extraordinária` |

---

## 8. Regras de Estilo e Tom

### O que a IA DEVE fazer:

1. **Usar terceira pessoa e voz passiva**: `"Foi informado que..."`, nunca `"Informamos que..."`
2. **Formalizar a linguagem oral**: Eliminar gírias, repetições, hesitações, interjeições
3. **Estruturar cronologicamente**: Cada pauta segue a ordem natural — apresentação → discussão → votação
4. **Incluir SEMPRE o resultado da votação**: Toda pauta deliberativa precisa de desfecho
5. **Identificar pessoas com unidade**: Sempre vincular o condômino à sua unidade
6. **Usar valores exatos**: Quando mencionados na transcrição, registrar valores em R$ com precisão
7. **Manter impessoalidade**: A ata é um documento objetivo, sem juízo de valor
8. **Conectar parágrafos com expressões formais**: `"Em continuidade..."`, `"Após esclarecimentos..."`, `"Dando seguimento..."`, `"Submetida a matéria..."`, `"Diante disso..."`

### O que a IA NÃO deve fazer:

1. **Não inventar informações**: Se a transcrição não menciona algo, não incluir
2. **Não incluir falas coloquiais**: `"aí o cara falou"` → `"O Sr. [Nome] informou que..."`
3. **Não omitir conflitos**: Se houve discordância, registrar de forma neutra
4. **Não usar primeira pessoa**: Exceto no encerramento (`"por mim, secretário(a)"`)
5. **Não abreviar nomes de condomínio**: Usar nome completo na primeira menção

---

## 9. Mapeamento Transcrição → Ata (Pipeline para AssemblyAI)

### Etapas sugeridas para o processamento:

```
┌─────────────────────────────────────────────────┐
│ 1. TRANSCRIÇÃO BRUTA (AssemblyAI)               │
│    - Áudio → texto com timestamps               │
│    - Speaker diarization (quem fala)             │
│    - Identificação de tópicos (chapters)         │
└──────────────────┬──────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────┐
│ 2. PRÉ-PROCESSAMENTO                            │
│    - Mapear speakers para nomes reais            │
│    - Segmentar por item da ordem do dia          │
│    - Detectar momentos de votação                │
│    - Extrair valores monetários e percentuais    │
└──────────────────┬──────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────┐
│ 3. GERAÇÃO DA ATA (LLM)                         │
│    - Aplicar padrão estrutural (este documento)  │
│    - Formalizar linguagem                        │
│    - Preencher template por bloco                │
│    - Garantir resultado de votação por item      │
└──────────────────┬──────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────┐
│ 4. REVISÃO HUMANA (Editor de texto com IA)       │
│    - Ajustar nomes e unidades                    │
│    - Validar valores e percentuais               │
│    - Completar campos do cabeçalho               │
│    - Aprovar ou editar cada bloco                │
└─────────────────────────────────────────────────┘
```

### Sinais na transcrição que indicam mudança de pauta:

```
"Vamos para o próximo item..."
"Passando ao item [N]..."
"Agora vamos tratar de..."
"O próximo assunto é..."
"Dando continuidade à ordem do dia..."
"Item [N] da pauta..."
```

### Sinais que indicam momento de votação:

```
"Vamos votar..."
"Quem é a favor levante a mão..."
"Os contrários..."
"Abstenções..."
"Está aprovado..."
"Foi aprovado por..."
"Unanimidade..."
"Maioria..."
```

### Sinais que indicam registro formal:

```
"Que conste em ata..."
"Quero registrar que..."
"Fique registrado..."
"Para fins de registro..."
"Que fique consignado..."
```

---

## 10. Template JSON para Dados Estruturados

Schema sugerido para o editor de IA processar internamente:

```json
{
  "tipo_assembleia": "AGO | AGE",
  "condominio": {
    "nome": "string",
    "endereco": "string",
    "cnpj": "string"
  },
  "cabecalho": {
    "edital_convocacao": "date",
    "data_assembleia": "date",
    "horario": "string",
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
      "contextualizacao": "string — resumo do que foi apresentado",
      "explanacoes": ["string — detalhes, valores, opções"],
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
        "detalhes": "string — ex: opção A aprovada, reajuste de 4,76%",
        "vigencia": "string | null — ex: a partir de Jan/26"
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
    "formula": "string",
    "data_extenso": "São Paulo, [dia] de [mês] de [ano]"
  }
}
```

---

## 11. Prompt de Sistema Sugerido para a IA do Editor

```
Você é um assistente especializado em redação de Atas de Assembleia Condominial
no padrão brasileiro. Sua função é transformar transcrições de áudio de assembleias
em atas formais, seguindo rigorosamente o padrão estrutural definido.

REGRAS:
1. Use SEMPRE terceira pessoa e voz passiva predominante.
2. Formalize toda linguagem coloquial.
3. Cada item da ordem do dia deve conter: contextualização, explanação,
   debates (se houver) e resultado da votação.
4. Identifique pessoas sempre com nome + unidade + cargo (quando aplicável).
5. Valores monetários devem ser registrados com precisão (R$ X.XXX,XX).
6. O resultado da votação é OBRIGATÓRIO para itens deliberativos.
7. Use as fórmulas padrão do universo condominial para transições e desfechos.
8. Não invente informações ausentes na transcrição.
9. Marque com [A CONFIRMAR] qualquer dado que não ficou claro na transcrição.
10. Quando detectar nomes próprios na transcrição que parecem incorretos
    (erro de speech-to-text), marque como [VERIFICAR: "nome transcrito"].
```

---

## 12. Observações sobre Qualidade da Transcrição (AssemblyAI)

Com base no Arquivo 1 analisado (transcrição bruta com timestamps), foram identificados os seguintes problemas típicos:

| Problema | Exemplo | Solução |
|---|---|---|
| Nomes próprios incorretos | Transcrição gera nomes inventados | Fornecer lista de condôminos + unidades como contexto |
| Termos técnicos distorcidos | "cota ordinária" → "cota ou dinária" | Glossário de termos condominiais no custom vocabulary |
| Sobreposição de falas | Dois speakers no mesmo timestamp | Usar speaker diarization + post-processing |
| Ruído de fundo | Palavras sem sentido no final | Filtrar segmentos com confidence < threshold |
| Timestamps imprecisos | Fala atribuída ao speaker errado | Validação humana no editor |

### Custom Vocabulary recomendado para AssemblyAI:

```json
["cota ordinária", "fundo de reserva", "previsão orçamentária",
 "corpo diretivo", "conselho consultivo", "prestação de contas",
 "balancete", "rateio extraordinário", "arrecadação", "quórum",
 "síndico", "subsíndico", "assembleia geral ordinária",
 "assembleia geral extraordinária", "convenção condominial",
 "regulamento interno", "procuração", "Zangari", "AABIC",
 "IPEVECON", "Sabesp", "INSS", "edital de convocação"]
```

---

*Documento gerado a partir da análise de 3 atas reais da Zangari Administradora e 1 template de transcrição.*
