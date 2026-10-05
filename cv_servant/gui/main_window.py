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
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
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
    font-size: 13px;
}
QTableWidget::item {
    padding: 8px 10px;
}
QHeaderView::section {
    background-color: #0F172A;
    color: #94A3B8;
    font-weight: bold;
    padding: 10px 8px;
    border: 1px solid #334155;
    font-size: 13px;
}
QCheckBox {
    color: #F8FAFC;
    font-size: 13px;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 22px;
    height: 22px;
    border-radius: 5px;
    border: 1px solid #64748B;
    background-color: #0F172A;
}
QCheckBox::indicator:hover {
    border: 1px solid #38BDF8;
}
QCheckBox::indicator:checked {
    background-color: #10B981;
    border: 1px solid #059669;
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
/* Explicit QMenu Context Menu Styling for high-contrast dark theme */
QMenu {
    background-color: #1E293B;
    border: 1px solid #475569;
    border-radius: 8px;
    padding: 6px;
    color: #F8FAFC;
    font-size: 13px;
}
QMenu::item {
    background-color: transparent;
    padding: 8px 24px 8px 16px;
    border-radius: 6px;
    color: #F8FAFC;
    font-weight: 500;
}
QMenu::item:selected {
    background-color: #2563EB;
    color: #FFFFFF;
}
QMenu::item:disabled {
    color: #64748B;
    background-color: transparent;
}
QMenu::separator {
    height: 1px;
    background-color: #334155;
    margin: 4px 8px;
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


class RefineJobWorker(QThread):
    finished_signal = Signal(dict)
    error_signal = Signal(str)

    def __init__(self, coordinator: ApplicationCoordinator, job_data: dict, instruction: str):
        super().__init__()
        self.coordinator = coordinator
        self.job_data = job_data
        self.instruction = instruction

    def run(self):
        try:
            res = self.coordinator.refine_job_package(self.job_data, self.instruction)
            self.finished_signal.emit(res)
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
        self.resize(1360, 880)
        self.setMinimumSize(1250, 750)
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
        self.hunter_table.setColumnCount(8)
        self.hunter_table.setHorizontalHeaderLabels([
            "المسمى الوظيفي", "الشركة", "الدولة / المدينة", "المصدر", "الكفالة (Sponsorship)", "درجة المطابقة", "تم التقديم ☑️", "إجراء فوري"
        ])
        self.hunter_table.verticalHeader().setDefaultSectionSize(48)
        self.hunter_table.verticalHeader().setVisible(True)
        self.hunter_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.hunter_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)
        self.hunter_table.setColumnWidth(6, 150)
        self.hunter_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Fixed)
        self.hunter_table.setColumnWidth(7, 320)
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
            self.hunter_table.setRowHeight(row, 48)

            t_item = QTableWidgetItem(job.get("job_title", ""))
            t_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self.hunter_table.setItem(row, 0, t_item)

            c_item = QTableWidgetItem(job.get("company_name", ""))
            c_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self.hunter_table.setItem(row, 1, c_item)

            l_item = QTableWidgetItem(f"{job.get('country', '')} - {job.get('city', '')}")
            l_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self.hunter_table.setItem(row, 2, l_item)

            s_item = QTableWidgetItem(job.get("source", ""))
            s_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            self.hunter_table.setItem(row, 3, s_item)

            # Sponsorship badge
            spon_item = QTableWidgetItem(job.get("visa_sponsorship", "Not Mentioned"))
            spon_item.setForeground(QColor("#10B981" if "Available" in str(spon_item.text()) else "#94A3B8"))
            spon_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            self.hunter_table.setItem(row, 4, spon_item)

            # Fit score
            fit_item = QTableWidgetItem(f"{job.get('fit_score', 85)}%")
            fit_item.setForeground(QColor("#38BDF8"))
            fit_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            self.hunter_table.setItem(row, 5, fit_item)

            # Check if this job was already applied to in tracker
            job_url = job.get("job_url", "")
            title = job.get("job_title", "")
            company = job.get("company_name", "")
            existing = self.coordinator.tracker.find_job_by_url_or_title(job_url, title, company)
            is_already_applied = bool(existing and "Applied" in str(existing.get("status", "")))

            # Col 6: Interactive Checkbox for external tracking
            chk_w = QWidget()
            chk_lay = QHBoxLayout(chk_w)
            chk_lay.setContentsMargins(6, 4, 6, 4)
            chk_lay.setAlignment(Qt.AlignCenter)

            chk_app = QCheckBox("تم التقديم")
            chk_app.setToolTip("تحديد لتسجيل هذه الوظيفة في جدول الإكسيل وجوجل درايف كتقديم تم بالفعل (خارجي)")
            if is_already_applied:
                chk_app.setChecked(True)
                chk_app.setText("تم التقديم ✅")
                chk_app.setStyleSheet("color: #10B981; font-weight: bold;")
            else:
                chk_app.setStyleSheet("color: #94A3B8;")

            chk_app.toggled.connect(lambda checked, j=job, cb=chk_app: self._on_hunter_job_applied_toggled(j, checked, cb))
            chk_lay.addWidget(chk_app)
            self.hunter_table.setCellWidget(row, 6, chk_w)

            # Col 7: Action Buttons widget (fills cell completely with zero margins)
            act_w = QWidget()
            act_lay = QHBoxLayout(act_w)
            act_lay.setContentsMargins(0, 0, 0, 0)
            act_lay.setSpacing(1)

            btn_open = QPushButton("🔗")
            btn_open.setFixedWidth(44)
            btn_open.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            btn_open.setStyleSheet("""
                QPushButton {
                    background-color: #0284C7;
                    color: white;
                    border: none;
                    border-radius: 0px;
                    margin: 0px;
                    padding: 0px;
                    font-size: 15px;
                }
                QPushButton:hover {
                    background-color: #0369A1;
                }
            """)
            btn_open.setToolTip("فتح إعلان الوظيفة المباشر في المتصفح")
            btn_open.clicked.connect(lambda ch, u=job.get("job_url", ""): os.system(f'start "" "{u}"') if u else None)
            act_lay.addWidget(btn_open)

            btn_apply = QPushButton("⚡ تفصيل الـ ATS والتقديم")
            btn_apply.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            btn_apply.setStyleSheet("""
                QPushButton {
                    background-color: #059669;
                    color: white;
                    border: none;
                    border-radius: 0px;
                    margin: 0px;
                    padding: 0px;
                    font-size: 13px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #047857;
                }
            """)
            btn_apply.clicked.connect(lambda ch, j=job: self._apply_to_hunter_job(j))
            act_lay.addWidget(btn_apply, stretch=1)

            self.hunter_table.setCellWidget(row, 7, act_w)

        self.hunter_table.setColumnWidth(6, 150)
        self.hunter_table.setColumnWidth(7, 320)

    def _on_hunter_job_applied_toggled(self, job: Dict[str, Any], is_applied: bool, checkbox: QCheckBox):
        job_id = self.coordinator.tracker.track_external_application(job, is_applied)
        self.coordinator.gdrive.sync_tracker_to_drive()
        if is_applied:
            checkbox.setText("تم التقديم ✅")
            checkbox.setStyleSheet("color: #10B981; font-weight: bold;")
        else:
            checkbox.setText("غير مقدم")
            checkbox.setStyleSheet("color: #94A3B8;")
        self._load_tracked_jobs()

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
        self.txt_job_input.setAcceptRichText(False)
        self.txt_job_input.setPlaceholderText("الصق هنا تفاصيل الوظيفة أو رابط الإعلان، أو اسحب صورة الإعلان إلى هنا...")
        self.txt_job_input.setContextMenuPolicy(Qt.CustomContextMenu)
        self.txt_job_input.customContextMenuRequested.connect(self._show_job_input_context_menu)
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

        # Cover Letter / Summary Preview Header & Manual Save Button
        prev_header_box = QHBoxLayout()
        lbl_prev_title = QLabel("📝 خطاب التقديم والإيميل (قابل للتعديل المباشر):")
        lbl_prev_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        prev_header_box.addWidget(lbl_prev_title)
        prev_header_box.addStretch()

        self.btn_save_manual = QPushButton("💾 حفظ التعديل اليدوي")
        self.btn_save_manual.setProperty("class", "Secondary")
        self.btn_save_manual.setEnabled(False)
        self.btn_save_manual.setToolTip("حفظ التعديلات المكتوبة في المربع وتحديث ملفات الخطاب والـ PDF")
        self.btn_save_manual.clicked.connect(self._save_manual_preview_edits)
        prev_header_box.addWidget(self.btn_save_manual)
        right_layout.addLayout(prev_header_box)

        self.txt_preview = QTextEdit()
        self.txt_preview.setAcceptRichText(False)
        self.txt_preview.setPlaceholderText("سيظهر هنا خطاب التقديم والإيميل المخصص... يمكنك التعديل المباشر عليه أو طلب تعديل بالـ AI.")
        self.txt_preview.setContextMenuPolicy(Qt.CustomContextMenu)
        self.txt_preview.customContextMenuRequested.connect(self._show_preview_context_menu)
        right_layout.addWidget(self.txt_preview)

        # AI Refinement Section
        refine_frame = QFrame()
        refine_frame.setStyleSheet("""
            QFrame {
                background-color: #0F172A;
                border: 1px solid #334155;
                border-radius: 8px;
            }
        """)
        refine_layout = QVBoxLayout(refine_frame)
        refine_layout.setContentsMargins(8, 8, 8, 8)
        refine_layout.setSpacing(6)

        lbl_refine = QLabel("🪄 طلب تعديل الخطاب بالذكاء الاصطناعي (Refine with AI):")
        lbl_refine.setStyleSheet("color: #38BDF8; font-weight: bold; font-size: 12px;")
        refine_layout.addWidget(lbl_refine)

        refine_input_row = QHBoxLayout()
        self.txt_refine_note = QLineEdit()
        self.txt_refine_note.setPlaceholderText("اكتب ملحوظتك هنا (مثال: ركز أكثر على خبرة Navisworks وRevit، أو احذف الفقرة الأخيرة، أو خفف النبرة)...")
        self.txt_refine_note.setStyleSheet("""
            QLineEdit {
                background-color: #1E293B;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 8px 12px;
                color: #F8FAFC;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #38BDF8;
            }
        """)
        self.txt_refine_note.returnPressed.connect(self._apply_ai_refinement)
        refine_input_row.addWidget(self.txt_refine_note, stretch=1)

        self.btn_refine = QPushButton("🪄 تطبيق التعديل")
        self.btn_refine.setEnabled(False)
        self.btn_refine.setToolTip("تطبيق ملحوظتك وإعادة صياغة الخطاب بالذكاء الاصطناعي")
        self.btn_refine.clicked.connect(self._apply_ai_refinement)
        refine_input_row.addWidget(self.btn_refine)

        refine_layout.addLayout(refine_input_row)
        right_layout.addWidget(refine_frame)

        # Action Buttons
        act_box = QHBoxLayout()
        self.btn_send_email = QPushButton("🚀 إرسال الإيميل")
        self.btn_send_email.setProperty("class", "Success")
        self.btn_send_email.setEnabled(False)
        self.btn_send_email.clicked.connect(self._send_application_email)
        act_box.addWidget(self.btn_send_email)

        self.btn_open_folder = QPushButton("📁 مجلد التقديم")
        self.btn_open_folder.setProperty("class", "Secondary")
        self.btn_open_folder.setEnabled(False)
        self.btn_open_folder.clicked.connect(self._open_current_folder)
        act_box.addWidget(self.btn_open_folder)

        self.btn_open_pdf = QPushButton("📄 فتح الـ CV (PDF)")
        self.btn_open_pdf.setProperty("class", "Secondary")
        self.btn_open_pdf.setEnabled(False)
        self.btn_open_pdf.clicked.connect(self._open_current_pdf)
        act_box.addWidget(self.btn_open_pdf)

        self.btn_open_cl_pdf = QPushButton("📑 خطاب التقديم (PDF)")
        self.btn_open_cl_pdf.setProperty("class", "Secondary")
        self.btn_open_cl_pdf.setEnabled(False)
        self.btn_open_cl_pdf.clicked.connect(self._open_current_cl_pdf)
        act_box.addWidget(self.btn_open_cl_pdf)

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
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "كود الوظيفة", "التاريخ", "الشركة", "المسمى الوظيفي",
            "الدولة", "الكفالة", "طريقة التقديم", "الحالة", "تم التقديم ☑️", "الإجراء والموافقة"
        ])
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.verticalHeader().setVisible(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.Fixed)
        self.table.setColumnWidth(8, 150)
        self.table.horizontalHeader().setSectionResizeMode(9, QHeaderView.Fixed)
        self.table.setColumnWidth(9, 330)
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

    # ------------------ Context Menus ------------------
    def _show_job_input_context_menu(self, pos):
        menu = QMenu(self)

        act_paste = menu.addAction("📋 لصق الإعلان من الحافظة (Paste)")
        act_paste.setShortcut("Ctrl+V")
        act_paste.triggered.connect(self.txt_job_input.paste)

        has_sel = self.txt_job_input.textCursor().hasSelection()
        act_copy = menu.addAction("📄 نسخ النص المحدد (Copy)")
        act_copy.setShortcut("Ctrl+C")
        act_copy.setEnabled(has_sel)
        act_copy.triggered.connect(self.txt_job_input.copy)

        act_cut = menu.addAction("✂️ قص النص المحدد (Cut)")
        act_cut.setShortcut("Ctrl+X")
        act_cut.setEnabled(has_sel)
        act_cut.triggered.connect(self.txt_job_input.cut)

        menu.addSeparator()

        act_undo = menu.addAction("↩️ تراجع (Undo)")
        act_undo.setShortcut("Ctrl+Z")
        act_undo.setEnabled(self.txt_job_input.document().isUndoAvailable())
        act_undo.triggered.connect(self.txt_job_input.undo)

        act_redo = menu.addAction("↪️ إعادة (Redo)")
        act_redo.setShortcut("Ctrl+Y")
        act_redo.setEnabled(self.txt_job_input.document().isRedoAvailable())
        act_redo.triggered.connect(self.txt_job_input.redo)

        menu.addSeparator()

        has_text = bool(self.txt_job_input.toPlainText().strip())
        act_select_all = menu.addAction("🔘 تحديد الكل (Select All)")
        act_select_all.setShortcut("Ctrl+A")
        act_select_all.setEnabled(has_text)
        act_select_all.triggered.connect(self.txt_job_input.selectAll)

        act_clear = menu.addAction("🗑️ مسح وتفريغ المربع (Clear All)")
        act_clear.setEnabled(has_text)
        act_clear.triggered.connect(self.txt_job_input.clear)

        menu.exec(self.txt_job_input.mapToGlobal(pos))

    def _show_preview_context_menu(self, pos):
        menu = QMenu(self)
        has_sel = self.txt_preview.textCursor().hasSelection()
        act_copy = menu.addAction("📄 نسخ النص المحدد (Copy)")
        act_copy.setShortcut("Ctrl+C")
        act_copy.setEnabled(has_sel)
        act_copy.triggered.connect(self.txt_preview.copy)

        has_text = bool(self.txt_preview.toPlainText().strip())
        act_select_all = menu.addAction("🔘 تحديد الكل (Select All)")
        act_select_all.setShortcut("Ctrl+A")
        act_select_all.setEnabled(has_text)
        act_select_all.triggered.connect(self.txt_preview.selectAll)

        menu.exec(self.txt_preview.mapToGlobal(pos))

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

        comp_display = result.get("company_name", "N/A")
        contact_person = result.get("contact_person", "")
        if contact_person and contact_person != comp_display:
            comp_display = f"{comp_display} – {contact_person}"
        self.lbl_res_company.setText(comp_display)
        self.lbl_res_title.setText(result.get("job_title", "N/A"))
        self.lbl_res_country.setText(result.get("country", "N/A"))
        self.lbl_res_sponsorship.setText(f"{result.get('visa_sponsorship')} ({result.get('sponsorship_notes', '')})")

        email_val = result.get("application_email") or ""
        phone_val = result.get("contact_phone") or ""
        contact_str = email_val
        if phone_val:
            contact_str += f" | 📞 {phone_val}" if contact_str else phone_val
        self.lbl_res_email.setText(contact_str or "غير متوفر (تقديم يدوي)")
        self.lbl_res_fit.setText(f"{result.get('fit_score', 90)}%")

        preview_text = (
            f"EMAIL SUBJECT:\n{result.get('email_subject')}\n\n"
            f"EMAIL BODY:\n{result.get('email_body')}\n\n"
            f"--------------------------------------------------\n"
            f"COVER LETTER:\n{result.get('cover_letter')}"
        )
        self.txt_preview.setText(preview_text)

        self.btn_send_email.setEnabled(bool(result.get("application_email")))
        self.btn_open_folder.setEnabled(bool(result.get("folder_path")))
        self.btn_open_pdf.setEnabled(bool(result.get("pdf_cv_path")))
        self.btn_open_cl_pdf.setEnabled(bool(result.get("pdf_cl_path")))
        self.btn_save_manual.setEnabled(True)
        self.btn_refine.setEnabled(True)

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

        # Synchronize any user edits from the preview box directly into email_body before sending
        preview_content = self.txt_preview.toPlainText()
        if "EMAIL BODY:" in preview_content:
            body_part = preview_content.split("EMAIL BODY:")[1].strip()
            if body_part:
                self.current_job["email_body"] = body_part
                if job_id and job_id in self.coordinator.cached_jobs:
                    self.coordinator.cached_jobs[job_id]["email_body"] = body_part

        self._approve_and_send_job_id(job_id)

    def _approve_and_send_job_id(self, job_id: str):
        # Find job
        job = None
        for j in self.coordinator.tracker.get_all_jobs():
            if j.get("job_id") == job_id:
                job = j
                break

        contact = str(job.get("contact", "")).strip().strip(".,;:<>\"'()[]{} \t\r\n") if job else ""
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
            err = getattr(self.coordinator, "last_error", "")
            msg = f"لم يتم إرسال الإيميل.\nالسبب:\n{err}" if err else "لم يتم إرسال الإيميل. تحقق من إعدادات الجيميل أو اتصال الإنترنت."
            QMessageBox.warning(self, "فشل الإرسال", msg)

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

    def _open_current_cl_pdf(self):
        cl_pdf = self.current_job.get("pdf_cl_path")
        if cl_pdf and Path(cl_pdf).exists():
            os.startfile(str(cl_pdf))

    def _save_manual_preview_edits(self):
        if not self.current_job:
            return
        text = self.txt_preview.toPlainText().strip()
        if not text:
            return

        subject = self.current_job.get("email_subject", "")
        body = self.current_job.get("email_body", "")
        cl = self.current_job.get("cover_letter", "")

        # Extract sections if headers are present
        if "EMAIL SUBJECT:" in text and "EMAIL BODY:" in text:
            part1 = text.split("EMAIL SUBJECT:")[1]
            subject_part = part1.split("EMAIL BODY:")[0].strip()
            rest = part1.split("EMAIL BODY:")[1]
            if "COVER LETTER:" in rest:
                body_part = rest.split("COVER LETTER:")[0].replace("--------------------------------------------------", "").strip()
                cl_part = rest.split("COVER LETTER:")[1].strip()
                if cl_part:
                    cl = cl_part
            else:
                body_part = rest.strip()
            if subject_part:
                subject = subject_part
            if body_part:
                body = body_part
        elif "EMAIL BODY:" in text:
            body = text.split("EMAIL BODY:")[1].strip()
        else:
            body = text

        self.current_job = self.coordinator.update_job_texts_manually(
            job_data=self.current_job,
            new_subject=subject,
            new_email_body=body,
            new_cover_letter=cl
        )
        QMessageBox.information(
            self,
            "تم حفظ التعديل",
            "تم حفظ التعديلات اليدوية وتحديث ملفات الخطاب والإيميل وملف الـ PDF بنجاح!"
        )

    def _apply_ai_refinement(self):
        if not self.current_job:
            QMessageBox.warning(self, "تنبيه", "يرجى تجهيز حزمة وظيفة أولاً لتعديلها.")
            return

        instruction = self.txt_refine_note.text().strip()
        if not instruction:
            QMessageBox.warning(self, "تنبيه", "يرجى كتابة الملحوظة أو التعديل المطلوب أولاً.")
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.btn_refine.setEnabled(False)
        self.btn_save_manual.setEnabled(False)

        self.refine_worker = RefineJobWorker(self.coordinator, self.current_job, instruction)
        self.refine_worker.finished_signal.connect(self._on_refinement_success)
        self.refine_worker.error_signal.connect(self._on_refinement_error)
        self.refine_worker.start()

    def _on_refinement_success(self, updated_job: dict):
        self.progress_bar.setVisible(False)
        self.btn_refine.setEnabled(True)
        self.btn_save_manual.setEnabled(True)
        self.current_job = updated_job

        preview_text = (
            f"EMAIL SUBJECT:\n{updated_job.get('email_subject')}\n\n"
            f"EMAIL BODY:\n{updated_job.get('email_body')}\n\n"
            f"--------------------------------------------------\n"
            f"COVER LETTER:\n{updated_job.get('cover_letter')}"
        )
        self.txt_preview.setText(preview_text)
        self.txt_refine_note.clear()
        QMessageBox.information(
            self,
            "تم التعديل بالذكاء الاصطناعي",
            "تم تطبيق ملحوظتك وإعادة صياغة الخطاب والإيميل وتحديث ملفات الـ PDF بنجاح!"
        )

    def _on_refinement_error(self, err_msg: str):
        self.progress_bar.setVisible(False)
        self.btn_refine.setEnabled(True)
        self.btn_save_manual.setEnabled(True)
        QMessageBox.critical(self, "خطأ في التعديل", f"تعذر تطبيق التعديل:\n{err_msg}")

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
            self.table.setRowHeight(row, 48)
            job_id = str(job.get("job_id", ""))
            status = str(job.get("status", ""))
            method = str(job.get("application_method", ""))
            contact = str(job.get("contact", "")).strip().strip(".,;:<>\"'()[]{} \t\r\n")
            folder_path = job.get("folder_path", "")

            it0 = QTableWidgetItem(job_id)
            it0.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            self.table.setItem(row, 0, it0)

            it1 = QTableWidgetItem(str(job.get("date_detected", "")))
            it1.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            self.table.setItem(row, 1, it1)

            it2 = QTableWidgetItem(str(job.get("company_name", "")))
            it2.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self.table.setItem(row, 2, it2)

            it3 = QTableWidgetItem(str(job.get("job_title", "")))
            it3.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self.table.setItem(row, 3, it3)

            it4 = QTableWidgetItem(str(job.get("country", "")))
            it4.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            self.table.setItem(row, 4, it4)

            it5 = QTableWidgetItem(str(job.get("visa_sponsorship", "")))
            it5.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            self.table.setItem(row, 5, it5)

            it6 = QTableWidgetItem(method or ("EMAIL" if "@" in contact else "WEBSITE_FORM"))
            it6.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            self.table.setItem(row, 6, it6)

            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            if "Interview" in status:
                status_item.setForeground(QColor("#06B6D4"))
            elif "Rejected" in status:
                status_item.setForeground(QColor("#EF4444"))
            elif "Under Review" in status or "Received" in status:
                status_item.setForeground(QColor("#38BDF8"))
            elif "Applied" in status or "Sent" in status:
                status_item.setForeground(QColor("#10B981"))
            elif "Pending" in status:
                status_item.setForeground(QColor("#F59E0B"))
            self.table.setItem(row, 7, status_item)

            # Col 8: Applied CheckBox for tracking manual/external applications
            chk_w = QWidget()
            chk_lay = QHBoxLayout(chk_w)
            chk_lay.setContentsMargins(6, 4, 6, 4)
            chk_lay.setAlignment(Qt.AlignCenter)

            chk_app = QCheckBox("تم التقديم")
            chk_app.setToolTip("تحديد لتحديث حالة الوظيفة في الإكسيل وجوجل درايف إلى تم التقديم (خارجي)")
            is_applied = any(w in status for w in ["Applied", "Sent", "Under Review", "Interview", "Received"])
            if is_applied:
                chk_app.setChecked(True)
                chk_app.setText("تم التقديم ✅")
                chk_app.setStyleSheet("color: #10B981; font-weight: bold;")
            else:
                chk_app.setText("معلق")
                chk_app.setStyleSheet("color: #94A3B8;")

            chk_app.toggled.connect(lambda checked, jid=job_id, cb=chk_app, si=status_item: self._on_tracked_job_applied_toggled(jid, checked, cb, si))
            chk_lay.addWidget(chk_app)
            self.table.setCellWidget(row, 8, chk_w)

            # Col 9: Action Buttons cell (fills cell completely with zero margins)
            action_widget = QWidget()
            act_layout = QHBoxLayout(action_widget)
            act_layout.setContentsMargins(0, 0, 0, 0)
            act_layout.setSpacing(1)

            # Determine whether this is an Email job or Website Form job
            is_email_job = "@" in contact or method == "EMAIL"

            if is_email_job:
                btn_send = QPushButton("🚀 إرسال الإيميل")
                btn_send.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                btn_send.setStyleSheet("""
                    QPushButton {
                        background-color: #059669;
                        color: white;
                        border: none;
                        border-radius: 0px;
                        margin: 0px;
                        padding: 0px;
                        font-weight: bold;
                        font-size: 13px;
                    }
                    QPushButton:hover {
                        background-color: #047857;
                    }
                """)
                btn_send.setToolTip(f"إرسال التقديم والمرفقات إلى {contact}")
                btn_send.clicked.connect(lambda ch, jid=job_id: self._approve_and_send_job_id(jid))
                act_layout.addWidget(btn_send, stretch=1)
            else:
                btn_portal = QPushButton("🌐 موقع التقديم")
                btn_portal.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                btn_portal.setStyleSheet("""
                    QPushButton {
                        background-color: #0284C7;
                        color: white;
                        border: none;
                        border-radius: 0px;
                        margin: 0px;
                        padding: 0px;
                        font-weight: bold;
                        font-size: 13px;
                    }
                    QPushButton:hover {
                        background-color: #0369A1;
                    }
                """)
                btn_portal.setToolTip("فتح صفحة التقديم في المتصفح ومجلد الـ ATS")
                btn_portal.clicked.connect(lambda ch, jid=job_id: self._open_job_portal_action(jid))
                act_layout.addWidget(btn_portal, stretch=1)

            # Folder button
            if folder_path and Path(folder_path).exists():
                btn_f = QPushButton("📁")
                btn_f.setFixedWidth(44)
                btn_f.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
                btn_f.setStyleSheet("""
                    QPushButton {
                        background-color: #334155;
                        color: white;
                        border: none;
                        border-radius: 0px;
                        margin: 0px;
                        padding: 0px;
                        font-size: 15px;
                    }
                    QPushButton:hover {
                        background-color: #475569;
                    }
                """)
                btn_f.setToolTip("فتح مجلد التقديم")
                btn_f.clicked.connect(lambda ch, fp=folder_path: os.startfile(fp))
                act_layout.addWidget(btn_f)

            # Delete button
            btn_del = QPushButton("🗑️")
            btn_del.setFixedWidth(44)
            btn_del.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            btn_del.setStyleSheet("""
                QPushButton {
                    background-color: #991B1B;
                    color: white;
                    border: none;
                    border-radius: 0px;
                    margin: 0px;
                    padding: 0px;
                    font-size: 15px;
                }
                QPushButton:hover {
                    background-color: #B91C1C;
                }
            """)
            btn_del.setToolTip("حذف هذه الوظيفة من السجل")
            btn_del.clicked.connect(lambda ch, jid=job_id: self._delete_job_action(jid))
            act_layout.addWidget(btn_del)

            self.table.setCellWidget(row, 9, action_widget)

        self.table.setColumnWidth(8, 150)
        self.table.setColumnWidth(9, 330)

    def _on_tracked_job_applied_toggled(self, job_id: str, is_applied: bool, checkbox: QCheckBox, status_item: QTableWidgetItem):
        new_status = "Applied (External / تم التقديم)" if is_applied else "Pending Approval"
        self.coordinator.tracker.update_job_status(job_id, new_status)
        self.coordinator.gdrive.sync_tracker_to_drive()
        if is_applied:
            checkbox.setText("تم التقديم ✅")
            checkbox.setStyleSheet("color: #10B981; font-weight: bold;")
            status_item.setText(new_status)
            status_item.setForeground(QColor("#10B981"))
        else:
            checkbox.setText("معلق")
            checkbox.setStyleSheet("color: #94A3B8;")
            status_item.setText("Pending Approval")
            status_item.setForeground(QColor("#F59E0B"))

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
            details = "\n".join([f"• {r.get('company_name')}: {r.get('detected_status')} ({r.get('subject')})" for r in replies])
            QMessageBox.information(
                self, 
                "تم فحص الردود بنجاح", 
                f"تم العثور على {len(replies)} ردود وتحديث السجل وإكسيل تلقائياً:\n\n{details}"
            )
        else:
            QMessageBox.information(self, "فحص البريد", "لا توجد ردود جديدة من الشركات في صندوق الوارد.")


def launch_app():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    launch_app()
