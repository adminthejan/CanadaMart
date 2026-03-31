"""Receipt printer service – ESC/POS thermal + PDF fallback."""
import os
import io
import tempfile
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


class ReceiptPrinter:
    """
    Handles receipt printing via:
      - ESC/POS USB / Serial / Network thermal printers
      - PDF file generation (reportlab) as save/email fallback
    """

    def __init__(self, config):
        self.config = config
        self._printer = None

    # ------------------------------------------------------------------ #
    #  ESC/POS connection helpers                                          #
    # ------------------------------------------------------------------ #
    def _get_escpos_printer(self):
        ptype = self.config.get("printer_type", "none")
        try:
            from escpos import printer as ep
            if ptype == "escpos_usb":
                vendor = int(self.config.get("printer_usb_vendor", "0x04b8"), 16)
                product = int(self.config.get("printer_usb_product", "0x0202"), 16)
                return ep.Usb(vendor, product)
            elif ptype == "escpos_serial":
                port = self.config.get("printer_port", "COM1")
                baud = int(self.config.get("printer_baudrate", 9600))
                return ep.Serial(devfile=port, baudrate=baud)
            elif ptype == "escpos_network":
                ip = self.config.get("printer_network_ip", "")
                port = int(self.config.get("printer_network_port", 9100))
                return ep.Network(ip, port)
        except ImportError:
            print("[Printer] python-escpos not installed.")
        except Exception as e:
            print(f"[Printer] Connection error: {e}")
        return None

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #
    def print_receipt(self, sale: Dict, items: List[Dict],
                      customer: Optional[Dict] = None) -> bool:
        """
        Print a receipt. Returns True on success.
        Falls back to PDF if ESC/POS fails.
        """
        ptype = self.config.get("printer_type", "none")
        copies = int(self.config.get("receipt_copies", 1))

        if ptype == "none":
            return True  # silent

        if ptype in ("escpos_usb", "escpos_serial", "escpos_network"):
            for _ in range(copies):
                ok = self._print_escpos(sale, items, customer)
                if not ok:
                    break
            return ok

        if ptype == "pdf":
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

    def print_barcode_label(self, barcode_image, product_name: str, price_str: str, copies: int = 1, settings: dict = None) -> bool:
        """
        Prints a barcode label.
        - ESC/POS: Uses the image printing functionality.
        - PDF: Falls back to PDF generation.
        """
        settings = settings or {}
        ptype = self.config.get("printer_type", "none")
        if ptype == "none":
            return True

        if ptype in ("escpos_usb", "escpos_serial", "escpos_network"):
            return self._print_barcode_escpos(barcode_image, settings, copies)

        if ptype == "pdf":
            path = self._generate_barcode_pdf(barcode_image, settings, copies)
            if path:
                self._open_pdf(path)
                return True
        return False

    def _print_barcode_escpos(self, barcode_image, settings: dict, copies: int) -> bool:
        p = self._get_escpos_printer()
        if not p:
            return False
        try:
            p.set(align="center")
            
            from PIL import Image
            cols = int(settings.get("barcode_columns_per_row", 1))
            # Assume ~8 dots/mm for thermal printers
            gap_x_px = int(float(settings.get("barcode_gap_x_mm", 2.0)) * 8)
            
            single_w = barcode_image.width
            single_h = barcode_image.height
            row_w = (single_w * cols) + (max(0, gap_x_px) * (cols - 1))
            row_image = Image.new("RGB", (row_w, single_h), "white")
            for i in range(cols):
                row_image.paste(barcode_image, (i * (single_w + max(0, gap_x_px)), 0))
                
            rows = copies // cols
            leftover = copies % cols
            
            for _ in range(rows):
                p.image(row_image)
            
            if leftover > 0:
                last_row = Image.new("RGB", (row_w, single_h), "white")
                for i in range(leftover):
                    last_row.paste(barcode_image, (i * (single_w + max(0, gap_x_px)), 0))
                p.image(last_row)
            
            p.cut()
            return True
        except Exception as e:
            print(f"[Printer] ESC/POS barcode error: {e}")
            return False
        finally:
            try:
                p.close()
            except Exception:
                pass

    def _generate_barcode_pdf(self, barcode_image, settings: dict, copies: int) -> Optional[str]:
        try:
            from reportlab.lib.units import mm
            from reportlab.pdfgen import canvas
            from reportlab.lib.utils import ImageReader
            import tempfile, os
            
            fd, path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            
            width_mm = float(settings.get("barcode_label_width_mm", 50.0))
            height_mm = float(settings.get("barcode_label_height_mm", 25.0))
            
            c = canvas.Canvas(path, pagesize=(width_mm * mm, height_mm * mm))
            img_reader = ImageReader(barcode_image)
            
            for _ in range(copies):
                c.drawImage(img_reader, 0, 0, width=width_mm * mm, height=height_mm * mm, preserveAspectRatio=True, anchor='c')
                c.showPage()
                
            c.save()
            return path
        except Exception as e:
            print(f"[Printer] PDF barcode error: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  ESC/POS rendering                                                   #
    # ------------------------------------------------------------------ #
    def _print_escpos(self, sale: Dict, items: List[Dict],
                      customer: Optional[Dict]) -> bool:
        p = self._get_escpos_printer()
        if not p:
            return False
        try:
            width = int(self.config.get("receipt_paper_width", 80))
            chars = 48 if width >= 80 else 32

            def divider():
                p.text("-" * chars + "\n")

            # Header
            bname = self.config.get("business_name", "")
            p.set(align="center", bold=True, height=2, width=2)
            p.text(bname + "\n")
            p.set(align="center", bold=False, height=1, width=1)

            tagline = self.config.get("business_tagline", "")
            if tagline:
                p.text(tagline + "\n")

            addr = self.config.get("business_address", "")
            phone = self.config.get("business_phone", "")
            if addr:
                p.text(addr + "\n")
            if phone:
                p.text(phone + "\n")

            header_txt = self.config.get("receipt_header", "")
            if header_txt:
                p.text(header_txt + "\n")

            divider()

            # Invoice details
            dt = datetime.now().strftime("%d-%b-%Y  %H:%M")
            p.set(align="left")
            p.text(f"Invoice : {sale.get('invoice_number', '')}\n")
            p.text(f"Date    : {dt}\n")
            if customer:
                p.text(f"Customer: {customer.get('name', '')}\n")
                p.text(f"Mobile  : {customer.get('mobile', '')}\n")
            if sale.get("notes"):
                p.text(f"Notes   : {sale['notes']}\n")
            divider()

            # Items header
            sym = self.config.get("currency_symbol", "$")
            col_w = chars - 12
            p.set(bold=True)
            p.text(f"{'Item':<{col_w}} {'Qty':>3} {'Amount':>8}\n")
            p.set(bold=False)
            divider()

            # Items
            for item in items:
                name = item["product_name"][:col_w]
                qty = item["quantity"]
                total = item["total"]
                p.text(f"{name:<{col_w}} {qty:>3} {sym}{total:>7.2f}\n")
                if item.get("discount_percent", 0) > 0:
                    p.text(f"  Discount: {item['discount_percent']:.0f}%\n")

            divider()

            # Totals
            p.set(align="right")
            subtotal = sale.get("subtotal", 0)
            tax = sale.get("tax_amount", 0)
            disc = sale.get("discount_amount", 0)
            total = sale.get("total", 0)

            if disc > 0:
                p.text(f"Subtotal : {sym}{subtotal:.2f}\n")
                p.text(f"Discount : -{sym}{disc:.2f}\n")
            if tax > 0:
                tname = self.config.get("tax_name", "Tax")
                p.text(f"{tname}     : {sym}{tax:.2f}\n")

            p.set(align="right", bold=True, height=2, width=2)
            p.text(f"TOTAL: {sym}{total:.2f}\n")
            p.set(align="right", bold=False, height=1, width=1)

            method = sale.get("payment_method", "cash").upper()
            paid = sale.get("amount_paid", total)
            change = sale.get("change_amount", 0)
            p.text(f"Paid ({method}): {sym}{paid:.2f}\n")
            if change > 0:
                p.text(f"Change : {sym}{change:.2f}\n")

            divider()

            # Footer
            footer = self.config.get("receipt_footer", "Thank you!")
            p.set(align="center")
            p.text(footer + "\n\n")

            # Barcode (invoice number)
            if self.config.get("receipt_show_barcode", False):
                try:
                    inv = sale.get("invoice_number", "")
                    if inv:
                        p.barcode(inv, "CODE128", 64, 2, "BELOW", "B")
                except Exception:
                    pass

            p.cut()
            return True
        except Exception as e:
            print(f"[Printer] ESC/POS error: {e}")
            return False
        finally:
            try:
                p.close()
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    #  PDF rendering                                                       #
    # ------------------------------------------------------------------ #
    def _generate_pdf(self, sale: Dict, items: List[Dict],
                      customer: Optional[Dict],
                      directory: str = None) -> Optional[str]:
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
                                 alignment=TA_CENTER, fontSize=12, fontName="Helvetica-Bold")
        total_s = ParagraphStyle("total", parent=styles["Normal"],
                                 alignment=TA_RIGHT, fontSize=11, fontName="Helvetica-Bold")

        sym = self.config.get("currency_symbol", "$")
        story = []

        # Business name
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
