"""
PySide6 Modern Desktop Dashboard for CV Servant.
Optimized for 60 FPS silky smooth UI, zero-lag background threading,
live job hunting on Seek/Bayt/Glassdoor, and instant approvals.
"""
import os
from pathlib import Path
import sys
from typing import Any, Dict, List

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
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
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from cv_servant.config import EXCEL_TRACKER_PATH, GMAIL_USER
from cv_servant.coordinator import ApplicationCoordinator
from cv_servant.hunter.job_hunter import LiveJobHunter

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
    padding: 10px 20px;
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
    padding: 8px 16px;
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
QPushButton.Warning {
    background-color: #D97706;
}
QPushButton.Warning:hover {
    background-color: #B45309;
}
QLineEdit, QTextEdit, QComboBox {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 8px;
    color: #F8FAFC;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border: 1px solid #38BDF8;
}
QTableWidget {
    background-color: #1E293B;
    border: 1px solid #334155;
    gridline-color: #334155;
    border-radius: 8px;
    selection-background-color: #3B82F6;
    color: #F8FAFC;
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
    color: #FFFFFF;
}
QProgressBar::chunk {
    background-color: #38BDF8;
    border-radius: 4px;
}
/* Explicit MessageBox Styling to prevent white-on-white text */
QMessageBox {
    background-color: #1E293B;
}
QMessageBox QLabel {
    color: #F8FAFC !important;
    font-size: 13px;
    background-color: transparent;
}
QMessageBox QPushButton {
    background-color: #2563EB;
    color: #FFFFFF;
    border-radius: 6px;
    padding: 6px 20px;
    min-width: 80px;
}
"""


class BackgroundTelegramThread(QThread):
    """Background polling thread for Telegram Bot so the GUI never hangs."""
    approval_received = Signal(str, str)
    job_received = Signal(dict)

    def __init__(self, coordinator: ApplicationCoordinator):
        super().__init__()
        self.coordinator = coordinator
        self.running = True

    def run(self):
        while self.running:
            try:
                if self.coordinator.telegram.is_configured():
                    self.coordinator.telegram.poll_updates()
            except Exception:
                pass
            self.msleep(3000)  # Sleep 3 seconds off the main thread

    def stop(self):
        self.running = False


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


class HunterWorker(QThread):
    results_signal = Signal(list)
    error_signal = Signal(str)

    def __init__(self, hunter: LiveJobHunter, keywords: str, country: str, sponsorship_only: bool):
        super().__init__()
        self.hunter = hunter
        self.keywords = keywords
        self.country = country
        self.sponsorship_only = sponsorship_only

    def run(self):
        try:
            res = self.hunter.search_online_jobs(
                keywords=self.keywords,
                country=self.country,
                sponsorship_only=self.sponsorship_only,
                limit=15
            )
            self.results_signal.emit(res)
        except Exception as e:
            self.error_signal.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.coordinator = ApplicationCoordinator()
        self.hunter = LiveJobHunter(self.coordinator.analyzer)
        self.current_job: Dict[str, Any] = {}
        self.discovered_jobs: List[Dict[str, Any]] = []

        self.setWindowTitle("CV Servant | خادم التوظيف الذكي للمهندس مصطفى شوقي")
        self.resize(1220, 820)
        self.setStyleSheet(DARK_THEME_QSS)

        self._build_ui()
        self._load_tracked_jobs()

        # Start non-blocking background Telegram thread
        self.tg_thread = BackgroundTelegramThread(self.coordinator)
        self.tg_thread.start()

    def closeEvent(self, event):
        self.tg_thread.stop()
        self.tg_thread.wait(1000)
        super().closeEvent(event)

    def _build_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # Header Bar
        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title_box = QVBoxLayout()
        app_title = QLabel("CV Servant • خادم التوظيف الذكي")
        app_title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        app_title.setStyleSheet("color: #38BDF8;")
        app_sub = QLabel("البحث المباشر في المواقع العالمية • تفصيل الـ ATS • فحص الكفالة (Sponsorship) • التقديم الآلي")
        app_sub.setStyleSheet("color: #94A3B8; font-size: 11px;")
        title_box.addWidget(app_title)
        title_box.addWidget(app_sub)
        header_layout.addLayout(title_box)

        header_layout.addStretch()

        # Status Chips
        badge_box = QHBoxLayout()
        self.lbl_ollama_status = QLabel("🟢 Ollama Qwen3.5 (GPU)")
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
        self.tab_hunter = QWidget()
        self.tab_process = QWidget()
        self.tab_tracker = QWidget()
        self.tab_settings = QWidget()

        self.tabs.addTab(self.tab_hunter, "🌐 البحث المباشر في المواقع (Live Job Hunter)")
        self.tabs.addTab(self.tab_process, "🎯 تفصيل ومعالجة الإعلانات (Job Processor & ATS)")
        self.tabs.addTab(self.tab_tracker, "📊 سجل التقديمات واللوج (Job Applications Log)")
        self.tabs.addTab(self.tab_settings, "⚙️ إعدادات الإيميل والدرايف والموبايل")

        main_layout.addWidget(self.tabs)

        self._setup_hunter_tab()
        self._setup_process_tab()
        self._setup_tracker_tab()
        self._setup_settings_tab()

    # ------------------ Tab 1: Live Job Hunter ------------------
    def _setup_hunter_tab(self):
        layout = QVBoxLayout(self.tab_hunter)
        layout.setSpacing(12)

        # Search Controls Card
        card = QFrame()
        card.setProperty("class", "Card")
        c_layout = QHBoxLayout(card)

        # Country Filter
        c_layout.addWidget(QLabel("🌍 الدولة المستهدفة:"))
        self.combo_country = QComboBox()
        self.combo_country.addItems(["Australia", "Canada", "New Zealand", "Saudi Arabia", "Kuwait"])
        c_layout.addWidget(self.combo_country)

        # Keywords Filter
        c_layout.addWidget(QLabel("🔍 المسمى والتخصص:"))
        self.combo_keywords = QComboBox()
        self.combo_keywords.setEditable(True)
        self.combo_keywords.addItems(["Senior BIM Specialist", "BIM Manager", "Architect", "BIM Coordinator", "Computational Architect"])
        c_layout.addWidget(self.combo_keywords)

        # Sponsorship Checkbox
        self.chk_sponsorship_only = QCheckBox("🌟 وظائف الكفالة فقط (Visa Sponsorship / LMIA / TSS 482)")
        self.chk_sponsorship_only.setChecked(True)
        c_layout.addWidget(self.chk_sponsorship_only)

        # Search Button
        self.btn_search_jobs = QPushButton("🚀 بدء مسح المواقع (Seek, Bayt, Glassdoor...)")
        self.btn_search_jobs.clicked.connect(self._run_job_search)
        c_layout.addWidget(self.btn_search_jobs)

        layout.addWidget(card)

        self.hunter_progress = QProgressBar()
        self.hunter_progress.setVisible(False)
        layout.addWidget(self.hunter_progress)

        # Results Table
        self.hunter_table = QTableWidget()
        self.hunter_table.setColumnCount(7)
        self.hunter_table.setHorizontalHeaderLabels([
            "المسمى الوظيفي", "الشركة", "الدولة / المدينة", "المصدر", "الكفالة (Sponsorship)", "درجة المطابقة", "إجراء فوري"
        ])
        self.hunter_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.hunter_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        layout.addWidget(self.hunter_table)

    def _run_job_search(self):
        country = self.combo_country.currentText()
        keywords = self.combo_keywords.currentText().strip()
        sponsorship_only = self.chk_sponsorship_only.isChecked()

        self.hunter_progress.setVisible(True)
        self.hunter_progress.setRange(0, 0)
        self.btn_search_jobs.setEnabled(False)

        self.hunter_worker = HunterWorker(self.hunter, keywords, country, sponsorship_only)
        self.hunter_worker.results_signal.connect(self._on_hunter_results)
        self.hunter_worker.error_signal.connect(self._on_hunter_error)
        self.hunter_worker.start()

    def _on_hunter_results(self, jobs: List[Dict[str, Any]]):
        self.hunter_progress.setVisible(False)
        self.btn_search_jobs.setEnabled(True)
        self.discovered_jobs = jobs

        self.hunter_table.setRowCount(len(jobs))
        for row, job in enumerate(jobs):
            self.hunter_table.setItem(row, 0, QTableWidgetItem(job.get("job_title", "")))
            self.hunter_table.setItem(row, 1, QTableWidgetItem(job.get("company_name", "")))
            self.hunter_table.setItem(row, 2, QTableWidgetItem(f"{job.get('country', '')} - {job.get('city', '')}"))
            self.hunter_table.setItem(row, 3, QTableWidgetItem(job.get("source", "")))

            # Sponsorship badge
            spon_item = QTableWidgetItem(job.get("visa_sponsorship", "Not Mentioned"))
            spon_item.setForeground(QColor("#10B981" if "Available" in str(spon_item.text()) else "#94A3B8"))
            spon_item.setTextAlignment(Qt.AlignCenter)
            self.hunter_table.setItem(row, 4, spon_item)

            # Fit score
            fit_item = QTableWidgetItem(f"{job.get('fit_score', 85)}%")
            fit_item.setForeground(QColor("#38BDF8"))
            fit_item.setTextAlignment(Qt.AlignCenter)
            self.hunter_table.setItem(row, 5, fit_item)

            # Action Buttons widget
            act_w = QWidget()
            act_lay = QHBoxLayout(act_w)
            act_lay.setContentsMargins(2, 2, 2, 2)
            act_lay.setSpacing(4)

            btn_open = QPushButton("🔗")
            btn_open.setProperty("class", "Secondary")
            btn_open.setStyleSheet("background-color: #0284C7; color: white; padding: 6px 10px;")
            btn_open.setToolTip("فتح إعلان الوظيفة المباشر في المتصفح")
            btn_open.clicked.connect(lambda ch, u=job.get("job_url", ""): os.system(f'start "" "{u}"') if u else None)
            act_lay.addWidget(btn_open)

            btn_apply = QPushButton("⚡ تفصيل الـ ATS والتقديم")
            btn_apply.setProperty("class", "Success")
            btn_apply.clicked.connect(lambda ch, j=job: self._apply_to_hunter_job(j))
            act_lay.addWidget(btn_apply)

            self.hunter_table.setCellWidget(row, 6, act_w)

    def _on_hunter_error(self, err: str):
        self.hunter_progress.setVisible(False)
        self.btn_search_jobs.setEnabled(True)
        QMessageBox.critical(self, "خطأ في البحث", f"حدث خطأ أثناء فحص المواقع:\n{err}")

    def _apply_to_hunter_job(self, job: Dict[str, Any]):
        """Transfers discovered job directly to the ATS Tailor pipeline."""
        self.tabs.setCurrentIndex(1)  # Switch to Job Processor Tab
        full_text = (
            f"Job Title: {job.get('job_title')}\n"
            f"Company: {job.get('company_name')}\n"
            f"Country: {job.get('country')}\n"
            f"City: {job.get('city')}\n"
            f"Source URL: {job.get('job_url')}\n"
            f"Description & Requirements:\n{job.get('description')}\n"
            f"Visa Sponsorship Details: {job.get('visa_sponsorship')}\n"
        )
        self.txt_job_input.setText(full_text)
        self._process_text_job()

    # ------------------ Tab 2: Job Processor & ATS ------------------
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

    # ------------------ Tab 3: Job Applications Tracker ------------------
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

        # Table with Direct Approval Buttons
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "كود الوظيفة", "التاريخ", "الشركة", "المسمى الوظيفي",
            "الدولة", "الكفالة", "طريقة التقديم", "الحالة", "الإجراء والموافقة"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

    # ------------------ Tab 4: Settings & Mobile ------------------
    def _setup_settings_tab(self):
        layout = QVBoxLayout(self.tab_settings)

        card = QFrame()
        card.setProperty("class", "Card")
        c_layout = QVBoxLayout(card)

        lbl_settings_head = QLabel("⚙️ إعدادات الحساب والربط (تُحفظ تلقائياً في ملف الإعدادات)")
        lbl_settings_head.setFont(QFont("Segoe UI", 12, QFont.Bold))
        c_layout.addWidget(lbl_settings_head)

        grid = QGridLayout()

        # Gmail
        grid.addWidget(QLabel("📧 بريد التقديم (Gmail):"), 0, 0)
        self.input_gmail_user = QLineEdit(GMAIL_USER)
        grid.addWidget(self.input_gmail_user, 0, 1)

        grid.addWidget(QLabel("🔑 كلمة مرور التطبيق (App Password):"), 1, 0)
        self.input_gmail_pass = QLineEdit()
        self.input_gmail_pass.setEchoMode(QLineEdit.Password)
        self.input_gmail_pass.setPlaceholderText("16 حرفاً من إعدادات أمان جوجل (بعد تفعيل التحقق بخطوتين)")
        grid.addWidget(self.input_gmail_pass, 1, 1)

        # Telegram
        grid.addWidget(QLabel("🤖 توكن بوت التليجرام (Bot Token):"), 2, 0)
        self.input_tg_token = QLineEdit()
        self.input_tg_token.setPlaceholderText("احصل عليه من @BotFather (مثال: 7123456789:AAH...)")
        grid.addWidget(self.input_tg_token, 2, 1)

        grid.addWidget(QLabel("🆔 رقم الشات الخاص بك (Chat ID):"), 3, 0)
        self.input_tg_chat_id = QLineEdit()
        self.input_tg_chat_id.setPlaceholderText("احصل عليه من @userinfobot (مثال: 987654321)")
        grid.addWidget(self.input_tg_chat_id, 3, 1)

        # Google Drive paths
        grid.addWidget(QLabel("📥 مجلد سحب الصور (Drive Inbox):"), 4, 0)
        self.input_drive_inbox = QLineEdit()
        self.input_drive_inbox.setPlaceholderText("مسار المجلد المحلي على جهازك (اختياري)")
        grid.addWidget(self.input_drive_inbox, 4, 1)

        grid.addWidget(QLabel("☁️ مجلد النسخ الاحتياطي (Drive Backup):"), 5, 0)
        self.input_drive_archive = QLineEdit()
        self.input_drive_archive.setPlaceholderText("مسار مجلد الأرشيف (اختياري)")
        grid.addWidget(self.input_drive_archive, 5, 1)

        c_layout.addLayout(grid)

        # Load existing values from .env if present
        self._load_env_to_inputs()

        # Save button
        self.btn_save_settings = QPushButton("💾 حفظ الإعدادات وتحديث البرنامج")
        self.btn_save_settings.clicked.connect(self._save_settings_to_env)
        c_layout.addWidget(self.btn_save_settings)

        layout.addWidget(card)

        # Guidance Card
        info_card = QFrame()
        info_card.setProperty("class", "Card")
        i_layout = QVBoxLayout(info_card)
        i_layout.addWidget(QLabel("💡 إرشادات سريعة لربط الحسابات:"))
        info_text = (
            "1. <b>تليجرام (للموبايل):</b> افتح تليجرام وابحث عن @BotFather وأرسل /newbot واختر اسماً ليمنحك الـ Token. "
            "ثم ادخل للبوت الخاص بك واضغط /start حتى يتمكن من مراسلتك.\n"
            "2. <b>جيميل (App Password):</b> لحل رسالة 'The setting is not available'، يجب أولاً تفعيل 'التحقق بخطوتين (2-Step Verification)' "
            "في حساب جوجل، ثم البحث في شريط البحث عن 'App passwords' أو 'كلمات مرور التطبيقات'."
        )
        lbl_info = QLabel(info_text)
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet("color: #94A3B8; font-size: 11px;")
        i_layout.addWidget(lbl_info)

        layout.addWidget(info_card)
        layout.addStretch()

    def _load_env_to_inputs(self):
        from cv_servant.config import ENV_PATH
        if ENV_PATH.exists():
            from dotenv import dotenv_values
            vals = dotenv_values(ENV_PATH)
            if vals.get("GMAIL_USER"):
                self.input_gmail_user.setText(vals["GMAIL_USER"])
            if vals.get("GMAIL_APP_PASSWORD"):
                self.input_gmail_pass.setText(vals["GMAIL_APP_PASSWORD"])
            if vals.get("TELEGRAM_BOT_TOKEN"):
                self.input_tg_token.setText(vals["TELEGRAM_BOT_TOKEN"])
            if vals.get("TELEGRAM_CHAT_ID"):
                self.input_tg_chat_id.setText(vals["TELEGRAM_CHAT_ID"])
            if vals.get("GDRIVE_INBOX_DIR"):
                self.input_drive_inbox.setText(vals["GDRIVE_INBOX_DIR"])
            if vals.get("GDRIVE_ARCHIVE_DIR"):
                self.input_drive_archive.setText(vals["GDRIVE_ARCHIVE_DIR"])

    def _save_settings_to_env(self):
        from cv_servant.config import ENV_PATH
        content = (
            f"GMAIL_USER={self.input_gmail_user.text().strip()}\n"
            f"GMAIL_APP_PASSWORD={self.input_gmail_pass.text().strip()}\n"
            f"OLLAMA_BASE_URL=http://127.0.0.1:11434\n"
            f"OLLAMA_TEXT_MODEL=qwen3.5:9b\n"
            f"OLLAMA_VISION_MODEL=qwen3-vl:8b\n"
            f"TELEGRAM_BOT_TOKEN={self.input_tg_token.text().strip()}\n"
            f"TELEGRAM_CHAT_ID={self.input_tg_chat_id.text().strip()}\n"
            f"GDRIVE_INBOX_DIR={self.input_drive_inbox.text().strip()}\n"
            f"GDRIVE_ARCHIVE_DIR={self.input_drive_archive.text().strip()}\n"
        )
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.write(content)

        # Reload coordinator credentials
        self.coordinator.telegram.token = self.input_tg_token.text().strip()
        self.coordinator.telegram.chat_id = self.input_tg_chat_id.text().strip()
        self.coordinator.telegram.api_url = f"https://api.telegram.org/bot{self.coordinator.telegram.token}" if self.coordinator.telegram.token else ""
        self.coordinator.mailer.user = self.input_gmail_user.text().strip()
        self.coordinator.mailer.app_password = self.input_gmail_pass.text().strip()

        QMessageBox.information(self, "تم الحفظ", "تم حفظ الإعدادات وتحديث البرنامج بنجاح!")

    # ------------------ Core Actions & Workers ------------------
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
        self._start_worker("image", images[0])

    def _process_text_job(self):
        text = self.txt_job_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "تنبيه", "يرجى لصق نص الوظيفة أو اختيار صورة إعلان أولاً.")
            return
        self._start_worker("text", text)

    def _start_worker(self, input_type: str, payload: Any):
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
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
        self._approve_and_send_job_id(job_id)

    def _approve_and_send_job_id(self, job_id: str):
        # Find job
        job = None
        for j in self.coordinator.tracker.get_all_jobs():
            if j.get("job_id") == job_id:
                job = j
                break

        contact = str(job.get("contact", "")) if job else ""
        if not contact or "@" not in contact:
            QMessageBox.warning(
                self,
                "تنبيه: التقديم عبر الموقع",
                "هذه الوظيفة لا تحتوي على بريد إلكتروني مباشر؛ طريقة التقديم هي عبر موقع الشركة/الفورم. استخدم زر '🌐 موقع التقديم'."
            )
            return

        success = self.coordinator.execute_action(job_id, "SEND_EMAIL")
        if success:
            QMessageBox.information(self, "تم الإرسال", f"تم إرسال إيميل التقديم بنجاح إلى {contact}\nوتحديث السجل والمزامنة مع Google Drive!")
            self._load_tracked_jobs()
        else:
            QMessageBox.warning(self, "فشل الإرسال", "لم يتم إرسال الإيميل. تحقق من إعدادات الجيميل أو اتصال الإنترنت.")

    def _open_job_portal_action(self, job_id: str):
        self.coordinator.execute_action(job_id, "OPEN_PORTAL")
        self._load_tracked_jobs()
        QMessageBox.information(
            self,
            "تم فتح صفحة التقديم",
            "1. تم فتح رابط التقديم في متصفحك.\n2. تم فتح مجلد ملفات الـ ATS المخصصة لك لتسحب السيرة الذاتية وترفعها على الموقع فوراً!"
        )

    def _delete_job_action(self, job_id: str):
        confirm = QMessageBox.question(
            self,
            "تأكيد الحذف",
            f"هل أنت متأكد من حذف الوظيفة ({job_id}) من السجل؟",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.coordinator.tracker.delete_job(job_id)
            self.coordinator.gdrive.sync_tracker_to_drive()
            self._load_tracked_jobs()

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
        # Filter out empty or None jobs
        valid_jobs = [j for j in jobs if str(j.get("company_name", "")) not in ["None", ""] and str(j.get("job_title", "")) not in ["None", ""]]
        self.table.setRowCount(len(valid_jobs))

        for row, job in enumerate(valid_jobs):
            job_id = str(job.get("job_id", ""))
            status = str(job.get("status", ""))
            method = str(job.get("application_method", ""))
            contact = str(job.get("contact", ""))
            folder_path = job.get("folder_path", "")

            self.table.setItem(row, 0, QTableWidgetItem(job_id))
            self.table.setItem(row, 1, QTableWidgetItem(str(job.get("date_detected", ""))))
            self.table.setItem(row, 2, QTableWidgetItem(str(job.get("company_name", ""))))
            self.table.setItem(row, 3, QTableWidgetItem(str(job.get("job_title", ""))))
            self.table.setItem(row, 4, QTableWidgetItem(str(job.get("country", ""))))
            self.table.setItem(row, 5, QTableWidgetItem(str(job.get("visa_sponsorship", ""))))
            self.table.setItem(row, 6, QTableWidgetItem(method or ("EMAIL" if "@" in contact else "WEBSITE_FORM")))

            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 7, status_item)

            # Action Buttons cell
            action_widget = QWidget()
            act_layout = QHBoxLayout(action_widget)
            act_layout.setContentsMargins(2, 2, 2, 2)
            act_layout.setSpacing(4)

            # Determine whether this is an Email job or Website Form job
            is_email_job = "@" in contact or method == "EMAIL"

            if is_email_job:
                btn_send = QPushButton("🚀 إرسال الإيميل")
                btn_send.setProperty("class", "Success")
                btn_send.setToolTip(f"إرسال التقديم والمرفقات إلى {contact}")
                btn_send.clicked.connect(lambda ch, jid=job_id: self._approve_and_send_job_id(jid))
                act_layout.addWidget(btn_send)
            else:
                btn_portal = QPushButton("🌐 موقع التقديم")
                btn_portal.setProperty("class", "Secondary")
                btn_portal.setStyleSheet("background-color: #0284C7; color: white;")
                btn_portal.setToolTip("فتح صفحة التقديم في المتصفح ومجلد الـ ATS")
                btn_portal.clicked.connect(lambda ch, jid=job_id: self._open_job_portal_action(jid))
                act_layout.addWidget(btn_portal)

            # Folder button
            if folder_path and Path(folder_path).exists():
                btn_f = QPushButton("📁")
                btn_f.setProperty("class", "Secondary")
                btn_f.setToolTip("فتح مجلد التقديم")
                btn_f.clicked.connect(lambda ch, fp=folder_path: os.startfile(fp))
                act_layout.addWidget(btn_f)

            # Delete button
            btn_del = QPushButton("🗑️")
            btn_del.setProperty("class", "Secondary")
            btn_del.setStyleSheet("background-color: #991B1B; color: white;")
            btn_del.setToolTip("حذف هذه الوظيفة من السجل")
            btn_del.clicked.connect(lambda ch, jid=job_id: self._delete_job_action(jid))
            act_layout.addWidget(btn_del)

            self.table.setCellWidget(row, 8, action_widget)

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


def launch_app():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    launch_app()
