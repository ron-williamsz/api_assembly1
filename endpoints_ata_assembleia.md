# Endpoints AssemblyAI para Transcrição de Atas de Assembleia

## Estrutura de uma Ata de Assembleia (PT-BR)

Baseado na análise do exemplo, uma ata típica contém:

### 1. **Cabeçalho Administrativo**
- Edital de Convocação
- Data da Assembleia
- Horário
- Local
- Presentes/Representados
- Presidente e Secretário

### 2. **Corpo Principal**
- **Ordem do Dia**: Tópicos a serem discutidos
- **Discussões**: Explicações e esclarecimentos
- **Votações**: Resultados (aprovado/rejeitado, unanimidade/maioria)
- **Deliberações**: Decisões tomadas
- **Sorteios**: Resultados de sorteios (garagens, churrasqueira, etc)
- **Assuntos Adicionais**: Sugestões, orientações

### 3. **Encerramento**
- Assinaturas (Presidente e Secretário)
- Data e local final

---

## Endpoints AssemblyAI Recomendados para Ata de Assembleia

### **1. POST /v2/transcript** - Transcrição Base
**URL**: `https://api.assemblyai.com/v2/transcript`

**Parâmetros essenciais para ata:**
```json
{
  "audio_url": "URL_DO_AUDIO_OU_VIDEO",
  "language_code": "pt",
  "language_detection": false,
  "punctuate": true,
  "format_text": true,
  "speaker_labels": true,
  "speakers_expected": 2,
  "word_boost": ["assembleia", "deliberação", "votação", "aprovado", "rejeitado"],
  "boost_param": "high"
}
```

**Por que:**
- `speaker_labels`: Identifica "quem falou o quê" (Presidente, Secretário, Condôminos)
- `punctuate`: Adiciona pontuação automática
- `format_text`: Formata o texto (maiúsculas, números)
- `word_boost`: Garante reconhecimento de palavras-chave de atas

---

### **2. GET /v2/transcript/:transcript_id** - Recuperar Transcrição
**URL**: `https://api.assemblyai.com/v2/transcript/{transcript_id}`

**Resposta inclui:**
- Status completo da transcrição
- Texto completo
- Itens com timestamps (palavras e timestamps)
- Speaker labels com atribuição

---

### **3. POST /v2/transcript/:transcript_id/auto-chapters** - Auto Chapters
**URL**: `https://api.assemblyai.com/v2/transcript/{transcript_id}/auto-chapters`

**Parâmetros:**
```json
{
  "transcript_id": "seu_transcript_id"
}
```

**Por que:**
- Quebra a assembleia em "capítulos" (cada ponto da Ordem do Dia)
- Cada capítulo tem título, resumo e timestamps
- Perfeito para estruturar: "1. Aprovação das Contas", "2. Eleição de Síndico", etc.

---

### **4. POST /v2/transcript/:transcript_id/summarization** - Resumo
**URL**: `https://api.assemblyai.com/v2/transcript/{transcript_id}/summarization`

**Parâmetros:**
```json
{
  "transcript_id": "seu_transcript_id",
  "type": "bullets",
  "model": "informative"
}
```

**Opções:**
- `type`: "bullets" (resumo em pontos) | "paragraph" (parágrafo corrido) | "gist" (ultra-conciso)
- `model`: "informative" (detalhado) | "conversational" (natural)

**Por que:**
- Gera "Decisões Tomadas" ou seção de destaques
- Ideal para a seção de "Deliberações"

---

### **5. POST /v2/transcript/:transcript_id/topic-detection** - Detecção de Tópicos
**URL**: `https://api.assemblyai.com/v2/transcript/{transcript_id}/topic-detection`

**Parâmetros:**
```json
{
  "transcript_id": "seu_transcript_id",
  "iab_categories": true
}
```

**Por que:**
- Classifica automaticamente tópicos (Financeiro, RH, Infraestrutura, etc.)
- Útil para categorizar os itens da "Ordem do Dia"

---

### **6. POST /v2/transcript/:transcript_id/sentiment-analysis** - Análise de Sentimento
**URL**: `https://api.assemblyai.com/v2/transcript/{transcript_id}/sentiment-analysis`

**Por que:**
- Identifica sentimentos nas discussões (aprovação, preocupação, discordância)
- Útil para detectar votações acirradas

---

## Fluxo Recomendado para Sua Aplicação

```
1. [Upload Áudio/Vídeo]
   ↓
2. [POST /v2/transcript] 
   Ativa: speaker_labels, punctuate, format_text
   ↓
3. [Aguarda status === "completed"]
   ↓
4. [GET /v2/transcript/:id]
   Obtém transcrição completa com speakers
   ↓
5. [POST .../auto-chapters]
   Quebra em itens da Ordem do Dia
   ↓
6. [POST .../summarization]
   Tipo: "bullets" + model: "informative"
   ↓
7. [POST .../topic-detection]
   Classifica tópicos por seção
   ↓
8. [Processa JSON] 
   Transforma em documento .docx estruturado
   ↓
9. [Exporta] 
   Documento final com cabeçalho, votações, decisões
```

---

## Estrutura JSON da Resposta para Montar a Ata

### Transcription Response (resumido)
```json
{
  "id": "abc123",
  "status": "completed",
  "text": "texto completo da assembleia...",
  "words": [
    {
      "text": "assembleia",
      "start": 1000,
      "end": 1500,
      "speaker": "A"
    }
  ],
  "speaker_labels": [
    {
      "speaker": "A",
      "confidence": 0.95,
      "name": "Presidente"
    }
  ]
}
```

### Auto Chapters Response
```json
{
  "chapters": [
    {
      "title": "Aprovação das Contas",
      "start": 0,
      "end": 120000,
      "summary": "Apresentação das contas do período outubro/2024..."
    },
    {
      "title": "Eleição de Síndico",
      "start": 120000,
      "end": 240000,
      "summary": "Eleição da Sra. Silvana Gercke..."
    }
  ]
}
```

---

## Campos da Ata a Preencher

| Campo | Fonte | Método |
|-------|-------|--------|
| **Cabeçalho** (data, hora, local) | Manual/Config | Input do usuário |
| **Presentes** | Transcrição + Manual | Extração de speaker_labels |
| **Presidente** | Transcrição | Primeira menção |
| **Secretário** | Transcrição | Primeira menção |
| **Ordem do Dia** | Auto Chapters | Títulos dos capítulos |
| **Discussões/Votos** | Transcrição + Summarization | Texto direto + resumo |
| **Decisões** | Summarization | Tipo bullets |
| **Tópicos** | Topic Detection | Classificação automática |
| **Assinaturas** | Manual | Campos para assinatura digital |

---

## Headers Obrigatórios em Todas as Requisições

```
Authorization: <YOUR_API_KEY>
Content-Type: application/json
```

---

## Rate Limits

- **Limite padrão**: Verificar com `X-RateLimit-*` headers na resposta
- **Endpoints**: Verificar headers:
  - `X-RateLimit-Limit`
  - `X-RateLimit-Remaining`
  - `X-RateLimit-Reset`

---

## Base URL

```
https://api.assemblyai.com/v2
```

Para EU (opcional):
```
https://api.eu.assemblyai.com/v2
```

---

## Próximos Passos

1. Implementar cliente Python/SDK que chama os endpoints em sequência
2. Mapear speaker_labels para nomes reais de participantes
3. Transformar JSON em estrutura de documento .docx
4. Adicionar campos de cabeçalho (data, hora, local) manualmente ou via input
5. Gerar assinatura digital (opcional)

