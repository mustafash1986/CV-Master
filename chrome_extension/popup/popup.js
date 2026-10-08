/**
 * CV Servant - Chrome Extension Popup Script
 */

document.addEventListener("DOMContentLoaded", async () => {
  const statusBadge = document.getElementById("connection-status");
  const statusText = document.getElementById("status-text");
  const detectedTitle = document.getElementById("detected-job-title");
  const detectedCompany = document.getElementById("detected-company");
  const platformTag = document.getElementById("job-platform");
  const btnAutofill = document.getElementById("btn-autofill");
  const btnTrack = document.getElementById("btn-track");
  const toast = document.getElementById("popup-toast");

  let currentPageJobInfo = null;

  // 1. Check local server connection
  chrome.runtime.sendMessage({ action: "CHECK_STATUS" }, (response) => {
    if (response && response.online) {
      statusBadge.className = "status-badge status-online";
      statusText.innerText = "متصل بالبرنامج";
    } else {
      statusBadge.className = "status-badge status-offline";
      statusText.innerText = "البرنامج غير متصل";
    }
  });

  // 2. Query active tab for page job information
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (!tabs || !tabs[0]) return;
    const activeTab = tabs[0];

    // Try communicating with content script
    chrome.tabs.sendMessage(activeTab.id, { action: "GET_PAGE_JOB_INFO" }, (response) => {
      if (chrome.runtime.lastError || !response || !response.jobInfo) {
        // Fallback: Infer from tab title and URL
        const titleParts = (activeTab.title || "").split(/[-|–•]/);
        currentPageJobInfo = {
          job_title: titleParts[0]?.trim() || "وظيفة غير محددة",
          company_name: titleParts[1]?.trim() || "جهة التوظيف",
          country: "Australia",
          city: "",
          job_url: activeTab.url || "",
          source: (new URL(activeTab.url || "http://web.com")).hostname.replace("www.", "").split(".")[0].toUpperCase()
        };
      } else {
        currentPageJobInfo = response.jobInfo;
      }

      detectedTitle.innerText = currentPageJobInfo.job_title;
      detectedCompany.innerText = currentPageJobInfo.company_name;
      platformTag.innerText = currentPageJobInfo.source || "WEB";
    });
  });

  // 3. AutoFill Button Click
  btnAutofill.addEventListener("click", () => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs || !tabs[0]) return;
      showToast("⏳ جاري تعبئة بيانات المرشح في الصفحة...");

      chrome.tabs.sendMessage(tabs[0].id, { action: "TRIGGER_AUTOFILL" }, (response) => {
        if (chrome.runtime.lastError) {
          showToast("⚠️ يرجى تحديث الصفحة والمحاولة مرة أخرى.");
        } else if (response && response.success) {
          showToast(`⚡ تم تعبئة ${response.stats?.filled || 0} حقلاً بنجاح!`);
        }
      });
    });
  });

  // 4. Track Job Button Click
  btnTrack.addEventListener("click", () => {
    if (!currentPageJobInfo) {
      showToast("لم يتم اكتشاف بيانات الوظيفة بعد.");
      return;
    }

    showToast("⏳ جاري تسجيل الوظيفة في تطبيق CV Servant...");
    btnTrack.disabled = true;

    chrome.runtime.sendMessage({
      action: "TRACK_APPLICATION",
      payload: {
        ...currentPageJobInfo,
        notes: "تم التقديم وتسجيل الوظيفة عبر إضافة المتصفح CV Servant"
      }
    }, (response) => {
      btnTrack.disabled = false;
      if (response && response.success) {
        showToast("✅ تم تسجيل الوظيفة بنجاح في سجل إكسل!");
        btnTrack.innerHTML = "<span>✅</span><span>تم التسجيل</span>";
        btnTrack.style.background = "#059669";
      } else {
        showToast("⚠️ حدث خطأ أو البرنامج مغلق.");
      }
    });
  });

  // 5. Quick Copy Buttons
  document.querySelectorAll(".copy-pill").forEach((btn) => {
    btn.addEventListener("click", () => {
      const textToCopy = btn.getAttribute("data-copy");
      if (textToCopy) {
        navigator.clipboard.writeText(textToCopy).then(() => {
          const originalText = btn.innerHTML;
          btn.classList.add("copied");
          btn.innerHTML = "<span>✓ تم النسخ بنجاح</span>";
          setTimeout(() => {
            btn.innerHTML = originalText;
            btn.classList.remove("copied");
          }, 1500);
        });
      }
    });
  });

  // Toast Helper
  function showToast(msg) {
    toast.innerText = msg;
    toast.classList.add("visible");
    setTimeout(() => {
      toast.classList.remove("visible");
    }, 3000);
  }
});
