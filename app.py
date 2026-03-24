"""Flask API principal — Arquitetura em 2 estágios (Transcrição + Análise LLM)."""

import json
import logging
import os
import uuid

from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

from config import Config
from processors import rag_client
from processors.llm_processor import assistente_editor
from tasks import celery_app, get_redis_client, task_analyze, task_transcribe

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)
app.config["MAX_CONTENT_LENGTH"] = Config.MAX_FILE_SIZE
CORS(app)

# Ensure required directories exist
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(Config.PROCESSED_FOLDER, exist_ok=True)


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_EXTENSIONS


# ──────────────────────────────────────────────
# ESTÁGIO 1 — Transcrição
# ──────────────────────────────────────────────


@app.route("/transcrever", methods=["POST"])
def transcrever():
    """POST /transcrever — Envia áudio para transcrição (Estágio 1)."""
    if "file" not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado. Use o campo 'file'."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Nome de arquivo vazio."}), 400

    if not allowed_file(file.filename):
        return (
            jsonify(
                {
                    "error": f"Formato não suportado. Formatos aceitos: {', '.join(Config.ALLOWED_EXTENSIONS)}"
                }
            ),
            400,
        )

    language = request.form.get("language", "pt")
    speaker_labels = request.form.get("speaker_labels", "true").lower() == "true"

    # Save uploaded file
    task_id = str(uuid.uuid4())
    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{task_id}.{ext}"
    filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
    file.save(filepath)

    logger.info("File saved: %s (task: %s)", filepath, task_id)

    # Enqueue Estágio 1
    task = task_transcribe.apply_async(
        kwargs={
            "file_path": filepath,
            "language": language,
            "speaker_labels": speaker_labels,
        },
        task_id=task_id,
    )

    return (
        jsonify(
            {
                "task_id": task.id,
                "message": "Arquivo enviado para transcrição (Estágio 1)",
                "status_url": f"/status/{task.id}",
            }
        ),
        202,
    )


@app.route("/transcricao/<task_id>", methods=["GET"])
def get_transcricao(task_id: str):
    """GET /transcricao/<task_id> — Retorna transcrição bruta em JSON."""
    r = get_redis_client()
    data = r.get(f"transcricao:{task_id}")

    if not data:
        return jsonify({"error": "Transcrição não encontrada ou expirada."}), 404

    return jsonify(json.loads(data)), 200


# ──────────────────────────────────────────────
# ESTÁGIO 2 — Análise LLM
# ──────────────────────────────────────────────


@app.route("/analisar/<transcricao_task_id>", methods=["POST"])
def analisar(transcricao_task_id: str):
    """POST /analisar/<transcricao_task_id> — Inicia análise LLM (Estágio 2)."""
    # Verificar se transcrição existe
    r = get_redis_client()
    if not r.exists(f"transcricao:{transcricao_task_id}"):
        return (
            jsonify(
                {
                    "error": "Transcrição não encontrada ou expirada. Execute /transcrever primeiro."
                }
            ),
            404,
        )

    participantes = request.form.get("participantes", None)
    dados_condominio = request.form.get("dados_condominio", None)
    condominio_context = request.form.get("condominio_context", None)

    # Também aceitar JSON body
    if request.is_json:
        body = request.get_json()
        participantes = participantes or body.get("participantes")
        dados_condominio = dados_condominio or body.get("dados_condominio")
        condominio_context = condominio_context or body.get("condominio_context")

    # Se participantes for dict/list, converter para JSON string
    if isinstance(participantes, (dict, list)):
        participantes = json.dumps(participantes, ensure_ascii=False)
    if isinstance(dados_condominio, (dict, list)):
        dados_condominio = json.dumps(dados_condominio, ensure_ascii=False)

    analyze_task_id = str(uuid.uuid4())

    task = task_analyze.apply_async(
        kwargs={
            "transcricao_task_id": transcricao_task_id,
            "participantes_json": participantes,
            "dados_condominio": dados_condominio,
            "condominio_context": condominio_context,
        },
        task_id=analyze_task_id,
    )

    return (
        jsonify(
            {
                "task_id": task.id,
                "transcricao_task_id": transcricao_task_id,
                "message": "Análise LLM iniciada (Estágio 2)",
                "status_url": f"/status/{task.id}",
            }
        ),
        202,
    )


@app.route("/ata/<task_id>", methods=["GET"])
def get_ata(task_id: str):
    """GET /ata/<task_id> — Retorna ata estruturada em JSON."""
    r = get_redis_client()
    data = r.get(f"ata:{task_id}")

    if not data:
        return jsonify({"error": "Ata não encontrada ou expirada."}), 404

    return jsonify(json.loads(data)), 200


# ──────────────────────────────────────────────
# ASSISTENTE DE EDITOR (LLM)
# ──────────────────────────────────────────────


