"""
Exportação de DOCX usando template com marcas d'água e estilização.
Recebe o JSON do editor e gera um DOCX formatado usando o template base.
Segue o padrão visual das ATAs Zangari: sem linhas separadoras, deliberações
em texto corrido com numeração em negrito.
"""
import io
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn


TEMPLATE_PATH = 'exemplos_atas/MODELO - Papel Carta para Ata.docx'


def gerar_docx_from_editor(ata_json: dict) -> io.BytesIO:
    """Gera DOCX a partir do JSON do editor Tiptap, usando o template base."""
    doc = Document(TEMPLATE_PATH)

    # Extrair contexto do sistema de ATAs (nome, tipo, CNPJ)
    context = ata_json.pop('_context', None)

    # Clear all existing body content but keep section properties (headers, footers, watermarks)
    body = doc.element.body
    final_sectpr = body.find(qn('w:sectPr'))

    # Extrair headerReference/footerReference de sectPr inline (dentro de parágrafos)
    # e copiar para o sectPr final, para manter marca d'água e cabeçalho/rodapé
    for child in list(body):
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if tag == 'p':
            pPr = child.find(qn('w:pPr'))
            if pPr is not None:
                sect = pPr.find(qn('w:sectPr'))
                if sect is not None and final_sectpr is not None:
                    for ref in sect.findall(qn('w:headerReference')) + sect.findall(qn('w:footerReference')):
                        from copy import deepcopy
                        final_sectpr.insert(0, deepcopy(ref))
            body.remove(child)
        elif tag in ('tbl', 'bookmarkEnd'):
            body.remove(child)

    # Substituir placeholders no header do template (marca d'água)
    if context:
        _replace_header_placeholders(doc, context)
    else:
        doc.add_paragraph()

    blocks = ata_json.get('content', [])

    # Flatten ataSection blocks - extract children, no separators (modelo não usa linhas)
    flat_blocks = []
    for block in blocks:
        if block.get('type') == 'ataSection':
            for child in block.get('content', []):
                flat_blocks.append(child)
        else:
            flat_blocks.append(block)

    for block in flat_blocks:
        _process_block(doc, block)

    # Extract president/secretary names for signature block
    presidente_nome = ''
    secretario_nome = ''
    for block in flat_blocks:
        if block.get('type') == 'paragraph':
            text = extract_text(block)
            upper = text.upper().strip()
            if upper.startswith('PRESIDENTE:'):
                presidente_nome = text.split(':', 1)[1].strip()
            elif any(upper.startswith(p) for p in ['SECRETÁRIO', 'SECRETÁRIA', 'SECRETARIO', 'SECRETARIA']):
                if ':' in text:
                    secretario_nome = text.split(':', 1)[1].strip()

    # Signature block
    doc.add_paragraph()
    doc.add_paragraph()

    table = doc.add_table(rows=2, cols=3)
    table.autofit = True
    _remove_table_borders(table)

    _set_sig_cell(table.cell(0, 0), presidente_nome or '___________________')
    _set_sig_cell(table.cell(0, 2), secretario_nome or '___________________')
    _set_sig_cell(table.cell(1, 0), 'Presidente', bold=True)
    _set_sig_cell(table.cell(1, 2), 'Secretária', bold=True)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def _process_block(doc, block):
    """Process a single Tiptap block node."""
    block_type = block.get('type', '')

    if block_type == 'heading':
        level = block.get('attrs', {}).get('level', 2)
        text = extract_text(block)
        p = doc.add_paragraph()
        # Títulos nível 1-2 centralizados (ORDEM DO DIA, DELIBERAÇÕES, nome do condomínio)
        # Nível 3+ alinhado à esquerda (títulos de deliberações)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER if level <= 2 else WD_ALIGN_PARAGRAPH.JUSTIFY
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(12 if level == 1 else 11 if level == 2 else 10)
        run.font.name = 'Arial'
        p.space_after = Pt(4)
        p.space_before = Pt(8 if level <= 2 else 6)

    elif block_type == 'paragraph':
        content = block.get('content', [])
        if not content:
            # Parágrafo vazio = espaçamento
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.space_before = Pt(0)
            return

        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        _add_runs(p, content)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.space_before = Pt(0)
        # Set font defaults for runs without explicit font
        for run in p.runs:
            if run.font.name is None:
                run.font.name = 'Arial'
            if run.font.size is None:
                run.font.size = Pt(10)

    elif block_type == 'horizontalRule':
        # No modelo Zangari não usa linhas separadoras - pula silenciosamente
        pass

    elif block_type == 'votacao':
        resultado = block.get('attrs', {}).get('resultado', '')
        text = extract_text(block)
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

        is_aprovado = resultado.startswith('aprovado') if resultado else True
        prefix = 'APROVADO' if is_aprovado else 'REJEITADO'

        run_prefix = p.add_run(f'[{prefix}] ')
        run_prefix.bold = True
        run_prefix.font.name = 'Arial'
        run_prefix.font.size = Pt(10)
        run_prefix.font.color.rgb = RGBColor(0, 128, 0) if is_aprovado else RGBColor(200, 0, 0)

        run_text = p.add_run(text)
        run_text.font.name = 'Arial'
        run_text.font.size = Pt(10)
        p.paragraph_format.space_after = Pt(4)

    elif block_type == 'bulletList':
        for item in block.get('content', []):
            if item.get('type') == 'listItem':
                for child in item.get('content', []):
                    text = extract_text(child)
                    if text:
                        p = doc.add_paragraph()
                        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                        run = p.add_run(f'• {text}')
                        run.font.name = 'Arial'
                        run.font.size = Pt(10)
                        p.paragraph_format.space_after = Pt(2)
                        p.paragraph_format.left_indent = Pt(18)

    elif block_type == 'orderedList':
        for idx, item in enumerate(block.get('content', []), 1):
            if item.get('type') == 'listItem':
                for child in item.get('content', []):
                    text = extract_text(child)
                    if text:
                        p = doc.add_paragraph()
                        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                        run_num = p.add_run(f'{idx}. ')
                        run_num.bold = True
                        run_num.font.name = 'Arial'
                        run_num.font.size = Pt(10)
                        run_text = p.add_run(text)
                        run_text.font.name = 'Arial'
                        run_text.font.size = Pt(10)
                        p.paragraph_format.space_after = Pt(2)

    elif block_type == 'table':
        rows_data = block.get('content', [])
        if rows_data:
            num_rows = len(rows_data)
            num_cols = max(len(r.get('content', [])) for r in rows_data)
            table = doc.add_table(rows=num_rows, cols=num_cols)
            try:
                table.style = 'Table Grid'
            except KeyError:
                pass
            for r_idx, row_node in enumerate(rows_data):
                cells = row_node.get('content', [])
                for c_idx, cell_node in enumerate(cells):
                    if c_idx < num_cols:
                        cell_text = extract_text(cell_node)
                        cell = table.cell(r_idx, c_idx)
                        cell.text = ''
                        p = cell.paragraphs[0]
                        run = p.add_run(cell_text)
                        run.font.name = 'Arial'
                        run.font.size = Pt(9)
                        is_header = cell_node.get('type') == 'tableHeader'
                        if is_header or r_idx == 0:
                            run.bold = True


