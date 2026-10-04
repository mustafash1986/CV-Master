"""
PySide6 Modern Desktop Dashboard for CV Servant.
Features:
- Dual-Engine OCR (Arabic & English) + Vision processing
- Live ATS tailoring and PDF/Word generation
- Job Tracker table with Excel & Google Drive auto-sync
- Gmail direct dispatch and response checking
- Mobile Telegram Bot listener for remote approvals
"""
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from cv_servant.config import EXCEL_TRACKER_PATH, GMAIL_USER
from cv_servant.coordinator import ApplicationCoordinator

DARK_THEME_QSS = """
QMainWindow {
    background-color: #0F172A;
}
QWidget {
    color: #E2E8F0;
    font-family: 'Segoe UI', 'Cairo', Arial, sans-serif;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #1E293B;
    background-color: #0F172A;
    border-radius: 8px;
}
QTabBar::tab {
    background-color: #1E293B;
    color: #94A3B8;
    padding: 10px 24px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: bold;
}
QTabBar::tab:selected {
    background-color: #2563EB;
    color: #FFFFFF;
}
QFrame.Card {
    background-color: #1E293B;
    border-radius: 10px;
    border: 1px solid #334155;
    padding: 16px;
}
QPushButton {
    background-color: #2563EB;
    color: #FFFFFF;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: bold;
    border: none;
}
QPushButton:hover {
    background-color: #1D4ED8;
}
QPushButton:pressed {
    background-color: #1E40AF;
}
QPushButton.Secondary {
    background-color: #334155;
    color: #F8FAFC;
}
QPushButton.Secondary:hover {
    background-color: #475569;
}
QPushButton.Success {
    background-color: #059669;
}
QPushButton.Success:hover {
    background-color: #047857;
}
QLineEdit, QTextEdit {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 8px;
    color: #F8FAFC;
    selection-background-color: #2563EB;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #38BDF8;
}
QTableWidget {
    background-color: #1E293B;
    border: 1px solid #334155;
    gridline-color: #334155;
    border-radius: 8px;
    selection-background-color: #3B82F6;
}
QHeaderView::section {
    background-color: #0F172A;
    color: #94A3B8;
    font-weight: bold;
    padding: 8px;
    border: 1px solid #334155;
}
QProgressBar {
    border: 1px solid #334155;
    border-radius: 4px;
    text-align: center;
    background-color: #0F172A;
}
QProgressBar::chunk {
    background-color: #38BDF8;
    border-radius: 4px;
}
"""


