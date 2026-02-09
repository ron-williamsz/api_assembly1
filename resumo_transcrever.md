Transcrição de Áudio com AssemblyAI - Guia Essencial
Arquitetura Básica

[Cliente] → [Flask API] → [Celery Task] → [AssemblyAI API] → [Arquivo .docx]
Dependências Mínimas

Flask>=2.0.0
assemblyai>=0.20.0
celery>=5.0.0
redis>=4.0.0
python-docx>=0.8.0
1. Configuração da API AssemblyAI

import assemblyai as aai

# Configurar chave da API (obtenha em https://www.assemblyai.com)
aai.settings.api_key = os.environ.get("ASSEMBLYAI_API_KEY", "sua_chave_aqui")
2. Transcrição Simples (Síncrona)

import assemblyai as aai

aai.settings.api_key = "sua_chave"

def transcrever_audio(filepath, language='pt', identificar_falantes=False):
    """Transcreve um arquivo de áudio usando AssemblyAI"""
    
    # Configuração básica
    config = aai.TranscriptionConfig(
        language_code=language,      # 'pt', 'en', 'es', etc.
        punctuate=True,              # Adiciona pontuação
        format_text=True,            # Formata o texto
        speaker_labels=identificar_falantes,  # Diarização
        speakers_expected=5          # Número esperado de falantes (max 10)
    )
    
    # Criar transcriber e executar
    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(filepath, config=config)
    
    # Verificar status
    if transcript.status != "completed":
        raise ValueError("Transcrição falhou")
    
    return transcript
3. Acessando os Resultados

# Texto completo
texto = transcript.text

# Com identificação de falantes (diarização)
if transcript.utterances:
    for utterance in transcript.utterances:
        falante = utterance.speaker      # "A", "B", "C", etc.
        texto = utterance.text           # Texto falado
        inicio = utterance.start / 1000  # Timestamp início (segundos)
        fim = utterance.end / 1000       # Timestamp fim (segundos)
        
        print(f"[{falante}] ({inicio:.1f}s-{fim:.1f}s): {texto}")
4. Versão Mínima Funcional (Sem Celery)

from flask import Flask, request, jsonify
import assemblyai as aai
import os

app = Flask(__name__)
aai.settings.api_key = os.environ.get("ASSEMBLYAI_API_KEY")

@app.route('/transcrever', methods=['POST'])
def transcrever():
    if 'file' not in request.files:
        return jsonify({'error': 'Arquivo não enviado'}), 400
    
    file = request.files['file']
    filepath = f"uploads/{file.filename}"
    file.save(filepath)
    
    # Parâmetros opcionais
    language = request.form.get('language', 'pt')
    speaker_labels = request.form.get('speaker_labels', 'false') == 'true'
    
    # Transcrever
    config = aai.TranscriptionConfig(
        language_code=language,
        punctuate=True,
        format_text=True,
        speaker_labels=speaker_labels
    )
    
    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(filepath, config=config)
    
    os.remove(filepath)  # Limpar arquivo
    
    if transcript.status != "completed":
        return jsonify({'error': 'Falha na transcrição'}), 500
    
    # Retornar resultado
    resultado = {'texto': transcript.text}
    
    if speaker_labels and transcript.utterances:
        resultado['utterances'] = [
            {
                'speaker': u.speaker,
                'text': u.text,
                'start': u.start,
                'end': u.end
            }
            for u in transcript.utterances
        ]
    
    return jsonify(resultado)

if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    app.run(port=5000)
5. Opções de Configuração Úteis
Parâmetro	Descrição
language_code	Idioma do áudio (pt, en, es, etc.)
punctuate	Adiciona pontuação automática
format_text	Formata números, datas, etc.
speaker_labels	Ativa diarização (identifica falantes)
speakers_expected	Número esperado de falantes (1-10)
6. Exemplo de Chamada via cURL

# Transcrição simples
curl -X POST http://localhost:5000/transcrever \
  -F "file=@audio.mp3" \
  -F "language=pt"

# Com identificação de falantes
curl -X POST http://localhost:5000/transcrever \
  -F "file=@audio.mp3" \
  -F "language=pt" \
  -F "speaker_labels=true"
Notas Importantes
Formatos suportados: MP3, WAV, M4A, FLAC, OGG, WebM, etc.
Limite de tamanho: Até 5GB por arquivo
Diarização: Funciona melhor quando cada falante fala pelo menos 30 segundos
Processamento: É assíncrono na API - arquivos grandes podem demorar
Custo: A API é paga por minuto de áudio transcrito
O código original usa Celery para processamento assíncrono, o que é útil para arquivos grandes. Se precisar apenas de transcrições rápidas de arquivos pequenos, a versão síncrona (seção 4) é suficiente.

bom é interessante ter o celery para conseguir processar paralelamente
Exato, o Celery permite processar múltiplos áudios simultaneamente. Vou complementar o resumo com a versão usando Celery:

Versão com Celery (Processamento Paralelo)
Estrutura de Arquivos

transcrever/
├── app.py              # Flask API
├── tasks.py            # Celery tasks
├── requirements.txt
├── .env
├── uploads/            # Arquivos temporários
└── processed/          # Resultados
.env

