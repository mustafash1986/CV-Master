"""
Telegram Mobile Remote Agent.
Allows sending job postings or flyer images from smartphone,
tailoring the ATS application on the local PC,
and sending interactive approval buttons back to the phone before dispatching.
"""
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional
import requests

from cv_servant.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


class TelegramMobileAgent:
    def __init__(
        self,
        token: str = TELEGRAM_BOT_TOKEN,
        chat_id: str = TELEGRAM_CHAT_ID,
        on_job_received: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_approval: Optional[Callable[[str, str], None]] = None,
    ):
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{self.token}" if self.token else ""
        self.on_job_received = on_job_received
        self.on_approval = on_approval
        self.last_update_id = 0

    def is_configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def send_message(self, text: str, reply_markup: Optional[Dict[str, Any]] = None) -> bool:
        """Send a formatted text message to user's mobile."""
        if not self.is_configured():
            return False

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)

        try:
            res = requests.post(f"{self.api_url}/sendMessage", json=payload, timeout=10)
            return res.status_code == 200
        except Exception as e:
            logger.error(f"Telegram sendMessage failed: {e}")
            return False

    def send_document(self, file_path: Path, caption: str = "") -> bool:
        """Send generated PDF CV to mobile for preview."""
        if not self.is_configured() or not file_path.exists():
            return False

        try:
            with open(file_path, "rb") as f:
                res = requests.post(
                    f"{self.api_url}/sendDocument",
                    data={"chat_id": self.chat_id, "caption": caption},
                    files={"document": f},
                    timeout=30,
                )
            return res.status_code == 200
        except Exception as e:
            logger.error(f"Telegram sendDocument failed: {e}")
            return False

    def send_approval_request(self, job_data: Dict[str, Any], pdf_path: Optional[Path] = None):
        """
        Sends complete job package summary to mobile phone with 1-click interactive approval buttons.
        """
        job_id = job_data.get("job_id", "")
        company = job_data.get("company_name", "N/A")
        title = job_data.get("job_title", "N/A")
        country = job_data.get("country", "N/A")
        sponsorship = job_data.get("visa_sponsorship", "Not Mentioned")
        email_addr = job_data.get("application_email", "N/A")
        fit_score = job_data.get("fit_score", 90)

        message_text = (
            f"🎯 <b>فرصة عمل جديدة جاهزة للمراجعة:</b>\n\n"
            f"🏢 <b>الشركة:</b> {company}\n"
            f"📌 <b>المسمى:</b> {title}\n"
            f"🌍 <b>الدولة:</b> {country}\n"
            f"🛂 <b>الكفالة (Sponsorship):</b> {sponsorship}\n"
            f"📊 <b>درجة المطابقة:</b> {fit_score}%\n"
            f"✉️ <b>التقديم عبر:</b> {email_addr}\n\n"
            f"<i>تم تجهيز السيرة الذاتية المفصلة وخطاب التقديم ومسودة الإيميل بنجاح. اختر الإجراء:</i>"
        )

        inline_keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ موافقة وإرسال الإيميل الآن", "callback_data": f"approve_{job_id}"},
                ],
                [
                    {"text": "📁 حفظ كملف تقديم يدوي فقط", "callback_data": f"manual_{job_id}"},
                    {"text": "❌ تجاهل / إلغاء", "callback_data": f"reject_{job_id}"}
                ]
            ]
        }

        # Send PDF document first if exists
        if pdf_path and pdf_path.exists():
            self.send_document(pdf_path, caption=f"📄 السيرة الذاتية المفصلة لـ {company}")

        # Send interactive message
        self.send_message(message_text, reply_markup=inline_keyboard)

    def poll_updates(self):
        """Poll Telegram for incoming messages and button clicks."""
        if not self.is_configured():
            return

        try:
            params = {"offset": self.last_update_id + 1, "timeout": 5}
            res = requests.get(f"{self.api_url}/getUpdates", params=params, timeout=10)
            if res.status_code != 200:
                return

            updates = res.json().get("result", [])
            for update in updates:
                self.last_update_id = update["update_id"]

                # Handle Button Clicks (Callback Queries)
                if "callback_query" in update:
                    cb = update["callback_query"]
                    cb_data = cb.get("data", "")
                    cb_id = cb.get("id")

                    # Acknowledge callback
                    requests.post(f"{self.api_url}/answerCallbackQuery", json={"callback_query_id": cb_id})

                    if cb_data.startswith("approve_"):
                        job_id = cb_data.replace("approve_", "")
                        if self.on_approval:
                            self.on_approval(job_id, "SEND_EMAIL")
                        self.send_message(f"🚀 <b>جارٍ إرسال الإيميل للوظيفة ({job_id}) وتحديث السجلات...</b>")

                    elif cb_data.startswith("manual_"):
                        job_id = cb_data.replace("manual_", "")
                        if self.on_approval:
                            self.on_approval(job_id, "MANUAL_FOLDER")
                        self.send_message(f"📁 <b>تم حفظ ملفات الوظيفة ({job_id}) في مجلد مخصص للموقع.</b>")

                    elif cb_data.startswith("reject_"):
                        job_id = cb_data.replace("reject_", "")
                        if self.on_approval:
                            self.on_approval(job_id, "REJECT")
                        self.send_message(f"❌ <b>تم إلغاء التقديم على الوظيفة ({job_id}).</b>")

                # Handle Incoming Messages (Text / Photo from mobile)
                elif "message" in update:
                    msg = update["message"]
                    # If user sent text or link
                    if "text" in msg:
                        text_content = msg["text"]
                        if self.on_job_received and not text_content.startswith("/"):
                            self.on_job_received({"type": "text", "content": text_content})
                            self.send_message("📥 <b>تم استلام الوظيفة! جاري التحليل وتجهيز حزمة الـ ATS...</b>")

                    # If user sent a photo
                    elif "photo" in msg:
                        photos = msg["photo"]
                        best_photo = photos[-1]  # Highest resolution
                        file_id = best_photo["file_id"]

                        # Get download path
                        f_info = requests.get(f"{self.api_url}/getFile", params={"file_id": file_id}).json()
                        file_path_remote = f_info.get("result", {}).get("file_path")
                        if file_path_remote:
                            download_url = f"https://api.telegram.org/file/bot{self.token}/{file_path_remote}"
                            img_data = requests.get(download_url).content
                            if self.on_job_received:
                                self.on_job_received({"type": "image_bytes", "content": img_data, "filename": f"tg_{file_id[:8]}.jpg"})
                                self.send_message("📷 <b>تم استلام صورة الإعلان! جاري قراءة النصوص وتجهيز السيرة الذاتية...</b>")

        except Exception as e:
            logger.error(f"Error polling Telegram updates: {e}")
