/**
 * CV Servant - Smart Job Auto-Fill & Tracker Content Script
 * High-intelligence form matching for Workday, Taleo, Greenhouse, Lever, LinkedIn,
 * Seek, Indeed, and modern ATS job application portals.
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

    // Inject floating widget if this looks like a job page
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
      "linkedin.com", "indeed.com", "seek.com.au", "seek.co.nz",
      "myworkdayjobs.com", "workday.com", "greenhouse.io", "lever.co",
      "smartrecruiters.com", "workable.com", "bamboohr.com", "taleo.net",
      "icims.com", "ashbyhq.com", "jobvite.com"
    ];

    const hasDomain = jobDomains.some(d => hostname.includes(d));
    const hasJobWords = url.includes("job") || url.includes("career") || url.includes("apply") || url.includes("vacancy") || url.includes("position");
    const hasFormWords = text.includes("apply") || text.includes("resume") || text.includes("cv") || text.includes("first name") || text.includes("application");

    return hasDomain || hasJobWords || hasFormWords;
  }

  // Extracts current Job Title, Company Name, Location, and URL from the DOM
  function extractPageJobInfo() {
    const url = window.location.href;
    let title = "";
    let company = "";
    let location = "";

    // 1. Workday specific
    const wdTitle = document.querySelector("[data-automation-id='jobPostingHeader'], [data-automation-id='jobTitle']");
    if (wdTitle) title = wdTitle.innerText.trim();

    const wdComp = document.querySelector("[data-automation-id='legalEntityName'], [data-automation-id='company']");
    if (wdComp) company = wdComp.innerText.trim();

    // 2. LinkedIn specific
    if (window.location.hostname.includes("linkedin.com")) {
      const titleElem = document.querySelector(".jobs-unified-top-card__job-title, .job-details-jobs-unified-top-card__job-title, h1.t-24, h1");
      if (titleElem) title = titleElem.innerText.trim();

      const compElem = document.querySelector(".jobs-unified-top-card__company-name, .job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__subtitle-primary a");
      if (compElem) company = compElem.innerText.trim();

      const locElem = document.querySelector(".jobs-unified-top-card__bullet, .job-details-jobs-unified-top-card__bullet, .jobs-unified-top-card__workplace-type");
      if (locElem) location = locElem.innerText.trim();
    }

    // 3. General fallbacks
    if (!title) {
      const h1 = document.querySelector("h1, .job-title, [data-qa='job-title']");
      if (h1) title = h1.innerText.trim();
    }

    if (!company) {
      const compNode = document.querySelector(".company-name, .employer, [data-automation='advertiser-name'], [data-qa='company-name']");
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
      job_title: title || "Architect & BIM Role",
      company_name: company || "Direct Employer",
      country: location || "Australia",
      city: location || "",
      job_url: url,
      source: window.location.hostname.replace("www.", "").split(".")[0].toUpperCase()
    };
  }

  // Set input value cleanly with React / Vue / Angular / Workday native setter override
  function setNativeValue(element, value) {
    if (!element || value === undefined || value === null) return;

    const valueToSet = String(value);

    try {
      element.focus();
    } catch (e) {}

    // Call native prototype setter to bypass React 16+ / Workday synthetic event suppression
    const prototype = Object.getPrototypeOf(element);
    const nativeDescriptor = Object.getOwnPropertyDescriptor(prototype, "value");
    if (nativeDescriptor && nativeDescriptor.set) {
      nativeDescriptor.set.call(element, valueToSet);
    } else {
      element.value = valueToSet;
    }

    // Dispatch full cycle of synthetic events for frameworks with character limits (e.g. 0/200)
    element.dispatchEvent(new Event("input", { bubbles: true, cancelable: true }));
    element.dispatchEvent(new Event("change", { bubbles: true, cancelable: true }));
    element.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, cancelable: true, key: "a" }));
    element.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, cancelable: true, key: "a" }));
    element.dispatchEvent(new Event("blur", { bubbles: true, cancelable: true }));

    // Visual highlight feedback
    element.style.transition = "background-color 0.4s ease";
    element.style.backgroundColor = "rgba(16, 185, 129, 0.18)";
  }

  // Deep inspection: climbs up ancestor elements up to 8 levels to extract full context,
  // Workday automation IDs, labels, headings, and field legends
  function getFieldContextText(field) {
    let parts = [];

    // 1. Direct attributes of the field
    parts.push(field.id || "");
    parts.push(field.name || "");
    parts.push(field.placeholder || "");
    parts.push(field.getAttribute("aria-label") || "");
    parts.push(field.getAttribute("autocomplete") || "");
    parts.push(field.getAttribute("data-automation-id") || "");
    parts.push(field.getAttribute("data-qa") || "");
    parts.push(field.getAttribute("data-testid") || "");
    parts.push(field.getAttribute("title") || "");

    // 2. aria-labelledby and aria-describedby
    const labelledBy = field.getAttribute("aria-labelledby");
    if (labelledBy) {
      labelledBy.split(/\s+/).forEach((lblId) => {
        const el = document.getElementById(lblId);
        if (el) parts.push(el.innerText || "");
      });
    }

    // 3. Associated <label for="id">
    if (field.id) {
      try {
        const lbl = document.querySelector(`label[for="${CSS.escape(field.id)}"]`);
        if (lbl) parts.push(lbl.innerText || "");
      } catch (e) {}
    }

    // 4. Ancestor climbing: Check up to 8 parent levels
    // This solves the Workday / nested container problem where the label is in an outer wrapper
    let curr = field.parentElement;
    let depth = 0;
    while (curr && depth < 8 && curr !== document.body) {
      // Check data-automation-id on container (e.g. data-automation-id="formField-legalNameSection_firstName")
      const autoId = curr.getAttribute("data-automation-id");
      if (autoId) parts.push(autoId);

      const qaId = curr.getAttribute("data-qa") || curr.getAttribute("data-testid");
      if (qaId) parts.push(qaId);

      // Check class name tokens
      if (curr.className && typeof curr.className === "string") {
        parts.push(curr.className);
      }

      // Check for labels or headings inside this container
      const labels = curr.querySelectorAll("label, [data-automation-id='formLabel'], .label, h1, h2, h3, h4, h5, legend, p, span.title");
      labels.forEach((lbl) => {
        const txt = (lbl.innerText || "").trim();
        // Ignore character counter texts like "0/200"
        if (txt && !txt.match(/^\d+\s*\/\s*\d+$/) && txt.length < 150) {
          parts.push(txt);
        }
      });

      // If we hit a known major form row / field container in Workday, collect its immediate siblings then stop
      if (autoId && (autoId.includes("formField") || autoId.includes("formGroup"))) {
        break;
      }
      if (curr.classList.contains("form-group") || curr.classList.contains("field") || curr.tagName === "TR") {
        break;
      }

      curr = curr.parentElement;
      depth++;
    }

    // 5. Preceding sibling elements (common in table or grid layouts)
    let prev = field.previousElementSibling;
    let sibCount = 0;
    while (prev && sibCount < 3) {
      const pt = (prev.innerText || "").trim();
      if (pt && !pt.match(/^\d+\s*\/\s*\d+$/)) {
        parts.push(pt);
      }
      prev = prev.previousElementSibling;
      sibCount++;
    }

    return parts.join(" ").toLowerCase();
  }

  // Matches a form field to candidate data based on its attributes and labels
  function matchFieldDescriptor(field) {
    const fullStr = getFieldContextText(field);

    // 1. First Name (English + Arabic + Workday data-automation-id)
    if (
      fullStr.includes("first_name") ||
      fullStr.includes("firstname") ||
      fullStr.includes("first name") ||
      fullStr.includes("given name") ||
      fullStr.includes("given_name") ||
      fullStr.includes("givenname") ||
      fullStr.includes("fname") ||
      fullStr.includes("legalnamesection_firstname") ||
      fullStr.includes("الاسم الأول") ||
      fullStr.includes("اسمك الأول")
    ) {
      return "first_name";
    }

    // 2. Last Name / Surname (English + Arabic + Workday)
    if (
      fullStr.includes("last_name") ||
      fullStr.includes("lastname") ||
      fullStr.includes("last name") ||
      fullStr.includes("surname") ||
      fullStr.includes("family_name") ||
      fullStr.includes("family name") ||
      fullStr.includes("familyname") ||
      fullStr.includes("lname") ||
      fullStr.includes("legalnamesection_lastname") ||
      fullStr.includes("اسم العائلة") ||
      fullStr.includes("الاسم الأخير") ||
      fullStr.includes("اللقب")
    ) {
      return "last_name";
    }

    // 3. Middle Name
    if (
      fullStr.includes("middle_name") ||
      fullStr.includes("middlename") ||
      fullStr.includes("middle name") ||
      fullStr.includes("legalnamesection_middlename") ||
      fullStr.includes("الاسم الأوسط")
    ) {
      return "middle_name";
    }

    // 4. Full Name (only if not distinct first/last)
    if (
      fullStr.includes("full_name") ||
      fullStr.includes("fullname") ||
      fullStr.includes("full name") ||
      fullStr.includes("candidate name") ||
      fullStr.includes("applicant name") ||
      fullStr.includes("your name") ||
      fullStr.includes("الاسم بالكامل") ||
      fullStr.includes("الاسم الكامل") ||
      fullStr.includes("اسم المرشح")
    ) {
      return "full_name";
    }

    // 5. Email (English + Arabic + Workday)
    if (
      fullStr.includes("email") ||
      fullStr.includes("e-mail") ||
      field.type === "email" ||
      fullStr.includes("البريد") ||
      fullStr.includes("الإيميل")
    ) {
      return "email";
    }

    // 6. Phone Country / Dial Code
    if (
      fullStr.includes("country code") ||
      fullStr.includes("dial code") ||
      fullStr.includes("country dial") ||
      fullStr.includes("كود الدولة") ||
      fullStr.includes("رمز الدولة")
    ) {
      return "phone_country_code";
    }

    // 7. Phone Device Type (Workday specific dropdown)
    if (
      fullStr.includes("device type") ||
      fullStr.includes("phone device") ||
      fullStr.includes("phone type") ||
      fullStr.includes("نوع الهاتف")
    ) {
      return "phone_device_type";
    }

    // 8. Phone Number (English + Arabic + Workday)
    if (
      fullStr.includes("phone") ||
      fullStr.includes("mobile") ||
      fullStr.includes("cell") ||
      fullStr.includes("tel") ||
      fullStr.includes("contact number") ||
      field.type === "tel" ||
      fullStr.includes("phone-number") ||
      fullStr.includes("الهاتف") ||
      fullStr.includes("الجوال") ||
      fullStr.includes("الموبايل") ||
      fullStr.includes("رقم الاتصال")
    ) {
      return "phone";
    }

    // 9. Links & Portfolios
    if (fullStr.includes("linkedin") || fullStr.includes("لينكد")) {
      return "linkedin";
    }
    if (
      fullStr.includes("portfolio") ||
      fullStr.includes("website") ||
      fullStr.includes("personal site") ||
      fullStr.includes("web link") ||
      fullStr.includes("بورتفوليو") ||
      fullStr.includes("معرض الأعمال") ||
      fullStr.includes("موقعك")
    ) {
      return "portfolio";
    }
    if (fullStr.includes("github")) {
      return "github";
    }

    // 10. Address Line 1 / Street (Workday: addressSection_addressLine1)
    if (
      fullStr.includes("addressline1") ||
      fullStr.includes("address line 1") ||
      fullStr.includes("address line") ||
      fullStr.includes("street") ||
      fullStr.includes("street address") ||
      fullStr.includes("address_1") ||
      (fullStr.includes("address") && !fullStr.includes("email") && !fullStr.includes("ip")) ||
      fullStr.includes("العنوان") ||
      fullStr.includes("الشارع")
    ) {
      return "address";
    }

    // 11. City / Suburb (Workday: addressSection_city)
    if (
      fullStr.includes("city") ||
      fullStr.includes("town") ||
      fullStr.includes("suburb") ||
      fullStr.includes("addresssection_city") ||
      fullStr.includes("المدينة") ||
      fullStr.includes("البلدة")
    ) {
      return "city";
    }

    // 12. State / Region / Province
    if (
      fullStr.includes("state") ||
      fullStr.includes("province") ||
      fullStr.includes("region") ||
      fullStr.includes("addresssection_countryregion") ||
      fullStr.includes("المنطقة") ||
      fullStr.includes("المحافظة") ||
      fullStr.includes("الولاية")
    ) {
      return "city";
    }

    // 13. Postal Code / Zip (Workday: addressSection_postalCode)
    if (
      fullStr.includes("postal") ||
      fullStr.includes("zip") ||
      fullStr.includes("postcode") ||
      fullStr.includes("postalcode") ||
      fullStr.includes("addresssection_postalcode") ||
      fullStr.includes("الرمز البريدي")
    ) {
      return "postal_code";
    }

    // 14. Country / Nationality
    if (
      fullStr.includes("nationality") ||
      fullStr.includes("citizenship") ||
      fullStr.includes("الجنسية")
    ) {
      return "nationality";
    }
    if (
      fullStr.includes("country") &&
      !fullStr.includes("code") &&
      !fullStr.includes("dial") ||
      fullStr.includes("الدولة") ||
      fullStr.includes("البلد")
    ) {
      return "country";
    }

    // 15. How Did You Hear About Us? (Workday source prompt)
    if (
      fullStr.includes("hear about") ||
      fullStr.includes("how did you hear") ||
      fullStr.includes("source") ||
      fullStr.includes("referral") ||
      fullStr.includes("من أين سمعت")
    ) {
      return "source_referral";
    }

    // 16. Current Company / Title
    if (
      fullStr.includes("current company") ||
      fullStr.includes("current employer") ||
      fullStr.includes("company name") ||
      fullStr.includes("organization") ||
      fullStr.includes("الشركة الحالية") ||
      fullStr.includes("جهة العمل")
    ) {
      return "current_company";
    }
    if (
      fullStr.includes("job title") ||
      fullStr.includes("current title") ||
      fullStr.includes("current role") ||
      fullStr.includes("designation") ||
      fullStr.includes("المسمى الوظيفي")
    ) {
      return "current_title";
    }

    // 17. Experience & Technical Skills
    if (fullStr.includes("revit") || fullStr.includes("ريفيت")) {
      return "revit_experience_years";
    }
    if (fullStr.includes("bim") || fullStr.includes("بيم")) {
      return "bim_experience_years";
    }
    if (fullStr.includes("autocad") || fullStr.includes("cad") || fullStr.includes("أوتوكاد")) {
      return "autocad_experience_years";
    }
    if (
      (fullStr.includes("experience") && (fullStr.includes("year") || fullStr.includes("total"))) ||
      fullStr.includes("سنوات الخبرة")
    ) {
      return "total_experience_years";
    }

    // 18. Certifications (PMP)
    if (fullStr.includes("pmp")) {
      return "pmp_certified";
    }

    // 19. Notice period & Availability
    if (
      fullStr.includes("notice") ||
      fullStr.includes("availability") ||
      fullStr.includes("start date") ||
      fullStr.includes("commence") ||
      fullStr.includes("فترة الإشعار") ||
      fullStr.includes("تاريخ البدء")
    ) {
      return "notice_period";
    }

    // 20. Summary / Cover letter / Notes
    if (
      fullStr.includes("cover letter") ||
      fullStr.includes("cover_letter") ||
      fullStr.includes("خطاب التقديم") ||
      fullStr.includes("رسالة التغطية")
    ) {
      return "cover_letter";
    }
    if (
      fullStr.includes("summary") ||
      fullStr.includes("about yourself") ||
      fullStr.includes("bio") ||
      fullStr.includes("additional info") ||
      fullStr.includes("why should we hire you") ||
      fullStr.includes("نبذة") ||
      fullStr.includes("ملخص")
    ) {
      return "summary";
    }

    // 21. Salary
    if (
      fullStr.includes("salary") ||
      fullStr.includes("compensation") ||
      fullStr.includes("remuneration") ||
      fullStr.includes("expectation") ||
      fullStr.includes("الراتب")
    ) {
      return "salary_expectation";
    }

    // 22. Sponsorship / Visa
    if (
      fullStr.includes("sponsor") ||
      fullStr.includes("visa") ||
      fullStr.includes("work rights") ||
      fullStr.includes("كفالة") ||
      fullStr.includes("فيزا") ||
      fullStr.includes("إقامة")
    ) {
      return "sponsorship";
    }

    return null;
  }

  // Executes form autofill across inputs, textareas, and selects
  async function performAutoFill() {
    // Ensure candidate data is loaded
    if (!candidateData) {
      if (typeof DEFAULT_CANDIDATE_PROFILE !== "undefined") {
        candidateData = Object.assign({}, DEFAULT_CANDIDATE_PROFILE);
      }
    }

    if (!candidateData) {
      showToast("❌ بيانات المرشح غير متوفرة.", "error");
      return { filled: 0 };
    }

    let filledCount = 0;

    // Selector covers all standard inputs, Workday search inputs, textareas, selects, and contenteditable
    const inputs = document.querySelectorAll(
      "input:not([type='hidden']):not([type='submit']):not([type='file']):not([type='button']), textarea, select"
    );

    console.log(`[CV Servant AutoFill] Found ${inputs.length} candidate inputs on page.`);

    inputs.forEach((elem, idx) => {
      // Don't overwrite if user already typed non-empty text (unless it's just spaces)
      if (elem.value && elem.value.trim().length > 0 && elem.type !== "select-one") {
        return;
      }

      const matchType = matchFieldDescriptor(elem);
      console.log(`[CV Servant AutoFill] Input #${idx} (${elem.id || elem.name || 'unnamed'}): matchType = ${matchType}`);

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
        case "phone_device_type":
          valueToFill = "Mobile";
          break;
        case "linkedin":
          valueToFill = candidateData.linkedin;
          break;
        case "portfolio":
          valueToFill = candidateData.portfolio;
          break;
        case "github":
          valueToFill = candidateData.github;
          break;
        case "current_company":
          valueToFill = candidateData.current_company;
          break;
        case "current_title":
          valueToFill = candidateData.current_title;
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
        case "source_referral":
          valueToFill = "LinkedIn";
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

    if (filledCount > 0) {
      showToast(`⚡ تم تعبئة ${filledCount} حقلاً بنجاح عبر CV Servant!`, "success");
    } else {
      showToast("ℹ️ تم فحص الحقول على الصفحة. يرجى التأكد من وقوفك على صفحة استمارة التقديم.", "warning");
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
        notes: "تم التقديم وتعبئة النموذج عبر إضافة المتصفح CV Servant"
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
