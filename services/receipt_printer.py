"""Receipt printer service – PyQt6 Windows native printing + PDF fallback."""
import os
import io
import sys
import tempfile
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

from PyQt6.QtPrintSupport import QPrinter, QPrinterInfo
from PyQt6.QtGui import QTextDocument, QPainter, QPageSize
from PyQt6.QtCore import QMarginsF, QSizeF, QCoreApplication
from PyQt6.QtWidgets import QApplication


class ReceiptPrinter:
    """
    Handles receipt printing via:
      - PyQt6 Windows native printer (QPrinter → default printer)
      - PDF file generation (reportlab) as fallback
    """

    def __init__(self, config):
        self.config = config
        self._printer = None
        self._ensure_qt_app()
    
    def _ensure_qt_app(self):
        """Ensure QApplication exists for PyQt6 printing."""
        app = QApplication.instance()
        if app is None:
            # Create QApplication for non-GUI context
            QApplication(sys.argv)


    # ================================================================ #
    #  PyQt6 Windows Native Printing (Primary Method)                 #
    # ================================================================ #
    def print_to_windows_default(self, receipt_data: Dict, items: List[Dict],
                                  customer: Optional[Dict] = None) -> bool:
        """Print to the default system printer. Works with thermal 80mm/58mm."""
        try:
            default_printer_info = QPrinterInfo.defaultPrinter()
            if not default_printer_info or not default_printer_info.printerName():
                print("[Printer] No default printer found. Falling back to PDF.")
                return False

            page_width_mm = float(self.config.get("receipt_paper_width", 80))
            html_content = self._generate_receipt_html(receipt_data, items, customer)

            # ScreenResolution → CSS pixels (96 DPI).  doc.print() handles
            # the scaling to the printer's real DPI automatically —
            # just like a browser's @media print.
            printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
            printer.setPrinterName(default_printer_info.printerName())

            # Continuous page: 80 mm wide, absurdly tall so Qt never
            # inserts a page-break.  Thermal printer feeds only what it needs.
            continuous_page = QPageSize(
                QSizeF(page_width_mm, 5000),
                QPageSize.Unit.Millimeter,
                "Receipt",
                QPageSize.SizeMatchPolicy.ExactMatch,
            )
            printer.setPageSize(continuous_page)
            printer.setPageMargins(QMarginsF(0, 0, 0, 0))

            # Layout width: 80 mm expressed in CSS pixels (96 DPI).
            css_width = page_width_mm * 96.0 / 25.4          # ≈ 302 px

            doc = QTextDocument()
            doc.setDocumentMargin(0)
            doc.setHtml(html_content)
            doc.setTextWidth(css_width)
            # Make the document's own page match so it won't paginate internally
            doc.setPageSize(QSizeF(css_width, 50000))

            # doc.print() is the Qt equivalent of window.print() — it
            # creates a QPainter, scales CSS→device DPI, and renders.
            doc.print(printer)

            print(f"[Printer] Receipt printed to '{default_printer_info.printerName()}'")
            return True

        except Exception as e:
            print(f"[Printer] Native printing error: {e}")
            return False

    def _generate_receipt_html(self, sale: Dict, items: List[Dict],
                                customer: Optional[Dict]) -> str:
        """Generate a professional HTML receipt compatible with Qt's HTML renderer."""

        sym       = self.config.get("currency_symbol", "$")
        bname     = self.config.get("business_name", "CanadaMart")
        tagline   = self.config.get("business_tagline", "")
        addr      = self.config.get("business_address", "")
        phone     = self.config.get("business_phone", "")
        email     = self.config.get("business_email", "")
        header    = self.config.get("receipt_header", "")
        footer    = self.config.get("receipt_footer", "Thank you for your purchase!")
        tax_name  = self.config.get("tax_name", "Tax")
        show_logo = self.config.get("receipt_show_logo", True)
        logo_path = (self.config.get("receipt_logo_path", "").strip()
                     or self.config.get("logo_path", "").strip())
        dt        = datetime.now().strftime("%d %b %Y  %H:%M")

        # -- logo as base64 data-URI --------------------------------------
        logo_html = ""
        if show_logo and logo_path and os.path.exists(logo_path):
            try:
                import base64
                from PyQt6.QtGui import QImage
                from PyQt6.QtCore import QBuffer, QIODevice, QByteArray
                img = QImage(logo_path)
                if not img.isNull():
                    buf = QByteArray()
                    qbuf = QBuffer(buf)
                    qbuf.open(QIODevice.OpenModeFlag.WriteOnly)
                    img.save(qbuf, "PNG")
                    qbuf.close()
                    b64 = base64.b64encode(bytes(buf)).decode()
                    logo_html = (
                        f'<img src="data:image/png;base64,{b64}" '
                        f'style="max-width:160px; max-height:70px;"/>'
                    )
            except Exception:
                pass

        # -- store info lines ---------------------------------------------
        store_info_rows = ""
        for line in [tagline, addr, phone, email, header]:
            if line:
                store_info_rows += (
                    f'<tr><td align="center" style="font-size:9px; color:#000; '
                    f'font-weight:700; padding:0;">{line}</td></tr>'
                )

        # -- item rows ----------------------------------------------------
        rows_html = ""
        for item in items:
            name  = item["product_name"]
            qty   = int(item["quantity"])
            price = float(item.get("unit_price", 0))
            itotal = float(item["total"])
            disc  = float(item.get("discount_percent", 0))
            disc_badge = ""
            if disc > 0:
                disc_badge = (
                    f' <span style="font-size:10px; color:#000; '
                    f'font-weight:bold;">[DISC -{disc:.0f}%]</span>'
                )
            rows_html += f"""
            <tr>
              <td style="padding:1px 0; border-bottom:1px solid #000; vertical-align:middle;
                         font-size:8px; font-weight:700; color:#000;">{name}{disc_badge}</td>
              <td style="padding:1px 0; border-bottom:1px solid #000; vertical-align:middle;
                         text-align:center; font-size:8px; font-weight:700; color:#000; white-space:nowrap;">{qty}&times;{sym}{price:.2f}</td>
              <td style="padding:1px 0; border-bottom:1px solid #000; vertical-align:middle;
                         text-align:right; font-size:8px; font-weight:700; color:#000; white-space:nowrap;">{sym}{itotal:.2f}</td>
            </tr>"""

        # -- totals -------------------------------------------------------
        subtotal = float(sale.get("subtotal", 0))
        tax      = float(sale.get("tax_amount", 0))
        disc_amt = float(sale.get("discount_amount", 0))
        total    = float(sale.get("total", 0))
        paid     = float(sale.get("amount_paid", total))
        change   = float(sale.get("change_amount", 0))
        method   = sale.get("payment_method", "cash").upper()

        totals_html = ""
        if disc_amt > 0:
            totals_html += f"""
            <tr>
              <td style="padding:1px 0; font-size:9px; font-weight:700; color:#000;">Subtotal</td>
              <td style="padding:1px 0; font-size:9px; font-weight:700; color:#000; text-align:right;">{sym}{subtotal:.2f}</td>
            </tr>
            <tr>
              <td style="padding:1px 0; font-size:9px; font-weight:700; color:#000;">Discount</td>
              <td style="padding:1px 0; font-size:9px; font-weight:700; color:#000; text-align:right;">-{sym}{disc_amt:.2f}</td>
            </tr>"""
        if tax > 0:
            totals_html += f"""
            <tr>
              <td style="padding:1px 0; font-size:9px; font-weight:700; color:#000;">{tax_name}</td>
              <td style="padding:1px 0; font-size:9px; font-weight:700; color:#000; text-align:right;">{sym}{tax:.2f}</td>
            </tr>"""

        totals_html += f"""
            <tr>
              <td style="padding:2px 0; font-size:9px; font-weight:800; color:#000;
                         border-top:1px solid #000;">TOTAL</td>
              <td style="padding:2px 0; font-size:9px; font-weight:800; color:#000;
                         border-top:1px solid #000; text-align:right;">{sym}{total:.2f}</td>
            </tr>
            <tr>
              <td style="padding:1px 0; font-size:8px; font-weight:700; color:#000;
                         border-bottom:1px solid #000;">Paid ({method})</td>
              <td style="padding:1px 0; font-size:8px; font-weight:700; color:#000;
                         border-bottom:1px solid #000; text-align:right;">{sym}{paid:.2f}</td>
            </tr>"""
        if change > 0:
            totals_html += f"""
            <tr>
              <td style="padding:1px 0; font-size:9px; color:#000; font-weight:700;">Change Due</td>
              <td style="padding:1px 0; font-size:9px; color:#000; font-weight:700;
                         text-align:right;">{sym}{change:.2f}</td>
            </tr>"""

        # -- customer block -----------------------------------------------
        cust_html = ""
        if customer:
            cust_name = customer.get('name', '')
            cust_mob  = customer.get('mobile', '')
            cust_line = cust_name
            if cust_mob:
                cust_line += f"&nbsp;&nbsp;{cust_mob}"
            cust_html = f"""
            <tr>
              <td colspan="2" style="padding:1px 3px; font-size:9px; color:#000;">
                <span style="font-size:8px; font-weight:700;">CUSTOMER:</span>&nbsp;
                <span style="font-weight:600;">{cust_line}</span>
              </td>
            </tr>"""

        if sale.get("notes"):
            cust_html += f"""
            <tr>
              <td colspan="2" style="padding:1px 3px; font-size:9px; color:#000;">
                <span style="font-size:8px; font-weight:700;">NOTE:</span>&nbsp;{sale['notes']}
              </td>
            </tr>"""

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0; padding:0; background:#fff; font-family:'Courier New',Courier,monospace;">