class JobWorker(QThread):
    finished_signal = Signal(dict)
    error_signal = Signal(str)

    def __init__(self, coordinator: ApplicationCoordinator, input_type: str, payload: Any):
        super().__init__()
        self.coordinator = coordinator
        self.input_type = input_type
        self.payload = payload

    def run(self):
        try:
            if self.input_type == "text":
                res = self.coordinator.process_job_text(self.payload)
            elif self.input_type == "image":
                res = self.coordinator.process_image_ad(Path(self.payload))
            self.finished_signal.emit(res)
        except Exception as e:
            self.error_signal.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.coordinator = ApplicationCoordinator()
        self.current_job: Dict[str, Any] = {}

        self.setWindowTitle("CV Servant | خادم التوظيف الذكي للمهندس مصطفى شوقي")
        self.resize(1180, 780)
        self.setStyleSheet(DARK_THEME_QSS)

        self._build_ui()
        self._load_tracked_jobs()

        # Timer for polling Telegram mobile approvals & Drive inbox
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._background_poll)
        self.poll_timer.start(10000)  # Every 10 seconds

    def _build_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Header Bar
        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title_box = QVBoxLayout()
        app_title = QLabel("CV Servant • خادم التوظيف الذكي")
        app_title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        app_title.setStyleSheet("color: #38BDF8;")
        app_sub = QLabel("تتبع الوظائف • تفصيل الـ ATS • فحص الكفالة (Sponsorship) • التقديم الآلي والمزامنة")
        app_sub.setStyleSheet("color: #94A3B8; font-size: 11px;")
        title_box.addWidget(app_title)
        title_box.addWidget(app_sub)
        header_layout.addLayout(title_box)

        header_layout.addStretch()

        # Status Chips
        badge_box = QHBoxLayout()
        self.lbl_ollama_status = QLabel("🟢 Ollama Qwen3.5")
        self.lbl_ollama_status.setStyleSheet("background: #064E3B; color: #6EE7B7; padding: 6px 12px; border-radius: 6px; font-weight: bold;")
        self.lbl_ocr_status = QLabel("🟢 Arabic & English OCR")
        self.lbl_ocr_status.setStyleSheet("background: #1E3A8A; color: #93C5FD; padding: 6px 12px; border-radius: 6px; font-weight: bold;")
        self.lbl_drive_status = QLabel("☁️ Google Drive Sync")
        self.lbl_drive_status.setStyleSheet("background: #3B0764; color: #E9D5FF; padding: 6px 12px; border-radius: 6px; font-weight: bold;")

        badge_box.addWidget(self.lbl_ollama_status)
        badge_box.addWidget(self.lbl_ocr_status)
        badge_box.addWidget(self.lbl_drive_status)
        header_layout.addLayout(badge_box)

        main_layout.addWidget(header)

        # Tab Widget
        self.tabs = QTabWidget()
        self.tab_process = QWidget()
        self.tab_tracker = QWidget()
        self.tab_settings = QWidget()

        self.tabs.addTab(self.tab_process, "🎯 صيد ومعالجة الوظائف (Job Processor)")
        self.tabs.addTab(self.tab_tracker, "📊 سجل التقديمات واللوج (Job Applications Log)")
        self.tabs.addTab(self.tab_settings, "⚙️ إعدادات الإيميل والدرايف والموبايل")

        main_layout.addWidget(self.tabs)

        self._setup_process_tab()
        self._setup_tracker_tab()
        self._setup_settings_tab()

    def _setup_process_tab(self):
        layout = QHBoxLayout(self.tab_process)
        layout.setSpacing(16)

        # Left Column: Inputs (Text or Image)
        left_card = QFrame()
        left_card.setProperty("class", "Card")
        left_layout = QVBoxLayout(left_card)

        lbl_input = QLabel("📥 إدخال إعلان الوظيفة (نص أو صورة إعلان):")
        lbl_input.setFont(QFont("Segoe UI", 12, QFont.Bold))
        left_layout.addWidget(lbl_input)

        # Drop / Image select button
        btn_box = QHBoxLayout()
        self.btn_select_img = QPushButton("🖼️ اختيار صورة إعلان (Flyer / Image)")
        self.btn_select_img.setProperty("class", "Secondary")
        self.btn_select_img.clicked.connect(self._select_image_ad)
        btn_box.addWidget(self.btn_select_img)

        self.btn_scan_drive = QPushButton("🔄 فحص مجلد صور Google Drive")
        self.btn_scan_drive.setProperty("class", "Secondary")
        self.btn_scan_drive.clicked.connect(self._scan_drive_inbox)
        btn_box.addWidget(self.btn_scan_drive)
        left_layout.addLayout(btn_box)

        self.txt_job_input = QTextEdit()
        self.txt_job_input.setPlaceholderText("الصق هنا تفاصيل الوظيفة أو رابط الإعلان، أو اسحب صورة الإعلان إلى هنا...")
        left_layout.addWidget(self.txt_job_input)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_layout.addWidget(self.progress_bar)

        self.btn_process = QPushButton("⚡ تحليل وتفصيل السيرة الذاتية (Generate ATS Package)")
        self.btn_process.clicked.connect(self._process_text_job)
        left_layout.addWidget(self.btn_process)

        layout.addWidget(left_card, 1)

        # Right Column: Generated Package & Actions
        right_card = QFrame()
        right_card.setProperty("class", "Card")
        right_layout = QVBoxLayout(right_card)

        lbl_result = QLabel("📄 حزمة التقديم المخصصة (Tailored Application Package):")
        lbl_result.setFont(QFont("Segoe UI", 12, QFont.Bold))
        right_layout.addWidget(lbl_result)

        # Details Grid
        details_frame = QFrame()
        details_frame.setStyleSheet("background: #0F172A; border-radius: 8px; padding: 12px;")
        grid = QGridLayout(details_frame)

        grid.addWidget(QLabel("🏢 الشركة:"), 0, 0)
        self.lbl_res_company = QLabel("-")
        self.lbl_res_company.setStyleSheet("font-weight: bold; color: #38BDF8;")
        grid.addWidget(self.lbl_res_company, 0, 1)

        grid.addWidget(QLabel("📌 المسمى:"), 1, 0)
        self.lbl_res_title = QLabel("-")
        self.lbl_res_title.setStyleSheet("font-weight: bold;")
        grid.addWidget(self.lbl_res_title, 1, 1)

        grid.addWidget(QLabel("🌍 الدولة:"), 2, 0)
        self.lbl_res_country = QLabel("-")
        grid.addWidget(self.lbl_res_country, 2, 1)

        grid.addWidget(QLabel("🛂 الكفالة (Sponsorship):"), 3, 0)
        self.lbl_res_sponsorship = QLabel("-")
        self.lbl_res_sponsorship.setStyleSheet("font-weight: bold; color: #F59E0B;")
        grid.addWidget(self.lbl_res_sponsorship, 3, 1)

        grid.addWidget(QLabel("✉️ إيميل التقديم:"), 4, 0)
        self.lbl_res_email = QLabel("-")
        grid.addWidget(self.lbl_res_email, 4, 1)

        grid.addWidget(QLabel("📊 نسبة المطابقة:"), 5, 0)
        self.lbl_res_fit = QLabel("-")
        self.lbl_res_fit.setStyleSheet("font-weight: bold; color: #10B981;")
        grid.addWidget(self.lbl_res_fit, 5, 1)

        right_layout.addWidget(details_frame)

        # Cover Letter / Summary Preview
        right_layout.addWidget(QLabel("📝 معاينة خطاب التقديم والإيميل:"))
        self.txt_preview = QTextEdit()
        self.txt_preview.setReadOnly(True)
        right_layout.addWidget(self.txt_preview)

        # Action Buttons
        act_box = QHBoxLayout()
        self.btn_send_email = QPushButton("🚀 إرسال الإيميل مع المرفقات الآن")
        self.btn_send_email.setProperty("class", "Success")
        self.btn_send_email.setEnabled(False)
        self.btn_send_email.clicked.connect(self._send_application_email)
        act_box.addWidget(self.btn_send_email)

        self.btn_open_folder = QPushButton("📁 فتح مجلد التقديم")
        self.btn_open_folder.setProperty("class", "Secondary")
        self.btn_open_folder.setEnabled(False)
        self.btn_open_folder.clicked.connect(self._open_current_folder)
        act_box.addWidget(self.btn_open_folder)

        self.btn_open_pdf = QPushButton("📄 فتح الـ CV (PDF)")
        self.btn_open_pdf.setProperty("class", "Secondary")
        self.btn_open_pdf.setEnabled(False)
        self.btn_open_pdf.clicked.connect(self._open_current_pdf)
        act_box.addWidget(self.btn_open_pdf)

        right_layout.addLayout(act_box)
        layout.addWidget(right_card, 1)

    def _setup_tracker_tab(self):
        layout = QVBoxLayout(self.tab_tracker)

        # Toolbar
        toolbar = QHBoxLayout()
        self.btn_refresh_table = QPushButton("🔄 تحديث القائمة")
        self.btn_refresh_table.setProperty("class", "Secondary")
        self.btn_refresh_table.clicked.connect(self._load_tracked_jobs)
        toolbar.addWidget(self.btn_refresh_table)

        self.btn_open_excel = QPushButton("📊 فتح ملف Excel Tracker")
        self.btn_open_excel.setProperty("class", "Secondary")
        self.btn_open_excel.clicked.connect(self._open_excel_file)
        toolbar.addWidget(self.btn_open_excel)

        self.btn_check_replies = QPushButton("📬 فحص الردود في الجيميل (Check Replies)")
        self.btn_check_replies.setProperty("class", "Secondary")
        self.btn_check_replies.clicked.connect(self._check_email_replies)
        toolbar.addWidget(self.btn_check_replies)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "كود الوظيفة", "التاريخ", "الشركة", "المسمى الوظيفي",
            "الدولة", "الكفالة (Sponsorship)", "طريقة التقديم", "الحالة"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

    def _setup_settings_tab(self):
        layout = QVBoxLayout(self.tab_settings)

        card = QFrame()
        card.setProperty("class", "Card")
        c_layout = QVBoxLayout(card)

        c_layout.addWidget(QLabel("⚙️ إعدادات الحساب والربط السحابي"))

        # Gmail
        c_layout.addWidget(QLabel(f"📧 حساب التقديم: <b>{GMAIL_USER}</b>"))
        c_layout.addWidget(QLabel("ملاحظة: لتمكين الإرسال وفحص الردود، قم بإنشاء Google App Password وإضافته في ملف .env"))

        # Telegram
        c_layout.addWidget(QLabel("📱 ربط الموبايل عبر بوت تليجرام (Telegram Bot):"))
        c_layout.addWidget(QLabel("1. أنشئ بوت مجاني عبر @BotFather على تليجرام واحصل على الـ Token.\n2. احصل على الـ Chat ID الخاص بك من @userinfobot.\n3. أضفهما في ملف .env ليتمكن البرنامج من إرسال الوظائف لهاتفك لاستلام موافقتك بنقرة زر واحدة."))

        # Google Drive
        c_layout.addWidget(QLabel("☁️ مجلدات Google Drive:"))
        c_layout.addWidget(QLabel(f"• مجلد النسخ الاحتياطي: {self.coordinator.gdrive.archive_dir}"))
        c_layout.addWidget(QLabel(f"• مجلد سحب الصور (Drop Folder): {self.coordinator.gdrive.inbox_dir}"))

        layout.addWidget(card)
        layout.addStretch()

    def _select_image_ad(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "اختر صورة إعلان الوظيفة", "", "Images (*.png *.jpg *.jpeg *.webp *.jfif *.bmp)"
        )
        if file_path:
            self._start_worker("image", file_path)

    def _scan_drive_inbox(self):
        images = self.coordinator.gdrive.scan_for_new_images()
        if not images:
            QMessageBox.information(self, "فحص الدرايف", "لا توجد صور إعلانات جديدة في مجلد السحب.")
            return
        # Process first found image
        self._start_worker("image", images[0])

    def _process_text_job(self):
        text = self.txt_job_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "تنبيه", "يرجى لصق نص الوظيفة أو اختيار صورة إعلان أولاً.")
            return
        self._start_worker("text", text)

    def _start_worker(self, input_type: str, payload: Any):
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.btn_process.setEnabled(False)

        self.worker = JobWorker(self.coordinator, input_type, payload)
        self.worker.finished_signal.connect(self._on_job_processed)
        self.worker.error_signal.connect(self._on_worker_error)
        self.worker.start()

    def _on_job_processed(self, result: Dict[str, Any]):
        self.progress_bar.setVisible(False)
        self.btn_process.setEnabled(True)
        self.current_job = result

        self.lbl_res_company.setText(result.get("company_name", "N/A"))
        self.lbl_res_title.setText(result.get("job_title", "N/A"))
        self.lbl_res_country.setText(result.get("country", "N/A"))
        self.lbl_res_sponsorship.setText(f"{result.get('visa_sponsorship')} ({result.get('sponsorship_notes', '')})")
        self.lbl_res_email.setText(result.get("application_email") or "غير متوفر (تقديم يدوي)")
        self.lbl_res_fit.setText(f"{result.get('fit_score', 90)}%")

        preview_text = f"EMAIL SUBJECT:\n{result.get('email_subject')}\n\nEMAIL BODY:\n{result.get('email_body')}"
        self.txt_preview.setText(preview_text)

        self.btn_send_email.setEnabled(bool(result.get("application_email")))
        self.btn_open_folder.setEnabled(bool(result.get("folder_path")))
        self.btn_open_pdf.setEnabled(bool(result.get("pdf_cv_path")))

        self._load_tracked_jobs()
        QMessageBox.information(self, "نجاح", "تم تجهيز حزمة الـ ATS وحفظ الملفات في مجلد الوظيفة وتحديث سجل الإكسيل والدرايف بنجاح!")

    def _on_worker_error(self, err_msg: str):
        self.progress_bar.setVisible(False)
        self.btn_process.setEnabled(True)
        QMessageBox.critical(self, "خطأ في المعالجة", f"حدث خطأ أثناء المعالجة:\n{err_msg}")

    def _send_application_email(self):
        if not self.current_job:
            return
        job_id = self.current_job.get("job_id")
        success = self.coordinator.execute_action(job_id, "SEND_EMAIL")
        if success:
            QMessageBox.information(self, "تم الإرسال", "تم إرسال إيميل التقديم بنجاح وتحديث حالة الوظيفة في الإكسيل!")
            self._load_tracked_jobs()
        else:
            QMessageBox.warning(self, "فشل الإرسال", "لم يتم إرسال الإيميل. تأكد من إعداد GMAIL_APP_PASSWORD في ملف .env")

    def _open_current_folder(self):
        if self.current_job.get("folder_path"):
            folder = Path(self.current_job["folder_path"])
            if folder.exists():
                os.startfile(str(folder))

    def _open_current_pdf(self):
        if self.current_job.get("pdf_cv_path"):
            pdf = Path(self.current_job["pdf_cv_path"])
            if pdf.exists():
                os.startfile(str(pdf))

    def _open_excel_file(self):
        if EXCEL_TRACKER_PATH.exists():
            os.startfile(str(EXCEL_TRACKER_PATH))
        else:
            QMessageBox.information(self, "تنبيه", "ملف الإكسيل غير موجود بعد.")

    def _load_tracked_jobs(self):
        jobs = self.coordinator.tracker.get_all_jobs()
        self.table.setRowCount(len(jobs))
        for row, job in enumerate(jobs):
            self.table.setItem(row, 0, QTableWidgetItem(str(job.get("job_id", ""))))
            self.table.setItem(row, 1, QTableWidgetItem(str(job.get("date_detected", ""))))
            self.table.setItem(row, 2, QTableWidgetItem(str(job.get("company_name", ""))))
            self.table.setItem(row, 3, QTableWidgetItem(str(job.get("job_title", ""))))
            self.table.setItem(row, 4, QTableWidgetItem(str(job.get("country", ""))))
            self.table.setItem(row, 5, QTableWidgetItem(str(job.get("visa_sponsorship", ""))))
            self.table.setItem(row, 6, QTableWidgetItem(str(job.get("application_method", ""))))

            status_item = QTableWidgetItem(str(job.get("status", "")))
            status_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 7, status_item)

    def _check_email_replies(self):
        jobs = self.coordinator.tracker.get_all_jobs()
        replies = self.coordinator.mailer.check_inbox_responses(jobs)
        if replies:
            for r in replies:
                self.coordinator.tracker.update_job_status(
                    r["job_id"], r["detected_status"], notes=f"Reply from {r['sender']}: {r['subject']}"
                )
            self.coordinator.gdrive.sync_tracker_to_drive()
            self._load_tracked_jobs()
            QMessageBox.information(self, "تم فحص الردود", f"تم العثور على {len(replies)} ردود وتحديث السجل!")
        else:
            QMessageBox.information(self, "فحص البريد", "لا توجد ردود جديدة من الشركات في صندوق الوارد.")

    def _background_poll(self):
        """Periodically polls Telegram for mobile interactions."""
        if self.coordinator.telegram.is_configured():
            self.coordinator.telegram.poll_updates()


def launch_app():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    launch_app()
