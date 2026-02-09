# Prompt: Sistema de API de Transcrição para Atas de Assembleia

## 📋 CONTEXTO DO PROJETO

Você será responsável por construir um **Sistema de API de Transcrição de Áudio para Atas de Assembleia** que integra a plataforma AssemblyAI com processamento assíncrono, transformando gravações de áudio em documentos estruturados em formato .docx.

O sistema deve:
- Receber arquivos de áudio/vídeo de assembleias/reuniões
- Transcrever automaticamente com identificação de falantes
- Estruturar a transcrição no formato padrão de ata
- Gerar documento Word (.docx) profissional e pronto para assinatura

---

## 🏗️ ARQUITETURA DO SISTEMA

```
[Cliente] 
   ↓ (POST /transcrever)
[Flask API] 
   ↓ (enfileira)
[Redis Queue] 
   ↓ (processa)
[Celery Worker] 
   ↓ (chama)
[AssemblyAI API] 
   ↓ (processa)
[Endpoints Específicos para Ata]
   ├── /v2/transcript (transcrição com speaker labels)
   ├── /v2/transcript/{id}/auto-chapters (quebra por tópicos)
   ├── /v2/transcript/{id}/summarization (resumos em bullets)
   └── /v2/transcript/{id}/topic-detection (classificação)
   ↓ (transforma JSON)
[Processador de Ata]
   ↓ (monta estrutura)
[Gerador .docx]
   ↓ (documento final)
[Cliente] (documento pronto)
```

---

## 📦 DEPENDÊNCIAS

```
Flask>=2.0.0
assemblyai>=0.20.0
celery>=5.0.0
redis>=4.0.0
python-docx>=0.8.0
requests>=2.28.0
python-dotenv>=0.19.0
```

---

## 🎯 REQUISITOS FUNCIONAIS

### 1. **Endpoints da API**

#### `POST /transcrever`
- **Descrição**: Envia arquivo de áudio/vídeo para transcrição
- **Parâmetros**:
  - `file` (multipart/form-data): Arquivo de áudio (.mp3, .wav, .m4a, .flac, .ogg, .webm)
  - `language` (form): Idioma do áudio (padrão: "pt" para português Brasil)
  - `speaker_labels` (form): true/false - Ativar identificação de falantes (padrão: true)
  - `participantes` (form): JSON com nomes dos participantes (opcional)
  - `tipo_ata` (form): "assembleia" | "reuniao" (padrão: "assembleia")
- **Resposta**:
  ```json
  {
    "task_id": "abc-123-xyz",
    "message": "Arquivo enviado para processamento",
    "status_url": "/status/abc-123-xyz"
  }
  ```
- **Status HTTP**: 202 Accepted

#### `GET /status/<task_id>`
- **Descrição**: Verifica status de uma transcrição
- **Resposta**:
  ```json
  {
    "task_id": "abc-123-xyz",
    "state": "PROGRESS|SUCCESS|FAILURE|PENDING",
    "progress": {
      "current": 45,
      "total": 100,
      "message": "Processando auto-chapters..."
    },
    "resultado": {
      "documento_url": "/download/abc-123-xyz.docx",
      "estatisticas": {
        "duracao_audio": "45m30s",
        "total_palavras": 3500,
        "total_falantes": 5,
        "itens_pauta": 8
      }
    }
  }
  ```
- **Status HTTP**: 200 OK

#### `GET /download/<task_id>.docx`
- **Descrição**: Faz download do documento .docx gerado
- **Resposta**: Arquivo .docx binário
- **Status HTTP**: 200 OK

#### `POST /cancelar/<task_id>`
- **Descrição**: Cancela uma transcrição em andamento
- **Resposta**:
  ```json
  {
    "message": "Transcrição cancelada",
    "task_id": "abc-123-xyz"
  }
  ```
- **Status HTTP**: 200 OK

---

### 2. **Fluxo de Transcrição**

O sistema deve seguir este fluxo para processar cada áudio:

1. **Envio e Validação**
   - Receber arquivo (máximo 5GB)
   - Validar formato (MP3, WAV, M4A, FLAC, OGG, WebM)
   - Salvar em pasta temporária
   - Enfileirar task no Celery

