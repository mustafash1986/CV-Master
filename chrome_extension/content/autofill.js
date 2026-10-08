/**
 * CV Servant - Smart Job Auto-Fill & Tracker Content Script
 * High-intelligence form matching for SmartRecruiters, Workday, Taleo, Greenhouse,
 * Lever, LinkedIn, Seek, Indeed, and modern ATS job application portals.
 * Fully supports preliminary questionnaires and screening forms.
 */

(function () {
  // Always initialize candidateData with embedded default profile so it's NEVER null
  let candidateData = typeof DEFAULT_CANDIDATE_PROFILE !== "undefined"
    ? Object.assign({}, DEFAULT_CANDIDATE_PROFILE)
    : null;

  let isFloatingWidgetInjected = false;

  // Initialize and sync latest profile from local server
  function init() {
    try {
      chrome.runtime.sendMessage({ action: "GET_PROFILE" }, (response) => {
        if (response && response.success && response.profile) {
          candidateData = Object.assign({}, candidateData || {}, response.profile);
        }
      });
    } catch (e) {
      // Background context check
    }

    // Inject floating widget
    checkAndInjectFloatingWidget();

    // Listen for trigger messages from popup or background
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
      if (request.action === "TRIGGER_AUTOFILL") {
        if (request.payload && request.payload.profile) {
          candidateData = Object.assign({}, candidateData || {}, request.payload.profile);
        }
        performAutoFill().then((stats) => {
          sendResponse({ success: true, stats });
        });
        return true; // Keep channel open for async response
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
      "smartrecruiters.com", "linkedin.com", "indeed.com", "seek.com.au", "seek.co.nz",
      "myworkdayjobs.com", "workday.com", "greenhouse.io", "lever.co",
      "workable.com", "bamboohr.com", "taleo.net", "icims.com", "ashbyhq.com", "jobvite.com"
    ];

    const hasDomain = jobDomains.some((d) => hostname.includes(d));
    const hasJobWords = url.includes("job") || url.includes("career") || url.includes("apply") || url.includes("screening") || url.includes("publication");
    const hasFormWords = text.includes("apply") || text.includes("resume") || text.includes("cv") || text.includes("nationality") || text.includes("experience") || text.includes("questions");

    return hasDomain || hasJobWords || hasFormWords;
  }

  // Extracts current Job Title, Company Name, Location, and URL from the DOM
  function extractPageJobInfo() {
    const url = window.location.href;
    let title = "";
    let company = "";
    let location = "";

    // 1. SmartRecruiters specific
    if (window.location.hostname.includes("smartrecruiters.com")) {
      const srComp = document.querySelector(".company-name, [data-qa='company-name'], h1.brand, .logo-title, header img[alt]");
      if (srComp) company = srComp.getAttribute("alt") || srComp.innerText.trim();

      const srTitle = document.querySelector(".job-title, [data-qa='job-title'], h1, .c-header__title");
      if (srTitle) title = srTitle.innerText.trim();
    }

    // 2. Workday specific
    if (!title) {
      const wdTitle = document.querySelector("[data-automation-id='jobPostingHeader'], [data-automation-id='jobTitle']");
      if (wdTitle) title = wdTitle.innerText.trim();
    }
    if (!company) {
      const wdComp = document.querySelector("[data-automation-id='legalEntityName'], [data-automation-id='company']");
      if (wdComp) company = wdComp.innerText.trim();
    }

    // 3. LinkedIn specific
    if (!title && window.location.hostname.includes("linkedin.com")) {
      const titleElem = document.querySelector(".jobs-unified-top-card__job-title, .job-details-jobs-unified-top-card__job-title, h1.t-24, h1");
      if (titleElem) title = titleElem.innerText.trim();

      const compElem = document.querySelector(".jobs-unified-top-card__company-name, .job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__subtitle-primary a");
      if (compElem) company = compElem.innerText.trim();
    }

    // 4. General fallbacks
    if (!title) {
      const h1 = document.querySelector("h1, .job-title, [data-qa='job-title']");
      if (h1) title = h1.innerText.trim();
    }

    if (!company) {
      // Check URL path (e.g. /company/AECOM2/...)
      const mComp = url.match(/\/company\/([^/]+)/i);
      if (mComp) {
        company = mComp[1].replace(/\d+$/, "");
      }
    }

    if (!title && document.title) {
      const parts = document.title.split(/[-|–•]/);
      title = parts[0].trim();
      if (parts.length > 1 && !company) {
        company = parts[1].trim();
      }
    }

    return {
      job_title: title || "Architect",
      company_name: company || "AECOM",
      country: location || "Saudi Arabia / GCC",
      city: location || "",
      job_url: url,
      source: window.location.hostname.replace("www.", "").split(".")[0].toUpperCase()
    };
  }

  // Set input value cleanly with React / Vue / Angular / SmartRecruiters native setter override
  function setNativeValue(element, value) {
    if (!element || value === undefined || value === null) return;

    const valueToSet = String(value);

    try {
      element.focus();
    } catch (e) {}

    // Call native prototype setter to bypass synthetic event suppression
    const prototype = Object.getPrototypeOf(element);
    const nativeDescriptor = Object.getOwnPropertyDescriptor(prototype, "value");
    if (nativeDescriptor && nativeDescriptor.set) {
      nativeDescriptor.set.call(element, valueToSet);
    } else {
      element.value = valueToSet;
    }

    // Dispatch full cycle of synthetic events so character counters (e.g. 0/200) update immediately
    element.dispatchEvent(new Event("input", { bubbles: true, cancelable: true }));
    element.dispatchEvent(new Event("change", { bubbles: true, cancelable: true }));
    element.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, cancelable: true, key: "Enter" }));
    element.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, cancelable: true, key: "Enter" }));
    element.dispatchEvent(new Event("blur", { bubbles: true, cancelable: true }));

    // Visual feedback highlight
    element.style.transition = "all 0.3s ease";
    element.style.backgroundColor = "rgba(16, 185, 129, 0.15)";
    element.style.borderColor = "#10B981";
  }

  // Deep inspection to locate the exact question prompt / title for this field
  function getFieldQuestionTitle(field) {
    let parts = [];

    // 1. Direct attributes
    if (field.getAttribute("aria-label")) parts.push(field.getAttribute("aria-label"));
    if (field.getAttribute("placeholder")) parts.push(field.getAttribute("placeholder"));
    if (field.id) parts.push(field.id);
    if (field.name) parts.push(field.name);
    if (field.getAttribute("data-qa")) parts.push(field.getAttribute("data-qa"));
    if (field.getAttribute("data-automation-id")) parts.push(field.getAttribute("data-automation-id"));

    // 2. aria-labelledby
    const lblBy = field.getAttribute("aria-labelledby");
    if (lblBy) {
      lblBy.split(/\s+/).forEach((id) => {
        const el = document.getElementById(id);
        if (el) parts.push(el.innerText || "");
      });
    }

    // 3. Associated <label for="...">
    if (field.id) {
      try {
        const lbl = document.querySelector(`label[for="${CSS.escape(field.id)}"]`);
        if (lbl) parts.push(lbl.innerText || "");
      } catch (e) {}
    }

    // 4. Check preceding siblings of field and its parent wrappers
    // In SmartRecruiters, the question title is directly above the input container
    let p = field;
    for (let i = 0; i < 4; i++) {
      if (!p) break;
      let prev = p.previousElementSibling;
      while (prev) {
        const txt = (prev.innerText || "").trim();
        if (txt && !txt.match(/^\d+\s*\/\s*\d+$/) && txt.length < 250) {
          parts.push(txt);
        }
        prev = prev.previousElementSibling;
      }
      p = p.parentElement;
    }

    // 5. Container search (SmartRecruiters OneClick questionnaire blocks)
    let container = field.closest(
      ".c-question, .question, .form-group, .screening-question, .c-form-item, [class*='question'], [class*='screening'], [class*='field'], section, fieldset, li, tr, div"
    );

    let depth = 0;
    while (container && depth < 6 && container !== document.body) {
      const headings = container.querySelectorAll(
        "h1, h2, h3, h4, h5, label, legend, [class*='title'], [class*='header'], [class*='label'], p, span"
      );
      headings.forEach((h) => {
        const ht = (h.innerText || "").trim();
        // Ignore character counters and small symbols
        if (ht && !ht.match(/^\d+\s*\/\s*\d+$/) && ht.length > 3 && ht.length < 300) {
          parts.push(ht);
        }
      });

      if (container.classList && (container.classList.contains("c-question") || container.classList.contains("question") || container.classList.contains("screening-question"))) {
        break;
      }
      container = container.parentElement;
      depth++;
    }

    return parts.join(" ").toLowerCase();
  }

  // Matches any questionnaire or standard form field to the candidate's exact profile answer
  function getAnswerForField(field) {
    const text = getFieldQuestionTitle(field);
    console.log(`[CV Servant AutoFill] Field context: "${text.slice(0, 120)}"`);

    // --- SMARTRECRUITERS / AECOM PRELIMINARY QUESTIONS ---

    // 1. Nationality
    if (text.includes("nationality") || text.includes("citizenship") || text.includes("الجنسية")) {
      return candidateData.nationality || "Egyptian";
    }

    // 2. Current Location / Country of residence
    if (
      (text.includes("location") || text.includes("residence") || text.includes("where do you live") || text.includes("reside")) &&
      (text.includes("current") || text.includes("present") || text.includes("country"))
    ) {
      return candidateData.current_location || "Kuwait";
    }

    // 3. Family / Marital Status
    if (text.includes("family status") || text.includes("marital status") || text.includes("marital") || text.includes("الحالة الاجتماعية")) {
      return candidateData.family_status || "Married";
    }

    // 4. Family living in Saudi Arabia
    if (text.includes("family") && (text.includes("live with you") || text.includes("saudi"))) {
      return candidateData.family_in_saudi || "No";
    }

    // 5. Date of Birth / Birthday
    if (text.includes("date of birth") || text.includes("birth date") || text.includes("dob") || text.includes("birthday") || text.includes("تاريخ الميلاد")) {
      return candidateData.date_of_birth || "15/07/1986";
    }

    // 6. Professional Title in Iqama
    if (
      (text.includes("professional title") || text.includes("title in iqama")) ||
      (text.includes("title") && text.includes("iqama"))
    ) {
      return candidateData.iqama_title || "N/A";
    }

    // 7. Saudi Legal Residency Permit / Valid Iqama
    if (
      (text.includes("residency permit") || text.includes("legal residency") || text.includes("valid iqama") || text.includes("iqama")) &&
      (text.includes("saudi") || text.includes("ksa") || text.includes("permit"))
    ) {
      return candidateData.saudi_residency || "No";
    }

    // 8. Total Years of Experience overall
    if (
      (text.includes("total years of experience overall") || text.includes("years of experience overall") || text.includes("total years of experience") || text.includes("experience overall")) ||
      (text.includes("total") && text.includes("years") && text.includes("experience"))
    ) {
      return candidateData.total_experience_years || "19";
    }

    // 9. Total Years of Experience in GCC
    if (
      (text.includes("experience in gcc") || text.includes("years in gcc") || text.includes("gcc experience") || text.includes("experience overall in gcc")) ||
      (text.includes("years") && text.includes("gcc"))
    ) {
      return candidateData.gcc_experience_years || "17";
    }

    // 10. Worked with AECOM / Company before
    if (
      text.includes("worked with aecom") ||
      text.includes("worked for aecom") ||
      text.includes("worked with us before") ||
      text.includes("worked with company before") ||
      text.includes("previously employed") ||
      text.includes("previous employee")
    ) {
      return candidateData.worked_with_company_before || "No";
    }

    // 11. Relation or family member working for AECOM / Company
    if (
      text.includes("relation or family member") ||
      text.includes("relative working") ||
      text.includes("family member working") ||
      text.includes("relatives in company") ||
      text.includes("family member")
    ) {
      return candidateData.relatives_in_company || "No";
    }

    // 12. Monthly Salary Expectation (USD)
    if (
      text.includes("monthly salary expectation") ||
      text.includes("salary expectation (usd)") ||
      text.includes("salary expectation") ||
      text.includes("expected salary") ||
      text.includes("monthly salary") ||
      text.includes("salary (usd)")
    ) {
      return candidateData.salary_expectation_usd || "5000";
    }

    // 13. Highest Educational Degree earned
    if (
      text.includes("highest educational degree") ||
      text.includes("educational degree") ||
      text.includes("highest degree") ||
      text.includes("degree you have earned") ||
      text.includes("education level") ||
      text.includes("أعلى مؤهل")
    ) {
      return candidateData.highest_degree || "Bachelor's Degree";
    }

    // 14. Year of Graduation
    if (
      text.includes("year of graduation") ||
      text.includes("graduation year") ||
      text.includes("year of grad") ||
      text.includes("grad year") ||
      text.includes("سنة التخرج")
    ) {
      return candidateData.graduation_year || "2007";
    }

    // --- STANDARD PERSONAL INFO FIELDS ---

    // First Name
    if (
      text.includes("first_name") ||
      text.includes("firstname") ||
      text.includes("first name") ||
      text.includes("given name") ||
      text.includes("legalnamesection_firstname") ||
      text.includes("الاسم الأول")
    ) {
      return candidateData.first_name || "Mustafa";
    }

    // Last Name
    if (
      text.includes("last_name") ||
      text.includes("lastname") ||
      text.includes("last name") ||
      text.includes("surname") ||
      text.includes("family name") ||
      text.includes("legalnamesection_lastname") ||
      text.includes("اسم العائلة")
    ) {
      return candidateData.last_name || "Shawky";
    }

    // Full Name
    if (
      text.includes("full_name") ||
      text.includes("fullname") ||
      text.includes("full name") ||
      text.includes("applicant name") ||
      text.includes("candidate name") ||
      text.includes("الاسم بالكامل")
    ) {
      return candidateData.full_name || "Mustafa Mahmoud Shawky";
    }

    // Email
    if (text.includes("email") || text.includes("e-mail") || field.type === "email" || text.includes("البريد")) {
      return candidateData.email || "arch.mustafa.mahmoud.2007@gmail.com";
    }

    // Phone
    if (
      text.includes("phone") ||
      text.includes("mobile") ||
      text.includes("cell") ||
      text.includes("tel") ||
      text.includes("contact number") ||
      field.type === "tel" ||
      text.includes("الهاتف") ||
      text.includes("الجوال")
    ) {
      return candidateData.phone || "+965 9919 1358";
    }

    // Phone Country Code
    if (text.includes("country code") || text.includes("dial code")) {
      return candidateData.phone_country_code || "+965";
    }

    // LinkedIn
    if (text.includes("linkedin") || text.includes("لينكد")) {
      return candidateData.linkedin;
    }

    // Portfolio / Website
    if (text.includes("portfolio") || text.includes("website") || text.includes("personal site") || text.includes("بورتفوليو")) {
      return candidateData.portfolio;
    }

    // Current Employer / Company
    if (text.includes("current company") || text.includes("current employer") || text.includes("organization")) {
      return candidateData.current_company || "Pace";
    }

    // Current Job Title
    if (text.includes("job title") || text.includes("current title") || text.includes("current role") || text.includes("designation")) {
      return candidateData.current_title || "Senior Architect & BIM Specialist";
    }

    // General Technical Skills (Revit / BIM / CAD)
    if (text.includes("revit") || text.includes("ريفيت")) {
      return candidateData.revit_experience_years || "16";
    }
    if (text.includes("bim") || text.includes("بيم")) {
      return candidateData.bim_experience_years || "15";
    }
    if (text.includes("autocad") || text.includes("cad") || text.includes("أوتوكاد")) {
      return candidateData.autocad_experience_years || "19";
    }

    // PMP Certification
    if (text.includes("pmp")) {
      return candidateData.pmp_certified || "Yes";
    }

    // Notice Period / Availability
    if (text.includes("notice") || text.includes("availability") || text.includes("start date") || text.includes("commence")) {
      return candidateData.notice_period || "1 Month";
    }

    // Cover letter / Summary
    if (text.includes("cover letter") || text.includes("cover_letter") || text.includes("summary") || text.includes("bio") || text.includes("why hire")) {
      return candidateData.summary;
    }

    // General Visa Sponsorship question
    if (text.includes("sponsor") || text.includes("visa sponsorship") || text.includes("work authorization")) {
      return candidateData.common_answers?.sponsorship || "Yes";
    }

    return null;
  }

  // Executes form autofill across inputs, textareas, and selects
  async function performAutoFill() {
    if (!candidateData) {
      if (typeof DEFAULT_CANDIDATE_PROFILE !== "undefined") {
        candidateData = Object.assign({}, DEFAULT_CANDIDATE_PROFILE);
      }
    }

    let filledCount = 0;

    // Grab all interactive inputs, textareas, and selects
    const inputs = document.querySelectorAll(
      "input:not([type='hidden']):not([type='submit']):not([type='file']):not([type='button']), textarea, select"
    );

    console.log(`[CV Servant AutoFill] Total inputs detected: ${inputs.length}`);

    for (let i = 0; i < inputs.length; i++) {
      const elem = inputs[i];

      // Skip inputs that already have user-entered text (unless empty or spaces)
      if (elem.value && elem.value.trim().length > 0 && elem.type !== "select-one") {
        continue;
      }

      const answer = getAnswerForField(elem);
      if (answer === null || answer === undefined) continue;

      console.log(`[CV Servant AutoFill] Matching input #${i} => "${answer}"`);

      if (elem.tagName.toLowerCase() === "select") {
        // Standard <select> dropdown
        let found = false;
        const targetStr = String(answer).toLowerCase();
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
        // Text input / Search input / Textarea
        setNativeValue(elem, answer);
        filledCount++;

        // For SmartRecruiters search inputs with 🔍 dropdowns:
        // Try finding and clicking the matching dropdown item if an overlay appears
        await new Promise((r) => setTimeout(r, 60));
        try {
          const suggestions = document.querySelectorAll(
            "[role='listbox'] [role='option'], .select-options li, .suggestions li, [data-qa='select-option'], .dropdown-item, .c-select__option"
          );
          if (suggestions.length > 0) {
            const targetLower = String(answer).toLowerCase();
            for (let opt of suggestions) {
              if (opt.innerText && opt.innerText.toLowerCase().includes(targetLower)) {
                opt.click();
                break;
              }
            }
          }
        } catch (e) {}
      }
    }

    // Handle Radio buttons (Yes / No questions)
    const radioGroups = document.querySelectorAll("input[type='radio']");
    radioGroups.forEach((radio) => {
      const label = radio.parentElement ? radio.parentElement.innerText.toLowerCase() : "";
      const val = (radio.value || "").toLowerCase();
      const questionText = radio.closest(".c-question, .question, fieldset, .form-group, div")?.innerText.toLowerCase() || "";

      // Auto check "No" for AECOM worked before or relatives
      if (
        (questionText.includes("worked with aecom") || questionText.includes("relation or family member")) &&
        (label.includes("no") || val === "no" || val === "false")
      ) {
        radio.click();
        filledCount++;
      }
      // Auto check "Yes" for positive legal qualifications
      else if (
        (questionText.includes("18") || questionText.includes("relocate") || questionText.includes("license")) &&
        (label.includes("yes") || val === "yes" || val === "true")
      ) {
        radio.click();
        filledCount++;
      }
    });

    if (filledCount > 0) {
      showToast(`⚡ تم تعبئة ${filledCount} حقلاً بنجاح عبر CV Servant!`, "success");
    } else {
      showToast("ℹ️ تم فحص الحقول. تأكد من ظهور أسئلة استمارة التقديم على الشاشة.", "warning");
    }

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
        notes: "تم التقديم وتعبئة استمارة التقديم عبر إضافة المتصفح CV Servant"
      }
    }, (res) => {
      if (res && res.success) {
        showToast(`✅ تم تسجيل الوظيفة بنجاح في السجل (${jobInfo.company_name})!`, "success");
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
