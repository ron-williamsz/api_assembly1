"""
Extrai texto de editais (PDF, DOCX, imagem) e usa IA para extrair
ordem do dia e títulos de deliberações.
"""
import json
import requests
from io import BytesIO

API_REMOTA = 'http://192.168.0.77:5358'


def extrair_texto_docx(file_bytes: bytes) -> str:
    from docx import Document
    doc = Document(BytesIO(file_bytes))
    return '\n'.join(p.text for p in doc.paragraphs if p.text.strip())


def extrair_texto_pdf(file_bytes: bytes) -> str:
    import pdfplumber
    text_parts = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return '\n'.join(text_parts)


def extrair_texto(filename: str, file_bytes: bytes) -> str:
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    if ext in ('docx',):
        return extrair_texto_docx(file_bytes)
    elif ext in ('pdf',):
        return extrair_texto_pdf(file_bytes)
    elif ext in ('doc',):
        raise ValueError('Formato .doc não suportado. Converta para .docx ou PDF.')
    elif ext in ('jpg', 'jpeg', 'png', 'bmp', 'tiff', 'webp'):
        raise ValueError('Imagens ainda não são suportadas. Envie PDF ou DOCX.')
    else:
        # Tenta como texto puro
        try:
            return file_bytes.decode('utf-8')
        except Exception:
            raise ValueError(f'Formato não suportado: .{ext}')


def analisar_edital_com_ia(texto_edital: str) -> dict:
    """Chama POST /assistente na API remota para extrair ordem do dia e deliberações."""

    instrucao = """Analise este edital de convocação de assembleia condominial e extraia:

1. **ordem_do_dia**: Lista de todos os itens da ordem do dia/pauta, na ordem em que aparecem. Cada item deve ser uma string com o número e título.
2. **deliberacoes_titulos**: Lista dos títulos/assuntos que serão deliberados. Geralmente correspondem aos itens da ordem do dia, mas podem ter subtítulos mais detalhados.

Responda APENAS com JSON válido neste formato exato:
{
  "ordem_do_dia": ["1 - Título do item 1", "2 - Título do item 2", ...],
  "deliberacoes_titulos": ["Título deliberação 1", "Título deliberação 2", ...]
}

Não inclua explicações, apenas o JSON."""

    resp = requests.post(
        f'{API_REMOTA}/assistente',
        json={
            'instrucao': instrucao,
            'texto': texto_edital,
            'stream': False
        },
        timeout=60
    )

    if not resp.ok:
        raise RuntimeError(f'Erro ao chamar assistente IA: {resp.status_code}')

    data = resp.json()
    resultado = data.get('resultado', '')

    # Tenta extrair JSON da resposta
    try:
        # A IA pode retornar o JSON dentro de markdown ```json ... ```
        clean = resultado.strip()
        if clean.startswith('```'):
            # Remove ```json e ```
            lines = clean.split('\n')
            json_lines = []
            inside = False
            for line in lines:
                if line.strip().startswith('```') and not inside:
                    inside = True
                    continue
                elif line.strip() == '```' and inside:
                    break
                elif inside:
                    json_lines.append(line)
            clean = '\n'.join(json_lines)

        parsed = json.loads(clean)
        return {
            'ordem_do_dia': parsed.get('ordem_do_dia', []),
            'deliberacoes_titulos': parsed.get('deliberacoes_titulos', []),
        }
    except json.JSONDecodeError:
        # Fallback: retorna o texto bruto e listas vazias
        return {
            'ordem_do_dia': [],
            'deliberacoes_titulos': [],
        }


def processar_edital(filename: str, file_bytes: bytes) -> dict:
    """Pipeline completo: extrai texto → analisa com IA → retorna dados estruturados."""
    texto = extrair_texto(filename, file_bytes)

    if not texto.strip():
        raise ValueError('Não foi possível extrair texto do arquivo.')

    resultado = analisar_edital_com_ia(texto)
    resultado['texto_edital'] = texto

    return resultado
