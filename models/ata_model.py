from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Participante:
    nome: str
    speaker_label: str = ""
    cargo: str = ""


@dataclass
class ItemPauta:
    numero: int
    titulo: str
    discussao: str
    decisoes: str = ""
    votacao: str = ""
    timestamp_inicio: str = ""
    timestamp_fim: str = ""


@dataclass
class Deliberacao:
    texto: str


@dataclass
class Topico:
    categoria: str
    descricao: str
    relevancia: float = 0.0


@dataclass
class Estatisticas:
    duracao_audio: str = ""
    total_palavras: int = 0
    total_falantes: int = 0
    itens_pauta: int = 0
    tempo_processamento: str = ""


# ──────────────────────────────────────────────
# Estágio 1 — Transcrição bruta (AssemblyAI)
# ──────────────────────────────────────────────


@dataclass
class TranscricaoBruta:
    """Resultado serializado da transcrição do AssemblyAI."""

    task_id: str = ""
    idioma: str = "pt"
    duracao_audio: str = ""
    texto_completo: str = ""
    falantes: list[dict] = field(default_factory=list)
    utterances: list[dict] = field(default_factory=list)
    chapters: list[dict] = field(default_factory=list)
    estatisticas: Estatisticas = field(default_factory=Estatisticas)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "idioma": self.idioma,
            "duracao_audio": self.duracao_audio,
            "texto_completo": self.texto_completo,
            "falantes": self.falantes,
            "utterances": self.utterances,
            "chapters": self.chapters,
            "estatisticas": {
                "duracao_audio": self.estatisticas.duracao_audio,
                "total_palavras": self.estatisticas.total_palavras,
                "total_falantes": self.estatisticas.total_falantes,
                "itens_pauta": self.estatisticas.itens_pauta,
                "tempo_processamento": self.estatisticas.tempo_processamento,
            },
        }


# ──────────────────────────────────────────────
# Estágio 2 — Ata estruturada (LLM)
# ──────────────────────────────────────────────


@dataclass
class AtaEstruturada:
    """Ata formal no padrão PADRAO seção 10 — produzida pelo LLM."""

    tipo_assembleia: str = "AGO"
    condominio: dict = field(default_factory=lambda: {"nome": "", "endereco": "", "cnpj": ""})
    cabecalho: dict = field(
        default_factory=lambda: {
            "edital_convocacao": "",
            "data_assembleia": "",
            "horario": "",
            "convocacao": "segunda",
            "local": "",
            "formato": "presencial",
        }
    )
    mesa: dict = field(
        default_factory=lambda: {
            "presidente": {"nome": "", "unidade": ""},
            "secretario": {"nome": "", "cargo": "", "empresa": None},
        }
    )
    ordem_do_dia: list[dict] = field(default_factory=list)
    deliberacoes: list[dict] = field(default_factory=list)
    assuntos_gerais: list[dict] = field(default_factory=list)
    encerramento: dict = field(
        default_factory=lambda: {"formula": "", "data_extenso": ""}
    )
    estatisticas: Estatisticas = field(default_factory=Estatisticas)
    transcricao_task_id: str = ""

    def to_dict(self) -> dict:
        return {
            "tipo_assembleia": self.tipo_assembleia,
            "condominio": self.condominio,
            "cabecalho": self.cabecalho,
            "mesa": self.mesa,
            "ordem_do_dia": self.ordem_do_dia,
            "deliberacoes": self.deliberacoes,
            "assuntos_gerais": self.assuntos_gerais,
            "encerramento": self.encerramento,
            "estatisticas": {
                "duracao_audio": self.estatisticas.duracao_audio,
                "total_palavras": self.estatisticas.total_palavras,
                "total_falantes": self.estatisticas.total_falantes,
                "itens_pauta": self.estatisticas.itens_pauta,
                "tempo_processamento": self.estatisticas.tempo_processamento,
            },
            "transcricao_task_id": self.transcricao_task_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AtaEstruturada":
        """Reconstrói a partir de um dict (ex: JSON do Redis ou resposta do LLM)."""
        stats_data = data.get("estatisticas", {})
        stats = Estatisticas(
            duracao_audio=stats_data.get("duracao_audio", ""),
            total_palavras=stats_data.get("total_palavras", 0),
            total_falantes=stats_data.get("total_falantes", 0),
            itens_pauta=stats_data.get("itens_pauta", 0),
            tempo_processamento=stats_data.get("tempo_processamento", ""),
        )
        return cls(
            tipo_assembleia=data.get("tipo_assembleia", "AGO"),
            condominio=data.get("condominio", {"nome": "", "endereco": "", "cnpj": ""}),
            cabecalho=data.get("cabecalho", {}),
            mesa=data.get("mesa", {}),
            ordem_do_dia=data.get("ordem_do_dia", []),
            deliberacoes=data.get("deliberacoes", []),
            assuntos_gerais=data.get("assuntos_gerais", []),
            encerramento=data.get("encerramento", {"formula": "", "data_extenso": ""}),
            estatisticas=stats,
            transcricao_task_id=data.get("transcricao_task_id", ""),
        )


# ──────────────────────────────────────────────
# Legado (compatibilidade)
# ──────────────────────────────────────────────


@dataclass
class AtaModel:
    edital_convocacao: str = ""
    data_assembleia: str = ""
    horario: str = ""
    local: str = ""
    tipo_ata: str = "assembleia"
    participantes: list[Participante] = field(default_factory=list)
    presidente: Optional[Participante] = None
    secretario: Optional[Participante] = None
    itens_pauta: list[ItemPauta] = field(default_factory=list)
    deliberacoes: list[Deliberacao] = field(default_factory=list)
    topicos: list[Topico] = field(default_factory=list)
    estatisticas: Estatisticas = field(default_factory=Estatisticas)
    transcricao_completa: str = ""

    def to_dict(self) -> dict:
        return {
            "edital_convocacao": self.edital_convocacao,
            "data_assembleia": self.data_assembleia,
            "horario": self.horario,
            "local": self.local,
            "tipo_ata": self.tipo_ata,
            "participantes": [
                {"nome": p.nome, "speaker_label": p.speaker_label, "cargo": p.cargo}
                for p in self.participantes
            ],
            "presidente": self.presidente.nome if self.presidente else "",
            "secretario": self.secretario.nome if self.secretario else "",
            "itens_pauta": [
                {
                    "numero": item.numero,
                    "titulo": item.titulo,
                    "discussao": item.discussao,
                    "decisoes": item.decisoes,
                    "votacao": item.votacao,
                }
                for item in self.itens_pauta
            ],
            "deliberacoes": [d.texto for d in self.deliberacoes],
            "topicos": [
                {"categoria": t.categoria, "descricao": t.descricao}
                for t in self.topicos
            ],
            "estatisticas": {
                "duracao_audio": self.estatisticas.duracao_audio,
                "total_palavras": self.estatisticas.total_palavras,
                "total_falantes": self.estatisticas.total_falantes,
                "itens_pauta": self.estatisticas.itens_pauta,
                "tempo_processamento": self.estatisticas.tempo_processamento,
            },
        }
