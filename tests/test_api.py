"""Testes unitários e de integração para a API de transcrição de atas (v2 — 2 estágios)."""

import io
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from config import Config
from models.ata_model import (
    AtaEstruturada,
    AtaModel,
    Deliberacao,
    Estatisticas,
    ItemPauta,
    Participante,
    Topico,
    TranscricaoBruta,
)
from processors.ata_builder import map_speakers_to_participants
from processors.docx_generator import generate_docx, generate_docx_from_ata_estruturada
from processors.transcript_processor import format_duration


class TestConfig(unittest.TestCase):
    """Test configuration values."""

    def test_allowed_extensions(self):
        self.assertIn("mp3", Config.ALLOWED_EXTENSIONS)
        self.assertIn("wav", Config.ALLOWED_EXTENSIONS)
        self.assertIn("m4a", Config.ALLOWED_EXTENSIONS)
        self.assertIn("flac", Config.ALLOWED_EXTENSIONS)
        self.assertIn("ogg", Config.ALLOWED_EXTENSIONS)
        self.assertIn("webm", Config.ALLOWED_EXTENSIONS)

    def test_max_file_size(self):
        self.assertEqual(Config.MAX_FILE_SIZE, 5368709120)

    def test_port(self):
        self.assertEqual(Config.PORT, 5358)

    def test_transcription_ttl(self):
        self.assertEqual(Config.TRANSCRIPTION_TTL, 72 * 3600)