ASSEMBLYAI_API_KEY=sua_chave_aqui
REDIS_HOST=localhost
REDIS_PORT=6379
tasks.py (Worker Celery)

from celery import Celery
import assemblyai as aai
import os

# Configuração Celery + Redis
redis_host = os.environ.get("REDIS_HOST", "localhost")
redis_port = os.environ.get("REDIS_PORT", "6379")

app = Celery('tasks')
app.conf.update(
    broker_url=f"redis://{redis_host}:{redis_port}/0",
    result_backend=f"redis://{redis_host}:{redis_port}/0",
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    task_track_started=True
)

# AssemblyAI
aai.settings.api_key = os.environ.get("ASSEMBLYAI_API_KEY")

@app.task(bind=True)
def transcrever_audio(self, filepath, language='pt', speaker_labels=False):
    """Task assíncrona de transcrição"""
    
    # Atualizar status
    self.update_state(state='PROGRESS', meta={'status': 'Enviando para AssemblyAI...'})
    
    # Configurar transcrição
    config = aai.TranscriptionConfig(
        language_code=language,
        punctuate=True,
        format_text=True,
        speaker_labels=speaker_labels,
        speakers_expected=5 if speaker_labels else None
    )
    
    # Executar transcrição
    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(filepath, config=config)
    
    if transcript.status != "completed":
        raise ValueError("Transcrição falhou")
    
    # Limpar arquivo original
    if os.path.exists(filepath):
        os.remove(filepath)
    
    # Montar resultado
    resultado = {'texto': transcript.text}
    
    if speaker_labels and transcript.utterances:
        resultado['utterances'] = [
            {
                'speaker': u.speaker,
                'text': u.text,
                'start': u.start,
                'end': u.end
            }
            for u in transcript.utterances
        ]
    
    return resultado
app.py (API Flask)

from flask import Flask, request, jsonify
from celery.result import AsyncResult
from tasks import transcrever_audio, app as celery_app
import os

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/transcrever', methods=['POST'])
def enviar_transcricao():
    """Envia arquivo para fila de processamento"""
    if 'file' not in request.files:
        return jsonify({'error': 'Arquivo não enviado'}), 400
    
    file = request.files['file']
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)
    
    # Parâmetros
    language = request.form.get('language', 'pt')
    speaker_labels = request.form.get('speaker_labels', 'false') == 'true'
    
    # Enviar para fila Celery
    task = transcrever_audio.delay(filepath, language, speaker_labels)
    
    return jsonify({
        'task_id': task.id,
        'message': 'Arquivo enviado para processamento'
    })

@app.route('/status/<task_id>')
def verificar_status(task_id):
    """Verifica status de uma transcrição"""
    task = AsyncResult(task_id, app=celery_app)
    
    if task.state == 'PENDING':
        return jsonify({'state': 'PENDING', 'status': 'Aguardando...'})
    
    elif task.state == 'PROGRESS':
        return jsonify({'state': 'PROGRESS', 'status': task.info.get('status', '')})
    
    elif task.state == 'SUCCESS':
        return jsonify({'state': 'SUCCESS', 'result': task.get()})
    
    elif task.state == 'FAILURE':
        return jsonify({'state': 'FAILURE', 'error': str(task.info)})
    
    return jsonify({'state': task.state})

if __name__ == '__main__':
    app.run(port=5000)
Executando

# Terminal 1: Redis
redis-server

# Terminal 2: Celery Worker
celery -A tasks worker --loglevel=info

# Terminal 3: Flask
python app.py
Fluxo de Uso

# 1. Enviar arquivo
curl -X POST http://localhost:5000/transcrever \
  -F "file=@audio.mp3" \
  -F "language=pt"

# Resposta: {"task_id": "abc123", "message": "Arquivo enviado..."}

# 2. Verificar status (polling)
curl http://localhost:5000/status/abc123

# Resposta: {"state": "PROGRESS", "status": "Enviando para AssemblyAI..."}
# ...
# Resposta: {"state": "SUCCESS", "result": {"texto": "...", "utterances": [...]}}
Docker Compose (Opcional)

version: '3.8'
services:
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"

  worker:
    build: .
    command: celery -A tasks worker --loglevel=info
    environment:
      - ASSEMBLYAI_API_KEY=${ASSEMBLYAI_API_KEY}
      - REDIS_HOST=redis
    depends_on:
      - redis
    volumes:
      - ./uploads:/app/uploads

  api:
    build: .
    command: python app.py
    ports:
      - "5000:5000"
    environment:
      - REDIS_HOST=redis
    depends_on:
      - redis
      - worker
    volumes:
      - ./uploads:/app/uploads
Resumo: Celery vs Síncrono
Aspecto	Síncrono	Com Celery
Complexidade	Simples	Moderada
Dependências	Apenas Flask + AssemblyAI	+ Redis + Celery
Paralelismo	Não	Sim
Requisição	Bloqueia até terminar	Retorna imediatamente
Uso	Arquivos pequenos, poucos usuários	Múltiplos arquivos, produção
O Celery é a escolha certa se você precisa processar vários áudios ao mesmo tempo ou se os arquivos são grandes (evita timeout da requisição HTTP).