def extract_text(block: dict) -> str:
    """Extract plain text from a Tiptap block recursively."""
    content = block.get('content', [])
    parts = []
    for node in content:
        if node.get('type') == 'text':
            parts.append(node.get('text', ''))
        elif 'content' in node:
            parts.append(extract_text(node))
    return ''.join(parts)


def _add_runs(p, content_nodes: list):
    """Add formatted runs to a paragraph from Tiptap content nodes."""
    for node in content_nodes:
        if node.get('type') == 'hardBreak':
            p.add_run('\n')
            continue
        if node.get('type') != 'text':
            continue
        text = node.get('text', '')
        if not text:
            continue

        marks = node.get('marks', [])
        run = p.add_run(text)

        for mark in marks:
            mark_type = mark.get('type', '')
            if mark_type == 'bold':
                run.bold = True
            elif mark_type == 'italic':
                run.italic = True
            elif mark_type == 'underline':
                run.underline = True
            elif mark_type == 'textStyle':
                attrs = mark.get('attrs', {})
                color = attrs.get('color', '')
                if color and color.startswith('#') and len(color) >= 7:
                    try:
                        run.font.color.rgb = RGBColor(
                            int(color[1:3], 16),
                            int(color[3:5], 16),
                            int(color[5:7], 16)
                        )
                    except (ValueError, IndexError):
                        pass


