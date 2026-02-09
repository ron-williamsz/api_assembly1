"""Processa transcrições usando o SDK assemblyai."""

import logging
import re

import assemblyai as aai

from config import Config

logger = logging.getLogger(__name__)

# Configurar API key do SDK
aai.settings.api_key = Config.ASSEMBLYAI_API_KEY

# Idiomas que suportam summarization, auto_chapters e iab_categories
ENGLISH_MODELS_LANGUAGES = {"en", "en_au", "en_uk", "en_us"}

WORD_BOOST = [
    # Termos essenciais
    "assembleia", "deliberação", "votação", "aprovado", "rejeitado",
    "unanimidade", "maioria", "pauta", "condomínio", "síndico",
    "condômino", "edital", "convocação", "ata", "quórum", "procuração",
    # Vocabulário expandido PADRAO seção 12
    "cota ordinária", "fundo de reserva", "previsão orçamentária",
    "corpo diretivo", "conselho consultivo", "prestação de contas",
    "balancete", "rateio extraordinário", "arrecadação",
    "subsíndico", "assembleia geral ordinária",
    "assembleia geral extraordinária", "convenção condominial",
    "regulamento interno", "Zangari", "AABIC",
    "IPEVECON", "Sabesp", "INSS", "edital de convocação",
]


def transcrever_audio(
    filepath: str,
    language: str = "pt",
    speaker_labels: bool = True,
    speakers_expected: int = 5,
) -> aai.Transcript:
    """Transcreve um arquivo de áudio usando o SDK AssemblyAI."""
    logger.info("Iniciando transcrição: %s (idioma: %s)", filepath, language)

    is_english = language in ENGLISH_MODELS_LANGUAGES

    config_kwargs = {
        "language_code": language,
        "language_detection": False,
        "punctuate": True,
        "format_text": True,
        "speaker_labels": speaker_labels,
        "speakers_expected": speakers_expected if speaker_labels else None,
        "word_boost": WORD_BOOST if not is_english else None,
        "boost_param": "high" if not is_english else None,
    }

    # summarization, auto_chapters e iab_categories só disponíveis em inglês
    if is_english:
        config_kwargs["auto_chapters"] = True
        config_kwargs["summarization"] = True
        config_kwargs["summary_model"] = aai.SummarizationModel.informative
        config_kwargs["summary_type"] = aai.SummarizationType.bullets
        config_kwargs["iab_categories"] = True

    config = aai.TranscriptionConfig(**config_kwargs)

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(filepath, config=config)

    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(f"Transcrição falhou: {transcript.error}")

    logger.info("Transcrição concluída. ID: %s", transcript.id)
    return transcript


def extract_speakers(transcript: aai.Transcript) -> list[dict]:
    """Extrai falantes únicos das utterances."""
    speakers = {}
    if transcript.utterances:
        for utterance in transcript.utterances:
            speaker = utterance.speaker
            if speaker not in speakers:
                speakers[speaker] = {
                    "label": speaker,
                    "first_text": utterance.text[:100],
                }
    return list(speakers.values())


def extract_chapters(transcript: aai.Transcript) -> list[dict]:
    """Extrai auto chapters (itens da pauta). Retorna lista vazia se indisponível."""
    chapters = []
    if transcript.chapters:
        for chapter in transcript.chapters:
            chapters.append(
                {
                    "headline": chapter.headline or "",
                    "summary": chapter.summary or "",
                    "gist": chapter.gist or "",
                    "start": chapter.start or 0,
                    "end": chapter.end or 0,
                }
            )
    return chapters


def build_chapters_from_utterances(transcript: aai.Transcript) -> list[dict]:
    """Constrói capítulos a partir das utterances quando auto_chapters não está disponível.

    Agrupa utterances em blocos por pausas significativas (>10s) entre falas,
    gerando itens de pauta sintéticos.
    """
    if not transcript.utterances:
        return []

    chapters = []
    current_texts = []
    current_start = None
    current_end = None
    chapter_num = 0

    PAUSE_THRESHOLD_MS = 10000  # 10 segundos de pausa = novo capítulo

    for i, utterance in enumerate(transcript.utterances):
        utt_start = utterance.start or 0
        utt_end = utterance.end or 0

        if current_start is None:
            current_start = utt_start
            current_end = utt_end
            current_texts.append(utterance.text)
            continue

        gap = utt_start - current_end

        if gap > PAUSE_THRESHOLD_MS:
            # Finalizar capítulo atual
            chapter_num += 1
            full_text = " ".join(current_texts)
            headline = full_text[:80].strip()
            if len(full_text) > 80:
                headline += "..."
            chapters.append(
                {
                    "headline": f"Item {chapter_num}",
                    "summary": full_text[:300],
                    "gist": headline,
                    "start": current_start,
                    "end": current_end,
                }
            )
            current_texts = [utterance.text]
            current_start = utt_start
            current_end = utt_end
        else:
            current_texts.append(utterance.text)
            current_end = utt_end

    # Último capítulo
    if current_texts:
        chapter_num += 1
        full_text = " ".join(current_texts)
        headline = full_text[:80].strip()
        if len(full_text) > 80:
            headline += "..."
        chapters.append(
            {
                "headline": f"Item {chapter_num}",
                "summary": full_text[:300],
                "gist": headline,
                "start": current_start or 0,
                "end": current_end or 0,
            }
        )

    return chapters


