/**
 * Master Candidate Profile for Eng. Mustafa Mahmoud Shawky.
 * Embedded directly inside the Chrome Extension to guarantee 100% availability
 * with zero latency, even before local desktop app handshake.
 */

const DEFAULT_CANDIDATE_PROFILE = {
  first_name: "Mustafa",
  middle_name: "Mahmoud",
  last_name: "Shawky",
  full_name: "Mustafa Mahmoud Shawky",
  headline: "Senior Architect & BIM Specialist / BIM Manager",
  email: "arch.mustafa.mahmoud.2007@gmail.com",
  phone: "+965 9919 1358",
  phone_country_code: "+965",
  phone_national: "99191358",
  address: "Sabah Elsalem",
  city: "Sabah Elsalem",
  country: "Kuwait",
  nationality: "Egyptian",
  residency: "Kuwait (Transferable Visa)",
  postal_code: "44000",
  linkedin: "https://www.linkedin.com/in/mostafamahmoud-architect",
  portfolio: "https://mustafash1986.github.io/mustafa-portfolio1/",
  github: "https://github.com/mustafash1986",
  current_company: "Pace",
  current_title: "Senior Architect & BIM Specialist",
  total_experience_years: 19,
  revit_experience_years: 16,
  bim_experience_years: 15,
  autocad_experience_years: 19,
  navisworks_experience_years: 12,
  pmp_certified: "Yes",
  pmp_license: "PMP #3010938 (PMI - Valid through May 2027)",
  revit_certified: "Yes",
  revit_license: "Autodesk Certified Professional #00424122",
  kse_registered: "Yes (Registered Professional Architect, Kuwait Society of Engineers)",
  notice_period: "1 Month",
  notice_period_days: 30,
  willing_to_relocate: "Yes",
  work_mode: "Hybrid / Onsite / Remote",
  summary: "Accomplished Architectural Engineer and BIM Manager with over 19 years of distinguished experience in architectural working drawings, comprehensive Revit modeling, onsite construction investigations, and advanced BIM process implementation. Proven track record leading multidisciplinary teams on large-scale institutional, healthcare, commercial, and administrative projects across Kuwait and the Gulf region.",
  education: {
    degree: "Bachelor of Architecture (B.Arch.)",
    institution: "Minia University, Faculty of Engineering",
    country: "Egypt",
    graduation_year: 2007,
    grade: "Graduated with Excellency"
  },
  languages: [
    { name: "Arabic", level: "Native / Mother Tongue" },
    { name: "English", level: "Professional Working Proficiency (BUSUU B2 Certified)" }
  ],
  common_answers: {
    sponsorship: "Will require work visa sponsorship for overseas positions (Transferable residency in Kuwait).",
    work_authorization: "Authorized to work in Kuwait (Transferable Visa). Require sponsorship for international roles.",
    relocate: "Yes, fully willing and prepared to relocate internationally.",
    salary_expectation: "Negotiable based on market benchmark, package, and cost of living.",
    commence_date: "Within 30 days of offer acceptance (Standard notice period).",
    criminal_record: "No",
    over_18: "Yes",
    drivers_license: "Yes (Valid driving license)"
  }
};

// Expose globally for both Service Worker and Window contexts
if (typeof self !== "undefined") {
  self.DEFAULT_CANDIDATE_PROFILE = DEFAULT_CANDIDATE_PROFILE;
}
if (typeof window !== "undefined") {
  window.DEFAULT_CANDIDATE_PROFILE = DEFAULT_CANDIDATE_PROFILE;
}
