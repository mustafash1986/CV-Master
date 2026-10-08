/**
 * CV Servant - Chrome Extension Background Service Worker
 * Manages communication between web pages, extension popup, and local CV Servant REST API.
 */

try {
  importScripts("../common/candidate_profile.js");
} catch (e) {
  console.warn("Could not import candidate_profile.js in service worker:", e);
}

const LOCAL_BRIDGE_URL = "http://127.0.0.1:5822";

// Check health of local CV Servant server
async function checkBridgeStatus() {
  try {
    const res = await fetch(`${LOCAL_BRIDGE_URL}/api/status`, {
      method: "GET",
      cache: "no-store"
    });
    if (res.ok) {
      const data = await res.json();
      return { online: true, data };
    }
  } catch (err) {
    // Local server not running or unreachable
  }
  return { online: false };
}

// Fetch candidate profile with live server priority, local cache fallback, and embedded profile default
async function getCandidateProfile() {
  try {
    const res = await fetch(`${LOCAL_BRIDGE_URL}/api/profile`, {
      method: "GET",
      cache: "no-store"
    });
    if (res.ok) {
      const json = await res.json();
      if (json.candidate) {
        // Cache profile in chrome.storage for offline resilience
        await chrome.storage.local.set({ cachedProfile: json.candidate, lastSync: Date.now() });
        return { success: true, profile: json.candidate, source: "live_server" };
      }
    }
  } catch (err) {
    // Local server offline or busy
  }

  // Fallback 1: Cached profile in chrome.storage
  try {
    const storage = await chrome.storage.local.get(["cachedProfile"]);
    if (storage.cachedProfile) {
      return { success: true, profile: storage.cachedProfile, source: "cache" };
    }
  } catch (e) {
    // Storage error
  }

  // Fallback 2: Embedded default profile
  const fallback = typeof DEFAULT_CANDIDATE_PROFILE !== "undefined" ? DEFAULT_CANDIDATE_PROFILE : null;
  return {
    success: true,
    profile: fallback,
    source: "embedded_default"
  };
}

// Send tracked application to CV Servant local server
async function trackJobApplication(jobData) {
  try {
    const res = await fetch(`${LOCAL_BRIDGE_URL}/api/track_application`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(jobData)
    });

    if (res.ok) {
      const result = await res.json();
      return { success: true, data: result };
    } else {
      const errText = await res.text();
      return { success: false, error: errText };
    }
  } catch (err) {
    // If desktop app is closed, save to pending queue in chrome storage
    const storage = await chrome.storage.local.get(["pendingSyncJobs"]);
    const pending = storage.pendingSyncJobs || [];
    pending.push({ ...jobData, queuedAt: Date.now() });
    await chrome.storage.local.set({ pendingSyncJobs: pending });

    return {
      success: true,
      queued: true,
      message: "تم حفظ الوظيفة في قائمة الانتظار (سيتم ترحيلها عند تشغيل البرنامج)"
    };
  }
}

// Check if current URL/job is already tracked
async function checkJobTracked(url, title, company) {
  try {
    const params = new URLSearchParams({
      url: url || "",
      title: title || "",
      company: company || ""
    });
    const res = await fetch(`${LOCAL_BRIDGE_URL}/api/check_job?${params.toString()}`);
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    // Ignore error
  }
  return { is_tracked: false };
}

// Message Listener
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  const { action, payload } = request;

  if (action === "CHECK_STATUS") {
    checkBridgeStatus().then(sendResponse);
    return true; // Keep channel open for async response
  }

  if (action === "GET_PROFILE") {
    getCandidateProfile().then(sendResponse);
    return true;
  }

  if (action === "TRACK_APPLICATION") {
    trackJobApplication(payload).then(sendResponse);
    return true;
  }

  if (action === "CHECK_JOB") {
    const { url, title, company } = payload || {};
    checkJobTracked(url, title, company).then(sendResponse);
    return true;
  }
});
