"""Gera documento .docx estruturado a partir do modelo de ata."""

import logging
import os

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

from models.ata_model import AtaModel

logger = logging.getLogger(__name__)


def _add_separator(doc: Document, char: str = "─", width: int = 60):
    """Add a visual separator line."""
    p = doc.add_paragraph(char * width)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in p.runs:
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(128, 128, 128)


def _add_heading_styled(doc: Document, text: str, level: int = 1):
    """Add a styled heading."""
    heading = doc.add_heading(text, level=level)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return heading


def _set_paragraph_format(paragraph, space_before=0, space_after=6, line_spacing=1.15):
    """Set common paragraph formatting."""
    pf = paragraph.paragraph_format
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    pf.line_spacing = line_spacing


def _setup_document(doc: Document):
    """Configure document margins and default font."""
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1.2)
        section.right_margin = Inches(1.2)

    style = doc.styles["Normal"]
    font = style.font
    font.name = "Arial"
    font.size = Pt(11)


def _add_field(doc: Document, label: str, value: str):
    """Add a label: value paragraph."""
    p = doc.add_paragraph()
    run_label = p.add_run(f"{label}: ")
    run_label.bold = True
    run_label.font.size = Pt(11)
    run_value = p.add_run(value or "[A definir]")
    run_value.font.size = Pt(11)
    _set_paragraph_format(p, space_before=2, space_after=2)


# ──────────────────────────────────────────────
# Gerador para AtaEstruturada (5 blocos PADRAO)
# ──────────────────────────────────────────────


