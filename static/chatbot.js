// static/chatbot.js
(function () {
  let currentController = null;
  let sessionId = generateSessionId();
  let currentView = "web";
  let currentMessageElement = null; // Track current message being typed

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

  function formatText(text) {
    return text
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(
        /^### (.*$)/gm,
        "<h3 style='font-size: 1.2em; font-weight: bold; margin: 10px 0 5px 0;'>$1</h3>"
      )
      .replace(
        /^## (.*$)/gm,
        "<h2 style='font-size: 1.4em; font-weight: bold; margin: 12px 0 6px 0;'>$1</h2>"
      )
      .replace(
        /^# (.*$)/gm,
        "<h1 style='font-size: 1.6em; font-weight: bold; margin: 15px 0 8px 0;'>$1</h1>"
      )
      .replace(/\n/g, "<br>");
  }

  function createBotMessage() {
    const bubble = $("<div>").addClass("chat-bubble").addClass("bot");
    const logo = $("<img>")
      .attr("src", "/static/assets/Jazz-Company-logo-.png")
      .attr("alt", "Jazz Logo")
      .css({ width: "24px", height: "24px", marginRight: "10px" });

    const messageContent = $("<span>");
    bubble.append(logo).append(messageContent);
    $("#chat-box").append(bubble);
    $("#chat-box").scrollTop($("#chat-box")[0].scrollHeight);

    return messageContent;
  }

  // Function to send a message with real-time streaming
  function sendMessage() {
    let responseTimeout = setTimeout(() => {
      if ($("#send-btn").prop("disabled")) {
        if (currentMessageElement) {
          currentMessageElement.html("<em>Error: Response timed out. Please try again.</em>");
        }
        enableUI();
      }
    }, 60000); // 1 minute timeout

    console.log("sendMessage called");
    const input = $("#user-input");
    const userMsg = input.val().trim();
    if (!userMsg) return;

    appendMessage(userMsg, "user");
    input.val("");
    disableUI();

    // Create bot message container
    currentMessageElement = createBotMessage();
    let accumulatedText = "";

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
      .then(async (response) => {
        console.log("Fetch response received");
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
          const { done, value } = await reader.read();

          if (done) {
            console.log("Stream complete");
            break;
          }

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split("\n");

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.substring(6));

                if (data.type === "content") {
                  // Real-time streaming: immediately append each chunk
                  accumulatedText += data.chunk;
                  if (currentMessageElement) {
                    currentMessageElement.html(formatText(accumulatedText));
                    $("#chat-box").scrollTop($("#chat-box")[0].scrollHeight);
                  }
                } else if (data.type === "complete") {
                  console.log("Response complete");
                  enableUI();
                  clearTimeout(responseTimeout);
                } else if (data.type === "stopped") {
                  console.log("Response stopped");
                  if (currentMessageElement) {
                    accumulatedText += "\n\n[Response stopped by user]";
                    currentMessageElement.html(formatText(accumulatedText));
                  }
                  enableUI();
                  clearTimeout(responseTimeout);
                } else if (data.type === "error") {
                  console.log("Error received:", data.message);
                  if (currentMessageElement) {
                    currentMessageElement.html(
                      `<em>Error: ${data.message}</em>`
                    );
                  }
                  enableUI();
                  clearTimeout(responseTimeout);
                }
              } catch (e) {
                console.log("Error parsing JSON:", e);
              }
            }
          }
        }
      })
      .catch((error) => {
        console.log("Error in fetch:", error);
        if (error.name === "AbortError") {
          console.log("Request was aborted");
          if (currentMessageElement) {
            const currentText = currentMessageElement.text();
            currentMessageElement.html(
              formatText(currentText + "\n\n[Response stopped by user]")
            );
          }
        } else {
          if (currentMessageElement) {
            currentMessageElement.html(`<em>Error: ${error.message}</em>`);
          }
        }
        enableUI();
        clearTimeout(responseTimeout);
      });
  }

  function stopResponse() {
    if (currentController) {
      console.log("Stopping response...");
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
        "Hello! I'm your JazzBot. How can I help you today?",
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
  });
})();