class TestFlaskEndpoints(unittest.TestCase):
    """Test Flask API endpoints."""

    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["version"], "2.0")

    def test_transcrever_no_file(self):
        response = self.client.post("/transcrever")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_transcrever_empty_filename(self):
        data = {"file": (io.BytesIO(b""), "")}
        response = self.client.post(
            "/transcrever", data=data, content_type="multipart/form-data"
        )
        self.assertEqual(response.status_code, 400)

    def test_transcrever_invalid_extension(self):
        data = {"file": (io.BytesIO(b"fake content"), "test.txt")}
        response = self.client.post(
            "/transcrever", data=data, content_type="multipart/form-data"
        )
        self.assertEqual(response.status_code, 400)
        resp_data = response.get_json()
        self.assertIn("Formato não suportado", resp_data["error"])

    @patch("app.task_transcribe")
    def test_transcrever_success(self, mock_task):
        mock_async = MagicMock()
        mock_async.id = "test-task-id-123"
        mock_task.apply_async.return_value = mock_async

        data = {
            "file": (io.BytesIO(b"fake audio content"), "test.mp3"),
            "language": "pt",
            "speaker_labels": "true",
        }
        response = self.client.post(
            "/transcrever", data=data, content_type="multipart/form-data"
        )
        self.assertEqual(response.status_code, 202)
        resp_data = response.get_json()
        self.assertEqual(resp_data["task_id"], "test-task-id-123")
        self.assertIn("status_url", resp_data)

    @patch("app.get_redis_client")
    def test_get_transcricao_found(self, mock_redis):
        mock_r = MagicMock()
        mock_r.get.return_value = json.dumps({"task_id": "abc", "texto_completo": "Olá"})
        mock_redis.return_value = mock_r

        response = self.client.get("/transcricao/abc")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["task_id"], "abc")

    @patch("app.get_redis_client")
    def test_get_transcricao_not_found(self, mock_redis):
        mock_r = MagicMock()
        mock_r.get.return_value = None
        mock_redis.return_value = mock_r

        response = self.client.get("/transcricao/nonexistent")
        self.assertEqual(response.status_code, 404)

    @patch("app.task_analyze")
    @patch("app.get_redis_client")
    def test_analisar_success(self, mock_redis, mock_task):
        mock_r = MagicMock()
        mock_r.exists.return_value = True
        mock_redis.return_value = mock_r

        mock_async = MagicMock()
        mock_async.id = "analyze-task-id-456"
        mock_task.apply_async.return_value = mock_async

        response = self.client.post("/analisar/test-transcricao-id")
        self.assertEqual(response.status_code, 202)
        data = response.get_json()
        self.assertEqual(data["task_id"], "analyze-task-id-456")
        self.assertEqual(data["transcricao_task_id"], "test-transcricao-id")

    @patch("app.get_redis_client")
    def test_analisar_transcricao_not_found(self, mock_redis):
        mock_r = MagicMock()
        mock_r.exists.return_value = False
        mock_redis.return_value = mock_r

        response = self.client.post("/analisar/nonexistent")
        self.assertEqual(response.status_code, 404)

    @patch("app.get_redis_client")
    def test_get_ata_found(self, mock_redis):
        mock_r = MagicMock()
        ata = {"tipo_assembleia": "AGO", "deliberacoes": []}
        mock_r.get.return_value = json.dumps(ata)
        mock_redis.return_value = mock_r

        response = self.client.get("/ata/abc")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["tipo_assembleia"], "AGO")

    @patch("app.get_redis_client")
    def test_get_ata_not_found(self, mock_redis):
        mock_r = MagicMock()
        mock_r.get.return_value = None
        mock_redis.return_value = mock_r

        response = self.client.get("/ata/nonexistent")
        self.assertEqual(response.status_code, 404)

    def test_download_not_found(self):
        response = self.client.get("/download/nonexistent")
        self.assertEqual(response.status_code, 404)

    @patch("app.celery_app")
    def test_cancelar(self, mock_celery):
        response = self.client.post("/cancelar/test-task-id")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["task_id"], "test-task-id")

    def test_not_found_endpoint(self):
        response = self.client.get("/nonexistent")
        self.assertEqual(response.status_code, 404)

    def test_assistente_missing_json(self):
        response = self.client.post("/assistente", data="not json")
        self.assertEqual(response.status_code, 400)

    def test_assistente_missing_instrucao(self):
        response = self.client.post(
            "/assistente",
            json={"texto": "algum texto"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("instrucao", response.get_json()["error"])

    def test_assistente_missing_texto(self):
        response = self.client.post(
            "/assistente",
            json={"instrucao": "formalize"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("texto", response.get_json()["error"])

    @patch("app.assistente_editor")
    def test_assistente_success(self, mock_llm):
        mock_llm.return_value = {
            "resultado": "O Sr. Síndico informou que as contas foram aprovadas.",
            "fontes_rag": [],
        }

        response = self.client.post(
            "/assistente",
            json={
                "instrucao": "formalize este texto",
                "texto": "o sindico falou que aprovaram as contas",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("resultado", data)
        self.assertIn("Síndico", data["resultado"])
        self.assertEqual(data["fontes_rag"], [])

    @patch("app.assistente_editor")
    def test_assistente_with_historico(self, mock_llm):
        mock_llm.return_value = {"resultado": "Texto corrigido.", "fontes_rag": []}

        response = self.client.post(
            "/assistente",
            json={
                "instrucao": "corrija",
                "texto": "texto com erro",
                "historico": [
                    {"role": "user", "content": "formalize"},
                    {"role": "assistant", "content": "texto formal"},
                ],
            },
        )
        self.assertEqual(response.status_code, 200)

    @patch("app.assistente_editor")
    def test_assistente_stream(self, mock_llm):
        mock_llm.return_value = iter([{"content": "chunk1"}, {"content": "chunk2"}])

        response = self.client.post(
            "/assistente",
            json={
                "instrucao": "formalize",
                "texto": "texto qualquer",
                "stream": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.content_type)

    @patch("app.assistente_editor")
    def test_assistente_error(self, mock_llm):
        mock_llm.side_effect = RuntimeError("API error")

        response = self.client.post(
            "/assistente",
            json={
                "instrucao": "formalize",
                "texto": "texto",
            },
        )
        self.assertEqual(response.status_code, 500)
        self.assertIn("error", response.get_json())


class TestFormatDuration(unittest.TestCase):
    """Test duration formatting utility."""

    def test_format_duration_minutes(self):
        self.assertEqual(format_duration(90000), "1m30s")

    def test_format_duration_hours(self):
        self.assertEqual(format_duration(3661000), "1h01m01s")

    def test_format_duration_zero(self):
        self.assertEqual(format_duration(0), "0m00s")


class TestMapSpeakers(unittest.TestCase):
    """Test speaker-to-participant mapping."""

    def test_map_speakers_with_names_list(self):
        speakers = [{"label": "A"}, {"label": "B"}]
        names_json = json.dumps(["João Silva", "Maria Santos"])
        participants = map_speakers_to_participants(speakers, names_json)

        self.assertEqual(len(participants), 2)
        self.assertEqual(participants[0].nome, "João Silva")
        self.assertEqual(participants[1].nome, "Maria Santos")

    def test_map_speakers_with_dict(self):
        speakers = [{"label": "A"}, {"label": "B"}]
        names_json = json.dumps({"A": "João", "B": "Maria"})
        participants = map_speakers_to_participants(speakers, names_json)

        self.assertEqual(participants[0].nome, "João")
        self.assertEqual(participants[1].nome, "Maria")

    def test_map_speakers_no_names(self):
        speakers = [{"label": "A"}, {"label": "B"}]
        participants = map_speakers_to_participants(speakers, None)

        self.assertEqual(participants[0].nome, "Participante A")
        self.assertEqual(participants[1].nome, "Participante B")

    def test_map_speakers_invalid_json(self):
        speakers = [{"label": "A"}]
        participants = map_speakers_to_participants(speakers, "not valid json")
        self.assertEqual(participants[0].nome, "Participante A")


class TestDocxGeneratorLegado(unittest.TestCase):
    """Test .docx document generation (legado AtaModel)."""

    def test_generate_docx(self):
        ata = AtaModel(
            edital_convocacao="01/01/2026",
            data_assembleia="15/01/2026",
            horario="19:00",
            local="Salão de festas",
            tipo_ata="assembleia",
            participantes=[
                Participante(nome="João Silva", speaker_label="A", cargo="Presidente"),
                Participante(nome="Maria Santos", speaker_label="B", cargo="Secretário(a)"),
            ],
            presidente=Participante(nome="João Silva", speaker_label="A", cargo="Presidente"),
            secretario=Participante(nome="Maria Santos", speaker_label="B", cargo="Secretário(a)"),
            itens_pauta=[
                ItemPauta(
                    numero=1,
                    titulo="Aprovação das contas",
                    discussao="Discussão sobre as contas do período.",
                    decisoes="Aprovado por unanimidade.",
                    votacao="Unanimidade",
                    timestamp_inicio="0m00s",
                    timestamp_fim="15m00s",
                ),
            ],
            deliberacoes=[
                Deliberacao(texto="Contas aprovadas por unanimidade"),
            ],
            topicos=[
                Topico(categoria="Financeiro", descricao="Prestação de contas", relevancia=0.9),
            ],
            estatisticas=Estatisticas(
                duracao_audio="45m00s",
                total_palavras=3500,
                total_falantes=5,
                itens_pauta=1,
                tempo_processamento="5m00s",
            ),
        )

        output_path = os.path.join(Config.PROCESSED_FOLDER, "test_output.docx")
        os.makedirs(Config.PROCESSED_FOLDER, exist_ok=True)
        result = generate_docx(ata, output_path)

        self.assertTrue(os.path.exists(result))
        self.assertTrue(result.endswith(".docx"))

        if os.path.exists(result):
            os.remove(result)


class TestDocxGeneratorPadrao(unittest.TestCase):
    """Test .docx generation from AtaEstruturada (5 blocos PADRAO)."""

    def test_generate_docx_from_ata_estruturada(self):
        ata_data = {
            "tipo_assembleia": "AGO",
            "condominio": {
                "nome": "Condomínio Residencial Teste",
                "endereco": "Rua Teste, 123",
                "cnpj": "12.345.678/0001-90",
            },
            "cabecalho": {
                "edital_convocacao": "01/01/2026",
                "data_assembleia": "15/01/2026",
                "horario": "19:30hs, em segunda convocação.",
                "convocacao": "segunda",
                "local": "No salão de festas do próprio condomínio.",
                "formato": "presencial",
            },
            "mesa": {
                "presidente": {"nome": "Sr. João Silva", "unidade": "APTO 92 A"},
                "secretario": {"nome": "Sra. Maria Santos", "cargo": "Representante", "empresa": "Administradora XYZ"},
            },
            "ordem_do_dia": [
                {"numero": 1, "titulo": "Prestação de contas 2025", "categoria": "prestacao_contas", "deliberativo": True},
                {"numero": 2, "titulo": "Reforma da fachada", "categoria": "obras", "deliberativo": True},
            ],
            "deliberacoes": [
                {
                    "item_ordem_dia": 1,
                    "contextualizacao": "Em continuidade, a representante da administradora apresentou a prestação de contas do exercício de 2025, informando que a pasta contendo os demonstrativos financeiros encontrava-se à disposição dos condôminos desde o dia 10/12/2025.",
                    "explanacoes": ["Receitas totais: R$ 500.000,00", "Despesas totais: R$ 480.000,00"],
                    "opcoes_apresentadas": [],
                    "debates": [
                        {"pessoa": "Sr. Carlos", "unidade": "APTO 31 B", "manifestacao": "Questionou sobre despesas extraordinárias."}
                    ],
                    "votacao": {
                        "ocorreu": True,
                        "resultado": "aprovado_unanimidade",
                        "abstencoes": None,
                        "votos_contrarios": None,
                        "detalhes": "Contas aprovadas sem ressalvas.",
                        "vigencia": None,
                        "opcao_escolhida": None,
                    },
                    "condicoes": ["Ficou consignado que o superávit apurado será revertido ao Fundo de Reserva."],
                    "tabela_financeira": {
                        "titulo": "Prestação de Contas 2025",
                        "colunas": ["Categoria", "Previsto", "Realizado"],
                        "linhas": [
                            {"categoria": "DESPESA COM PESSOAL", "valores": ["R$ 300.000,00", "R$ 280.000,00"]},
                            {"categoria": "CONSUMO", "valores": ["R$ 80.000,00", "R$ 85.000,00"]},
                            {"categoria": "MANUTENÇÃO", "valores": ["R$ 120.000,00", "R$ 115.000,00"]},
                        ],
                        "total": ["R$ 500.000,00", "R$ 480.000,00"],
                    },
                },
                {
                    "item_ordem_dia": 2,
                    "contextualizacao": "Na sequência, passou ao 2º item da Ordem do Dia, referente à reforma da fachada do edifício.",
                    "explanacoes": ["Foram apresentados três orçamentos de empresas especializadas."],
                    "opcoes_apresentadas": [
                        {"descricao": "Opção A: Empresa Alpha — reforma completa", "valor": "R$ 280.000,00", "detalhes": "Prazo de 6 meses"},
                        {"descricao": "Opção B: Empresa Beta — reforma parcial", "valor": "R$ 150.000,00", "detalhes": "Prazo de 3 meses"},
                    ],
                    "debates": [],
                    "votacao": {
                        "ocorreu": True,
                        "resultado": "aprovado_maioria",
                        "abstencoes": None,
                        "votos_contrarios": 2,
                        "detalhes": "Aprovada por maioria a proposta da Empresa Alpha.",
                        "vigencia": None,
                        "opcao_escolhida": "Opção A: Empresa Alpha",
                    },
                    "condicoes": [
                        "Ficou consignado que o síndico deverá apresentar o contrato para aprovação do Conselho em até 30 dias.",
                        "Ficou registrado que o rateio extraordinário será cobrado em 10 parcelas.",
                    ],
                    "tabela_financeira": None,
                },
            ],
            "assuntos_gerais": [
                {"descricao": "Manutenção do elevador social.", "encaminhamento": "Síndico irá solicitar orçamentos."},
            ],
            "encerramento": {
                "formula": "Não havendo mais assuntos a serem tratados, a Sra. Presidente deu por encerrada a assembleia.",
                "data_extenso": "São Paulo, 15 de janeiro de 2026.",
            },
        }

        output_path = os.path.join(Config.PROCESSED_FOLDER, "test_padrao_output.docx")
        os.makedirs(Config.PROCESSED_FOLDER, exist_ok=True)
        result = generate_docx_from_ata_estruturada(ata_data, output_path)

        self.assertTrue(os.path.exists(result))
        self.assertTrue(result.endswith(".docx"))

        if os.path.exists(result):
            os.remove(result)

    def test_generate_docx_backward_compat(self):
        """Ata sem campos novos (opcoes, condicoes, tabela) gera normalmente."""
        ata_data = {
            "tipo_assembleia": "AGO",
            "condominio": {"nome": "Cond Teste", "endereco": "Rua A", "cnpj": ""},
            "cabecalho": {
                "edital_convocacao": "01/01/2026",
                "data_assembleia": "15/01/2026",
                "horario": "19:00",
                "convocacao": "segunda",
                "local": "Salão de festas",
                "formato": "presencial",
            },
            "mesa": {
                "presidente": {"nome": "João", "unidade": "101"},
                "secretario": {"nome": "Maria", "cargo": "Representante", "empresa": None},
            },
            "ordem_do_dia": [
                {"numero": 1, "titulo": "Contas", "categoria": "prestacao_contas", "deliberativo": True},
            ],
            "deliberacoes": [
                {
                    "item_ordem_dia": 1,
                    "contextualizacao": "Apresentação das contas.",
                    "explanacoes": ["Aprovadas sem ressalvas."],
                    "debates": [],
                    "votacao": {
                        "ocorreu": True,
                        "resultado": "aprovado_unanimidade",
                        "abstencoes": None,
                        "votos_contrarios": None,
                        "detalhes": "Aprovado.",
                        "vigencia": None,
                    },
                },
            ],
            "assuntos_gerais": [],
            "encerramento": {"formula": "Encerrada.", "data_extenso": "São Paulo, 15 de janeiro de 2026."},
        }

        output_path = os.path.join(Config.PROCESSED_FOLDER, "test_compat_output.docx")
        os.makedirs(Config.PROCESSED_FOLDER, exist_ok=True)
        result = generate_docx_from_ata_estruturada(ata_data, output_path)

        self.assertTrue(os.path.exists(result))
        self.assertTrue(result.endswith(".docx"))

        if os.path.exists(result):
            os.remove(result)


class TestTranscricaoBrutaModel(unittest.TestCase):
    """Test TranscricaoBruta model."""

    def test_to_dict(self):
        t = TranscricaoBruta(
            task_id="abc-123",
            idioma="pt",
            duracao_audio="45m00s",
            texto_completo="Olá, bem-vindos à assembleia.",
            falantes=[{"label": "A", "first_text": "Olá"}],
            utterances=[{"speaker": "A", "text": "Olá", "start": 0, "end": 5000}],
        )
        d = t.to_dict()
        self.assertEqual(d["task_id"], "abc-123")
        self.assertEqual(d["idioma"], "pt")
        self.assertEqual(len(d["falantes"]), 1)
        self.assertEqual(len(d["utterances"]), 1)


class TestAtaEstruturadaModel(unittest.TestCase):
    """Test AtaEstruturada model."""

    def test_to_dict(self):
        ata = AtaEstruturada(
            tipo_assembleia="AGO",
            ordem_do_dia=[{"numero": 1, "titulo": "Contas", "deliberativo": True}],
            deliberacoes=[{"item_ordem_dia": 1, "contextualizacao": "Apresentação de contas"}],
        )
        d = ata.to_dict()
        self.assertEqual(d["tipo_assembleia"], "AGO")
        self.assertEqual(len(d["ordem_do_dia"]), 1)
        self.assertEqual(len(d["deliberacoes"]), 1)

    def test_from_dict(self):
        data = {
            "tipo_assembleia": "AGE",
            "condominio": {"nome": "Teste", "endereco": "Rua A", "cnpj": ""},
            "cabecalho": {"data_assembleia": "15/01/2026"},
            "mesa": {"presidente": {"nome": "João", "unidade": "101"}},
            "ordem_do_dia": [{"numero": 1, "titulo": "Item 1"}],
            "deliberacoes": [],
            "assuntos_gerais": [],
            "encerramento": {"formula": "Encerrada", "data_extenso": "15 de janeiro"},
            "estatisticas": {"duracao_audio": "1h00m00s", "total_palavras": 5000},
        }
        ata = AtaEstruturada.from_dict(data)
        self.assertEqual(ata.tipo_assembleia, "AGE")
        self.assertEqual(ata.condominio["nome"], "Teste")
        self.assertEqual(ata.estatisticas.duracao_audio, "1h00m00s")
        self.assertEqual(ata.estatisticas.total_palavras, 5000)


class TestAtaModelLegado(unittest.TestCase):
    """Test AtaModel serialization (legado)."""

    def test_to_dict(self):
        ata = AtaModel(
            edital_convocacao="01/01/2026",
            data_assembleia="15/01/2026",
            participantes=[
                Participante(nome="João", speaker_label="A", cargo="Presidente"),
            ],
            presidente=Participante(nome="João", speaker_label="A", cargo="Presidente"),
            deliberacoes=[Deliberacao(texto="Aprovado")],
            topicos=[Topico(categoria="Financeiro", descricao="Contas")],
        )

        d = ata.to_dict()
        self.assertEqual(d["edital_convocacao"], "01/01/2026")
        self.assertEqual(len(d["participantes"]), 1)
        self.assertEqual(d["presidente"], "João")
        self.assertEqual(len(d["deliberacoes"]), 1)
        self.assertEqual(len(d["topicos"]), 1)

    def test_to_dict_empty(self):
        ata = AtaModel()
        d = ata.to_dict()
        self.assertEqual(d["presidente"], "")
        self.assertEqual(d["secretario"], "")
        self.assertEqual(d["participantes"], [])


class TestRAGClient(unittest.TestCase):
    """Test RAG-Z client module."""

    @patch("processors.rag_client._get_client")
    def test_list_contexts_success(self, mock_get_client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "contexts": [{"name": "cond_0388", "total_files": 5}],
            "total": 1,
        }
        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_get_client.return_value = mock_client_instance

        from processors.rag_client import list_contexts

        result = list_contexts()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "cond_0388")

    @patch("processors.rag_client._get_client")
    def test_list_contexts_error(self, mock_get_client):
        mock_client_instance = MagicMock()
        mock_client_instance.get.side_effect = Exception("Connection refused")
        mock_get_client.return_value = mock_client_instance

        from processors.rag_client import list_contexts

        result = list_contexts()
        self.assertEqual(result, [])

    @patch("processors.rag_client._get_client")
    def test_query_hierarchical_success(self, mock_get_client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "De acordo com o artigo 15...",
            "sources": [{"content": "Art 15...", "file": "convencao.pdf", "chunk": "12/50"}],
            "contexts_searched": ["cond_0388"],
            "hierarchy_applied": True,
        }
        mock_response.raise_for_status = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_get_client.return_value = mock_client_instance

        from processors.rag_client import query_hierarchical

        result = query_hierarchical("Posso ter cachorro?", "cond_0388")
        self.assertIn("answer", result)
        self.assertEqual(len(result["sources"]), 1)

    @patch("processors.rag_client._get_client")
    def test_query_hierarchical_timeout(self, mock_get_client):
        import httpx

        mock_client_instance = MagicMock()
        mock_client_instance.post.side_effect = httpx.TimeoutException("timeout")
        mock_get_client.return_value = mock_client_instance

        from processors.rag_client import query_hierarchical

        result = query_hierarchical("Pergunta?", "cond_0388")
        self.assertEqual(result["answer"], "")
        self.assertIn("error", result)

    def test_format_rag_result_for_llm(self):
        from processors.rag_client import format_rag_result_for_llm

        result = {
            "answer": "Animais são permitidos.",
            "sources": [{"file": "convencao.pdf", "chunk": "12/50", "content": "Art 15..."}],
            "contexts_searched": ["cond_0388"],
        }
        text = format_rag_result_for_llm(result)
        self.assertIn("Animais são permitidos", text)
        self.assertIn("convencao.pdf", text)

    def test_format_rag_result_empty(self):
        from processors.rag_client import format_rag_result_for_llm

        result = {"answer": "", "sources": []}
        text = format_rag_result_for_llm(result)
        self.assertIn("Nenhuma informação", text)


class TestAssistenteRAGIntegration(unittest.TestCase):
    """Test /assistente endpoint with RAG integration."""

    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    @patch("app.assistente_editor")
    def test_assistente_with_condominio_context(self, mock_llm):
        mock_llm.return_value = {
            "resultado": "Texto formalizado com base legal.",
            "fontes_rag": [{"file": "convencao.pdf", "chunk": "12/50", "content": "Art 15..."}],
        }

        response = self.client.post(
            "/assistente",
            json={
                "instrucao": "formalize e valide legalmente",
                "texto": "o sindico falou que pode ter cachorro",
                "condominio_context": "cond_0388",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("resultado", data)
        self.assertIn("fontes_rag", data)
        self.assertEqual(len(data["fontes_rag"]), 1)

    @patch("app.assistente_editor")
    def test_assistente_without_condominio_context(self, mock_llm):
        mock_llm.return_value = {
            "resultado": "Texto formalizado.",
            "fontes_rag": [],
        }

        response = self.client.post(
            "/assistente",
            json={
                "instrucao": "formalize",
                "texto": "texto qualquer",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("resultado", data)
        self.assertEqual(data["fontes_rag"], [])

    @patch("app.rag_client")
    def test_contextos_rag_available(self, mock_rag):
        mock_rag.is_available.return_value = True
        mock_rag.list_contexts.return_value = [
            {"name": "cond_0388", "total_files": 5, "total_chunks": 120},
        ]

        response = self.client.get("/contextos-rag")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["disponivel"])
        self.assertEqual(data["total"], 1)

    @patch("app.rag_client")
    def test_contextos_rag_unavailable(self, mock_rag):
        mock_rag.is_available.return_value = False

        response = self.client.get("/contextos-rag")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data["disponivel"])
        self.assertEqual(data["total"], 0)

    @patch("app.rag_client")
    def test_contextos_rag_stats_found(self, mock_rag):
        mock_rag.get_context_stats.return_value = {
            "name": "cond_0388",
            "total_files": 5,
            "total_chunks": 120,
        }

        response = self.client.get("/contextos-rag/cond_0388/stats")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["name"], "cond_0388")

    @patch("app.rag_client")
    def test_contextos_rag_stats_not_found(self, mock_rag):
        mock_rag.get_context_stats.return_value = None

        response = self.client.get("/contextos-rag/nonexistent/stats")
        self.assertEqual(response.status_code, 404)


class TestAnalisarRAGIntegration(unittest.TestCase):
    """Test POST /analisar with condominio_context parameter."""

    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    @patch("app.get_redis_client")
    @patch("app.task_analyze")
    def test_analisar_with_condominio_context(self, mock_task, mock_redis):
        mock_r = MagicMock()
        mock_r.exists.return_value = True
        mock_redis.return_value = mock_r

        mock_async = MagicMock()
        mock_async.id = "analyze-task-123"
        mock_task.apply_async.return_value = mock_async

        response = self.client.post(
            "/analisar/transcricao-123",
            json={"condominio_context": "cond_0388"},
        )
        self.assertEqual(response.status_code, 202)

        # Verify condominio_context was passed to task
        call_kwargs = mock_task.apply_async.call_args[1]["kwargs"]
        self.assertEqual(call_kwargs["condominio_context"], "cond_0388")

    @patch("app.get_redis_client")
    @patch("app.task_analyze")
    def test_analisar_without_condominio_context(self, mock_task, mock_redis):
        mock_r = MagicMock()
        mock_r.exists.return_value = True
        mock_redis.return_value = mock_r

        mock_async = MagicMock()
        mock_async.id = "analyze-task-456"
        mock_task.apply_async.return_value = mock_async

        response = self.client.post("/analisar/transcricao-456")
        self.assertEqual(response.status_code, 202)

        call_kwargs = mock_task.apply_async.call_args[1]["kwargs"]
        self.assertIsNone(call_kwargs["condominio_context"])


if __name__ == "__main__":
    unittest.main()
