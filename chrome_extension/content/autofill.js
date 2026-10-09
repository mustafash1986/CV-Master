/**
 * CV Servant - Smart Job Auto-Fill & Tracker Content Script
 * High-precision two-way autofill engine supporting SmartRecruiters OneClick,
 * Workday, Taleo, Greenhouse, Lever, LinkedIn, Seek, and Indeed.
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
    } catch (e) {}

    // Inject floating widget ONLY on top window (never in iframes!)
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
    const hasFormWords = text.includes("apply") || text.includes("resume") || text.includes("cv") || text.includes("first name") || text.includes("personal information");

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

      const srLoc = document.querySelector(".job-location, [data-qa='job-location'], .c-header__meta");
      if (srLoc) location = srLoc.innerText.trim();
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

    // 3. Fallbacks
    if (!company) {
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

    // Dispatch full cycle of synthetic events so character counters and validations update immediately
    element.dispatchEvent(new Event("input", { bubbles: true, cancelable: true }));
    element.dispatchEvent(new Event("change", { bubbles: true, cancelable: true }));
    element.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, cancelable: true, key: "Enter" }));
    element.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, cancelable: true, key: "Enter" }));
    element.dispatchEvent(new Event("blur", { bubbles: true, cancelable: true }));

    // Visual green feedback highlight
    element.style.transition = "all 0.3s ease";
    element.style.backgroundColor = "rgba(16, 185, 129, 0.15)";
    element.style.borderColor = "#10B981";
  }

  // Locates the EXACT direct label for a specific field (without section bleeding)
  function getExactFieldLabel(field) {
    // 1. Direct field attributes
    let directTokens = [];
    if (field.getAttribute("aria-label")) directTokens.push(field.getAttribute("aria-label"));
    if (field.getAttribute("placeholder")) directTokens.push(field.getAttribute("placeholder"));
    if (field.getAttribute("data-qa")) directTokens.push(field.getAttribute("data-qa"));
    if (field.getAttribute("data-automation-id")) directTokens.push(field.getAttribute("data-automation-id"));
    if (field.name) directTokens.push(field.name);
    if (field.id) directTokens.push(field.id);

    // 2. aria-labelledby
    const lblBy = field.getAttribute("aria-labelledby");
    if (lblBy) {
      lblBy.split(/\s+/).forEach((id) => {
        const el = document.getElementById(id);
        if (el && el.innerText) directTokens.push(el.innerText.trim());
      });
    }

    // 3. Associated <label for="field.id">
    if (field.id) {
      try {
        const lbl = document.querySelector(`label[for="${CSS.escape(field.id)}"]`);
        if (lbl && lbl.innerText) return lbl.innerText.trim().toLowerCase();
      } catch (e) {}
    }

    // 4. Parent <label>
    const parentLabel = field.closest("label");
    if (parentLabel && parentLabel.innerText) {
      return parentLabel.innerText.trim().toLowerCase();
    }

    // 5. Immediate wrapper search (SmartRecruiters OneClick structure)
    // <div class="c-form-item"> (or c-input)
    //   <label class="c-label">First name*</label>
    //   <input ...>
    // </div>
    let wrapper = field.parentElement;
    for (let i = 0; i < 4 && wrapper; i++) {
      // Find a label or title that belongs directly to this input's immediate wrapper
      const directLbl = wrapper.querySelector(
        ":scope > label, :scope > .c-label, :scope > .label, :scope > .c-question__header, :scope > h3, :scope > h4, :scope > p.label"
      );
      if (directLbl && directLbl.innerText) {
        const t = directLbl.innerText.trim().toLowerCase();
        if (!t.match(/^\d+\s*\/\s*\d+$/) && t.length < 120) {
          return t;
        }
      }

      // Check immediate previous sibling of the input's wrapper
      const prev = wrapper.previousElementSibling;
      if (prev && prev.innerText) {
        const pt = prev.innerText.trim().toLowerCase();
        if (!pt.match(/^\d+\s*\/\s*\d+$/) && pt.length < 150) {
          // If the previous element is a label or small title, return it
          if (prev.tagName === "LABEL" || prev.tagName === "H3" || prev.tagName === "H4" || prev.tagName === "P" || prev.classList.contains("c-label")) {
            return pt;
          }
        }
      }

      // Stop before climbing out to the entire section or form!
      if (wrapper.tagName === "SECTION" || wrapper.tagName === "FORM" || wrapper.classList.contains("c-section")) {
        break;
      }
      wrapper = wrapper.parentElement;
    }

    if (directTokens.length > 0) {
      return directTokens.join(" ").toLowerCase();
    }

    return "";
  }

  // Matches a label to the candidate's exact profile answer
  function getAnswerForLabel(label, field) {
    label = (label || "").toLowerCase();

    // 1. Confirm Email (must be checked before regular email!)
    if (label.includes("confirm") && label.includes("email")) {
      return candidateData.email || "arch.mustafa.mahmoud.2007@gmail.com";
    }

    // 2. Email Address
    if (
      label.includes("email") ||
      label.includes("e-mail") ||
      field.type === "email" ||
      label.includes("البريد") ||
      label.includes("الإيميل")
    ) {
      return candidateData.email || "arch.mustafa.mahmoud.2007@gmail.com";
    }

    // 3. First Name
    if (
      label.includes("first name") ||
      label.includes("firstname") ||
      label.includes("first_name") ||
      label.includes("given name") ||
      label.includes("fname") ||
      label.includes("legalnamesection_firstname") ||
      label.includes("الاسم الأول")
    ) {
      return candidateData.first_name || "Mustafa";
    }

    // 4. Last Name / Surname / Family Name
    if (
      label.includes("last name") ||
      label.includes("lastname") ||
      label.includes("last_name") ||
      label.includes("surname") ||
      label.includes("family name") ||
      label.includes("family_name") ||
      label.includes("lname") ||
      label.includes("legalnamesection_lastname") ||
      label.includes("اسم العائلة") ||
      label.includes("الاسم الأخير")
    ) {
      return candidateData.last_name || "Shawky";
    }

    // 5. Middle Name
    if (label.includes("middle name") || label.includes("middlename") || label.includes("الاسم الأوسط")) {
      return candidateData.middle_name || "Mahmoud";
    }

    // 6. Full Name
    if (
      label.includes("full name") ||
      label.includes("fullname") ||
      label.includes("candidate name") ||
      label.includes("applicant name") ||
      label.includes("your name") ||
      label.includes("الاسم بالكامل")
    ) {
      return candidateData.full_name || "Mustafa Mahmoud Shawky";
    }

    // 7. Phone Country / Dial Code
    if (label.includes("country code") || label.includes("dial code")) {
      return candidateData.phone_country_code || "+965";
    }

    // 8. Phone Number (SmartRecruiters & Workday)
    if (
      label.includes("phone number") ||
      label.includes("phone") ||
      label.includes("mobile") ||
      label.includes("cell") ||
      label.includes("tel") ||
      label.includes("contact number") ||
      field.type === "tel" ||
      label.includes("الهاتف") ||
      label.includes("الجوال")
    ) {
      // If there is an international flag/dial dropdown right next to it (+965), fill national number
      const hasFlag = field.closest(".c-phone, .input-group, div")?.querySelector(".iti__selected-flag, .c-phone__country, [class*='dial'], select");
      if (hasFlag) {
        return candidateData.phone_national || "99191358";
      }
      return candidateData.phone || "+965 9919 1358";
    }

    // 9. City / Suburb (SmartRecruiters City* field)
    if (
      label.includes("city") ||
      label.includes("town") ||
      label.includes("suburb") ||
      label.includes("المدينة")
    ) {
      return candidateData.city || "Sabah Elsalem";
    }

    // 10. LinkedIn URL
    if (label.includes("linkedin") || label.includes("لينكد")) {
      return candidateData.linkedin;
    }

    // 11. Portfolio / Website / Personal URL
    if (
      label.includes("portfolio") ||
      label.includes("website") ||
      label.includes("personal site") ||
      label.includes("personal url") ||
      label.includes("web link") ||
      label.includes("بورتفوليو") ||
      label.includes("معرض الأعمال")
    ) {
      return candidateData.portfolio;
    }

    // 12. Address Line / Street
    if (label.includes("address") || label.includes("street") || label.includes("العنوان") || label.includes("الشارع")) {
      return candidateData.address || "Sabah Elsalem";
    }

    // 13. Postal Code / Zip
    if (label.includes("postal") || label.includes("zip") || label.includes("postcode") || label.includes("الرمز البريدي")) {
      return candidateData.postal_code || "44000";
    }

    // 14. Nationality / Citizenship
    if (label.includes("nationality") || label.includes("citizenship") || label.includes("الجنسية")) {
      return candidateData.nationality || "Egyptian";
    }

    // 15. Current Location / Residence
    if (
      label.includes("current location") ||
      label.includes("where do you live") ||
      label.includes("residence") ||
      label.includes("مكان الإقامة") ||
      (label.includes("location") && !label.includes("relocate"))
    ) {
      return candidateData.current_location || "Kuwait";
    }

    // 16. Family / Marital Status
    if (label.includes("family status") || label.includes("marital status") || label.includes("marital") || label.includes("الحالة الاجتماعية")) {
      return candidateData.family_status || "Married";
    }

    // 17. Family Living in Saudi Arabia
    if (label.includes("family") && (label.includes("live with you") || label.includes("saudi"))) {
      return "No";
    }

    // 18. Date of Birth / Birthday
    if (label.includes("date of birth") || label.includes("birth date") || label.includes("dob") || label.includes("birthday") || label.includes("تاريخ الميلاد")) {
      return candidateData.date_of_birth || "15/07/1986";
    }

    // 19. Professional Title in Iqama
    if (label.includes("professional title") || (label.includes("title") && label.includes("iqama"))) {
      return "N/A";
    }

    // 20. Saudi Residency Permit / Valid Iqama
    if ((label.includes("residency permit") || label.includes("legal residency") || label.includes("iqama")) && (label.includes("saudi") || label.includes("ksa"))) {
      return "No";
    }

    // 21. Total Years of Experience overall
    if (label.includes("total years") || (label.includes("years of experience") && label.includes("overall")) || label.includes("total experience")) {
      return candidateData.total_experience_years || "19";
    }

    // 22. Total Years of Experience in GCC
    if (label.includes("gcc") && (label.includes("experience") || label.includes("years"))) {
      return candidateData.gcc_experience_years || "17";
    }

    // 23. Worked with AECOM / Company before
    if (label.includes("worked with") || label.includes("worked for") || label.includes("previously employed")) {
      return "No";
    }

    // 24. Relation / Family member working for AECOM
    if (label.includes("relation") || label.includes("family member") || label.includes("relative")) {
      return "No";
    }

    // 25. Monthly Salary Expectation (USD)
    if (label.includes("salary") || label.includes("compensation") || label.includes("remuneration") || label.includes("الراتب")) {
      return candidateData.salary_expectation_usd || "5000";
    }

    // 26. Highest Educational Degree
    if (label.includes("highest") && (label.includes("degree") || label.includes("education") || label.includes("qualification"))) {
      return candidateData.highest_degree || "Bachelor's Degree";
    }

    // 27. Year of Graduation
    if (label.includes("graduation") || label.includes("graduating") || label.includes("year of grad") || label.includes("سنة التخرج")) {
      return candidateData.graduation_year || "2007";
    }

    // 28. Current Employer / Company
    if (label.includes("current company") || label.includes("current employer") || label.includes("الشركة الحالية")) {
      return candidateData.current_company || "Pace";
    }

    // 29. Current Job Title
    if (label.includes("job title") || label.includes("current title") || label.includes("المسمى الوظيفي")) {
      return candidateData.current_title || "Senior Architect & BIM Specialist";
    }

    // 30. Revit / BIM / CAD Experience
    if (label.includes("revit") || label.includes("ريفيت")) {
      return candidateData.revit_experience_years || "16";
    }
    if (label.includes("bim") || label.includes("بيم")) {
      return candidateData.bim_experience_years || "15";
    }
    if (label.includes("autocad") || label.includes("cad") || label.includes("أوتوكاد")) {
      return candidateData.autocad_experience_years || "19";
    }

    // 31. PMP Certification
    if (label.includes("pmp")) {
      return candidateData.pmp_certified || "Yes";
    }

    // 32. Notice Period / Availability
    if (label.includes("notice") || label.includes("availability") || label.includes("start date")) {
      return candidateData.notice_period || "1 Month";
    }

    // 33. Cover Letter / Summary / Bio
    if (label.includes("cover letter") || label.includes("summary") || label.includes("about yourself") || label.includes("bio")) {
      return candidateData.summary;
    }

    // 34. Visa Sponsorship
    if (label.includes("sponsor") || label.includes("visa") || label.includes("work authorization")) {
      return candidateData.common_answers?.sponsorship || "Yes";
    }

    return null;
  }

  // Executes form autofill using two-way matching (Label-Driven + Input-Driven)
  async function performAutoFill() {
    if (!candidateData) {
      if (typeof DEFAULT_CANDIDATE_PROFILE !== "undefined") {
        candidateData = Object.assign({}, DEFAULT_CANDIDATE_PROFILE);
      }
    }

    let filledCount = 0;
    const handledInputs = new Set();

    // Strategy 1: Label-driven search
    // Find every visible <label> on the page and match its target input
    const allLabels = document.querySelectorAll("label, .c-label, [data-qa='form-label']");
    allLabels.forEach((lbl) => {
      const labelText = (lbl.innerText || "").trim();
      if (!labelText || labelText.length < 2) return;

      // Find input associated with this label
      let targetInput = null;
      if (lbl.htmlFor) {
        targetInput = document.getElementById(lbl.htmlFor);
      }
      if (!targetInput) {
        targetInput = lbl.querySelector("input, textarea, select");
      }
      if (!targetInput) {
        // Look in parent container
        const parent = lbl.parentElement;
        if (parent) {
          targetInput = parent.querySelector("input:not([type='hidden']):not([type='submit']):not([type='file']), textarea, select");
        }
      }
      if (!targetInput && lbl.nextElementSibling) {
        if (["INPUT", "TEXTAREA", "SELECT"].includes(lbl.nextElementSibling.tagName)) {
          targetInput = lbl.nextElementSibling;
        } else {
          targetInput = lbl.nextElementSibling.querySelector("input, textarea, select");
        }
      }

      if (targetInput && !handledInputs.has(targetInput)) {
        // Don't overwrite if user already typed custom content
        if (!targetInput.value || targetInput.value.trim().length === 0 || targetInput.type === "select-one") {
          const answer = getAnswerForLabel(labelText, targetInput);
          if (answer !== null && answer !== undefined) {
            applyAnswerToElement(targetInput, answer);
            handledInputs.add(targetInput);
            filledCount++;
          }
        }
      }
    });

    // Strategy 2: Input-driven search (for all remaining unhandled inputs)
    const allInputs = document.querySelectorAll(
      "input:not([type='hidden']):not([type='submit']):not([type='file']):not([type='button']), textarea, select"
    );

    for (let i = 0; i < allInputs.length; i++) {
      const elem = allInputs[i];
      if (handledInputs.has(elem)) continue;

      if (elem.value && elem.value.trim().length > 0 && elem.type !== "select-one") {
        continue;
      }

      const exactLabel = getExactFieldLabel(elem);
      if (!exactLabel) continue;

      const answer = getAnswerForLabel(exactLabel, elem);
      if (answer !== null && answer !== undefined) {
        applyAnswerToElement(elem, answer);
        handledInputs.add(elem);
        filledCount++;
      }
    }

    // Strategy 3: Radio buttons (Yes / No questions)
    const radioGroups = document.querySelectorAll("input[type='radio']");
    radioGroups.forEach((radio) => {
      const label = (radio.parentElement ? radio.parentElement.innerText : "").toLowerCase();
      const val = (radio.value || "").toLowerCase();
      const questionText = (radio.closest(".c-question, .question, fieldset, .form-group, div")?.innerText || "").toLowerCase();

      // Check "No" for AECOM worked before or relatives
      if (
        (questionText.includes("worked with aecom") || questionText.includes("relation or family member")) &&
        (label.includes("no") || val === "no" || val === "false")
      ) {
        radio.click();
        filledCount++;
      }
      // Check "Yes" for positive legal qualifications
      else if (
        (questionText.includes("18") || questionText.includes("relocate") || questionText.includes("license")) &&
        (label.includes("yes") || val === "yes" || val === "true")
      ) {
        radio.click();
        filledCount++;
      }
    });

    if (filledCount > 0) {
      showToast(`⚡ تم تعبئة ${filledCount} حقول بنجاح عبر CV Servant!`, "success");
    } else {
      showToast("ℹ️ تم فحص الحقول. تأكد من ظهور استمارة التقديم على الشاشة.", "warning");
    }

    return { filled: filledCount };
  }

  // Applies an answer value to input, textarea, or select element
  function applyAnswerToElement(elem, value) {
    if (elem.tagName.toLowerCase() === "select") {
      let found = false;
      const targetStr = String(value).toLowerCase();
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
    } else {
      setNativeValue(elem, value);

      // Handle SmartRecruiters City or search dropdown overlay if one appears
      setTimeout(() => {
        try {
          const suggestions = document.querySelectorAll(
            "[role='listbox'] [role='option'], .select-options li, .suggestions li, [data-qa='select-option'], .c-select__option"
          );
          if (suggestions.length > 0) {
            const targetLower = String(value).toLowerCase();
            for (let opt of suggestions) {
              if (opt.innerText && opt.innerText.toLowerCase().includes(targetLower)) {
                opt.click();
                break;
              }
            }
          }
        } catch (e) {}
      }, 80);
    }
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

  // Floating widget injection (STRICTLY ON TOP WINDOW - NEVER IN IFRAMES)
  function checkAndInjectFloatingWidget() {
    // PREVENT DUPLICATES: Only top window gets floating widget!
    if (window.self !== window.top) {
      return;
    }

    if (isFloatingWidgetInjected || !isJobPage()) return;
    isFloatingWidgetInjected = true;

    // Remove any legacy instance
    const old = document.getElementById("cv-servant-floating-panel");
    if (old) old.remove();

    const widget = document.createElement("div");
    widget.id = "cv-servant-floating-panel";
    widget.innerHTML = `
      <div class="cvs-floating-box">
        <div class="cvs-floating-header">
          <div class="cvs-floating-title">
            <span class="cvs-dot"></span>
            <b>CV Servant</b>
          </div>
          <button id="cvs-minimize-btn" title="إخفاء الزر العائم">✕</button>
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
      // Minimize to small button or remove
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
