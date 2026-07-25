(function () {
  "use strict";

  // --- Question loading: strict JSON only ---
  function loadQuestions() {
    var jsonTag = document.getElementById("lesson-questions");
    if (jsonTag && jsonTag.type === "application/json") {
      try {
        return JSON.parse(jsonTag.textContent);
      } catch (e) {
        console.error("Invalid lesson-questions JSON", e);
      }
    }
    return [];
  }

  var questions = loadQuestions();
  var answered = new Map();
  var quiz = document.getElementById("quiz");
  var score = document.getElementById("scoreText");
  var reset = document.getElementById("resetQuiz");
  var progress = document.querySelector(".reading-progress span");
  var stageLinks = Array.from(document.querySelectorAll(".lesson-steps a, .section-index-link"));
  var quizSection = document.querySelector(".quiz-section");
  var lang = document.documentElement.getAttribute("lang") || "en";
 var i18n = {
  "zh-CN": { correct: "答对了。", wrong: "再看一眼。", answered: "已答", of: "/", correctLabel: "正确", questionLabel: "题目", flip: "点击翻转", resetLabel: "重新作答", listen: "播放", trueLabel: "对", falseLabel: "错", matchCompletedWithErrors: "已完成（本题曾配错，计 0 分）。" },
  "zh-HK": { correct: "答啱咗。", wrong: "再睇一次。", answered: "已答", of: "/", correctLabel: "啱", questionLabel: "題目", flip: "撳一下翻轉", resetLabel: "重做", listen: "播放", trueLabel: "啱", falseLabel: "錯", matchCompletedWithErrors: "已完成（本題曾配錯，計 0 分）。" },
  en: { correct: "Correct.", wrong: "Take another look.", answered: "Answered", of: "/", correctLabel: "correct", questionLabel: "Question", flip: "Click to flip", resetLabel: "Reset", listen: "Listen", trueLabel: "True", falseLabel: "False", matchCompletedWithErrors: "Completed with errors (scored 0)." },
};
 var a11y = (lang === "zh-HK") ? { selected: "已選中", wrong: "配錯咗，請重選", locked: "配對正確，已鎖定" } : (lang === "zh-CN") ? { selected: "已选中", wrong: "配错了，请重选", locked: "配对正确，已锁定" } : { selected: "Selected", wrong: "Incorrect match, try again", locked: "Matched correctly, locked" };
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
      var q = questions[index];
      if (!q) return;
      if (q.type === "matching") { if (choice === true) correct += 1; }
      else if (choice === q.answer) correct += 1;
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
    feedback.textContent = "";
    var fbLabel = document.createElement("strong");
    fbLabel.textContent = isCorrect ? t.correct : t.wrong;
    feedback.appendChild(fbLabel);
    feedback.appendChild(document.createTextNode(" " + (question.rationale || "")));
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
    var frontLabel = document.createElement("strong");
    frontLabel.textContent = question.stem;
    front.appendChild(frontLabel);
    var flipHint = document.createElement("p");
    flipHint.textContent = t.flip;
    front.appendChild(flipHint);

    var back = document.createElement("div");
    back.className = "flashcard-face flashcard-face--back";
    var backLabel = document.createElement("strong");
    backLabel.textContent = question.answer_text || "";
    back.appendChild(backLabel);
    if (question.rationale) {
      var backP = document.createElement("p");
      backP.textContent = question.rationale;
      back.appendChild(backP);
    }

    inner.appendChild(front);
    inner.appendChild(back);
    card.appendChild(inner);
    quiz.appendChild(card);
  }

  function appendQuestionAudio(stemElement, audioText) {
    if (!audioText || typeof audioText !== "string") return;
    var audioBtn = document.createElement("button");
    audioBtn.className = "audio-trigger";
    audioBtn.type = "button";
    audioBtn.setAttribute("data-text", audioText);
    audioBtn.setAttribute("aria-label", t.listen + ": " + audioText);
    audioBtn.textContent = t.listen;
    stemElement.insertBefore(audioBtn, stemElement.firstChild);
  }

  function renderTrueFalse(question, questionIndex) {
    var article = document.createElement("article");
    article.className = "question question-truefalse";
    article.id = "question-" + (questionIndex + 1);
    var meta = document.createElement("div");
    meta.className = "question-meta";
    meta.textContent = questionLabel + " " + (questionIndex + 1);
    article.appendChild(meta);
    var stem = document.createElement("p");
    stem.className = "question-stem";
    stem.textContent = question.stem;
    appendQuestionAudio(stem, question.audio_text);
    article.appendChild(stem);
    var wrap = document.createElement("div");
    wrap.className = "tf-options";
    [true, false].forEach(function (val) {
      var btn = document.createElement("button");
      btn.className = "tf-button";
      btn.type = "button";
      btn.dataset.question = String(questionIndex);
      btn.dataset.value = String(val);
      var icon = document.createElement("span");
      icon.className = "tf-icon";
      icon.textContent = val ? "\u2713" : "\u2717";
      var label = document.createElement("span");
      label.textContent = val ? t.trueLabel : t.falseLabel;
      btn.appendChild(icon);
      btn.appendChild(label);
      btn.addEventListener("click", function (event) {
        selectTrueFalse(event.currentTarget, question, questionIndex);
      });
      wrap.appendChild(btn);
    });
    article.appendChild(wrap);
    var fb = document.createElement("div");
    fb.className = "question-feedback";
    fb.setAttribute("role", "status");
    fb.setAttribute("aria-live", "polite");
    article.appendChild(fb);
    quiz.appendChild(article);
  }

  function selectTrueFalse(button, question, questionIndex) {
    if (answered.has(questionIndex)) return;
    var chosen = button.dataset.value === "true";
    answered.set(questionIndex, chosen);
    var buttons = button.parentElement.querySelectorAll(".tf-button");
    buttons.forEach(function (b) { b.disabled = true; });
    var isCorrect = chosen === question.answer;
    if (isCorrect) button.classList.add("is-correct");
    else {
      button.classList.add("is-wrong");
      var correctBtn = button.parentElement.querySelector('[data-value="' + question.answer + '"]');
      if (correctBtn) correctBtn.classList.add("is-correct");
    }
    var fb = document.getElementById("question-" + (questionIndex + 1)).querySelector(".question-feedback");
    if (fb) {
      fb.className = "question-feedback is-visible " + (isCorrect ? "is-correct" : "is-wrong");
      var fbLabel = document.createElement("strong");
      fbLabel.textContent = isCorrect ? t.correct : t.wrong;
      fb.appendChild(fbLabel);
      fb.appendChild(document.createTextNode(" " + (question.rationale || "")));
    }
    updateScore();
  }

  function renderMatching(question, questionIndex) {
    var article = document.createElement("article");
    article.className = "question question-matching";
    article.id = "question-" + (questionIndex + 1);
    var meta = document.createElement("div");
    meta.className = "question-meta";
    meta.textContent = questionLabel + " " + (questionIndex + 1);
    article.appendChild(meta);
    var stem = document.createElement("p");
    stem.className = "question-stem";
    stem.textContent = question.stem;
    appendQuestionAudio(stem, question.audio_text);
    article.appendChild(stem);

    var pairs = question.pairs;
    var rightOrder = pairs.map(function (_, i) { return i; });
    for (var i = rightOrder.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = rightOrder[i]; rightOrder[i] = rightOrder[j]; rightOrder[j] = tmp;
    }

    var grid = document.createElement("div");
    grid.className = "match-grid";
    var leftCol = document.createElement("div");
    leftCol.className = "match-col";
    var rightCol = document.createElement("div");
    rightCol.className = "match-col";

    var selectedLeft = null;
    var locked = {};
    var wrongPair = null;
    var hadError = false;

   function clearSelected() {
     leftCol.querySelectorAll(".match-item--selected").forEach(function (el) { el.classList.remove("match-item--selected"); });
     rightCol.querySelectorAll(".match-item--selected").forEach(function (el) { el.classList.remove("match-item--selected"); });
     selectedLeft = null;
   }
    function setA11y(el, pressed) {
      if (el) el.setAttribute("aria-pressed", pressed ? "true" : "false");
    }
    function announce(text) {
      var fb = article.querySelector(".question-feedback");
      if (fb) {
        // Make feedback visible so screen readers announce it (default state
        // is display:none; announce() is called for transient match states)
        fb.className = "question-feedback is-visible";
        fb.textContent = text;
      }
    }

   function clearWrong() {
     if (!wrongPair) return;
     var lb = leftCol.querySelector('[data-lidx="' + wrongPair.left + '"]');
     var rb = rightCol.querySelector('[data-ridx="' + wrongPair.right + '"]');
     if (lb) lb.classList.remove("match-item--wrong");
     if (rb) rb.classList.remove("match-item--wrong");
      setA11y(lb, false);
      setA11y(rb, false);
     wrongPair = null;
   }

    function checkComplete() {
      if (Object.keys(locked).length < pairs.length) return;
      var score = !hadError;
      answered.set(questionIndex, score);
      var fb = article.querySelector(".question-feedback");
      if (fb) {
        fb.textContent = "";
        var isCorrect = score;
        fb.className = "question-feedback is-visible " + (isCorrect ? "is-correct" : "is-wrong");
        var fbLabel = document.createElement("strong");
        fbLabel.textContent = isCorrect ? t.correct : t.matchCompletedWithErrors;
        fb.appendChild(fbLabel);
        fb.appendChild(document.createTextNode(" " + (question.rationale || "")));
      }
      updateScore();
    }

    function tryMatch(leftIdx, rightIdx) {
      if (leftIdx === rightIdx) {
        locked[leftIdx] = rightIdx;
        var lb = leftCol.querySelector('[data-lidx="' + leftIdx + '"]');
        var rb = rightCol.querySelector('[data-ridx="' + rightIdx + '"]');
       if (lb) { lb.classList.remove("match-item--selected"); lb.classList.add("match-item--correct"); lb.disabled = true; }
       if (rb) { rb.classList.remove("match-item--selected"); rb.classList.add("match-item--correct"); rb.disabled = true; }
        setA11y(lb, true);
        setA11y(rb, true);
        announce(a11y.locked);
       selectedLeft = null;
       checkComplete();
     } else {
       hadError = true;
       wrongPair = { left: leftIdx, right: rightIdx };
       var lb = leftCol.querySelector('[data-lidx="' + leftIdx + '"]');
       var rb = rightCol.querySelector('[data-ridx="' + rightIdx + '"]');
       if (lb) { lb.classList.remove("match-item--selected"); lb.classList.add("match-item--wrong"); }
       if (rb) { rb.classList.remove("match-item--selected"); rb.classList.add("match-item--wrong"); }
        setA11y(lb, false);
        setA11y(rb, false);
        announce(a11y.wrong);
       selectedLeft = null;
     }
    }

    pairs.forEach(function (pair, i) {
     var btn = document.createElement("button");
     btn.className = "match-item match-left";
     btn.type = "button";
     btn.dataset.lidx = String(i);
     btn.textContent = pair.left;
     btn.setAttribute("aria-pressed", "false");
     btn.addEventListener("click", function () {
       if (answered.has(questionIndex) || (i in locked)) return;
       if (wrongPair) clearWrong();
      clearSelected();
        // Reset aria-pressed on items that are NOT locked (locked pairs keep
        // their "true" state so screen readers report them as still matched)
        leftCol.querySelectorAll(".match-item").forEach(function (el) {
          if (!el.classList.contains("match-item--correct")) setA11y(el, false);
        });
        rightCol.querySelectorAll(".match-item").forEach(function (el) {
          if (!el.classList.contains("match-item--correct")) setA11y(el, false);
        });
      selectedLeft = i;
      btn.classList.add("match-item--selected");
       setA11y(btn, true);
       announce(a11y.selected);
     });
      leftCol.appendChild(btn);
    });

    rightOrder.forEach(function (origIdx) {
      var btn = document.createElement("button");
     btn.className = "match-item match-right";
     btn.type = "button";
     btn.dataset.ridx = String(origIdx);
     btn.textContent = pairs[origIdx].right;
     btn.setAttribute("aria-pressed", "false");
     btn.addEventListener("click", function () {
       if (answered.has(questionIndex)) return;
       if (Object.values(locked).indexOf(origIdx) !== -1) return;
       if (wrongPair) { clearWrong(); return; }
       if (selectedLeft === null) return;
       btn.classList.add("match-item--selected");
       setA11y(btn, true);
       tryMatch(selectedLeft, origIdx);
     });
      rightCol.appendChild(btn);
    });

    grid.appendChild(leftCol);
    grid.appendChild(rightCol);
    article.appendChild(grid);
    var fb = document.createElement("div");
    fb.className = "question-feedback";
    fb.setAttribute("role", "status");
    fb.setAttribute("aria-live", "polite");
    article.appendChild(fb);
    quiz.appendChild(article);
  }

  function renderQuiz() {
    if (!quiz) return;
    quiz.innerHTML = "";

    questions.forEach(function (question, questionIndex) {
      if (question.type === "flashcard") { renderFlashcard(question, questionIndex); return; }
      if (question.type === "true_false") { renderTrueFalse(question, questionIndex); return; }
      if (question.type === "matching") { renderMatching(question, questionIndex); return; }
      var article = document.createElement("article");
      article.className = "question";
      article.id = "question-" + (questionIndex + 1);

      var meta = document.createElement("div");
      meta.className = "question-meta";
      meta.textContent = questionLabel + " " + (questionIndex + 1);
      article.appendChild(meta);

     var stem = document.createElement("p");
     stem.className = "question-stem";
     stem.textContent = question.stem;
     appendQuestionAudio(stem, question.audio_text);
     article.appendChild(stem);

      var optionList = document.createElement("ol");
      optionList.className = "question-options";
      question.options.forEach(function (option, optionIndex) {
        var li = document.createElement("li");
        var btn = document.createElement("button");
        btn.className = "question-option";
        btn.type = "button";
        btn.dataset.question = String(questionIndex);
        btn.dataset.option = String(optionIndex);
        var key = document.createElement("span");
        key.className = "option-key";
        key.setAttribute("aria-hidden", "true");
        key.textContent = "ABCDEF"[optionIndex] || "?";
        var label = document.createElement("span");
        label.textContent = option;
        btn.appendChild(key);
        btn.appendChild(label);
        li.appendChild(btn);
        optionList.appendChild(li);
      });
      article.appendChild(optionList);

      var fb = document.createElement("div");
      fb.className = "question-feedback";
      fb.setAttribute("role", "status");
      fb.setAttribute("aria-live", "polite");
      article.appendChild(fb);
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

  var PERSISTENT = ["lesson-footer", "lesson-steps", "section-index"];

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
      function activate(event) {
        event.preventDefault();
        showStage(index);
        var hash = (link.getAttribute("href") || "").replace("#", "");
        if (hash && history.replaceState) history.replaceState(null, "", "#" + hash);
      }
      link.addEventListener("click", activate);
      link.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") activate(event);
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


 // --- Audio adapter: speechSynthesis -> remote TTS (if permitted) -> dictionary link ---
 function loadAudioConfig() {
   var tag = document.getElementById("audio-config");
   if (!tag || tag.type !== "application/json") return {};
   try { return JSON.parse(tag.textContent); } catch (e) { return {}; }
 }

function initAudio() {
  var config = loadAudioConfig();
   var allowRemote = config.allow_remote_tts === true && typeof config.tts_endpoint === "string" && /^https:\/\//.test(config.tts_endpoint);

   document.addEventListener("click", function (e) {
     var btn = e.target.closest ? e.target.closest(".audio-trigger") : null;
     if (!btn) return;
     var text = btn.getAttribute("data-text") || "";
     var lang = config.lang || btn.getAttribute("data-lang") || "en";
     if (typeof window.speechSynthesis !== "undefined" && window.speechSynthesis && hasVoiceForLang(lang)) {
       try {
         window.speechSynthesis.cancel();
         var u = new SpeechSynthesisUtterance(text);
         u.lang = lang;
         u.rate = 0.85;
         u.onerror = function () { tryRemoteOrFallback(text, config, btn); };
         window.speechSynthesis.speak(u);
         return;
       } catch (e) { /* fall through */ }
     }
     tryRemoteOrFallback(text, config, btn);
   });

   document.querySelectorAll(".audio-trigger").forEach(function (btn) {
     if (!btn.getAttribute("aria-label")) btn.setAttribute("aria-label", t.listen + ": " + (btn.getAttribute("data-text") || ""));
   });

   function tryRemoteOrFallback(text, config, btn) {
     if (allowRemote) {
       playRemoteTTS(config.tts_endpoint, text, function () { fallbackAudio(text, config, btn); });
       return;
     }
     fallbackAudio(text, config, btn);
   }

   function fallbackAudio(text, config, btn) {
     if (config.fallback_url && /^https:\/\//.test(config.fallback_url)) {
       window.open(config.fallback_url + encodeURIComponent(text), "_blank", "noopener");
       return;
     }
     var hint = btn.querySelector(".audio-hint");
     if (!hint) {
       hint = document.createElement("span");
       hint.className = "audio-hint";
       hint.setAttribute("aria-live", "polite");
       btn.insertAdjacentElement("afterend", hint);
     }
     hint.textContent = text;
     hint.removeAttribute("hidden");
   }
 }

 function hasVoiceForLang(lang) {
   if (typeof window.speechSynthesis === "undefined" || !window.speechSynthesis) return false;
   var voices = window.speechSynthesis.getVoices();
   if (!voices.length) return true;
   return voices.some(function (v) {
     return v.lang && v.lang.toLowerCase().indexOf(lang.toLowerCase()) === 0;
   });
 }

 var remoteAudioEl = null;
 function playRemoteTTS(endpoint, text, onFail) {
   if (remoteAudioEl) { remoteAudioEl.pause(); remoteAudioEl.removeAttribute("src"); remoteAudioEl.load(); }
   remoteAudioEl = new Audio();
   remoteAudioEl.src = endpoint + encodeURIComponent(text);
   remoteAudioEl.onerror = onFail;
   remoteAudioEl.play().catch(onFail);
 }

  window.addEventListener("scroll", updateProgress, { passive: true });
  window.addEventListener("resize", updateProgress);
  if (reset) reset.addEventListener("click", resetQuiz);
  renderQuiz();
  initStages();
  initAudio();
  updateProgress();
})();