def generate_docx_from_ata_estruturada(ata: dict, output_path: str) -> str:
    """Gera .docx no padrão de 5 blocos a partir de um dict AtaEstruturada."""
    logger.info("Gerando .docx (PADRAO 5 blocos): %s", output_path)

    doc = Document()
    _setup_document(doc)

    cabecalho = ata.get("cabecalho", {})
    mesa = ata.get("mesa", {})
    tipo = ata.get("tipo_assembleia", "AGO")
    condominio = ata.get("condominio", {})

    # ============================================================
    # BLOCO 1 — CABEÇALHO INSTITUCIONAL
    # ============================================================
    titulo = "ATA DE ASSEMBLEIA GERAL ORDINÁRIA" if tipo == "AGO" else "ATA DE ASSEMBLEIA GERAL EXTRAORDINÁRIA"
    _add_heading_styled(doc, titulo, level=0)

    if condominio.get("nome"):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(condominio["nome"])
        run.bold = True
        run.font.size = Pt(12)
        _set_paragraph_format(p, space_before=0, space_after=4)

    _add_separator(doc, "═", 70)

    _add_field(doc, "EDITAL DE CONVOCAÇÃO", cabecalho.get("edital_convocacao", ""))
    _add_field(doc, "DATA DA ASSEMBLEIA", cabecalho.get("data_assembleia", ""))
    _add_field(doc, "HORÁRIO", cabecalho.get("horario", ""))
    _add_field(doc, "LOCAL", cabecalho.get("local", ""))

    if cabecalho.get("formato"):
        _add_field(doc, "FORMATO", cabecalho["formato"].capitalize())

    # Presentes
    doc.add_paragraph()
    p = doc.add_paragraph()
    run = p.add_run("PRESENTES OU REPRESENTADOS: ")
    run.bold = True
    p.add_run("Conforme lista de presença, parte integrante desta ata.")
    _set_paragraph_format(p)

    # Mesa
    doc.add_paragraph()
    presidente = mesa.get("presidente", {})
    secretario = mesa.get("secretario", {})

    if presidente.get("nome"):
        p = doc.add_paragraph()
        run = p.add_run("PRESIDENTE: ")
        run.bold = True
        nome_pres = presidente["nome"]
        if presidente.get("unidade"):
            nome_pres += f" – {presidente['unidade']}"
        p.add_run(nome_pres)
        _set_paragraph_format(p)

    if secretario.get("nome"):
        p = doc.add_paragraph()
        run = p.add_run("SECRETÁRIO(A): ")
        run.bold = True
        nome_sec = secretario["nome"]
        if secretario.get("cargo"):
            nome_sec += f", {secretario['cargo']}"
        if secretario.get("empresa"):
            nome_sec += f" – {secretario['empresa']}"
        p.add_run(nome_sec)
        _set_paragraph_format(p)

    # ============================================================
    # BLOCO 2 — ORDEM DO DIA
    # ============================================================
    _add_separator(doc, "─", 70)
    _add_heading_styled(doc, "ORDEM DO DIA", level=1)
    _add_separator(doc, "─", 70)

    ordem = ata.get("ordem_do_dia", [])
    for item in ordem:
        numero = item.get("numero", "")
        titulo_item = item.get("titulo", "")
        p = doc.add_paragraph()
        run = p.add_run(f"{numero}. {titulo_item}")
        run.bold = True
        run.font.size = Pt(11)
        _set_paragraph_format(p, space_before=4, space_after=2)

    # ============================================================
    # BLOCO 3 — DELIBERAÇÕES
    # ============================================================
    _add_separator(doc, "─", 70)
    _add_heading_styled(doc, "DELIBERAÇÕES", level=1)
    _add_separator(doc, "─", 70)

    deliberacoes = ata.get("deliberacoes", [])
    for delib in deliberacoes:
        item_num = delib.get("item_ordem_dia", "")
        # Título do item (buscar da ordem_do_dia)
        titulo_delib = f"Item {item_num}"
        for od in ordem:
            if od.get("numero") == item_num:
                titulo_delib = f"{item_num}. {od.get('titulo', '')}"
                break

        p = doc.add_paragraph()
        run = p.add_run(titulo_delib)
        run.bold = True
        run.font.size = Pt(12)
        _set_paragraph_format(p, space_before=12, space_after=6)

        # Contextualização
        ctx = delib.get("contextualizacao", "")
        if ctx:
            p = doc.add_paragraph(ctx)
            _set_paragraph_format(p, space_before=4, space_after=4)

        # Tabela financeira (após contextualização, antes de explanações)
        tabela = delib.get("tabela_financeira")
        if tabela and tabela.get("colunas") and tabela.get("linhas"):
            if tabela.get("titulo"):
                p = doc.add_paragraph()
                run = p.add_run(tabela["titulo"])
                run.bold = True
                run.font.size = Pt(11)
                _set_paragraph_format(p, space_before=6, space_after=2)

            colunas = tabela["colunas"]
            linhas = tabela["linhas"]
            total = tabela.get("total", [])

            num_cols = len(colunas)
            num_rows = 1 + len(linhas) + (1 if total else 0)  # header + data + total
            table = doc.add_table(rows=num_rows, cols=num_cols)
            table.style = "Table Grid"

            # Header
            for i, col_name in enumerate(colunas):
                cell = table.rows[0].cells[i]
                cell.text = col_name
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.bold = True
                        run.font.size = Pt(10)

            # Data rows
            for row_idx, linha in enumerate(linhas, start=1):
                table.rows[row_idx].cells[0].text = linha.get("categoria", "")
                for val_idx, val in enumerate(linha.get("valores", [])):
                    if val_idx + 1 < num_cols:
                        table.rows[row_idx].cells[val_idx + 1].text = val
                for cell in table.rows[row_idx].cells:
                    for paragraph in cell.paragraphs:
                        for run in paragraph.runs:
                            run.font.size = Pt(10)

            # Total row
            if total:
                total_row_idx = num_rows - 1
                table.rows[total_row_idx].cells[0].text = "TOTAL"
                for val_idx, val in enumerate(total):
                    if val_idx + 1 < num_cols:
                        table.rows[total_row_idx].cells[val_idx + 1].text = val
                for cell in table.rows[total_row_idx].cells:
                    for paragraph in cell.paragraphs:
                        for run in paragraph.runs:
                            run.bold = True
                            run.font.size = Pt(10)

            doc.add_paragraph()  # spacing after table

        # Explanações
        explanacoes = delib.get("explanacoes", [])
        for exp in explanacoes:
            p = doc.add_paragraph(f"  • {exp}", style="List Bullet")
            _set_paragraph_format(p, space_before=0, space_after=2)

        # Opções apresentadas (após explanações, antes de debates)
        opcoes = delib.get("opcoes_apresentadas", [])
        if opcoes:
            p = doc.add_paragraph()
            run = p.add_run("Opções Apresentadas:")
            run.bold = True
            run.font.size = Pt(11)
            _set_paragraph_format(p, space_before=6, space_after=2)

            for i, opcao in enumerate(opcoes):
                letra = chr(65 + i)  # A, B, C...
                descricao = opcao.get("descricao", "")
                valor = opcao.get("valor")
                detalhes = opcao.get("detalhes")
                texto_opcao = f"{letra}) {descricao}"
                if valor:
                    texto_opcao += f" — {valor}"
                if detalhes:
                    texto_opcao += f" ({detalhes})"
                p = doc.add_paragraph(texto_opcao, style="List Bullet")
                _set_paragraph_format(p, space_before=0, space_after=2)

        # Debates
        debates = delib.get("debates", [])
        if debates:
            p = doc.add_paragraph()
            run = p.add_run("Debates:")
            run.bold = True
            run.font.size = Pt(11)
            _set_paragraph_format(p, space_before=6, space_after=2)

            for debate in debates:
                pessoa = debate.get("pessoa", "")
                unidade = debate.get("unidade", "")
                manifestacao = debate.get("manifestacao", "")
                id_pessoa = pessoa
                if unidade:
                    id_pessoa += f" ({unidade})"
                p = doc.add_paragraph()
                run = p.add_run(f"{id_pessoa}: ")
                run.bold = True
                p.add_run(manifestacao)
                _set_paragraph_format(p, space_before=2, space_after=2)

        # Votação
        votacao = delib.get("votacao", {})
        if votacao and votacao.get("ocorreu"):
            p = doc.add_paragraph()
            run = p.add_run("Votação: ")
            run.bold = True
            run.font.size = Pt(11)

            resultado = votacao.get("resultado", "")
            resultado_label = {
                "aprovado_unanimidade": "Aprovado por unanimidade",
                "aprovado_maioria": "Aprovado por maioria",
                "reprovado": "Reprovado",
                "adiado": "Adiado",
            }.get(resultado, resultado)

            detalhes = votacao.get("detalhes", "")
            texto_voto = resultado_label
            if votacao.get("opcao_escolhida"):
                texto_voto += f" — {votacao['opcao_escolhida']}"
            if detalhes:
                texto_voto += f". {detalhes}"
            if votacao.get("vigencia"):
                texto_voto += f" Vigência: {votacao['vigencia']}."
            if votacao.get("votos_contrarios"):
                texto_voto += f" Votos contrários: {votacao['votos_contrarios']}."
            if votacao.get("abstencoes"):
                texto_voto += f" Abstenções: {votacao['abstencoes']}."

            p.add_run(texto_voto)
            _set_paragraph_format(p, space_before=4, space_after=4)

        # Condições pós-aprovação
        condicoes = delib.get("condicoes", [])
        if condicoes:
            p = doc.add_paragraph()
            run = p.add_run("Ficou consignado que:")
            run.bold = True
            run.font.size = Pt(11)
            _set_paragraph_format(p, space_before=4, space_after=2)

            for cond in condicoes:
                p = doc.add_paragraph(f"  • {cond}", style="List Bullet")
                _set_paragraph_format(p, space_before=0, space_after=2)

    # ============================================================
    # BLOCO 4 — ASSUNTOS GERAIS
    # ============================================================
    assuntos = ata.get("assuntos_gerais", [])
    if assuntos:
        _add_separator(doc, "─", 70)
        _add_heading_styled(doc, "ASSUNTOS GERAIS", level=1)
        _add_separator(doc, "─", 70)

        for assunto in assuntos:
            descricao = assunto.get("descricao", "")
            encaminhamento = assunto.get("encaminhamento", "")

            p = doc.add_paragraph(f"• {descricao}")
            _set_paragraph_format(p, space_before=4, space_after=2)

            if encaminhamento:
                p = doc.add_paragraph()
                run = p.add_run("Encaminhamento: ")
                run.bold = True
                run.font.size = Pt(10)
                run_enc = p.add_run(encaminhamento)
                run_enc.font.size = Pt(10)
                _set_paragraph_format(p, space_before=0, space_after=6)

    # ============================================================
    # BLOCO 5 — ENCERRAMENTO E ASSINATURAS
    # ============================================================
    _add_separator(doc, "─", 70)
    _add_heading_styled(doc, "ENCERRAMENTO E ASSINATURAS", level=1)
    _add_separator(doc, "─", 70)

    encerramento = ata.get("encerramento", {})
    formula = encerramento.get("formula", "")
    data_extenso = encerramento.get("data_extenso", "")

    if formula:
        p = doc.add_paragraph(formula)
        _set_paragraph_format(p, space_before=6, space_after=4)

    if data_extenso:
        p = doc.add_paragraph(data_extenso)
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        _set_paragraph_format(p, space_before=4, space_after=12)

    doc.add_paragraph()

    # Assinatura Presidente
    nome_pres = presidente.get("nome", "________________")
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run("Presidente: ________________________  Data: __/__/_____")
    run.font.size = Pt(11)
    _set_paragraph_format(p, space_before=12, space_after=2)

    p = doc.add_paragraph()
    run = p.add_run(nome_pres)
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(128, 128, 128)
    _set_paragraph_format(p, space_before=0, space_after=20)

    # Assinatura Secretário
    nome_sec = secretario.get("nome", "________________")
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run("Secretário(a): ________________________  Data: __/__/_____")
    run.font.size = Pt(11)
    _set_paragraph_format(p, space_before=0, space_after=2)

    p = doc.add_paragraph()
    run = p.add_run(nome_sec)
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(128, 128, 128)
    _set_paragraph_format(p, space_before=0, space_after=12)

    _add_separator(doc, "═", 70)

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    logger.info("Documento salvo: %s", output_path)
    return output_path


