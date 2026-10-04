"""Synthetic PDF builders for evaluation and testing."""

from __future__ import annotations

import datetime
import io
import os
import tempfile
from pathlib import Path

import pikepdf
import pymupdf as fitz
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign import fields, signers
from pymupdf import mupdf


def make_plain_pdf(text: str = "This is a clean, standard contract document.", num_pages: int = 1) -> bytes:
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((50, 100), f"Page {i + 1}\n{text}", fontsize=11, fontname="helv", color=(0, 0, 0))
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_pdf_with_headers_footers() -> bytes:
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page(width=595, height=842)
        # Header
        page.insert_text((50, 40), "MASTER SERVICES AGREEMENT - CONFIDENTIAL", fontsize=9, fontname="helv", color=(0.3, 0.3, 0.3))
        # Body
        page.insert_text((50, 150), f"Section {i + 1}: General Terms and Operational Requirements.", fontsize=11, fontname="helv")
        page.insert_text((50, 180), "Both parties agree to standard commercial operational terms.", fontsize=11, fontname="helv")
        # Footer
        page.insert_text((270, 810), f"- Page {i + 1} of 3 -", fontsize=9, fontname="helv", color=(0.4, 0.4, 0.4))
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_pdf_with_links() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 100), "Visit our official legal portal for terms: https://example.com/terms", fontsize=11, fontname="helv")
    link_rect = fitz.Rect(50, 95, 300, 115)
    page.insert_link({"kind": fitz.LINK_URI, "from": link_rect, "uri": "https://example.com/terms"})
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_pdf_with_highlights() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 100), "This important indemnification clause is highlighted for review.", fontsize=11, fontname="helv")
    highlight_rect = fitz.Rect(50, 95, 250, 115)
    page.add_highlight_annot(highlight_rect)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_pdf_with_form_fields() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 100), "Customer Name: ", fontsize=11, fontname="helv")
    widget = fitz.Widget()
    widget.rect = fitz.Rect(150, 88, 350, 108)
    widget.field_type = mupdf.PDF_WIDGET_TYPE_TEXT
    widget.field_name = "customer_name"
    widget.field_value = "John Doe"
    page.add_widget(widget)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_word_like_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "CONFIDENTIAL AGREEMENT", fontsize=16, fontname="times-bold")
    page.insert_text((72, 120), "This agreement is drafted in Microsoft Word 2019.", fontsize=11, fontname="times-roman")
    now_pdf = datetime.datetime.now(datetime.UTC).strftime("D:%Y%m%d%H%M%SZ")
    doc.set_metadata({
        "producer": "Microsoft: Print to PDF",
        "creator": "Microsoft Word 2019",
        "creationDate": now_pdf,
        "modDate": now_pdf,
        "title": "Confidential Agreement",
    })
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_gdocs_like_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "Google Docs Draft Contract", fontsize=14, fontname="helv")
    page.insert_text((72, 110), "Exported directly via Chrome headless print.", fontsize=10, fontname="helv")
    now_pdf = datetime.datetime.now(datetime.UTC).strftime("D:%Y%m%d%H%M%SZ")
    doc.set_metadata({
        "producer": "Skia/PDF m115 Google Docs Renderer",
        "creator": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "creationDate": now_pdf,
        "modDate": now_pdf,
    })
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_scanned_pdf() -> bytes:
    """PDF with a dummy image occupying the page, simulating a scan with no text layer."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 400, 600), 0)
    pix.clear_with(245)
    page.insert_image(fitz.Rect(50, 50, 545, 792), pixmap=pix)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_mixed_fonts_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 80), "Title Header in 24pt Helvetica", fontsize=24, fontname="helv")
    page.insert_text((50, 130), "Section Header in 14pt Times-Bold", fontsize=14, fontname="times-bold")
    page.insert_text((50, 170), "Standard body paragraph in 10pt Times-Roman.", fontsize=10, fontname="times-roman")
    page.insert_text((50, 780), "Footnote 1: Legitimate footnote in 7pt Helvetica.", fontsize=7, fontname="helv", color=(0.2, 0.2, 0.2))
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_embedded_images_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 80), "Contract with Company Seal & Logo", fontsize=12, fontname="helv")
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 80, 80), 0)
    pix.clear_with(180)
    page.insert_image(fitz.Rect(450, 50, 530, 130), pixmap=pix)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_signed_pdf(
    modify_after: bool = False,
    corrupt_bytes: bool = False,
    sig_field_name: str = "Signature1",
) -> bytes:
    """Generate a valid signed PDF using pyHanko and a test certificate."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test Signer")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=30))
        .sign(key, hashes.SHA256())
    )

    kfd, kpath = tempfile.mkstemp(suffix=".pem")
    cfd, cpath = tempfile.mkstemp(suffix=".pem")
    os.close(kfd)
    os.close(cfd)

    try:
        Path(kpath).write_bytes(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        Path(cpath).write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        signer = signers.SimpleSigner.load(key_file=kpath, cert_file=cpath)

        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((100, 100), "Legitimate Signed Agreement between Alpha and Beta.")
        buf = io.BytesIO()
        doc.save(buf)
        doc.close()

        w = IncrementalPdfFileWriter(buf)
        fields.append_signature_field(w, sig_field_spec=fields.SigFieldSpec(sig_field_name=sig_field_name))
        out = io.BytesIO()
        signers.sign_pdf(w, signers.PdfSignatureMetadata(field_name=sig_field_name), signer=signer, output=out)
        signed_bytes = out.getvalue()

        if corrupt_bytes:
            arr = bytearray(signed_bytes)
            arr[120] ^= 0xFF
            return bytes(arr)

        if modify_after:
            tfd, tpath = tempfile.mkstemp(suffix=".pdf")
            os.close(tfd)
            try:
                Path(tpath).write_bytes(signed_bytes)
                t_doc = fitz.open(tpath)
                p = t_doc[0]
                p.insert_text((100, 250), "TAMPERED CLAUSE: Payment changed to Rs. 99,00,000", fontsize=12, color=(0, 0, 0))
                t_doc.save(tpath, incremental=True, encryption=mupdf.PDF_ENCRYPT_KEEP)
                t_doc.close()
                return Path(tpath).read_bytes()
            finally:
                Path(tpath).unlink(missing_ok=True)

        return signed_bytes
    finally:
        Path(kpath).unlink(missing_ok=True)
        Path(cpath).unlink(missing_ok=True)


def make_incremental_pdf(
    edit_text: bool = True,
    edit_amount: bool = False,
    append_page: bool = False,
    metadata_only: bool = False,
) -> bytes:
    """Create a PDF with an incremental update revision."""
    tfd, tpath = tempfile.mkstemp(suffix=".pdf")
    os.close(tfd)
    try:
        doc = fitz.open()
        p = doc.new_page(width=595, height=842)
        if edit_amount:
            p.insert_text((50, 100), "The fee is Rs. 10,00,000 payable upon invoice.", fontsize=11)
        else:
            p.insert_text((50, 100), "Initial clause content in first revision.", fontsize=11)
        doc.save(tpath)
        doc.close()

        doc2 = fitz.open(tpath)
        if metadata_only:
            doc2.set_metadata({"title": "Updated Title Only"})
        elif append_page:
            p2 = doc2.new_page(width=595, height=842)
            p2.insert_text((50, 100), "Appended page content.", fontsize=11)
        elif edit_amount:
            p0 = doc2[0]
            p0.add_redact_annot(fitz.Rect(110, 90, 220, 115), fill=(1, 1, 1))
            p0.apply_redactions()
            p0.insert_text((110, 100), "Rs. 99,00,000", fontsize=11)
        elif edit_text:
            p0 = doc2[0]
            p0.insert_text((50, 150), "Subsequent modification added in revision 2.", fontsize=11)

        doc2.save(tpath, incremental=True, encryption=mupdf.PDF_ENCRYPT_KEEP)
        doc2.close()

        return Path(tpath).read_bytes()
    finally:
        Path(tpath).unlink(missing_ok=True)


def make_hidden_text_pdf(kind: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 100), "Normal visible contract text here.", fontsize=11, color=(0, 0, 0))

    if kind == "white_on_white":
        page.insert_text((50, 150), "Secret clause inserted in pure white text", fontsize=10, color=(1.0, 1.0, 1.0))
    elif kind == "sub_1pt":
        page.insert_text((50, 150), "Microscopic liability disclaimer inserted here", fontsize=0.5, color=(0, 0, 0))
    elif kind == "render_mode_3":
        page.insert_text((50, 150), "Invisible render mode 3 text secret", fontsize=10, render_mode=3)
    elif kind == "offpage":
        page.insert_text((9000, 9000), "Text placed way off the printable page area", fontsize=10)
    elif kind == "occluded":
        page.insert_text((50, 200), "Hidden text completely covered by solid white rectangle", fontsize=11, color=(0, 0, 0))
        shape = page.new_shape()
        shape.draw_rect(fitz.Rect(40, 185, 450, 215))
        shape.finish(fill=(1.0, 1.0, 1.0))
        shape.commit()
    elif kind == "white_on_dark":
        shape = page.new_shape()
        shape.draw_rect(fitz.Rect(40, 250, 500, 300))
        shape.finish(fill=(0.1, 0.1, 0.1))
        shape.commit()
        page.insert_text((50, 280), "Legitimate white heading on dark header bar", fontsize=12, color=(1.0, 1.0, 1.0))

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_active_content_pdf(kind: str) -> bytes:
    base = make_plain_pdf()
    pdf = pikepdf.Pdf.open(io.BytesIO(base))

    if kind == "javascript":
        pdf.Root.Names = pikepdf.Dictionary(
            JavaScript=pikepdf.Dictionary(
                Names=pikepdf.Array([
                    pikepdf.String("MaliciousJS"),
                    pikepdf.Dictionary(
                        S=pikepdf.Name("/JavaScript"),
                        JS=pikepdf.String("app.alert('Injected JS');"),
                    ),
                ])
            )
        )
    elif kind == "launch":
        pdf.Root.OpenAction = pikepdf.Dictionary(
            S=pikepdf.Name("/Launch"),
            F=pikepdf.String("cmd.exe"),
        )
    elif kind == "open_action":
        pdf.Root.OpenAction = pikepdf.Dictionary(
            S=pikepdf.Name("/JavaScript"),
            JS=pikepdf.String("this.print();"),
        )
    elif kind == "overlay":
        page = pdf.pages[0]
        annot = pikepdf.Dictionary(
            Type=pikepdf.Name("/Annot"),
            Subtype=pikepdf.Name("/Square"),
            Rect=pikepdf.Array([50, 50, 550, 750]),
        )
        page.Annots = pikepdf.Array([annot])

    buf = io.BytesIO()
    pdf.save(buf)
    pdf.close()
    return buf.getvalue()


def make_metadata_pdf(kind: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 100), "Document with specific metadata configuration.")

    now = datetime.datetime.now(datetime.UTC)
    if kind == "future_date":
        future = now + datetime.timedelta(days=365)
        doc.set_metadata({
            "creationDate": future.strftime("D:%Y%m%d%H%M%SZ"),
            "modDate": future.strftime("D:%Y%m%d%H%M%SZ"),
        })
    elif kind == "mod_before_create":
        create_dt = now
        mod_dt = now - datetime.timedelta(days=10)
        doc.set_metadata({
            "creationDate": create_dt.strftime("D:%Y%m%d%H%M%SZ"),
            "modDate": mod_dt.strftime("D:%Y%m%d%H%M%SZ"),
        })
    elif kind == "ilovepdf":
        doc.set_metadata({
            "producer": "iLovePDF Online PDF Editor v2.1",
            "creator": "ilovepdf.com",
            "creationDate": now.strftime("D:%Y%m%d%H%M%SZ"),
            "modDate": now.strftime("D:%Y%m%d%H%M%SZ"),
        })

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()
