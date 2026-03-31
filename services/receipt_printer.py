"""Receipt printer service – PyQt6 Windows native printing + PDF fallback."""
import os
import io
import tempfile
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

from PyQt6.QtPrintSupport import QPrinter, QPrinterInfo
from PyQt6.QtGui import QTextDocument, QPainter
from PyQt6.QtCore import QMarginsF, QSizeF


class ReceiptPrinter:
    """
    Handles receipt printing via:
      - PyQt6 Windows native printer (QPrinter → default printer)
      - PDF file generation (reportlab) as fallback
    """

    def __init__(self, config):
        self.config = config
        self._printer = None

    # ================================================================ #
    #  PyQt6 Windows Native Printing (Primary Method)                 #
    # ================================================================ #
    def print_to_windows_default(self, receipt_data: Dict, items: List[Dict],
                                  customer: Optional[Dict] = None) -> bool:
        """
        Print directly to the Windows default printer using PyQt6 QPrinter.
        No print dialog - automatic, seamless printing.
        
        Args:
            receipt_data: Sale information dict
            items: List of sale items
            customer: Customer dict (optional)
            
        Returns:
            True on success, False on failure
        """
        try:
            # 1. Get system default printer
            default_printer_info = QPrinterInfo.defaultPrinter()
            if not default_printer_info.isValid():
                print("[Printer] No default printer found. Falling back to PDF.")
                return False

            # 2. Configure QPrinter for thermal receipt (80mm width)
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setPrinterName(default_printer_info.printerName())
            
            # Set custom page size for 80mm thermal roll
            # Standard thermal paper: 80mm width ≈ 3.15 inches
            # Height adjusts based on content
            page_width_mm = 80
            page_height_mm = 150  # Default, will be dynamically calculated
            
            printer.setPageSize(QPrinter.PageSize.Custom)
            printer.setPageSizeMM(page_width_mm, page_height_mm)
            
            # Set minimal margins for thermal receipt
            printer.setPageMargins(
                QMarginsF(2, 2, 2, 2)  # 2mm margins
            )
            
            # 3. Generate receipt HTML
            html_content = self._generate_receipt_html(receipt_data, items, customer)
            
            # 4. Create QTextDocument and render to printer
            doc = QTextDocument()
            doc.setHtml(html_content)
            
            # Set document width to match printer width
            doc.setPageSize(
                QSizeF(
                    printer.pageRect(QPrinter.Unit.Millimeter).width(),
                    printer.pageRect(QPrinter.Unit.Millimeter).height()
                )
            )
            
            # 5. Print the document
            doc.print(printer)
            
            print(f"[Printer] Receipt printed to '{default_printer_info.printerName()}'")
            return True
            
        except Exception as e:
            print(f"[Printer] PyQt6 native printing error: {e}")
            return False

    def _generate_receipt_html(self, sale: Dict, items: List[Dict],
                                customer: Optional[Dict]) -> str:
        """Generate HTML content for receipt - formatted for thermal printer."""
        
        sym = self.config.get("currency_symbol", "$")
        bname = self.config.get("business_name", "CanadaMart")
        tagline = self.config.get("business_tagline", "")
        addr = self.config.get("business_address", "")
        phone = self.config.get("business_phone", "")
        header = self.config.get("receipt_header", "")
        footer = self.config.get("receipt_footer", "Thank you!")
        
        # Format datetime
        dt = datetime.now().strftime("%d-%b-%Y  %H:%M")
        
        html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: 'Courier New', monospace;
                    margin: 0;
                    padding: 4px;
                    width: 80mm;
                    line-height: 1.2;
                    font-size: 11px;
                }}
                .center {{ text-align: center; }}
                .right {{ text-align: right; }}
                .left {{ text-align: left; }}
                h1 {{ font-size: 16px; font-weight: bold; margin: 2px 0; }}
                h2 {{ font-size: 12px; margin: 2px 0; }}
                .divider {{ border-bottom: 1px solid #000; margin: 4px 0; }}
                table {{ width: 100%; border-collapse: collapse; }}
                td {{ padding: 2px 0; }}
                .header {{ font-weight: bold; border-bottom: 1px solid #000; margin-bottom: 4px; }}
                .total {{ font-size: 14px; font-weight: bold; margin: 4px 0; }}
            </style>
        </head>
        <body>
            <!-- HEADER -->
            <div class="center">
                <h1>{bname}</h1>
        """
        
        if tagline:
            html += f"<div>{tagline}</div>"
        if addr:
            html += f"<div>{addr}</div>"
        if phone:
            html += f"<div>{phone}</div>"
        if header:
            html += f"<div>{header}</div>"
            
        html += """
            </div>
            <div class="divider"></div>
        """
        
        # INVOICE DETAILS
        html += f"""
            <div class="left">
                <strong>Invoice :</strong> {sale.get('invoice_number', '')}<br>
                <strong>Date    :</strong> {dt}<br>
        """
        
        if customer:
            html += f"<strong>Customer:</strong> {customer.get('name', '')}<br>"
            if customer.get("mobile"):
                html += f"<strong>Mobile  :</strong> {customer.get('mobile')}<br>"
                
        if sale.get("notes"):
            html += f"<strong>Notes   :</strong> {sale['notes']}<br>"
            
        html += """
            </div>
            <div class="divider"></div>
        """
        
        # ITEMS HEADER
        html += """
            <table class="header">
                <tr>
                    <td style="width: 55%;">Item</td>
                    <td style="width: 15%; text-align: right;">Qty</td>
                    <td style="width: 30%; text-align: right;">Amount</td>
                </tr>
            </table>
            <div class="divider"></div>
        """
        
        # ITEMS
        for item in items:
            name = item["product_name"][:50]  # Truncate long names
            qty = item["quantity"]
            total = item["total"]
            html += f"""
            <table>
                <tr>
                    <td style="width: 55%;">{name}</td>
                    <td style="width: 15%; text-align: right;">{int(qty)}</td>
                    <td style="width: 30%; text-align: right;">{sym}{total:.2f}</td>
                </tr>
            """
            
            if item.get("discount_percent", 0) > 0:
                html += f"""
                <tr>
                    <td colspan="3" style="font-size: 10px; color: #666;">
                        &nbsp;&nbsp;Discount: {item['discount_percent']:.0f}%
                    </td>
                </tr>
                """
            
            html += "</table>"
        
        html += """
            <div class="divider"></div>
        """
        
        # TOTALS
        subtotal = sale.get("subtotal", 0)
        tax = sale.get("tax_amount", 0)
        disc = sale.get("discount_amount", 0)
        total = sale.get("total", 0)
        paid = sale.get("amount_paid", total)
        change = sale.get("change_amount", 0)
        method = sale.get("payment_method", "cash").upper()
        
        html += "<div class='right'>"
        
        if disc > 0:
            html += f"<div>Subtotal : {sym}{subtotal:.2f}</div>"
            html += f"<div>Discount : -{sym}{disc:.2f}</div>"
            
        if tax > 0:
            tax_name = self.config.get("tax_name", "Tax")
            html += f"<div>{tax_name}     : {sym}{tax:.2f}</div>"
        
        html += f"""
            <div class="divider"></div>
            <div class="total">TOTAL: {sym}{total:.2f}</div>
            <div>Paid ({method}): {sym}{paid:.2f}</div>
        """
        
        if change > 0:
            html += f"<div>Change : {sym}{change:.2f}</div>"
            
        html += """
            </div>
            <div class="divider"></div>
        """
        
        # FOOTER & BARCODE
        html += f"""
            <div class="center">
                <div>{footer}</div>
                <div style="margin-top: 8px; font-size: 10px;">
                    {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}
                </div>
            </div>
        </body>
        </html>
        """
        
        return html

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
        ptype = self.config.get("printer_type", "windows_native")
        copies = int(self.config.get("receipt_copies", 1))

        if ptype == "none":
            return True  # Silent success - printing disabled

        # Try PyQt6 Windows native printing first
        if ptype in ("windows_native", "default", ""):
            for _ in range(copies):
                ok = self.print_to_windows_default(sale, items, customer)
                if ok:
                    return True
            # Fall back to PDF if native fails
            print("[Printer] Native printing failed, falling back to PDF.")
            ptype = "pdf"

        # PDF fallback
        if ptype == "pdf":
            path = self._generate_pdf(sale, items, customer)
            if path:
                self._open_pdf(path)
                return True
                
        return False

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
        ptype = self.config.get("printer_type", "windows_native")
        
        if ptype == "none":
            return True  # Silent success

        # Try native printing first
        if ptype in ("windows_native", "default", ""):
            try:
                ok = self._print_barcode_native(barcode_image, product_name, 
                                               price_str, settings, copies)
                if ok:
                    return True
            except Exception as e:
                print(f"[Printer] Native barcode printing failed: {e}")
            
            print("[Printer] Native barcode printing failed, falling back to PDF.")
            ptype = "pdf"

        # PDF fallback
        if ptype == "pdf":
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
            from PyQt6.QtGui import QImage, QPixmap
            from PyQt6.QtCore import QByteArray, QBuffer
            
            default_printer_info = QPrinterInfo.defaultPrinter()
            if not default_printer_info.isValid():
                return False

            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setPrinterName(default_printer_info.printerName())
            
            # Label size (e.g., 50x25mm for barcode labels)
            label_w = float(settings.get("barcode_label_width_mm", 50.0))
            label_h = float(settings.get("barcode_label_height_mm", 25.0))
            
            printer.setPageSize(QPrinter.PageSize.Custom)
            printer.setPageSizeMM(label_w, label_h)
            printer.setPageMargins(QMarginsF(2, 2, 2, 2))
            
            painter = QPainter()
            if not painter.begin(printer):
                return False
            
            x_offset = 5
            y_offset = 2
            
            for _ in range(copies):
                # Draw barcode image
                if isinstance(barcode_image, str):
                    pixmap = QPixmap(barcode_image)
                else:
                    pixmap = QPixmap.fromImage(barcode_image)
                
                painter.drawPixmap(x_offset, y_offset, 
                                 int(label_w - 10), int(label_h - 10), pixmap)
                
                # Draw product info
                painter.drawText(
                    5, int(label_h - 8), int(label_w - 10), 5,
                    0, f"{product_name} {price_str}"
                )
                
                # Page break for next copy
                if _ < copies - 1:
                    painter.end()
                    if not painter.begin(printer):
                        return False
            
            painter.end()
            print(f"[Printer] Barcode labels printed ({copies} copies)")
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
        """Generate PDF receipt as fallback."""
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

        page_width = width_mm * mm
        page_height = A4[1]

        doc = SimpleDocTemplate(
            path,
            pagesize=(page_width, page_height),
            leftMargin=5 * mm, rightMargin=5 * mm,
            topMargin=8 * mm, bottomMargin=8 * mm,
        )

        styles = getSampleStyleSheet()
        center = ParagraphStyle("center", parent=styles["Normal"],
                                alignment=TA_CENTER, fontSize=8)
        right = ParagraphStyle("right", parent=styles["Normal"],
                               alignment=TA_RIGHT, fontSize=8)
        left = ParagraphStyle("left", parent=styles["Normal"],
                              alignment=TA_LEFT, fontSize=8)
        title_s = ParagraphStyle("title", parent=styles["Normal"],
                                 alignment=TA_CENTER, fontSize=12, 
                                 fontName="Helvetica-Bold")
        total_s = ParagraphStyle("total", parent=styles["Normal"],
                                 alignment=TA_RIGHT, fontSize=11, 
                                 fontName="Helvetica-Bold")

        sym = self.config.get("currency_symbol", "$")
        story = []

        # Business info
        story.append(Paragraph(self.config.get("business_name", ""), title_s))
        if self.config.get("business_tagline"):
            story.append(Paragraph(self.config.get("business_tagline"), center))
        if self.config.get("business_address"):
            story.append(Paragraph(self.config.get("business_address"), center))
        if self.config.get("business_phone"):
            story.append(Paragraph(self.config.get("business_phone"), center))
        if self.config.get("receipt_header"):
            story.append(Paragraph(self.config.get("receipt_header"), center))

        story.append(HRFlowable(width="100%", color=colors.black))
        story.append(Spacer(1, 3 * mm))

        # Invoice info
        dt = datetime.now().strftime("%d-%b-%Y %H:%M")
        story.append(Paragraph(f"<b>Invoice:</b> {sale.get('invoice_number', '')}", left))
        story.append(Paragraph(f"<b>Date:</b> {dt}", left))
        if customer:
            story.append(Paragraph(f"<b>Customer:</b> {customer.get('name', '')}", left))
            if customer.get("mobile"):
                story.append(Paragraph(f"<b>Mobile:</b> {customer.get('mobile')}", left))

        story.append(HRFlowable(width="100%", color=colors.black))
        story.append(Spacer(1, 3 * mm))

        # Items table
        tdata = [["Item", "Qty", "Price", "Total"]]
        for item in items:
            disc_str = ""
            if item.get("discount_percent", 0) > 0:
                disc_str = f" (-{item['discount_percent']:.0f}%)"
            tdata.append([
                item["product_name"] + disc_str,
                str(item["quantity"]),
                f"{sym}{item['unit_price']:.2f}",
                f"{sym}{item['total']:.2f}",
            ])

        col_widths = [page_width * 0.45, page_width * 0.1,
                      page_width * 0.2, page_width * 0.2]
        tbl = Table(tdata, colWidths=col_widths)
        tbl.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(tbl)
        story.append(HRFlowable(width="100%", color=colors.black))
        story.append(Spacer(1, 2 * mm))

        # Totals
        subtotal = sale.get("subtotal", 0)
        tax = sale.get("tax_amount", 0)
        disc = sale.get("discount_amount", 0)
        total = sale.get("total", 0)
        paid = sale.get("amount_paid", total)
        change = sale.get("change_amount", 0)
        method = sale.get("payment_method", "cash").upper()

        if disc > 0:
            story.append(Paragraph(f"Subtotal: {sym}{subtotal:.2f}", right))
            story.append(Paragraph(f"Discount: -{sym}{disc:.2f}", right))
        if tax > 0:
            tname = self.config.get("tax_name", "Tax")
            story.append(Paragraph(f"{tname}: {sym}{tax:.2f}", right))

        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(f"TOTAL: {sym}{total:.2f}", total_s))
        story.append(Paragraph(f"Paid ({method}): {sym}{paid:.2f}", right))
        if change > 0:
            story.append(Paragraph(f"Change: {sym}{change:.2f}", right))

        story.append(HRFlowable(width="100%", color=colors.black))
        story.append(Spacer(1, 3 * mm))

        footer = self.config.get("receipt_footer", "Thank you!")
        story.append(Paragraph(footer, center))

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