def _remove_table_borders(table):
    """Remove all borders from a table."""
    tbl_pr = table._element.tblPr
    tbl_borders = tbl_pr.makeelement(qn('w:tblBorders'), {})
    for name in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        el = tbl_borders.makeelement(qn(f'w:{name}'), {
            qn('w:val'): 'none', qn('w:sz'): '0',
            qn('w:space'): '0', qn('w:color'): 'auto'
        })
        tbl_borders.append(el)
    tbl_pr.append(tbl_borders)


def _set_sig_cell(cell, text, bold=False):
    """Set signature table cell content."""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    run.font.name = 'Arial'
    run.font.size = Pt(10)
    run.bold = bold


def _format_cnpj(cnpj_raw):
    """Formata CNPJ: 00000000000100 → 00.000.000/0001-00"""
    if not cnpj_raw:
        return ''
    digits = ''.join(c for c in str(cnpj_raw) if c.isdigit())
    if len(digits) == 14:
        return f'{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}'
    return cnpj_raw  # Retorna como está se não tem 14 dígitos


def _replace_header_placeholders(doc, context):
    """Substitui placeholders no header do template DOCX com dados reais."""
    condominio = context.get('condominio', {})
    tipo_evento = context.get('tipo_evento', {})

    nome_cond = condominio.get('nome', '').upper()
    cnpj = _format_cnpj(condominio.get('cnpj', ''))

    # Montar título do tipo de assembleia
    nome_tipo = tipo_evento.get('nome', '')
    if nome_tipo:
        tipo_titulo = f'ATA DA {nome_tipo.upper()}'
    else:
        tipo_titulo = 'ATA DE ASSEMBLEIA'

    # Substituições: o template tem 2 linhas no textbox do header
    # Linha 1: "CONDOMÍNIO XXXXXXXX" → nome do condomínio
    # Linha 2: "ATA DE ASSEMBLEIA GERAL ORDINÁRIA CNPJ: 00.000.000/0001-59" → tipo + CNPJ
    cnpj_line = f'{tipo_titulo}'
    if cnpj:
        cnpj_line += f' CNPJ: {cnpj}'

    replacements = {
        'CONDOMÍNIO XXXXXXXX': nome_cond,
        'ATA DE ASSEMBLEIA GERAL ORDINÁRIA': tipo_titulo,
    }
    # O CNPJ pode estar em runs separados, vamos substituir a linha inteira
    cnpj_replacements = {
        'ATA DE ASSEMBLEIA GERAL ORDINÁRIÁ CNPJ: 00.000.000/0001-59': cnpj_line,
        'ATA DE ASSEMBLEIA GERAL ORDINÁRIA CNPJ: 00.000.000/0001-59': cnpj_line,
    }

    # Aplicar substituições em todas as seções do header
    # Primeiro as linhas completas (CNPJ), depois as parciais
    all_replacements = {**cnpj_replacements, **replacements}
    for section in doc.sections:
        for hdr in [section.header, section.even_page_header, section.first_page_header]:
            try:
                _replace_in_element(hdr._element, all_replacements)
            except Exception:
                pass


def _replace_in_element(element, replacements):
    """Substitui texto em todos os <w:t> dentro de um elemento XML.
    Processa cada <w:p> individualmente para não misturar parágrafos de textboxes."""
    ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

    # Encontrar todos os textboxContent e processar parágrafos dentro de cada um
    vml_ns = '{urn:schemas-microsoft-com:vml}'
    txbx_contents = element.findall(f'.//{vml_ns}textbox/{ns}txbxContent')

    # Se não tem textbox, processar parágrafos diretos
    containers = txbx_contents if txbx_contents else [element]

    for container in containers:
        for p_elem in container.findall(f'{ns}p'):
            runs = p_elem.findall(f'.//{ns}r')
            if not runs:
                continue

            # Concatenar texto dos runs DESTE parágrafo apenas
            full_text = ''
            for run in runs:
                t_elem = run.find(f'{ns}t')
                if t_elem is not None and t_elem.text:
                    full_text += t_elem.text

            # Verificar se algum replacement se aplica
            for old, new in replacements.items():
                if old in full_text:
                    new_text = full_text.replace(old, new)
                    # Colocar todo o texto no primeiro run e limpar os outros
                    first_t = True
                    for run in runs:
                        t_elem = run.find(f'{ns}t')
                        if t_elem is not None:
                            if first_t:
                                t_elem.text = new_text
                                t_elem.set(qn('xml:space'), 'preserve')
                                first_t = False
                            else:
                                t_elem.text = ''
                    break
