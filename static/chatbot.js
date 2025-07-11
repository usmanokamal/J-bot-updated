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

  // Modified appendMessage function to include feedback for bot messages
  function appendMessage(text, sender, messageId = null) {
    let bubble = $("<div>").addClass("chat-bubble").addClass(sender);

    if (sender === "bot") {
      const messageWrapper = $("<div>").addClass("bot-message-wrapper");

      const contentContainer = $("<div>").addClass("bot-content-container");
      const logo = $("<img>")
        .attr("src", "/static/assets/Jazz-Company-logo-.png")
        .attr("alt", "Jazz Logo")
        .css({ width: "24px", height: "24px", marginRight: "10px" });

      let formattedText = text
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\n/g, "<br>");

      const messageContent = $("<span>").html(formattedText);
      contentContainer.append(logo).append(messageContent);
      messageWrapper.append(contentContainer);

      // Add feedback buttons for bot messages at the end
      if (messageId) {
        const feedbackButtons = createFeedbackButtons(
          messageId,
          window.lastUserMessage,
          text
        );
        messageWrapper.append(feedbackButtons);
      }

      bubble.append(messageWrapper);
    } else {
      bubble.text(text);
      // Store user message for feedback context
      window.lastUserMessage = text;
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
    $("#stop-btn").show();
    startTypingAnimation();
  }

  function enableUI() {
    $("#send-btn").prop("disabled", false);
    $("#user-input").prop("disabled", false);
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

  function createBotMessage(messageId) {
    const bubble = $("<div>").addClass("chat-bubble").addClass("bot");
    const messageWrapper = $("<div>").addClass("bot-message-wrapper");

    const contentContainer = $("<div>").addClass("bot-content-container");
    const logo = $("<img>")
      .attr("src", "/static/assets/Jazz-Company-logo-.png")
      .attr("alt", "Jazz Logo")
      .css({ width: "24px", height: "24px", marginRight: "10px" });

    const messageContent = $("<span>");
    contentContainer.append(logo).append(messageContent);
    messageWrapper.append(contentContainer);

    // Add placeholder for feedback buttons at the end
    const feedbackContainer = $("<div>").addClass(
      "feedback-container-placeholder"
    );
    messageWrapper.append(feedbackContainer);

    bubble.append(messageWrapper);
    $("#chat-box").append(bubble);
    $("#chat-box").scrollTop($("#chat-box")[0].scrollHeight);

    return { messageContent, feedbackContainer };
  }

  // Function to send a message with real-time streaming
  function sendMessage() {
    let responseTimeout = setTimeout(() => {
      if ($("#send-btn").prop("disabled")) {
        if (currentMessageElement) {
          currentMessageElement.html(
            "<em>Error: Response timed out. Please try again.</em>"
          );
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

    // Generate unique message ID
    const messageId = Date.now().toString();

    // Create bot message container
    const { messageContent, feedbackContainer } = createBotMessage(messageId);
    currentMessageElement = messageContent;
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
            // Add feedback buttons after message is complete
            const feedbackButtons = createFeedbackButtons(
              messageId,
              userMsg,
              accumulatedText
            );
            feedbackContainer.replaceWith(feedbackButtons);
            break;
          }

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split("\n");

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.substring(6));

                if (data.type === "content") {
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
                  // Add feedback buttons even for stopped responses
                  const feedbackButtons = createFeedbackButtons(
                    messageId,
                    userMsg,
                    accumulatedText
                  );
                  feedbackContainer.replaceWith(feedbackButtons);
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
        // Add feedback buttons even for errors
        const feedbackButtons = createFeedbackButtons(
          messageId,
          userMsg,
          accumulatedText
        );
        feedbackContainer.replaceWith(feedbackButtons);
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

  // Function to create feedback buttons
  function createFeedbackButtons(messageId, userMessage, botResponse) {
    const feedbackContainer = $("<div>").addClass("feedback-container");

    // Translation button
    const translateBtn = createTranslationButton(
      messageId,
      botResponse,
      feedbackContainer
    );

    // Existing feedback buttons
    const thumbsUp = $("<button>")
      .addClass("feedback-btn thumbs-up")
      .attr("data-message-id", messageId)
      .attr("data-feedback", "good")
      .attr("title", "Good response")
      .click(function () {
        submitFeedback(messageId, userMessage, botResponse, "good", $(this));
      });

    const thumbsDown = $("<button>")
      .addClass("feedback-btn thumbs-down")
      .attr("data-message-id", messageId)
      .attr("data-feedback", "bad")
      .attr("title", "Bad response")
      .click(function () {
        submitFeedback(messageId, userMessage, botResponse, "bad", $(this));
      });

    feedbackContainer.append(translateBtn).append(thumbsUp).append(thumbsDown);
    return feedbackContainer;
  }

  // Function to submit feedback
  function submitFeedback(
    messageId,
    userMessage,
    botResponse,
    feedback,
    buttonElement
  ) {
    // Disable both buttons and show selected state
    const container = buttonElement.closest(".feedback-container");
    container.find(".feedback-btn").prop("disabled", true);
    buttonElement.addClass("selected");

    // Send feedback to backend
    fetch("/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message_id: messageId,
        user_message: userMessage,
        bot_response: botResponse,
        feedback: feedback,
        session_id: sessionId,
        timestamp: new Date().toISOString(),
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        console.log("Feedback submitted:", data);
        // Show thank you message briefly
        const thankYou = $("<span>")
          .addClass("thank-you-text")
          .text("Thank you for your feedback!");
        container.append(thankYou);
        setTimeout(() => thankYou.fadeOut(), 2000);
      })
      .catch((error) => {
        console.error("Error submitting feedback:", error);
        // Re-enable buttons on error
        container.find(".feedback-btn").prop("disabled", false);
        buttonElement.removeClass("selected");
      });
  }
  function detectLanguage(text) {
    // Enhanced language detection
    const romanUrduWords = [
      "aap",
      "hai",
      "hain",
      "kar",
      "ke",
      "ki",
      "ko",
      "se",
      "me",
      "main",
      "yeh",
      "woh",
      "kya",
      "kyun",
      "kab",
      "kahan",
      "kaisa",
      "kitna",
      "mera",
      "tera",
      "hamara",
      "tumhara",
      "nahi",
      "nahin",
      "bahut",
      "shukriya",
      "maaf",
      "ji",
      "han",
      "haan",
      "achha",
      "bura",
    ];

    const textLower = text.toLowerCase();
    const romanUrduCount = romanUrduWords.filter((word) =>
      textLower.includes(word)
    ).length;

    if (
      romanUrduCount >= 2 ||
      (romanUrduCount >= 1 && text.split(" ").length <= 5)
    ) {
      return "roman_urdu";
    }

    const englishWords = text.match(/\b[a-zA-Z]+\b/g) || [];
    const totalWords = text.split(/\s+/).length;

    if (totalWords === 0) return "english";

    const englishRatio = englishWords.length / totalWords;
    return englishRatio > 0.6 ? "english" : "roman_urdu";
  }

  function createTranslationButton(messageId, text, container) {
    const translateBtn = $("<button>")
      .addClass("translate-btn")
      .attr("data-message-id", messageId)
      .attr("data-original-bot-response", text) // Store original bot response
      .attr("data-current-lang", "english") // Bot always responds in English initially
      .attr("data-translated-text", "") // Will store translated version
      .attr("title", "Translate to Roman Urdu")
      .html("RomanUR")
      .click(function () {
        translateMessage($(this));
      });

    return translateBtn;
  }

  function translateMessage(buttonElement) {
    const messageId = buttonElement.attr("data-message-id");
    const originalBotResponse = buttonElement.attr(
      "data-original-bot-response"
    );
    const currentLang = buttonElement.attr("data-current-lang");
    const translatedText = buttonElement.attr("data-translated-text");

    // Show loading state
    buttonElement.html("...").prop("disabled", true);

    // Find the message content element
    const messageContent = buttonElement
      .closest(".bot-message-wrapper")
      .find(".bot-content-container span");

    if (currentLang === "english") {
      // Translate to Roman Urdu
      fetch("/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: originalBotResponse,
          target_language: "roman_urdu",
        }),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.status === "success") {
            // Update message content with translated text
            messageContent.html(formatText(data.translated_text));

            // Update button state
            buttonElement
              .html("EN")
              .attr("data-current-lang", "roman_urdu")
              .attr("data-translated-text", data.translated_text)
              .attr("title", "Show Original English")
              .prop("disabled", false);
          } else {
            console.error("Translation failed:", data.message);
            buttonElement.html("RomanUR").prop("disabled", false);
          }
        })
        .catch((error) => {
          console.error("Translation error:", error);
          buttonElement.html("RomanUR").prop("disabled", false);
        });
    } else {
      // Show original English response (no API call needed)
      messageContent.html(formatText(originalBotResponse));

      // Update button state
      buttonElement
        .html("RomanUR")
        .attr("data-current-lang", "english")
        .attr("title", "Translate to Roman Urdu")
        .prop("disabled", false);
    }
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
  window.toggleView = toggleView;

  $(document).ready(function () {
    console.log("Document ready, chatbot.js loaded!");
    $("#stop-btn").hide();

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