<table width="100%" cellpadding="0" cellspacing="0"
       style="background:#fff; color:#000; max-width:100%; margin:0; padding:0;">

  <!-- ── HEADER ──────────────────────────────────────── -->
  <tr>
    <td align="center" style="padding:1px 0;">
      {f'<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:0;">{logo_html}</td></tr></table>' if logo_html else ''}
      <div style="margin:0; padding:0; font-size:10px; font-weight:800; color:#000; text-align:center;">{bname}</div>
      <table width="100%" cellpadding="0" cellspacing="0">
        {store_info_rows}
      </table>
    </td>
  </tr>

  <!-- ── DIVIDER ──────────────────────────────────────── -->
  <tr>
    <td style="border-top:1px solid #000; font-size:0;">&nbsp;</td>
  </tr>

  <!-- ── INVOICE META ──────────────────────────────────── -->
  <tr>
    <td style="padding:1px 0;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="vertical-align:top;">
            <span style="font-size:8px; color:#000; font-weight:700;">INVOICE</span><br>
            <span style="font-size:9px; font-weight:700; color:#000;">{sale.get('invoice_number', '')}</span>
          </td>
          <td align="right" style="vertical-align:top;">
            <span style="font-size:8px; color:#000; font-weight:700;">DATE</span><br>
            <span style="font-size:9px; font-weight:700; color:#000;">{dt}</span>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ── CUSTOMER / NOTE ─────────────────────────────── -->
  {f"""<tr><td style="padding:0 3px;">
    <table width="100%" cellpadding="0" cellspacing="0">
      {cust_html}
    </table>
  </td></tr>""" if cust_html else ""}

  <!-- ── DOTTED DIVIDER ──────────────────────────────── -->
  <tr>
    <td style="border-top:1px dashed #000; font-size:0;">&nbsp;</td>
  </tr>

  <!-- ── ITEMS TABLE ──────────────────────────────────── -->
  <tr>
    <td style="padding:0;">
      <table width="100%" cellpadding="0" cellspacing="0"
             style="border-collapse:collapse;">
        <thead>
          <tr style="border-bottom:1px solid #000;">
            <th align="left"
                style="padding:1px 0; font-size:8px; color:#000;
                       font-weight:700; text-transform:uppercase;">Item</th>
            <th align="center"
                style="padding:1px 0; font-size:8px; color:#000;
                       font-weight:700; text-transform:uppercase;">Qty</th>
            <th align="right"
                style="padding:1px 0; font-size:8px; color:#000;
                       font-weight:700; text-transform:uppercase;">Amt</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </td>
  </tr>

  <!-- ── DOTTED DIVIDER ──────────────────────────────── -->
  <tr>
    <td style="border-top:1px dashed #000; font-size:0;">&nbsp;</td>
  </tr>

  <!-- ── TOTALS ───────────────────────────────────────── -->
  <tr>
    <td style="padding:0 0 1px 0;">
      <table width="100%" cellpadding="0" cellspacing="0"
             style="border-collapse:collapse;">
        {totals_html}
      </table>
    </td>
  </tr>

  <!-- ── SOLID DIVIDER ───────────────────────────────── -->
  <tr>
    <td style="border-top:1px solid #000; font-size:0;">&nbsp;</td>
  </tr>

  <!-- ── FOOTER ───────────────────────────────────────── -->
  <tr>
    <td align="center" style="padding:2px 2px 4px;">
      <div style="margin:0; padding:0 0 2px; font-size:9px; color:#000; font-weight:700;">{footer}</div>
      <div style="margin:0; padding:0; font-size:8px; font-weight:700; color:#000;">
        Printed {datetime.now().strftime('%d %b %Y  %H:%M')}
      </div>
    </td>
  </tr>

