"""Celery tasks para processamento assíncrono — 2 estágios."""

import json
import logging
import os
import time

import redis
from celery import Celery

from config import Config
from processors.docx_generator import generate_docx_from_ata_estruturada
from processors.llm_processor import analyze_transcription
from processors.transcript_processor import (
    format_duration,
    serialize_transcript,
    transcrever_audio,
)

logger = logging.getLogger(__name__)

celery_app = Celery(
    "tasks",
    broker=Config.CELERY_BROKER_URL,
    backend=Config.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


def get_redis_client() -> redis.Redis:
    """Retorna um cliente Redis para armazenamento inter-estágio."""
    return redis.Redis.from_url(Config.REDIS_URL, decode_responses=True)


# ──────────────────────────────────────────────
# ESTÁGIO 1 — Transcrição (AssemblyAI)
# ──────────────────────────────────────────────


@celery_app.task(bind=True, name="tasks.task_transcribe", max_retries=3)
def task_transcribe(
    self,
    file_path: str,
    language: str = "pt",
    speaker_labels: bool = True,
):
    """Estágio 1: transcreve áudio via AssemblyAI SDK e armazena resultado no Redis."""
    start_time = time.time()
    task_id = self.request.id

    try:
        # Passo 1: Transcrever áudio
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 10,
                "total": 100,
                "stage": "transcricao",
                "message": "Enviando áudio e iniciando transcrição com AssemblyAI... (Passo 1 de 2)",
            },
        )

        transcript = transcrever_audio(
            filepath=file_path,
            language=language,
            speaker_labels=speaker_labels,
        )

        # Passo 2: Serializar e armazenar no Redis
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 80,
                "total": 100,
                "stage": "transcricao",
                "message": "Processando e armazenando transcrição... (Passo 2 de 2)",
            },
        )

        elapsed = time.time() - start_time
        tempo_proc = format_duration(int(elapsed * 1000))

        transcricao_data = serialize_transcript(transcript, task_id=task_id, language=language)
        transcricao_data["estatisticas"]["tempo_processamento"] = tempo_proc

        # Armazenar no Redis com TTL de 72h
        r = get_redis_client()
        r.setex(
            f"transcricao:{task_id}",
            Config.TRANSCRIPTION_TTL,
            json.dumps(transcricao_data, ensure_ascii=False),
        )

        # Limpar arquivo temporário
        _cleanup_file(file_path)

        result = {
            "transcricao_url": f"/transcricao/{task_id}",
            "analisar_url": f"/analisar/{task_id}",
            "estatisticas": transcricao_data["estatisticas"],
        }

        logger.info("Task transcribe %s concluída com sucesso", task_id)
        return result

    except Exception as exc:
        logger.exception("Task transcribe %s falhou: %s", task_id, exc)
        _cleanup_file(file_path)

        error_msg = str(exc)
        serializable_exc = RuntimeError(error_msg)

        try:
            raise self.retry(exc=serializable_exc, countdown=30)
        except self.MaxRetriesExceededError:
            logger.error("Task transcribe %s: máximo de retries atingido", task_id)
            raise RuntimeError(f"Falha na transcrição após múltiplas tentativas: {error_msg}")


# ──────────────────────────────────────────────
# ESTÁGIO 2 — Análise LLM (OpenAI GPT)
# ──────────────────────────────────────────────


@celery_app.task(bind=True, name="tasks.task_analyze", max_retries=2)
def task_analyze(
    self,
    transcricao_task_id: str,
    participantes_json: str = None,
    dados_condominio: str = None,
    condominio_context: str = None,
):
    """Estágio 2: analisa transcrição com LLM e gera ata estruturada + .docx."""
    start_time = time.time()
    task_id = self.request.id

    try:
        # Passo 1: Buscar transcrição do Redis
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 10,
                "total": 100,
                "stage": "analise",
                "message": "Recuperando transcrição para análise... (Passo 1 de 3)",
            },
        )

        r = get_redis_client()
        transcricao_raw = r.get(f"transcricao:{transcricao_task_id}")
        if not transcricao_raw:
            raise RuntimeError(
                f"Transcrição {transcricao_task_id} não encontrada ou expirada no Redis."
            )

        transcricao_data = json.loads(transcricao_raw)

        # Passo 2: Analisar com LLM
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 30,
                "total": 100,
                "stage": "analise",
                "message": "Analisando transcrição com IA (OpenAI GPT)... (Passo 2 de 3)",
            },
        )

        analysis_result = analyze_transcription(
            transcricao=transcricao_data,
            participantes_json=participantes_json,
            dados_condominio=dados_condominio,
            condominio_context=condominio_context,
        )
        ata_data = analysis_result["ata"]
        fontes_rag = analysis_result.get("fontes_rag", [])

        # Adicionar metadados
        elapsed = time.time() - start_time
        tempo_proc = format_duration(int(elapsed * 1000))

        ata_data["transcricao_task_id"] = transcricao_task_id
        if "estatisticas" not in ata_data:
            ata_data["estatisticas"] = {}
        ata_data["estatisticas"]["tempo_processamento"] = tempo_proc
        # Copiar stats da transcrição original
        stats_orig = transcricao_data.get("estatisticas", {})
        ata_data["estatisticas"]["duracao_audio"] = stats_orig.get("duracao_audio", "")
        ata_data["estatisticas"]["total_palavras"] = stats_orig.get("total_palavras", 0)
        ata_data["estatisticas"]["total_falantes"] = stats_orig.get("total_falantes", 0)
        ata_data["estatisticas"]["itens_pauta"] = len(ata_data.get("ordem_do_dia", []))

        # Passo 3: Gerar .docx
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 80,
                "total": 100,
                "stage": "analise",
                "message": "Gerando documento .docx... (Passo 3 de 3)",
            },
        )

        output_filename = f"{task_id}.docx"
        output_path = os.path.join(Config.PROCESSED_FOLDER, output_filename)
        generate_docx_from_ata_estruturada(ata_data, output_path)

        # Armazenar ata no Redis com TTL de 72h
        r.setex(
            f"ata:{task_id}",
            Config.TRANSCRIPTION_TTL,
            json.dumps(ata_data, ensure_ascii=False),
        )

        elapsed = time.time() - start_time
        tempo_proc = format_duration(int(elapsed * 1000))
        ata_data["estatisticas"]["tempo_processamento"] = tempo_proc

        result = {
            "ata_url": f"/ata/{task_id}",
            "documento_url": f"/download/{task_id}",
            "transcricao_task_id": transcricao_task_id,
            "estatisticas": ata_data["estatisticas"],
        }
        if fontes_rag:
            result["fontes_rag"] = fontes_rag

        logger.info("Task analyze %s concluída com sucesso", task_id)
        return result

    except Exception as exc:
        logger.exception("Task analyze %s falhou: %s", task_id, exc)

        error_msg = str(exc)
        serializable_exc = RuntimeError(error_msg)

        try:
            raise self.retry(exc=serializable_exc, countdown=30)
        except self.MaxRetriesExceededError:
            logger.error("Task analyze %s: máximo de retries atingido", task_id)
            raise RuntimeError(f"Falha na análise após múltiplas tentativas: {error_msg}")


def _cleanup_file(file_path: str):
    """Remove arquivo temporário de forma segura."""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info("Arquivo temporário removido: %s", file_path)
    except OSError as e:
        logger.warning("Não foi possível remover arquivo temp %s: %s", file_path, e)
