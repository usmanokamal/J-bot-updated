// static/chatbot.js
(function () {
  let currentController = null; // Store the AbortController
  let sessionId = generateSessionId(); // Generate session ID
  let currentView = "web"; // Track current view state

  function generateSessionId() {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(
      /[xy]/g,
      function (c) {
        const r = (Math.random() * 16) | 0,
          v = c === "x" ? r : (r & 0x3) | 0x8;
        return v.toString(16);
      }
    );
  }

  function appendMessage(text, sender) {
    let bubble = $("<div>").addClass("chat-bubble").addClass(sender);

    if (sender === "bot") {
      const logo = $("<img>")
        .attr("src", "/static/assets/Jazz-Company-logo-.png")
        .attr("alt", "Jazz Logo")
        .css({ width: "24px", height: "24px", marginRight: "10px" });

      let formattedText = text
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\n/g, "<br>");

      const messageContent = $("<span>").html(formattedText);
      bubble.append(logo).append(messageContent);
    } else {
      bubble.text(text);
    }

    $("#chat-box").append(bubble);
    $("#chat-box").scrollTop($("#chat-box")[0].scrollHeight);
    return bubble;
  }

  function startTypingAnimation() {
    $("#robotArea").addClass("robot-thinking");
  }

  function stopTypingAnimation() {
    $("#robotArea").removeClass("robot-thinking");
  }

  function disableUI() {
    $("#send-btn").prop("disabled", true);
    $("#user-input").prop("disabled", true);
    $("#quick-replies button").prop("disabled", true);
    $("#stop-btn").show();
    startTypingAnimation();
  }

  function enableUI() {
    $("#send-btn").prop("disabled", false);
    $("#user-input").prop("disabled", false);
    $("#quick-replies button").prop("disabled", false);
    $("#stop-btn").hide();
    $("#user-input").focus();
    stopTypingAnimation();
  }

  // Typewriter effect for bot replies, with logging
  function typewriterEffect(fullText, element, doneCallback) {
    let i = 0;
    function type() {
      let partial = fullText.slice(0, i);
      let formatted = partial
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\n/g, "<br>");
      element.html(formatted);
      $("#chat-box").scrollTop($("#chat-box")[0].scrollHeight);

      if (i < fullText.length) {
        i++;
        setTimeout(type, 10); // 25ms for visible debugging, can reduce later
      } else if (doneCallback) {
        doneCallback();
      }
    }
    type();
  }

  // Function to send a message
  function sendMessage() {
    console.log("sendMessage called");
    const input = $("#user-input");
    const userMsg = input.val().trim();
    if (!userMsg) return;

    appendMessage(userMsg, "user");
    input.val("");
    disableUI();

    const bubble = $("<div>").addClass("chat-bubble").addClass("bot");
    const logo = $("<img>")
      .attr("src", "/static/assets/Jazz-Company-logo-.png")
      .attr("alt", "Jazz Logo")
      .css({ width: "24px", height: "24px", marginRight: "10px" });

    const messageContent = $("<span>");
    bubble.append(logo).append(messageContent);
    $("#chat-box").append(bubble);
    $("#chat-box").scrollTop($("#chat-box")[0].scrollHeight);

    const language = $("#language-select").val();

    currentController = new AbortController();
    const signal = currentController.signal;

    console.log("Sending fetch to /chat...");
    fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: userMsg,
        language: language,
        session_id: sessionId,
      }),
      signal: signal,
    })
      .then((response) => {
        console.log("Fetch response received");
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json(); // Expect JSON
      })
      .then((data) => {
        console.log("Data after JSON:", data);
        if (data && data.response) {
          console.log("Calling typewriterEffect!");
          typewriterEffect(data.response, messageContent, enableUI);
        } else {
          messageContent.html("<em>No response from bot.</em>");
          enableUI();
        }
      })
      .catch((error) => {
        console.log("Error in fetch:", error);
        bubble.remove();
        appendMessage("Error: " + error.message, "bot");
        enableUI();
      });
  }

  function stopResponse() {
    if (currentController) {
      currentController.abort();
      currentController = null;
    }
  }

  function sendQuickReply(message) {
    if ($("#quick-replies button").prop("disabled")) {
      return;
    }
    $("#user-input").val(message);
    sendMessage();
  }

  function updateQuickReplies() {
    const quickReplies = [
      "Offers",
      "Data Offers",
      "Packages",
      "B2C",
      "Digital",
      "Jazz Rox",
      "Support",
    ];
    $("#quick-replies").empty();
    quickReplies.forEach((reply) => {
      const button = $("<button>")
        .text(reply)
        .click(() => sendQuickReply(reply));
      $("#quick-replies").append(button);
    });
  }

  function toggleView() {
    const container = document.querySelector(".container");
    const webIcon = document.getElementById("web-icon");
    const mobileIcon = document.getElementById("mobile-icon");

    if (currentView === "web") {
      container.classList.remove("web-view");
      container.classList.add("mobile-view");
      webIcon.style.display = "none";
      mobileIcon.style.display = "block";
      currentView = "mobile";
    } else {
      container.classList.remove("mobile-view");
      container.classList.add("web-view");
      webIcon.style.display = "block";
      mobileIcon.style.display = "none";
      currentView = "web";
    }
  }

  // Global functions
  window.sendMessage = sendMessage;
  window.stopResponse = stopResponse;
  window.sendQuickReply = sendQuickReply;
  window.updateQuickReplies = updateQuickReplies;
  window.toggleView = toggleView;

  $(document).ready(function () {
    console.log("Document ready, chatbot.js loaded!");
    $("#stop-btn").hide();
    updateQuickReplies();

    // Initialize view state
    $(".container").addClass("web-view");
    currentView = "web";
    $("#web-icon").show();
    $("#mobile-icon").hide();

    // Add initial bot message
    setTimeout(() => {
      appendMessage(
        "Hello! I'm your Jazz Support Bot powered by AI. How can I help you today?",
        "bot"
      );
    }, 500);

    // Event listeners
    $("#user-input").on("keypress", function (e) {
      if (e.key === "Enter" && !$("#user-input").prop("disabled")) {
        sendMessage();
      }
    });
    $("#send-btn").click(sendMessage);
    $("#stop-btn").click(stopResponse);
    // No need for $("#view-toggle-btn").click(toggleView); since onclick is used in HTML
  });
})();
