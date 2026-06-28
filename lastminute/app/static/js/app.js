// ---------------------------------------------------------------
// Live countdown timers
// ---------------------------------------------------------------
function formatRemaining(ms) {
  if (ms <= 0) return "OVERDUE";
  const totalMin = Math.floor(ms / 60000);
  const days = Math.floor(totalMin / 1440);
  const hours = Math.floor((totalMin % 1440) / 60);
  const mins = totalMin % 60;
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}

function tickCountdowns() {
  document.querySelectorAll(".countdown[data-deadline]").forEach((el) => {
    const deadline = new Date(el.dataset.deadline + "Z");
    const valueEl = el.querySelector(".countdown-value");
    if (!valueEl) return;
    const remaining = deadline.getTime() - Date.now();
    valueEl.textContent = formatRemaining(remaining);
  });
}
tickCountdowns();
setInterval(tickCountdowns, 30000);

// ---------------------------------------------------------------
// Voice capture widget (Web Speech API)
// ---------------------------------------------------------------
(function setupVoiceWidget() {
  const fab = document.getElementById("voice-fab");
  const panel = document.getElementById("voice-panel");
  const transcriptEl = document.getElementById("voice-transcript");
  const resultEl = document.getElementById("voice-result");
  if (!fab) return;

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    fab.addEventListener("click", () => {
      panel.classList.remove("hidden");
      transcriptEl.textContent = "Voice capture isn't supported in this browser. Try Chrome.";
    });
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = "en-US";
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;

  let listening = false;

  fab.addEventListener("click", () => {
    if (listening) {
      recognition.stop();
      return;
    }
    panel.classList.remove("hidden");
    resultEl.textContent = "";
    transcriptEl.textContent = "Listening…";
    fab.classList.add("recording");
    listening = true;
    try {
      recognition.start();
    } catch (err) {
      listening = false;
      fab.classList.remove("recording");
    }
  });

  recognition.addEventListener("result", (event) => {
    let text = "";
    for (let i = 0; i < event.results.length; i++) {
      text += event.results[i][0].transcript;
    }
    transcriptEl.textContent = text;
  });

  recognition.addEventListener("end", async () => {
    listening = false;
    fab.classList.remove("recording");
    const transcript = transcriptEl.textContent.trim();
    if (!transcript || transcript.startsWith("Voice capture") || transcript === "Listening…") return;

    resultEl.textContent = "Adding task…";
    try {
      const res = await fetch("/api/voice-task", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript }),
      });
      const data = await res.json();
      if (data.ok) {
        resultEl.textContent = data.spoken_confirmation;
        speak(data.spoken_confirmation);
        setTimeout(() => window.location.reload(), 1400);
      } else {
        resultEl.textContent = data.error || "Could not parse that.";
      }
    } catch (err) {
      resultEl.textContent = "Network error — task not saved.";
    }
  });

  recognition.addEventListener("error", () => {
    listening = false;
    fab.classList.remove("recording");
    transcriptEl.textContent = "Didn't catch that — try again.";
  });

  function speak(text) {
    if (!window.speechSynthesis) return;
    const utter = new SpeechSynthesisUtterance(text);
    utter.rate = 1.05;
    window.speechSynthesis.speak(utter);
  }
})();