@app.route("/assistente", methods=["POST"])
def assistente():
    """POST /assistente — Assistente LLM para edição interativa de atas.

    Aceita JSON body:
    {
        "instrucao": "formalize este parágrafo",       (obrigatório)
        "texto": "o sindico falou que...",              (obrigatório)
        "contexto": "dados da transcrição...",          (opcional)
        "historico": [{"role":"user","content":"..."}], (opcional)
        "condominio_context": "cond_0388",              (opcional — RAG-Z)
        "stream": false                                 (opcional, default false)
    }
    """
    if not request.is_json:
        return jsonify({"error": "Content-Type deve ser application/json."}), 400

    body = request.get_json()

    instrucao = body.get("instrucao", "").strip()
    texto = body.get("texto", "").strip()

    if not instrucao:
        return jsonify({"error": "Campo 'instrucao' é obrigatório."}), 400
    if not texto:
        return jsonify({"error": "Campo 'texto' é obrigatório."}), 400

    contexto = body.get("contexto", None)
    historico = body.get("historico", None)
    stream = body.get("stream", False)
    condominio_context = body.get("condominio_context", None)

    # Opcionalmente carregar contexto da transcrição do Redis
    transcricao_task_id = body.get("transcricao_task_id")
    if transcricao_task_id and not contexto:
        r = get_redis_client()
        transcricao_raw = r.get(f"transcricao:{transcricao_task_id}")
        if transcricao_raw:
            transcricao_data = json.loads(transcricao_raw)
            contexto = transcricao_data.get("texto_completo", "")

    try:
        if stream:
            def generate():
                for event in assistente_editor(
                    instrucao=instrucao,
                    texto=texto,
                    contexto=contexto,
                    historico=historico,
                    stream=True,
                    condominio_context=condominio_context,
                ):
                    if "content" in event:
                        yield f"data: {json.dumps({'content': event['content']}, ensure_ascii=False)}\n\n"
                    elif "fontes_rag" in event:
                        yield f"data: {json.dumps({'fontes_rag': event['fontes_rag']}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

            return Response(
                generate(),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        result = assistente_editor(
            instrucao=instrucao,
            texto=texto,
            contexto=contexto,
            historico=historico,
            stream=False,
            condominio_context=condominio_context,
        )

        return jsonify(result), 200

    except Exception as exc:
        logger.exception("Erro no assistente: %s", exc)
        return jsonify({"error": f"Erro ao processar: {str(exc)}"}), 500


# ──────────────────────────────────────────────
# RAG-Z INTEGRATION
# ──────────────────────────────────────────────


@app.route("/contextos-rag", methods=["GET"])
def contextos_rag():
    """GET /contextos-rag — Lista contextos disponíveis no RAG-Z."""
    disponivel = rag_client.is_available()

    if not disponivel:
        return jsonify({
            "disponivel": False,
            "contextos": [],
            "total": 0,
            "mensagem": "API RAG-Z não está disponível no momento.",
        }), 200

    contextos = rag_client.list_contexts()

    return jsonify({
        "disponivel": True,
        "contextos": contextos,
        "total": len(contextos),
    }), 200


@app.route("/contextos-rag/<context_name>/stats", methods=["GET"])
def contextos_rag_stats(context_name: str):
    """GET /contextos-rag/<name>/stats — Stats de um contexto RAG-Z."""
    stats = rag_client.get_context_stats(context_name)

    if stats is None:
        return jsonify({"error": f"Contexto '{context_name}' não encontrado no RAG-Z."}), 404

    return jsonify(stats), 200


# ──────────────────────────────────────────────
# ENDPOINTS COMUNS
# ──────────────────────────────────────────────


@app.route("/status/<task_id>", methods=["GET"])
def status(task_id: str):
    """GET /status/<task_id> — Status de qualquer task (transcrição ou análise)."""
    task = celery_app.AsyncResult(task_id)

    response = {
        "task_id": task_id,
        "state": task.state,
    }

    if task.state == "PENDING":
        response["progress"] = {
            "current": 0,
            "total": 100,
            "message": "Aguardando na fila de processamento...",
        }
    elif task.state == "PROGRESS":
        info = task.info or {}
        response["progress"] = {
            "current": info.get("current", 0),
            "total": info.get("total", 100),
            "stage": info.get("stage", ""),
            "message": info.get("message", "Processando..."),
        }
    elif task.state == "SUCCESS":
        result = task.result or {}
        response["progress"] = {
            "current": 100,
            "total": 100,
            "message": "Concluído com sucesso!",
        }
        response["resultado"] = result
    elif task.state == "FAILURE":
        info = task.info
        error_msg = str(info) if info else "Erro desconhecido"
        response["progress"] = {
            "current": 0,
            "total": 100,
            "message": f"Falha no processamento: {error_msg}",
        }
    else:
        response["progress"] = {
            "current": 0,
            "total": 100,
            "message": f"Estado: {task.state}",
        }

    return jsonify(response), 200


@app.route("/download/<task_id>", methods=["GET"])
def download(task_id: str):
    """GET /download/<task_id> — Download do .docx gerado."""
    # Aceitar tanto task_id puro quanto task_id.docx
    clean_id = task_id.replace(".docx", "")
    filename = f"{clean_id}.docx"
    safe_filename = secure_filename(filename)

    filepath = os.path.join(Config.PROCESSED_FOLDER, safe_filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "Documento não encontrado."}), 404

    return send_from_directory(
        Config.PROCESSED_FOLDER,
        safe_filename,
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.route("/cancelar/<task_id>", methods=["POST"])
def cancelar(task_id: str):
    """POST /cancelar/<task_id> — Cancela task em andamento."""
    celery_app.control.revoke(task_id, terminate=True)
    logger.info("Task cancelled: %s", task_id)

    return (
        jsonify(
            {
                "message": "Task cancelada",
                "task_id": task_id,
            }
        ),
        200,
    )


@app.route("/health", methods=["GET"])
def health():
    """GET /health — Health check."""
    return jsonify({"status": "ok", "service": "api-transcricao-atas", "version": "2.0"}), 200


# ──────────────────────────────────────────────
# ERROR HANDLERS
# ──────────────────────────────────────────────


@app.errorhandler(413)
def file_too_large(e):
    max_size_mb = Config.MAX_FILE_SIZE / (1024 * 1024)
    return (
        jsonify({"error": f"Arquivo excede o tamanho máximo de {max_size_mb:.0f}MB."}),
        413,
    )


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Recurso não encontrado."}), 404


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Erro interno do servidor."}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.FLASK_DEBUG)
