/**
 * CV Servant - Chrome Extension Background Service Worker
 * Manages communication between web pages, extension popup, and local CV Servant REST API.
 */

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

// Fetch candidate profile from local server with local storage fallback
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
    console.warn("CV Servant local server not reachable, trying cached profile:", err);
  }

  // Fallback to cached profile if server isn't running
  const storage = await chrome.storage.local.get(["cachedProfile"]);
  if (storage.cachedProfile) {
    return { success: true, profile: storage.cachedProfile, source: "cache" };
  }

  return { success: false, error: "CV Servant local server not reachable. Please start CV Servant desktop application." };
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