2. **Transcrição Base** (POST /v2/transcript)
   - Parâmetros:
     ```python
     {
       "audio_url": "url_do_arquivo",
       "language_code": "pt",
       "language_detection": False,
       "punctuate": True,
       "format_text": True,
       "speaker_labels": True,
       "speakers_expected": 5,
       "word_boost": [
         "assembleia", "deliberação", "votação", "aprovado", 
         "rejeitado", "unanimidade", "maioria", "pauta"
       ],
       "boost_param": "high"
     }
     ```
   - Aguardar status === "completed"
   - Salvar ID da transcrição

3. **Auto Chapters** (POST /v2/transcript/{id}/auto-chapters)
   - Quebrar transcrição em capítulos
   - Cada capítulo = um item da Ordem do Dia
   - Extrair títulos, resumos e timestamps

4. **Summarization** (POST /v2/transcript/{id}/summarization)
   - Tipo: "bullets"
   - Modelo: "informative"
   - Gerar decisões/deliberações principais

5. **Topic Detection** (POST /v2/transcript/{id}/topic-detection)
   - Ativar `iab_categories: true`
   - Classificar tópicos por seção

6. **Processamento e Estruturação**
   - Mapear speaker labels para nomes reais (se fornecido)
   - Organizar seções da ata
   - Compilar votações e decisões
   - Calcular estatísticas (duração, total palavras, etc)

7. **Geração do Documento .docx**
   - Criar arquivo .docx estruturado
   - Adicionar cabeçalho (edital, data, hora, local, presentes)
   - Adicionar Ordem do Dia com discussões
   - Adicionar seção de Deliberações
   - Adicionar tópicos classificados
   - Adicionar assinaturas digitais (placeholders)
   - Salvar em pasta `processed/`

8. **Disponibilização**
   - Armazenar resultado em cache Redis
   - Disponibilizar download via GET /download/{task_id}.docx
   - Limpar arquivo temporário

---

### 3. **Estrutura do Documento .docx Gerado**

```
═══════════════════════════════════════════════════════════

                    ATA DE ASSEMBLEIA

═══════════════════════════════════════════════════════════

EDITAL DE CONVOCAÇÃO: [extraído ou padrão]
DATA DA ASSEMBLEIA: [extraído ou fornecido]
HORÁRIO: [extraído ou fornecido]
LOCAL: [extraído ou fornecido]

PRESENTES OU REPRESENTADOS: 
  - [Falante A] (identificado automaticamente)
  - [Falante B]
  - [Falante C]

PRESIDENTE: [primeiro falante identificado]
SECRETÁRIO: [segundo falante identificado]

───────────────────────────────────────────────────────────
ORDEM DO DIA
───────────────────────────────────────────────────────────

1. [Título do Auto Chapter 1]
   
   [Texto da discussão extraído da transcrição com timestamps]
   
   Decisões: [Resumo em bullets do que foi aprovado/rejeitado]
   
   Votação: [Unanimidade/Maioria]

2. [Título do Auto Chapter 2]
   
   [Texto da discussão...]
   
   Decisões: [...]
   
   Votação: [...]

[... mais itens da pauta ...]

───────────────────────────────────────────────────────────
DELIBERAÇÕES PRINCIPAIS
───────────────────────────────────────────────────────────

• [Ponto 1 do resumo em bullets]
• [Ponto 2 do resumo em bullets]
• [Ponto 3 do resumo em bullets]

───────────────────────────────────────────────────────────
TÓPICOS ABORDADOS
───────────────────────────────────────────────────────────

Financeiro: [descrição ou itens relacionados]
Infraestrutura: [descrição ou itens relacionados]
Recursos Humanos: [descrição ou itens relacionados]

───────────────────────────────────────────────────────────
ASSINATURAS
───────────────────────────────────────────────────────────

Presidente: ________________________  Data: __/__/_____

Secretário: ________________________  Data: __/__/_____

═══════════════════════════════════════════════════════════
```

---

### 4. **Configuração da API AssemblyAI**

- **Base URL**: `https://api.assemblyai.com/v2`
- **Autenticação**: Header `Authorization: <API_KEY>`
- **Timeout**: Transcrições podem levar horas (não bloquear HTTP)
- **Polling**: Implementar verificação de status a cada 5 segundos até conclusão

---

## 🔧 REQUISITOS TÉCNICOS

### Backend
- **Framework**: Flask 2.0+
- **Processamento Assíncrono**: Celery com Redis
- **Geração de Documentos**: python-docx
- **Idioma**: Python 3.9+
- **Servidor**: Gunicorn ou similar em produção

