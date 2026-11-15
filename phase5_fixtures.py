"""Deterministic blank, mixed and OCR-text fixtures derived without an LLM."""
from io import BytesIO
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, DecodedStreamObject, NameObject, TextStringObject


def text_pdf(text):
    writer=PdfWriter();page=writer.add_blank_page(width=612,height=792)
    add_text(writer,page,text)
    out=BytesIO();writer.write(out);return out.getvalue()


def add_text(writer,page,text,invisible=False):
    resources=page.get('/Resources')
    resources=resources.get_object() if resources is not None else DictionaryObject()
    fonts=resources.get('/Font')
    fonts=fonts.get_object() if fonts is not None else DictionaryObject()
    fonts[NameObject('/TestOCR')]=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    resources[NameObject('/Font')]=fonts;page[NameObject('/Resources')]=resources
    escaped=text.replace('\\','\\\\').replace('(','\\(').replace(')','\\)')
    stream=DecodedStreamObject();stream.set_data(b'q BT /TestOCR 12 Tf '+(b'3 Tr ' if invisible else b'')+b'40 700 Td ('+escaped.encode('ascii')+b') Tj ET Q')
    old=page.get('/Contents');new=writer._add_object(stream)
    page[NameObject('/Contents')]=ArrayObject([old,new]) if old is not None else new


def make_fixture(kind,root):
    if kind=='blank':
        writer=PdfWriter();writer.add_blank_page(width=612,height=792)
    elif kind=='mixed':
        writer=PdfWriter(clone_from=BytesIO((root/'fixtures'/'inputs'/'goodAccessible.pdf').read_bytes()))
        writer.add_page(PdfReader(root/'fixtures'/'inputs'/'ocr-unreadable-scan.pdf').pages[0])
        writer.add_blank_page(width=612,height=792)
    elif kind=='ocr-text':
        writer=PdfWriter(clone_from=BytesIO((root/'fixtures'/'inputs'/'ocr-unreadable-scan.pdf').read_bytes()))
        add_text(writer,writer.pages[0],'Recognized text from the page image.',invisible=True)
        writer.add_metadata({'/Title':'OCR text-layer fixture'})
        writer._root_object[NameObject('/Lang')]=TextStringObject('en-US')
    else: raise ValueError('Unknown synthetic fixture kind')
    out=BytesIO();writer.write(out);return out.getvalue()
