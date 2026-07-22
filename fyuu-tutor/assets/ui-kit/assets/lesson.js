(function () {
  "use strict";

  // --- Question loading: v2 JSON first, v1 JS fallback during migration ---
  function loadQuestions() {
    var jsonTag = document.getElementById("lesson-questions");
    if (jsonTag && jsonTag.type === "application/json") {
      try {
        var parsed = JSON.parse(jsonTag.textContent);
        return parsed.map(function (q) {
          return q.type === "flashcard"
            ? { _flash: true, id: q.id, stem: q.stem, answer_text: q.answer_text, rationale: q.rationale || "" }
            : { id: q.id, stem: q.stem, opts: q.options, answer: q.answer, why: q.rationale };
        });
      } catch (e) {
        console.error("Invalid lesson-questions JSON", e);
      }
    }
    return Array.isArray(window.LESSON_QUESTIONS) ? window.LESSON_QUESTIONS : [];
  }

  var questions = loadQuestions();
  var answered = new Map();
  var quiz = document.getElementById("quiz");
  var score = document.getElementById("scoreText");
  var reset = document.getElementById("resetQuiz");
  var progress = document.querySelector(".reading-progress span");
  var stageLinks = Array.from(document.querySelectorAll(".lesson-steps a"));
  var quizSection = document.querySelector(".quiz-section");
  var lang = document.documentElement.getAttribute("lang") || "en";
  var i18n = {
    "zh-CN": { correct: "答对了。", wrong: "再看一眼。", answered: "已答", of: "/", correctLabel: "正确", questionLabel: "题目", flip: "点击翻转", resetLabel: "重新作答" },
    en: { correct: "Correct.", wrong: "Take another look.", answered: "Answered", of: "/", correctLabel: "correct", questionLabel: "Question", flip: "Click to flip", resetLabel: "Reset" },
  };
  var t = i18n[lang] || i18n.en;
  var questionLabel = (quizSection && quizSection.getAttribute("data-question-label")) || t.questionLabel;

  function updateProgress() {
    if (!progress) return;
    var scrollable = document.documentElement.scrollHeight - document.documentElement.clientHeight;
    var value = scrollable > 0 ? window.scrollY / scrollable : 0;
    progress.style.width = Math.min(100, Math.max(0, value * 100)) + "%";
  }

  function updateScore() {
    if (!score) return;
    var correct = 0;
    answered.forEach(function (choice, index) {
      if (questions[index] && choice === questions[index].answer) correct += 1;
    });
    score.textContent = t.answered + " " + answered.size + " " + t.of + " " + questions.length + " · " + t.correctLabel + " " + correct;
  }

  function selectAnswer(event) {
    var button = event.currentTarget;
    var questionIndex = Number(button.dataset.question);
    var optionIndex = Number(button.dataset.option);
    if (answered.has(questionIndex)) return;

    answered.set(questionIndex, optionIndex);
    var question = questions[questionIndex];
    var questionElement = document.getElementById("question-" + (questionIndex + 1));
    var optionButtons = questionElement.querySelectorAll(".question-option");

    optionButtons.forEach(function (optionButton, index) {
      optionButton.disabled = true;
      if (index === question.answer) optionButton.classList.add("is-correct");
      if (index === optionIndex && optionIndex !== question.answer) optionButton.classList.add("is-wrong");
    });

    var isCorrect = optionIndex === question.answer;
    var feedback = questionElement.querySelector(".question-feedback");
    feedback.className = "question-feedback is-visible " + (isCorrect ? "is-correct" : "is-wrong");
    feedback.innerHTML = (isCorrect ? "<strong>" + t.correct + "</strong> " : "<strong>" + t.wrong + "</strong> ") + question.why;
    updateScore();
  }

  function renderFlashcard(question, index) {
    var card = document.createElement("div");
    card.className = "flashcard";
    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    card.setAttribute("aria-label", t.flip);

    var inner = document.createElement("div");
    inner.className = "flashcard-inner";

    var front = document.createElement("div");
    front.className = "flashcard-face flashcard-face--front";
    front.innerHTML = "<strong>" + question.stem + "</strong><p>" + t.flip + "</p>";

    var back = document.createElement("div");
    back.className = "flashcard-face flashcard-face--back";
    back.innerHTML = "<strong>" + (question.answer_text || "") + "</strong>" + (question.rationale ? "<p>" + question.rationale + "</p>" : "");

    inner.appendChild(front);
    inner.appendChild(back);
    card.appendChild(inner);
    quiz.appendChild(card);
  }

  function renderQuiz() {
    if (!quiz) return;
    quiz.innerHTML = "";

    questions.forEach(function (question, questionIndex) {
      if (question._flash) { renderFlashcard(question, questionIndex); return; }
      var article = document.createElement("article");
      article.className = "question";
      article.id = "question-" + (questionIndex + 1);

      var options = question.opts.map(function (option, optionIndex) {
        return '<li><button class="question-option" type="button" data-question="' + questionIndex + '" data-option="' + optionIndex + '"><span class="option-key" aria-hidden="true">' + "ABCDEF"[optionIndex] + "</span><span>" + option + "</span></button></li>";
      }).join("");

      article.innerHTML =
        '<div class="question-meta">' + questionLabel + " " + (questionIndex + 1) + "</div>" +
        '<p class="question-stem">' + question.stem + "</p>" +
        '<ol class="question-options">' + options + "</ol>" +
        '<div class="question-feedback" role="status" aria-live="polite"></div>';
      quiz.appendChild(article);
    });

    quiz.querySelectorAll(".question-option").forEach(function (button) {
      button.addEventListener("click", selectAnswer);
    });
    quiz.querySelectorAll(".flashcard").forEach(function (card) {
      card.addEventListener("click", function () { card.classList.toggle("is-flipped"); });
      card.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); card.classList.toggle("is-flipped"); }
      });
    });
    updateScore();
  }

  function resetQuiz() { answered.clear(); renderQuiz(); }

  var PERSISTENT = ["lesson-footer", "lesson-steps"];

  function stageGroups() {
    var shell = document.querySelector(".lesson-shell");
    if (!shell) return [];
    var targets = stageLinks.map(function (l) { return (l.getAttribute("href") || "").replace("#", ""); });
    var groups = stageLinks.map(function () { return []; });
    var current = -1;
    Array.prototype.forEach.call(shell.children, function (el) {
      if (PERSISTENT.some(function (c) { return el.classList.contains(c); })) return;
      var idx = targets.indexOf(el.id);
      if (idx === -1 && el.hasAttribute("data-stage")) idx = targets.indexOf(el.getAttribute("data-stage"));
      if (idx !== -1) current = idx;
      if (current !== -1) groups[current].push(el);
    });
    return groups;
  }

  function showStage(index) {
    var groups = stageGroups();
    if (index < 0 || index >= groups.length) return;
    groups.forEach(function (group, i) {
      var hidden = i !== index;
      group.forEach(function (el) { if (hidden) el.setAttribute("hidden", ""); else el.removeAttribute("hidden"); });
    });
    stageLinks.forEach(function (link, i) {
      if (i === index) link.setAttribute("aria-current", "step");
      else link.removeAttribute("aria-current");
    });
    var stageKey = "fyuu-stage-" + location.pathname;
    try { sessionStorage.setItem(stageKey, String(index)); } catch (e) {}
    window.scrollTo(0, 0);
  }

  function initStages() {
    if (stageLinks.length === 0) return;
    stageLinks.forEach(function (link, index) {
      link.addEventListener("click", function (event) {
        event.preventDefault();
        showStage(index);
        var hash = (link.getAttribute("href") || "").replace("#", "");
        if (hash && history.replaceState) history.replaceState(null, "", "#" + hash);
      });
    });
    var start = 0;
    var hash = (location.hash || "").replace("#", "");
    var targets = stageLinks.map(function (l) { return (l.getAttribute("href") || "").replace("#", ""); });
    var hashIdx = targets.indexOf(hash);
    if (hashIdx !== -1) start = hashIdx;
    else {
      try {
        var stageKey = "fyuu-stage-" + location.pathname;
        var saved = sessionStorage.getItem(stageKey);
        if (saved !== null) start = Math.min(stageLinks.length - 1, Math.max(0, Number(saved) || 0));
      } catch (e) {}
    }
    showStage(start);
  }

  window.addEventListener("scroll", updateProgress, { passive: true });
  window.addEventListener("resize", updateProgress);
  if (reset) reset.addEventListener("click", resetQuiz);
  renderQuiz();
  initStages();
  updateProgress();
})();