def extract_summary_bullets(transcript: aai.Transcript) -> list[str]:
    """Extrai bullets do resumo (deliberações). Retorna lista vazia se indisponível."""
    summary = transcript.summary or ""
    if not summary:
        return []
    return [line.strip("- ").strip() for line in summary.split("\n") if line.strip()]


def build_summary_from_utterances(transcript: aai.Transcript) -> list[str]:
    """Gera resumo básico a partir das utterances quando summarization não está disponível."""
    if not transcript.utterances:
        return []

    keywords = [
        "aprovad", "rejeitad", "votação", "votaçao", "unanimidade",
        "maioria", "deliber", "decidid", "ficou definid",
    ]

    bullets = []
    for utterance in transcript.utterances:
        text_lower = utterance.text.lower()
        if any(kw in text_lower for kw in keywords):
            clean = utterance.text.strip()
            if len(clean) > 20:
                bullets.append(clean[:200])

    return bullets


def extract_topics(transcript: aai.Transcript) -> list[dict]:
    """Extrai categorias IAB/tópicos. Retorna lista vazia se indisponível."""
    topics = []
    if not transcript.iab_categories or not transcript.iab_categories.summary:
        return topics

    for label, relevance in transcript.iab_categories.summary.items():
        parts = str(label).split(">")
        category = parts[-1].strip() if parts else str(label)
        topics.append({"categoria": category, "relevancia": relevance})

    topics.sort(key=lambda x: x["relevancia"], reverse=True)
    return topics[:10]


def extract_utterances_for_chapter(
    transcript: aai.Transcript, start_ms: int, end_ms: int
) -> str:
    """Extrai texto com identificação de falante para um intervalo de tempo."""
    lines = []
    if transcript.utterances:
        for utterance in transcript.utterances:
            utt_start = utterance.start or 0
            utt_end = utterance.end or 0
            if utt_start >= start_ms and utt_end <= end_ms:
                lines.append(f"[{utterance.speaker}]: {utterance.text}")
            elif utt_start > end_ms:
                break
    return "\n".join(lines)


def format_duration(ms: int) -> str:
    """Formata milissegundos para duração legível."""
    total_seconds = ms // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours}h{minutes:02d}m{seconds:02d}s"
    return f"{minutes}m{seconds:02d}s"


def count_words(transcript: aai.Transcript) -> int:
    """Conta total de palavras na transcrição."""
    text = transcript.text or ""
    return len(text.split()) if text else 0


def get_transcript_text(transcript: aai.Transcript) -> str:
    """Retorna o texto completo da transcrição."""
    return transcript.text or ""


def get_audio_duration_ms(transcript: aai.Transcript) -> int:
    """Retorna duração do áudio em milissegundos."""
    if transcript.audio_duration:
        return int(transcript.audio_duration * 1000)
    return 0


def serialize_transcript(transcript: aai.Transcript, task_id: str = "", language: str = "pt") -> dict:
    """Converte o objeto aai.Transcript em dict serializável JSON (Estágio 1)."""
    speakers = extract_speakers(transcript)
    chapters = extract_chapters(transcript)
    if not chapters:
        chapters = build_chapters_from_utterances(transcript)

    utterances = []
    if transcript.utterances:
        for utt in transcript.utterances:
            utterances.append({
                "speaker": utt.speaker,
                "text": utt.text,
                "start": utt.start or 0,
                "end": utt.end or 0,
                "confidence": utt.confidence if hasattr(utt, "confidence") else None,
            })

    audio_ms = get_audio_duration_ms(transcript)
    total_words = count_words(transcript)

    return {
        "task_id": task_id,
        "idioma": language,
        "duracao_audio": format_duration(audio_ms),
        "texto_completo": get_transcript_text(transcript),
        "falantes": speakers,
        "utterances": utterances,
        "chapters": chapters,
        "estatisticas": {
            "duracao_audio": format_duration(audio_ms),
            "total_palavras": total_words,
            "total_falantes": len(speakers),
            "itens_pauta": len(chapters),
            "tempo_processamento": "",
        },
    }
