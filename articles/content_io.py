"""Small, dependency-free Markdown and DOCX adapters for article portability."""

from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile
import xml.etree.ElementTree as ET


WORD_NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}


def docx_to_markdown(uploaded_file):
    """Extract paragraph text from a DOCX without requiring python-docx."""
    uploaded_file.seek(0)
    with ZipFile(uploaded_file) as archive:
        xml = archive.read('word/document.xml')
    root = ET.fromstring(xml)
    paragraphs = []
    for paragraph in root.findall('.//w:body/w:p', WORD_NS):
        text = ''.join(node.text or '' for node in paragraph.findall('.//w:t', WORD_NS)).strip()
        if not text:
            continue
        style = paragraph.find('./w:pPr/w:pStyle', WORD_NS)
        style_name = style.get('{%s}val' % WORD_NS['w']) if style is not None else ''
        if style_name in {'Heading1', 'heading 1'}:
            text = f'# {text}'
        elif style_name in {'Heading2', 'heading 2'}:
            text = f'## {text}'
        paragraphs.append(text)
    return '\n\n'.join(paragraphs)


def markdown_document(title, subtitle, content, summary=''):
    parts = [f'# {title}']
    if subtitle:
        parts.append(f'## {subtitle}')
    if summary:
        parts.append(f'> {summary}')
    parts.append(content or '')
    return '\n\n'.join(parts).strip() + '\n'


def markdown_to_docx(title, content):
    """Build a minimal valid DOCX package for newsroom handoff."""
    document_source = content or ''
    paragraphs = []
    for line in (f'# {title}\n\n{document_source}').splitlines():
        value = line.strip()
        if not value:
            paragraphs.append('<w:p/>')
            continue
        style = ''
        if value.startswith('## '):
            style = '<w:pPr><w:pStyle w:val="Heading2"/></w:pPr>'
            value = value[3:]
        elif value.startswith('# '):
            style = '<w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
            value = value[2:]
        paragraphs.append(f'<w:p>{style}<w:r><w:t xml:space="preserve">{escape(value)}</w:t></w:r></w:p>')
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>' + ''.join(paragraphs) +
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>'
        '</w:body></w:document>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '</Types>'
    )
    relationships = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '</Relationships>'
    )
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', content_types)
        archive.writestr('_rels/.rels', relationships)
        archive.writestr('word/document.xml', document)
    output.seek(0)
    return output