### Estrutura de Pastas
```
api-transcricao-atas/
├── app.py                 # Flask API principal
├── tasks.py              # Celery tasks
├── config.py             # Configurações
├── processors/
│   ├── __init__.py
│   ├── transcript_processor.py    # Processa resposta AssemblyAI
│   ├── ata_builder.py             # Monta estrutura da ata
│   └── docx_generator.py          # Gera arquivo .docx
├── models/
│   ├── __init__.py
│   └── ata_model.py               # Modelo de dados da ata
├── requirements.txt
├── .env.example
├── .env
├── Dockerfile
├── docker-compose.yml
├── uploads/               # Arquivos temporários
├── processed/             # Documentos gerados
└── tests/
    └── test_api.py
```

### Variáveis de Ambiente
```
ASSEMBLYAI_API_KEY=sua_chave_aqui
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
FLASK_ENV=production
FLASK_DEBUG=False
MAX_FILE_SIZE=5368709120  # 5GB em bytes
UPLOAD_FOLDER=uploads
PROCESSED_FOLDER=processed
```

---

## ✅ REQUISITOS NÃO-FUNCIONAIS

1. **Performance**
   - Resposta imediata do endpoint /transcrever (< 1s)
   - Status de progresso disponível em tempo real
   - Cache de resultados por 48 horas

2. **Segurança**
   - Validação de tipo de arquivo
   - Limite de tamanho de arquivo
   - Tokens de acesso para download (task_id como token)
   - Limpeza automática de arquivos temporários após 24h

3. **Confiabilidade**
   - Retry automático em caso de falha da AssemblyAI
   - Logging detalhado de todas as operações
   - Tratamento de erros com mensagens claras

4. **Escalabilidade**
   - Celery permite múltiplos workers
   - Redis para fila distribuída
   - Docker Compose para deploy simplificado

---

## 📝 EXEMPLO DE USO

### 1. Enviar arquivo
```bash
curl -X POST http://localhost:5000/transcrever \
  -F "file=@assembleia_25nov2025.mp3" \
  -F "language=pt" \
  -F "speaker_labels=true" \
  -F "tipo_ata=assembleia"
```

**Resposta:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Arquivo enviado para processamento",
  "status_url": "/status/550e8400-e29b-41d4-a716-446655440000"
}
```

### 2. Verificar status
```bash
curl http://localhost:5000/status/550e8400-e29b-41d4-a716-446655440000
```

**Resposta (em progresso):**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "state": "PROGRESS",
  "progress": {
    "current": 65,
    "total": 100,
    "message": "Processando auto-chapters... (Passo 3 de 5)"
  }
}
```

**Resposta (concluído):**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "state": "SUCCESS",
  "progress": {
    "current": 100,
    "total": 100,
    "message": "Ata gerada com sucesso!"
  },
  "resultado": {
    "documento_url": "/download/550e8400-e29b-41d4-a716-446655440000.docx",
    "estatisticas": {
      "duracao_audio": "45m30s",
      "total_palavras": 3456,
      "total_falantes": 5,
      "itens_pauta": 8,
      "tempo_processamento": "7m30s"
    }
  }
}
```

### 3. Fazer download
```bash
curl -O http://localhost:5000/download/550e8400-e29b-41d4-a716-446655440000.docx
```

---

## 🚀 DELIVERABLES

1. **Código fonte completo** com estrutura proposta
2. **API funcional** com todos os endpoints documentados
3. **Dockerfile e docker-compose.yml** para deploy
4. **Testes unitários** e de integração
5. **Documentação de API** (Swagger/OpenAPI)
6. **Guia de instalação e uso**
7. **Exemplo de arquivo .docx gerado**

---

## 📌 NOTAS IMPORTANTES

- A API AssemblyAI é **assíncrona**: arquivos grandes podem levar horas
- O Celery garante que múltiplos arquivos sejam processados em paralelo
- O Redis armazena estado das tasks e cache de resultados
- Documentos podem ser armazenados localmente ou em S3/Google Cloud Storage
- Considerar webhook para notificar cliente quando ata está pronta

---

## ✨ PRÓXIMAS FASES (Futuro)

- [ ] Integração com Google Drive/Dropbox para armazenamento
- [ ] Webhook para notificação de conclusão
- [ ] Dashboard web para visualizar status de transcrições
- [ ] Exportar em outros formatos (PDF, DOCX, Markdown)
- [ ] Assinatura digital com certificado
- [ ] Integração com ferramentas de collaboration (Google Docs, OneDrive)

---

**Versão**: 1.0  
**Data**: Fevereiro 2026  
**Status**: Especificação Completa
