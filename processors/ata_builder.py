"""Monta a estrutura da ata a partir dos dados processados da transcrição."""

import json
import logging
from typing import Optional

import assemblyai as aai

from models.ata_model import (
    AtaModel,
    Deliberacao,
    Estatisticas,
    ItemPauta,
    Participante,
    Topico,
)
from processors.transcript_processor import (
    build_chapters_from_utterances,
    build_summary_from_utterances,
    count_words,
    extract_chapters,
    extract_speakers,
    extract_summary_bullets,
    extract_topics,
    extract_utterances_for_chapter,
    format_duration,
    get_audio_duration_ms,
    get_transcript_text,
)

logger = logging.getLogger(__name__)


def map_speakers_to_participants(
    speakers: list[dict],
    participantes_json: Optional[str] = None,
) -> list[Participante]:
    """Mapeia speaker labels para nomes de participantes."""
    name_map = {}
    if participantes_json:
        try:
            names = json.loads(participantes_json)
            if isinstance(names, list):
                for i, name in enumerate(names):
                    label = chr(ord("A") + i)
                    name_map[label] = name
            elif isinstance(names, dict):
                name_map = names
        except (json.JSONDecodeError, TypeError):
            logger.warning("Não foi possível parsear JSON de participantes, usando labels")

    participants = []
    for speaker in speakers:
        label = speaker["label"]
        nome = name_map.get(label, f"Participante {label}")
        participants.append(Participante(nome=nome, speaker_label=label))

    return participants


def build_ata(
    transcript: aai.Transcript,
    participantes_json: Optional[str] = None,
    tipo_ata: str = "assembleia",
    tempo_processamento: str = "",
) -> AtaModel:
    """Constrói um AtaModel completo a partir do objeto Transcript do SDK."""
    logger.info("Montando estrutura da ata a partir da transcrição")

    ata = AtaModel(tipo_ata=tipo_ata)

    # Extrair e mapear falantes/participantes
    speakers = extract_speakers(transcript)
    ata.participantes = map_speakers_to_participants(speakers, participantes_json)

    # Definir presidente e secretário
    if len(ata.participantes) >= 1:
        ata.participantes[0].cargo = "Presidente"
        ata.presidente = ata.participantes[0]
    if len(ata.participantes) >= 2:
        ata.participantes[1].cargo = "Secretário(a)"
        ata.secretario = ata.participantes[1]

    # Extrair chapters como itens da pauta (com fallback para utterances)
    chapters = extract_chapters(transcript)
    if not chapters:
        logger.info("Auto-chapters indisponível, gerando capítulos a partir das utterances")
        chapters = build_chapters_from_utterances(transcript)

    for i, chapter in enumerate(chapters, 1):
        discussao = extract_utterances_for_chapter(
            transcript, chapter["start"], chapter["end"]
        )
        if not discussao:
            discussao = chapter.get("summary", "")

        item = ItemPauta(
            numero=i,
            titulo=chapter.get("headline", f"Item {i}"),
            discussao=discussao,
            decisoes=chapter.get("summary", ""),
            votacao="",
            timestamp_inicio=format_duration(chapter["start"]),
            timestamp_fim=format_duration(chapter["end"]),
        )
        ata.itens_pauta.append(item)

    # Extrair deliberações (com fallback para busca por keywords)
    bullets = extract_summary_bullets(transcript)
    if not bullets:
        logger.info("Summarization indisponível, extraindo deliberações das utterances")
        bullets = build_summary_from_utterances(transcript)

    for bullet in bullets:
        ata.deliberacoes.append(Deliberacao(texto=bullet))

    # Extrair tópicos (pode ficar vazio para idiomas não-inglês)
    topics = extract_topics(transcript)
    for topic in topics:
        ata.topicos.append(
            Topico(
                categoria=topic["categoria"],
                descricao="",
                relevancia=topic["relevancia"],
            )
        )

    # Calcular estatísticas
    audio_duration_ms = get_audio_duration_ms(transcript)
    ata.estatisticas = Estatisticas(
        duracao_audio=format_duration(audio_duration_ms),
        total_palavras=count_words(transcript),
        total_falantes=len(ata.participantes),
        itens_pauta=len(ata.itens_pauta),
        tempo_processamento=tempo_processamento,
    )

    # Texto completo da transcrição
    ata.transcricao_completa = get_transcript_text(transcript)

    logger.info(
        "Ata montada: %d itens, %d participantes, %d deliberações",
        len(ata.itens_pauta),
        len(ata.participantes),
        len(ata.deliberacoes),
    )

    return ata