</table>
</body>
</html>"""


    # ================================================================ #
    #  Public API                                                      #
    # ================================================================ #
    def print_receipt(self, sale: Dict, items: List[Dict],
                      customer: Optional[Dict] = None) -> bool:
        """
        Print a receipt. 
        Primary: Uses PyQt6 Windows native printing (QPrinter)
        Fallback: PDF generation if native printing fails
        
        Returns True on success.
        """
        copies = int(self.config.get("receipt_copies", 1))

        # Try system default printer
        for _ in range(copies):
            ok = self.print_to_windows_default(sale, items, customer)
            if ok:
                return True

        # Fall back to PDF if no default printer configured or printing fails
        print("[Printer] Native printing failed, falling back to PDF.")
        path = self._generate_pdf(sale, items, customer)
        if path:
            self._open_pdf(path)
            return True

        return False

    def save_pdf(self, sale: Dict, items: List[Dict],
                 customer: Optional[Dict] = None,
                 directory: str = None) -> Optional[str]:
        """Save receipt as PDF and return file path."""
        return self._generate_pdf(sale, items, customer, directory)

    def print_barcode_label(self, barcode_image, product_name: str, 
                            price_str: str, copies: int = 1, 
                            settings: dict = None) -> bool:
        """
        Prints a barcode label via native printer or PDF fallback.
        """
        settings = settings or {}
        # Try system default printer
        try:
            ok = self._print_barcode_native(barcode_image, product_name,
                                            price_str, settings, copies)
            if ok:
                return True
        except Exception as e:
            print(f"[Printer] Native barcode printing failed: {e}")

        # Fall back to PDF
        print("[Printer] Native barcode printing failed, falling back to PDF.")
        path = self._generate_barcode_pdf(barcode_image, settings, copies)
        if path:
            self._open_pdf(path)
            return True

        return False

    def _print_barcode_native(self, barcode_image, product_name: str,
                             price_str: str, settings: dict,
                             copies: int) -> bool:
        """Print barcode label using PyQt6 native printer."""
        try:
            from PyQt6.QtGui import QPixmap

            default_printer_info = QPrinterInfo.defaultPrinter()
            if not default_printer_info or not default_printer_info.printerName():
                return False

            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setPrinterName(default_printer_info.printerName())

            # Label size from settings
            label_w = float(settings.get("barcode_label_width_mm", 50.0))
            label_h = float(settings.get("barcode_label_height_mm", 25.0))

            printer.setPageSize(QPageSize(QSizeF(label_w, label_h), QPageSize.Unit.Millimeter))
            printer.setPageMargins(QMarginsF(2, 2, 2, 2))
            printer.setCopyCount(copies)

            # Convert barcode image to QPixmap
            if isinstance(barcode_image, str):
                pixmap = QPixmap(barcode_image)
            else:
                pixmap = QPixmap.fromImage(barcode_image)

            painter = QPainter()
            if not painter.begin(printer):
                return False

            # Draw the barcode image scaled to fill the printable page rect
            page_rect = printer.pageRect(QPrinter.Unit.DevicePixel).toRect()
            painter.drawPixmap(page_rect, pixmap)

            painter.end()
            print(f"[Printer] Barcode label sent to printer ({copies} copies)")
            return True

        except Exception as e:
            print(f"[Printer] Native barcode printing error: {e}")
            return False
    def _generate_barcode_pdf(self, barcode_image, settings: dict, 
                             copies: int) -> Optional[str]:
        """Generate PDF barcode labels."""
        try:
            from reportlab.lib.units import mm
            from reportlab.pdfgen import canvas
            from reportlab.lib.utils import ImageReader
            
            fd, path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            
            width_mm = float(settings.get("barcode_label_width_mm", 50.0))
            height_mm = float(settings.get("barcode_label_height_mm", 25.0))
            
            c = canvas.Canvas(path, pagesize=(width_mm * mm, height_mm * mm))
            img_reader = ImageReader(barcode_image)
            
            for _ in range(copies):
                c.drawImage(img_reader, 0, 0, width=width_mm * mm, 
                           height=height_mm * mm, preserveAspectRatio=True, anchor='c')
                c.showPage()
                
            c.save()
            return path
        except Exception as e:
            print(f"[Printer] PDF barcode error: {e}")
            return None
    # ================================================================ #
    #  PDF Fallback Generation                                         #
    # ================================================================ #
    def _generate_pdf(self, sale: Dict, items: List[Dict],
                      customer: Optional[Dict],
                      directory: str = None) -> Optional[str]:
        """Generate a modern PDF receipt."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.lib import colors
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer,
                Table, TableStyle, HRFlowable,
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
        except ImportError:
            print("[Printer] reportlab not installed.")
            return None

        width_mm = int(self.config.get("receipt_paper_width", 80))
        if directory:
            Path(directory).mkdir(parents=True, exist_ok=True)
            inv = sale.get("invoice_number", "receipt")
            path = str(Path(directory) / f"{inv}.pdf")
        else:
            fd, path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)

        page_width  = width_mm * mm
        page_height = A4[1]
        lm = rm = 6 * mm
        content_w = page_width - lm - rm

        doc = SimpleDocTemplate(
            path,
            pagesize=(page_width, page_height),
            leftMargin=lm, rightMargin=rm,
            topMargin=8 * mm, bottomMargin=10 * mm,
        )

        # ── colour palette (black & white) ──────────────────────────── #
        BLACK   = colors.HexColor("#111111")
        DGREY   = colors.HexColor("#444444")
        MGREY   = colors.HexColor("#888888")
        LGREY   = colors.HexColor("#eeeeee")
        WHITE   = colors.white

        # ── styles ──────────────────────────────────────────────────── #
        def _style(name, size, bold=False, align=TA_LEFT,
                   color=BLACK, space_before=0, space_after=0):
            return ParagraphStyle(
                name,
                fontName="Helvetica-Bold" if bold else "Helvetica",
                fontSize=size,
                textColor=color,
                alignment=align,
                spaceBefore=space_before * mm,
                spaceAfter=space_after * mm,
                leading=size * 1.35,
            )

        biz_s   = _style("biz",   14, bold=True,  align=TA_CENTER)
        sub_s   = _style("sub",    8, bold=False, align=TA_CENTER, color=DGREY)
        lbl_s   = _style("lbl",    7, bold=False, color=MGREY)
        val_s   = _style("val",    9, bold=True)
        item_s  = _style("item",   8)
        item_sm = _style("itemsm", 7, color=MGREY)
        tot_s   = _style("tot",   12, bold=True,  align=TA_RIGHT)
        amt_s   = _style("amt",    8, align=TA_RIGHT, color=DGREY)
        ftr_s   = _style("ftr",    7, align=TA_CENTER, color=MGREY)

        sym      = self.config.get("currency_symbol", "$")
        tax_name = self.config.get("tax_name", "Tax")
        story    = []

        # ── logo ────────────────────────────────────────────────────── #
        show_logo = self.config.get("receipt_show_logo", True)
        logo_path = (self.config.get("receipt_logo_path", "").strip()
                     or self.config.get("logo_path", "").strip())
        if show_logo and logo_path and os.path.exists(logo_path):
            try:
                from reportlab.platypus import Image as RLImage
                logo_img = RLImage(logo_path, width=36*mm, height=18*mm, kind="proportional")
                logo_img.hAlign = "CENTER"
                story.append(logo_img)
                story.append(Spacer(1, 2*mm))
            except Exception:
                pass

        # ── business header ─────────────────────────────────────────── #
        story.append(Paragraph(self.config.get("business_name", ""), biz_s))
        for field in ["business_tagline", "business_address",
                      "business_phone", "business_email", "receipt_header"]:
            val = self.config.get(field, "")
            if val:
                story.append(Paragraph(val, sub_s))
        story.append(Spacer(1, 2*mm))
        story.append(HRFlowable(width="100%", thickness=1.2, color=BLACK))
        story.append(Spacer(1, 3*mm))

        # ── invoice meta ────────────────────────────────────────────── #
        dt = datetime.now().strftime("%d %b %Y  %H:%M")
        meta = [
            [Paragraph("INVOICE", lbl_s), Paragraph("DATE", lbl_s)],
            [Paragraph(sale.get("invoice_number", ""), val_s),
             Paragraph(dt, _style("dt", 8, align=TA_RIGHT, color=DGREY))],
        ]
        meta_tbl = Table(meta, colWidths=[content_w * 0.55, content_w * 0.45])
        meta_tbl.setStyle(TableStyle([
            ("ALIGN",        (1, 0), (1, -1), "RIGHT"),
            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING",   (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 1),
        ]))
        story.append(meta_tbl)

        if customer:
            story.append(Spacer(1, 1.5*mm))
            story.append(Paragraph("CUSTOMER", lbl_s))
            cname = customer.get("name", "")
            cmob  = customer.get("mobile", "")
            story.append(Paragraph(
                f"{cname}" + (f"  ·  {cmob}" if cmob else ""),
                _style("cn", 8, bold=True)
            ))
        if sale.get("notes"):
            story.append(Paragraph(f"Note: {sale['notes']}",
                                   _style("notes", 7, color=MGREY)))

        story.append(Spacer(1, 3*mm))
        story.append(HRFlowable(width="100%", thickness=0.5,
                                color=BLACK, dash=[2, 2]))
        story.append(Spacer(1, 2*mm))

        # ── items ────────────────────────────────────────────────────── #
        # header row
        hdr_row = [
            Paragraph("ITEM",   _style("h", 7, bold=True, color=MGREY)),
            Paragraph("AMOUNT", _style("h", 7, bold=True,
                                       align=TA_RIGHT, color=MGREY)),
        ]
        rows = [hdr_row]
        for item in items:
            disc = float(item.get("discount_percent", 0))
            disc_str = f"  −{disc:.0f}%" if disc > 0 else ""
            name_para = Paragraph(
                f"{item['product_name']}{disc_str}<br/>"
                f"<font color='#888888' size='7'>"
                f"{sym}{float(item.get('unit_price', 0)):.2f} &times; {int(item['quantity'])}"
                f"</font>",
                item_s
            )
            amt_para = Paragraph(
                f"{sym}{float(item['total']):.2f}",
                _style("a", 9, bold=True, align=TA_RIGHT)
            )
            rows.append([name_para, amt_para])

        items_tbl = Table(rows, colWidths=[content_w * 0.68, content_w * 0.32])
        items_tbl.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("ALIGN",         (1, 0), (1, -1),  "RIGHT"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LINEBELOW",     (0, 0), (-1, 0),  0.5, MGREY),
            ("LINEBELOW",     (0, 1), (-1, -1), 0.3, LGREY),
        ]))
        story.append(items_tbl)
        story.append(Spacer(1, 2*mm))
        story.append(HRFlowable(width="100%", thickness=0.5,
                                color=BLACK, dash=[2, 2]))
        story.append(Spacer(1, 2*mm))

        # ── totals ───────────────────────────────────────────────────── #
        subtotal = float(sale.get("subtotal", 0))
        tax      = float(sale.get("tax_amount", 0))
        disc_amt = float(sale.get("discount_amount", 0))
        total    = float(sale.get("total", 0))
        paid     = float(sale.get("amount_paid", total))
        change   = float(sale.get("change_amount", 0))
        method   = sale.get("payment_method", "cash").upper()

        def _tot_row(label, value, bold=False, top_rule=False):
            s = _style("tr", 9, bold=bold, align=TA_RIGHT)
            sl = _style("tl", 9, bold=bold, color=DGREY)
            row = [Paragraph(label, sl), Paragraph(value, s)]
            return row

        tot_rows = []
        if disc_amt > 0:
            tot_rows.append(_tot_row("Subtotal",      f"{sym}{subtotal:.2f}"))
            tot_rows.append(_tot_row("Discount",      f"-{sym}{disc_amt:.2f}"))
        if tax > 0:
            tot_rows.append(_tot_row(tax_name,        f"{sym}{tax:.2f}"))
        tot_rows.append(_tot_row("TOTAL",             f"{sym}{total:.2f}", bold=True))
        tot_rows.append(_tot_row(f"Paid ({method})", f"{sym}{paid:.2f}"))
        if change > 0:
            tot_rows.append(_tot_row("Change",        f"{sym}{change:.2f}"))

        tot_tbl = Table(tot_rows, colWidths=[content_w * 0.55, content_w * 0.45])
        tot_tbl.setStyle(TableStyle([
            ("ALIGN",         (1, 0), (1, -1),  "RIGHT"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            # thick rule above TOTAL row
            ("LINEABOVE",
             (0, tot_rows.index(
                 next(r for r in tot_rows
                      if r[0].text and "TOTAL" in r[0].text)
             )),
             (-1, tot_rows.index(
                 next(r for r in tot_rows
                      if r[0].text and "TOTAL" in r[0].text)
             )),
             1.2, BLACK),
        ]))
        story.append(tot_tbl)

        story.append(Spacer(1, 3*mm))
        story.append(HRFlowable(width="100%", thickness=1.2, color=BLACK))
        story.append(Spacer(1, 3*mm))

        # ── footer ───────────────────────────────────────────────────── #
        footer = self.config.get("receipt_footer", "Thank you for your purchase!")
        story.append(Paragraph(footer, ftr_s))
        story.append(Paragraph(
            datetime.now().strftime("%d %b %Y %H:%M"), ftr_s
        ))

        try:
            doc.build(story)
            return path
        except Exception as e:
            print(f"[Printer] PDF build error: {e}")
            return None


    def _open_pdf(self, path: str):
        """Open PDF in default viewer."""
        import subprocess, sys
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            print(f"[Printer] Open PDF error: {e}")

    def get_receipt_html(self, sale: Dict, items: List[Dict],
                         customer: Optional[Dict] = None) -> str:
        """Return the receipt HTML string (used for preview)."""
        return self._generate_receipt_html(sale, items, customer)


# ═══════════════════════════════════════════════════════════════════════════
#  Receipt Preview Dialog
# ═══════════════════════════════════════════════════════════════════════════
class ReceiptPreviewDialog:
    """
    Shows a receipt preview in a PyQt6 dialog using QTextBrowser.
    Call ReceiptPreviewDialog.show(parent, config, sale, items, customer)
    Returns True if user clicked Print, False otherwise.
    """

    @staticmethod
    def show(parent, config, sale: Dict, items: List[Dict],
             customer: Optional[Dict] = None) -> bool:
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel,
            QPushButton, QTextBrowser, QSizePolicy
        )
        from PyQt6.QtCore import Qt

        printer_svc = ReceiptPrinter(config)
        html = printer_svc.get_receipt_html(sale, items, customer)

        dlg = QDialog(parent)
        dlg.setWindowTitle(f"Receipt Preview – {sale.get('invoice_number', '')}")
        dlg.setMinimumSize(540, 640)
        dlg.resize(580, 760)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)

        title = QLabel("🧾  Receipt Preview")
        title.setStyleSheet("font-size:15px; font-weight:bold; color:#f1f5f9;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        browser = QTextBrowser()
        browser.setHtml(html)
        browser.setStyleSheet(
            "background:#ffffff; color:#000; border:1px solid #334155;"
            "border-radius:6px; padding:0px;"
        )
        browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(browser)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        close_btn = QPushButton("✖  Close")
        close_btn.setMinimumHeight(44)
        close_btn.setStyleSheet(
            "background:#374151; color:#f1f5f9; border-radius:6px; font-size:13px;"
        )
        close_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(close_btn)

        print_btn = QPushButton("🖨️  Print")
        print_btn.setMinimumHeight(44)
        print_btn.setObjectName("SuccessBtn")
        print_btn.setStyleSheet(
            "background:#16a34a; color:#fff; border-radius:6px; font-size:13px; font-weight:bold;"
        )
        print_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(print_btn)

        layout.addLayout(btn_row)

        result = dlg.exec()
        return result == QDialog.DialogCode.Accepted
