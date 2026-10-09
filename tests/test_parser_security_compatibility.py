"""Small local fixtures exercise the reviewed optional parser releases."""

import pytest

from book_to_skill.parsers.pdf import extract_with_pypdf


@pytest.mark.parametrize("compressed", [False, True])
def test_pypdf_extracts_text_from_a_real_local_pdf(tmp_path, compressed):
    pypdf = pytest.importorskip("pypdf")
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

    writer = pypdf.PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
    })
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 20 100 Td (Parser security smoke) Tj ET")
    page[NameObject("/Contents")] = content.flate_encode() if compressed else content
    path = tmp_path / "synthetic.pdf"
    writer.write(path)
    assert "Parser security smoke" in extract_with_pypdf(str(path))


def test_docling_converts_local_markdown_without_pdf_models(tmp_path):
    pytest.importorskip("docling")
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import PdfPipelineOptions

    # Import and construct the same option types as our technical PDF wrapper,
    # but convert only Markdown: no PDF pipeline or model download is started.
    options = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
    assert PdfFormatOption(pipeline_options=options).pipeline_options is options
    path = tmp_path / "synthetic.md"
    path.write_text("# Parser security smoke\n\nLocal content only.\n", encoding="utf-8")
    result = DocumentConverter(allowed_formats=[InputFormat.MD]).convert(path)
    exported = result.document.export_to_markdown()
    assert "Parser security smoke" in exported
    assert "Local content only." in exported


def test_pypdf_rejects_more_than_sixteen_stream_filters():
    pytest.importorskip("pypdf")
    from pypdf._configuration import get_configuration
    from pypdf.errors import LimitReachedError
    from pypdf.filters import decode_stream_data
    from pypdf.generic import ArrayObject, EncodedStreamObject, NameObject

    configuration = get_configuration()
    assert configuration.stream_filters_maximum_length == 16
    assert configuration.stream_decoding_work_maximum_length == 300_000_000
    stream = EncodedStreamObject()
    stream._data = b""
    stream[NameObject("/Filter")] = ArrayObject(
        [NameObject("/ASCIIHexDecode")] * 16
    )
    assert decode_stream_data(stream) == b""
    stream[NameObject("/Filter")].append(NameObject("/ASCIIHexDecode"))
    # Even an empty stream must reject an excessive filter chain before decode.
    with pytest.raises(LimitReachedError, match="Maximum filter count"):
        decode_stream_data(stream)


def test_pypdf_counts_both_input_and_output_decoding_work():
    pytest.importorskip("pypdf")
    from pypdf._configuration import apply_configuration
    from pypdf.errors import LimitReachedError
    from pypdf.filters import decode_stream_data
    from pypdf.generic import EncodedStreamObject, NameObject

    stream = EncodedStreamObject()
    stream._data = b"41>"
    stream[NameObject("/Filter")] = NameObject("/ASCIIHexDecode")
    with apply_configuration(stream_decoding_work_maximum_length=4):
        assert decode_stream_data(stream) == b"A"
    with apply_configuration(stream_decoding_work_maximum_length=3):
        with pytest.raises(LimitReachedError, match="maximum accumulated"):
            decode_stream_data(stream)