# ──────────────────────────────────────────────
# Gerador legado (compatibilidade com AtaModel)
# ──────────────────────────────────────────────


def generate_docx(ata: AtaModel, output_path: str) -> str:
    """Generate a .docx document from an AtaModel (legado) and save to output_path."""
    logger.info("Generating .docx document (legado): %s", output_path)

    doc = Document()
    _setup_document(doc)

    # HEADER
    titulo = "ATA DE ASSEMBLEIA" if ata.tipo_ata == "assembleia" else "ATA DE REUNIÃO"
    _add_heading_styled(doc, titulo, level=0)
    _add_separator(doc, "═", 70)

    campos = [
        ("EDITAL DE CONVOCAÇÃO", ata.edital_convocacao or "[A definir]"),
        ("DATA DA ASSEMBLEIA", ata.data_assembleia or "[A definir]"),
        ("HORÁRIO", ata.horario or "[A definir]"),
        ("LOCAL", ata.local or "[A definir]"),
    ]

    for label, value in campos:
        _add_field(doc, label, value)

    # Participants
    doc.add_paragraph()
    p = doc.add_paragraph()
    run = p.add_run("PRESENTES OU REPRESENTADOS:")
    run.bold = True
    run.font.size = Pt(11)
    _set_paragraph_format(p)

    for participante in ata.participantes:
        cargo_txt = f" ({participante.cargo})" if participante.cargo else ""
        p = doc.add_paragraph(
            f"  • {participante.nome}{cargo_txt}", style="List Bullet"
        )
        _set_paragraph_format(p, space_before=0, space_after=1)

    doc.add_paragraph()
    if ata.presidente:
        p = doc.add_paragraph()
        run = p.add_run("PRESIDENTE: ")
        run.bold = True
        p.add_run(ata.presidente.nome)
        _set_paragraph_format(p)

    if ata.secretario:
        p = doc.add_paragraph()
        run = p.add_run("SECRETÁRIO(A): ")
        run.bold = True
        p.add_run(ata.secretario.nome)
        _set_paragraph_format(p)

    # ORDEM DO DIA
    _add_separator(doc, "─", 70)
    _add_heading_styled(doc, "ORDEM DO DIA", level=1)
    _add_separator(doc, "─", 70)

    for item in ata.itens_pauta:
        p = doc.add_paragraph()
        run = p.add_run(f"{item.numero}. {item.titulo}")
        run.bold = True
        run.font.size = Pt(12)
        _set_paragraph_format(p, space_before=12, space_after=6)

        if item.timestamp_inicio and item.timestamp_fim:
            p = doc.add_paragraph()
            run = p.add_run(f"[{item.timestamp_inicio} - {item.timestamp_fim}]")
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(128, 128, 128)
            _set_paragraph_format(p, space_before=0, space_after=4)

        if item.discussao:
            p = doc.add_paragraph(item.discussao)
            _set_paragraph_format(p, space_before=4, space_after=6)

        if item.decisoes:
            p = doc.add_paragraph()
            run = p.add_run("Decisões: ")
            run.bold = True
            run.font.size = Pt(11)
            p.add_run(item.decisoes)
            _set_paragraph_format(p, space_before=4, space_after=4)

        if item.votacao:
            p = doc.add_paragraph()
            run = p.add_run("Votação: ")
            run.bold = True
            run.font.size = Pt(11)
            p.add_run(item.votacao)
            _set_paragraph_format(p, space_before=2, space_after=8)

    # DELIBERAÇÕES
    if ata.deliberacoes:
        _add_separator(doc, "─", 70)
        _add_heading_styled(doc, "DELIBERAÇÕES PRINCIPAIS", level=1)
        _add_separator(doc, "─", 70)

        for delib in ata.deliberacoes:
            p = doc.add_paragraph(f"• {delib.texto}")
            _set_paragraph_format(p, space_before=2, space_after=4)

    # TÓPICOS
    if ata.topicos:
        _add_separator(doc, "─", 70)
        _add_heading_styled(doc, "TÓPICOS ABORDADOS", level=1)
        _add_separator(doc, "─", 70)

        for topico in ata.topicos:
            p = doc.add_paragraph()
            run = p.add_run(f"{topico.categoria}: ")
            run.bold = True
            desc = topico.descricao if topico.descricao else f"Relevância: {topico.relevancia:.1%}"
            p.add_run(desc)
            _set_paragraph_format(p, space_before=2, space_after=4)

    # ASSINATURAS
    _add_separator(doc, "─", 70)
    _add_heading_styled(doc, "ASSINATURAS", level=1)
    _add_separator(doc, "─", 70)

    doc.add_paragraph()

    nome_presidente = ata.presidente.nome if ata.presidente else "________________"
    nome_secretario = ata.secretario.nome if ata.secretario else "________________"

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run("Presidente: ________________________  Data: __/__/_____")
    run.font.size = Pt(11)
    _set_paragraph_format(p, space_before=12, space_after=2)

    p = doc.add_paragraph()
    run = p.add_run(nome_presidente)
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(128, 128, 128)
    _set_paragraph_format(p, space_before=0, space_after=20)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run("Secretário(a): ________________________  Data: __/__/_____")
    run.font.size = Pt(11)
    _set_paragraph_format(p, space_before=0, space_after=2)

    p = doc.add_paragraph()
    run = p.add_run(nome_secretario)
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(128, 128, 128)
    _set_paragraph_format(p, space_before=0, space_after=12)

    _add_separator(doc, "═", 70)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    logger.info("Document saved: %s", output_path)
    return output_path
