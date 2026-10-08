/**
 * CV Servant - Smart Job Auto-Fill & Tracker Content Script
 * Auto-detects career forms and fills candidate data with native event simulation.
 * Scrapes job details and synchronizes with CV Servant desktop tracker.
 */

(function () {
  let candidateData = null;
  let isFloatingWidgetInjected = false;

  // Initialize and check if this page is a job board or application
  async function init() {
    // Request candidate profile from background service worker
    chrome.runtime.sendMessage({ action: "GET_PROFILE" }, (response) => {
      if (response && response.success && response.profile) {
        candidateData = response.profile;
        checkAndInjectFloatingWidget();
      }
    });

    // Listen for manual trigger messages from the extension popup
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
      if (request.action === "TRIGGER_AUTOFILL") {
        const stats = performAutoFill();
        sendResponse({ success: true, stats });
      } else if (request.action === "GET_PAGE_JOB_INFO") {
        const jobInfo = extractPageJobInfo();
        sendResponse({ success: true, jobInfo });
      }
    });
  }

  // Detects if the current webpage looks like a job posting or application form
  function isJobPage() {
    const url = window.location.href.toLowerCase();
    const hostname = window.location.hostname.toLowerCase();
    const text = document.body ? document.body.innerText.slice(0, 3000).toLowerCase() : "";

    const jobDomains = [
      "linkedin.com", "indeed.com", "seek.com.au", "seek.co.nz",
      "myworkdayjobs.com", "greenhouse.io", "lever.co", "smartrecruiters.com",
      "workable.com", "bamboohr.com", "taleo.net", "icims.com"
    ];

    const hasDomain = jobDomains.some(d => hostname.includes(d));
    const hasJobWords = url.includes("job") || url.includes("career") || url.includes("apply") || url.includes("vacancy");
    const hasFormWords = text.includes("apply") || text.includes("resume") || text.includes("cv") || text.includes("first name");

    return hasDomain || hasJobWords || hasFormWords;
  }

  // Extracts current Job Title, Company Name, Location, and URL from the DOM
  function extractPageJobInfo() {
    const url = window.location.href;
    let title = "";
    let company = "";
    let location = "";

    // 1. LinkedIn
    if (window.location.hostname.includes("linkedin.com")) {
      const titleElem = document.querySelector(".jobs-unified-top-card__job-title, .job-details-jobs-unified-top-card__job-title, h1.t-24, h1");
      if (titleElem) title = titleElem.innerText.trim();

      const compElem = document.querySelector(".jobs-unified-top-card__company-name, .job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__subtitle-primary a");
      if (compElem) company = compElem.innerText.trim();

      const locElem = document.querySelector(".jobs-unified-top-card__bullet, .job-details-jobs-unified-top-card__bullet, .jobs-unified-top-card__workplace-type");
      if (locElem) location = locElem.innerText.trim();
    }

    // 2. Seek / Indeed / Workday / Greenhouse
    if (!title) {
      const h1 = document.querySelector("h1, [data-automation-id='jobPostingHeader'], .job-title");
      if (h1) title = h1.innerText.trim();
    }

    if (!company) {
      const compNode = document.querySelector("[data-automation-id='legalEntityName'], .company-name, .employer, [data-automation='advertiser-name']");
      if (compNode) company = compNode.innerText.trim();
    }

    // Fallback: Document title
    if (!title && document.title) {
      const parts = document.title.split(/[-|–•]/);
      title = parts[0].trim();
      if (parts.length > 1 && !company) {
        company = parts[1].trim();
      }
    }

    return {
      job_title: title || "BIM Role",
      company_name: company || "Direct Employer",
      country: location || "Australia",
      city: location || "",
      job_url: url,
      source: window.location.hostname.replace("www.", "").split(".")[0].toUpperCase()
    };
  }

  // Set input value cleanly with React / Vue / Angular native setter override
  function setNativeValue(element, value) {
    if (!element || value === undefined || value === null) return;

    const valueToSet = String(value);

    // Call native setter to bypass React 16+ synthetic event suppression
    const prototype = Object.getPrototypeOf(element);
    const nativeDescriptor = Object.getOwnPropertyDescriptor(prototype, "value");
    if (nativeDescriptor && nativeDescriptor.set) {
      nativeDescriptor.set.call(element, valueToSet);
    } else {
      element.value = valueToSet;
    }

    // Dispatch synthetic bubbles
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
    element.dispatchEvent(new Event("blur", { bubbles: true }));
  }

  // Matches a form field to candidate data based on its attributes and labels
  function matchFieldDescriptor(field) {
    const id = (field.id || "").toLowerCase();
    const name = (field.name || "").toLowerCase();
    const placeholder = (field.placeholder || "").toLowerCase();
    const aria = (field.getAttribute("aria-label") || "").toLowerCase();
    const autocomplete = (field.getAttribute("autocomplete") || "").toLowerCase();

    // Associated label search
    let labelText = "";
    if (field.id) {
      const lbl = document.querySelector(`label[for="${field.id}"]`);
      if (lbl) labelText = lbl.innerText.toLowerCase();
    }
    if (!labelText && field.closest("label")) {
      labelText = field.closest("label").innerText.toLowerCase();
    }
    if (!labelText) {
      const parent = field.parentElement;
      if (parent) {
        const prevLabel = parent.querySelector("label, .label, span");
        if (prevLabel) labelText = prevLabel.innerText.toLowerCase();
      }
    }

    const fullStr = `${id} ${name} ${placeholder} ${aria} ${autocomplete} ${labelText}`;

    // Matching logic
    if (fullStr.includes("first") && (fullStr.includes("name") || fullStr.includes("given"))) {
      return "first_name";
    }
    if (fullStr.includes("last") && (fullStr.includes("name") || fullStr.includes("surname") || fullStr.includes("family"))) {
      return "last_name";
    }
    if (fullStr.includes("middle") && fullStr.includes("name")) {
      return "middle_name";
    }
    if ((fullStr.includes("full") && fullStr.includes("name")) || (fullStr.includes("applicant") && fullStr.includes("name")) || name === "name" || id === "name") {
      return "full_name";
    }
    if (fullStr.includes("email") || fullStr.includes("e-mail") || autocomplete.includes("email")) {
      return "email";
    }
    if (fullStr.includes("phone") || fullStr.includes("mobile") || fullStr.includes("cell") || fullStr.includes("tel") || autocomplete.includes("tel")) {
      if (fullStr.includes("country") || fullStr.includes("code")) return "phone_country_code";
      return "phone";
    }
    if (fullStr.includes("linkedin")) {
      return "linkedin";
    }
    if (fullStr.includes("portfolio") || fullStr.includes("website") || fullStr.includes("github") || fullStr.includes("personal site")) {
      return "portfolio";
    }
    if (fullStr.includes("address") || fullStr.includes("street")) {
      return "address";
    }
    if (fullStr.includes("city") || fullStr.includes("town")) {
      return "city";
    }
    if (fullStr.includes("country") && !fullStr.includes("phone")) {
      return "country";
    }
    if (fullStr.includes("postal") || fullStr.includes("zip")) {
      return "postal_code";
    }
    if (fullStr.includes("nationality") || fullStr.includes("citizenship")) {
      return "nationality";
    }
    if (fullStr.includes("revit") && (fullStr.includes("year") || fullStr.includes("experience"))) {
      return "revit_experience_years";
    }
    if (fullStr.includes("bim") && (fullStr.includes("year") || fullStr.includes("experience"))) {
      return "bim_experience_years";
    }
    if ((fullStr.includes("cad") || fullStr.includes("autocad")) && (fullStr.includes("year") || fullStr.includes("experience"))) {
      return "autocad_experience_years";
    }
    if (fullStr.includes("experience") && fullStr.includes("year") && !fullStr.includes("company")) {
      return "total_experience_years";
    }
    if (fullStr.includes("notice") || fullStr.includes("availability") || fullStr.includes("start date")) {
      return "notice_period";
    }
    if (fullStr.includes("cover") && (fullStr.includes("letter") || fullStr.includes("note"))) {
      return "cover_letter";
    }
    if (fullStr.includes("summary") || fullStr.includes("about") || fullStr.includes("bio")) {
      return "summary";
    }
    if (fullStr.includes("pmp")) {
      return "pmp_certified";
    }
    if (fullStr.includes("salary") || fullStr.includes("compensation")) {
      return "salary_expectation";
    }
    if (fullStr.includes("sponsor") || fullStr.includes("visa")) {
      return "sponsorship";
    }

    return null;
  }

  // Executes form autofill across inputs, textareas, and selects
  function performAutoFill() {
    if (!candidateData) {
      showToast("❌ بيانات المرشح غير محملة. تأكد من تشغيل تطبيق CV Servant.", "error");
      return { filled: 0 };
    }

    let filledCount = 0;
    const inputs = document.querySelectorAll("input:not([type='hidden']):not([type='submit']):not([type='file']), textarea, select");

    inputs.forEach((elem) => {
      // Don't overwrite if user already entered custom content unless empty
      if (elem.value && elem.value.trim().length > 0 && elem.type !== "select-one") {
        return;
      }

      const matchType = matchFieldDescriptor(elem);
      if (!matchType) return;

      let valueToFill = "";
      switch (matchType) {
        case "first_name":
          valueToFill = candidateData.first_name;
          break;
        case "last_name":
          valueToFill = candidateData.last_name;
          break;
        case "middle_name":
          valueToFill = candidateData.middle_name;
          break;
        case "full_name":
          valueToFill = candidateData.full_name;
          break;
        case "email":
          valueToFill = candidateData.email;
          break;
        case "phone":
          valueToFill = candidateData.phone;
          break;
        case "phone_country_code":
          valueToFill = candidateData.phone_country_code;
          break;
        case "linkedin":
          valueToFill = candidateData.linkedin;
          break;
        case "portfolio":
          valueToFill = candidateData.portfolio;
          break;
        case "address":
          valueToFill = candidateData.address;
          break;
        case "city":
          valueToFill = candidateData.city;
          break;
        case "country":
          valueToFill = candidateData.country;
          break;
        case "postal_code":
          valueToFill = candidateData.postal_code;
          break;
        case "nationality":
          valueToFill = candidateData.nationality;
          break;
        case "total_experience_years":
          valueToFill = candidateData.total_experience_years;
          break;
        case "revit_experience_years":
          valueToFill = candidateData.revit_experience_years;
          break;
        case "bim_experience_years":
          valueToFill = candidateData.bim_experience_years;
          break;
        case "autocad_experience_years":
          valueToFill = candidateData.autocad_experience_years;
          break;
        case "notice_period":
          valueToFill = candidateData.notice_period;
          break;
        case "summary":
          valueToFill = candidateData.summary;
          break;
        case "cover_letter":
          valueToFill = candidateData.summary;
          break;
        case "pmp_certified":
          valueToFill = candidateData.pmp_certified;
          break;
        case "salary_expectation":
          valueToFill = candidateData.common_answers?.salary_expectation || "Negotiable";
          break;
        case "sponsorship":
          valueToFill = candidateData.common_answers?.sponsorship || "Yes";
          break;
      }

      if (valueToFill !== undefined && valueToFill !== "") {
        if (elem.tagName.toLowerCase() === "select") {
          // Find matching option
          let found = false;
          const targetStr = String(valueToFill).toLowerCase();
          for (let opt of elem.options) {
            const optText = opt.text.toLowerCase();
            const optVal = opt.value.toLowerCase();
            if (optText.includes(targetStr) || optVal.includes(targetStr)) {
              elem.value = opt.value;
              elem.dispatchEvent(new Event("change", { bubbles: true }));
              found = true;
              break;
            }
          }
          if (found) filledCount++;
        } else {
          setNativeValue(elem, valueToFill);
          filledCount++;
          elem.style.transition = "background-color 0.4s ease";
          elem.style.backgroundColor = "rgba(16, 185, 129, 0.15)";
        }
      }
    });

    // Check radio buttons (e.g. Yes/No questions)
    const radioGroups = document.querySelectorAll("input[type='radio']");
    radioGroups.forEach((radio) => {
      const label = radio.parentElement ? radio.parentElement.innerText.toLowerCase() : "";
      const val = (radio.value || "").toLowerCase();
      // Auto-check "Yes" for positive qualifications (legal age, driving license, etc.)
      if ((label.includes("yes") || val === "yes" || val === "true") && !radio.checked) {
        const questionText = radio.closest("fieldset, .form-group, div")?.innerText.toLowerCase() || "";
        if (
          questionText.includes("18") ||
          questionText.includes("relocate") ||
          questionText.includes("revit") ||
          questionText.includes("eligible") ||
          questionText.includes("authorized") ||
          questionText.includes("license")
        ) {
          radio.click();
          filledCount++;
        }
      }
    });

    showToast(`⚡ تم تعبئة ${filledCount} حقلاً بنجاح عبر CV Servant!`, "success");
    return { filled: filledCount };
  }

  // Sends the current page's job info to CV Servant desktop tracker
  async function trackCurrentJob() {
    const jobInfo = extractPageJobInfo();
    showToast("⏳ جاري تسجيل الوظيفة في تطبيق CV Servant ومزامنة إكسل...", "info");

    chrome.runtime.sendMessage({
      action: "TRACK_APPLICATION",
      payload: {
        ...jobInfo,
        notes: "تم التقديم وتعبئة النموذج عبر إضافة المتصفح CV Servant"
      }
    }, (res) => {
      if (res && res.success) {
        showToast(`✅ تم تسجيل الوظيفة بنجاح في السجل (${jobInfo.company_name})!`, "success");
        // Update floating widget button style
        const trackBtn = document.getElementById("cvs-floating-track-btn");
        if (trackBtn) {
          trackBtn.innerHTML = "✅ تم التتبع";
          trackBtn.style.backgroundColor = "#059669";
        }
      } else {
        showToast("⚠️ تم حفظ الوظيفة محلياً وسيتم ترحيلها عند تشغيل البرنامج.", "warning");
      }
    });
  }

  // Floating widget injection
  function checkAndInjectFloatingWidget() {
    if (isFloatingWidgetInjected || !isJobPage()) return;
    isFloatingWidgetInjected = true;

    const widget = document.createElement("div");
    widget.id = "cv-servant-floating-panel";
    widget.innerHTML = `
      <div class="cvs-floating-box">
        <div class="cvs-floating-header">
          <div class="cvs-floating-title">
            <span class="cvs-dot"></span>
            <b>CV Servant</b>
          </div>
          <button id="cvs-minimize-btn" title="تصغير/إخفاء">✕</button>
        </div>
        <div class="cvs-floating-actions">
          <button id="cvs-floating-fill-btn" class="cvs-btn cvs-btn-fill">
            ⚡ تعبئة النموذج
          </button>
          <button id="cvs-floating-track-btn" class="cvs-btn cvs-btn-track">
            📌 تتبع التقديم
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(widget);

    // Event listeners
    document.getElementById("cvs-floating-fill-btn").addEventListener("click", () => {
      performAutoFill();
    });

    document.getElementById("cvs-floating-track-btn").addEventListener("click", () => {
      trackCurrentJob();
    });

    document.getElementById("cvs-minimize-btn").addEventListener("click", () => {
      widget.classList.toggle("cvs-minimized");
    });
  }

  // Toast notification system
  function showToast(message, type = "info") {
    let toast = document.getElementById("cvs-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "cvs-toast";
      document.body.appendChild(toast);
    }
    toast.className = `cvs-toast cvs-toast-${type} cvs-toast-visible`;
    toast.innerText = message;

    setTimeout(() => {
      toast.classList.remove("cvs-toast-visible");
    }, 4000);
  }

  // Start script
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
