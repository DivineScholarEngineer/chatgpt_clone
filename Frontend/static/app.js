const elements = {
  conversationList: document.getElementById("conversation-list"),
  messages: document.getElementById("messages"),
  messageInput: document.getElementById("message-input"),
  sendButton: document.getElementById("send-button"),
  newChatButton: document.getElementById("new-chat"),
  fileInput: document.getElementById("file-input"),
  attachmentBar: document.getElementById("attachment-bar"),
  chatTitle: document.getElementById("chat-title"),
  chatSubtitle: document.getElementById("chat-subtitle"),
  conversationSectionTitle: document.getElementById("conversation-section-title"),
  archiveToggle: document.getElementById("archive-toggle"),
  refreshConversations: document.getElementById("refresh-conversations"),
  settingsButton: document.getElementById("settings-button"),
  controlCenter: document.getElementById("control-center"),
  closeSettings: document.getElementById("close-settings"),
  tabButtons: Array.from(document.querySelectorAll(".tab-button")),
  tabPanels: Array.from(document.querySelectorAll(".tab-panel")),
  authButton: document.getElementById("auth-button"),
  authDialog: document.getElementById("auth-dialog"),
  authTitle: document.getElementById("auth-title"),
  closeAuth: document.getElementById("close-auth"),
  authForm: document.getElementById("auth-form"),
  authUsername: document.getElementById("auth-username"),
  authEmail: document.getElementById("auth-email"),
  authPassword: document.getElementById("auth-password"),
  authSubmit: document.getElementById("auth-submit"),
  authToggleMode: document.getElementById("auth-toggle-mode"),
  authConfirmWrapper: document.getElementById("auth-confirm-wrapper"),
  authConfirmPassword: document.getElementById("auth-confirm-password"),
  authForgotPassword: document.getElementById("auth-forgot-password"),
  authHelpText: document.getElementById("auth-help-text"),
  themeToggle: document.getElementById("theme-toggle"),
  insightsBar: document.getElementById("insights-bar"),
  composerStatus: document.getElementById("composer-status"),
  renameChat: document.getElementById("rename-chat"),
  conversationMenu: document.getElementById("conversation-menu"),
  notifications: document.getElementById("notifications"),
  toolboxButton: document.getElementById("toolbox-button"),
  toolPopover: document.getElementById("tool-popover"),
  openSearch: document.getElementById("open-search"),
  searchPanel: document.getElementById("web-search-panel"),
  closeSearch: document.getElementById("close-search"),
  searchForm: document.getElementById("search-form"),
  searchQuery: document.getElementById("search-query"),
  searchResults: document.getElementById("search-results"),
  openImages: document.getElementById("open-images"),
  imagePanel: document.getElementById("image-panel"),
  closeImages: document.getElementById("close-images"),
  imageForm: document.getElementById("image-form"),
  imagePrompt: document.getElementById("image-prompt"),
  imageCount: document.getElementById("image-count"),
  imageCountOutput: document.getElementById("image-count-output"),
  imageJobs: document.getElementById("image-jobs"),
  becomeAdmin: document.getElementById("become-admin"),
  refreshAdmin: document.getElementById("refresh-admin"),
  adminStats: document.getElementById("admin-stats"),
};

const state = {
  session: null,
  conversations: [],
  currentConversation: null,
  pendingAttachments: [],
  showArchived: false,
  authMode: "login",
  popoverOpen: false,
  persona: null,
};

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "numeric",
});

const timeFormatter = new Intl.DateTimeFormat(undefined, {
  hour: "numeric",
  minute: "numeric",
});

function showToast(message, duration = 4000) {
  if (!elements.notifications) return;
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  elements.notifications.appendChild(toast);
  setTimeout(() => {
    toast.classList.add("fade-out");
    setTimeout(() => toast.remove(), 320);
  }, duration);
}

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    credentials: "include",
    ...options,
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || response.statusText);
  }
  return response.json();
}

function formatISODate(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  return dateFormatter.format(date);
}

function formatISOTime(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  return timeFormatter.format(date);
}

function groupConversations(conversations) {
  const groups = new Map();
  conversations.forEach((conversation) => {
    const key = formatISODate(conversation.created_at);
    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key).push(conversation);
  });
  return groups;
}

function renderConversations() {
  elements.conversationList.innerHTML = "";
  if (!state.conversations.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = state.showArchived
      ? "No archived conversations yet"
      : "Start a conversation to see it here";
    elements.conversationList.appendChild(empty);
    return;
  }

  const groups = groupConversations(state.conversations);
  groups.forEach((items, label) => {
    const header = document.createElement("div");
    header.className = "conversation-group-header";
    header.textContent = label;
    elements.conversationList.appendChild(header);

    items.forEach((conversation) => {
      const item = document.createElement("div");
      item.className = "conversation-item";
      if (state.currentConversation && state.currentConversation.id === conversation.id) {
        item.classList.add("active");
      }

      const title = document.createElement("div");
      title.className = "title";
      title.textContent = conversation.title || "New chat";

      const meta = document.createElement("div");
      meta.className = "meta";
      const time = formatISOTime(conversation.created_at);
      meta.textContent = `${time}${conversation.archived ? " · archived" : ""}`;

      item.appendChild(title);
      item.appendChild(meta);

      item.addEventListener("click", () => loadConversation(conversation.id));
      elements.conversationList.appendChild(item);
    });
  });
}

function createMessageRow(message) {
  const row = document.createElement("div");
  row.className = `message-row ${message.role}`;

  const role = document.createElement("div");
  role.className = "message-role";
  role.textContent = message.role === "assistant" ? "🤖" : "🧑";

  const content = document.createElement("div");
  content.className = "message-content";
  content.textContent = message.content;

  if (message.attachments && message.attachments.length) {
    const attachments = document.createElement("div");
    attachments.className = "attachment-preview";
    message.attachments.forEach((attachment) => {
      const link = document.createElement("a");
      link.href = `/${attachment.filename}`;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = attachment.original_name;
      attachments.appendChild(link);
    });
    content.appendChild(attachments);
  }

  row.appendChild(role);
  row.appendChild(content);

  return row;
}

function renderMessages(conversation) {
  elements.messages.innerHTML = "";
  if (!conversation) {
    elements.chatTitle.textContent = "DIV GPT-OSS Studio";
    elements.chatSubtitle.textContent = "Personal intelligence that remembers and adapts";
    return;
  }

  elements.chatTitle.textContent = conversation.title || "New chat";
  elements.chatSubtitle.textContent = conversation.archived
    ? "This conversation is archived"
    : `Started ${formatISODate(conversation.created_at)}`;

  conversation.messages.forEach((message) => {
    elements.messages.appendChild(createMessageRow(message));
  });
  elements.messages.scrollTop = elements.messages.scrollHeight;
}

function renderAttachments() {
  elements.attachmentBar.innerHTML = "";
  state.pendingAttachments.forEach((attachment, index) => {
    const pill = document.createElement("div");
    pill.className = "attachment-pill";
    pill.textContent = attachment.original_name;

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.textContent = "✕";
    removeBtn.addEventListener("click", async (event) => {
      event.stopPropagation();
      const [removed] = state.pendingAttachments.splice(index, 1);
      renderAttachments();
      if (removed) {
        try {
          await fetch(`/attachments/${removed.id}`, { method: "DELETE" });
        } catch (error) {
          console.error("Failed to delete attachment", error);
        }
      }
    });

    pill.appendChild(removeBtn);
    elements.attachmentBar.appendChild(pill);
  });
  updateComposerStatus();
}

function updateComposerStatus() {
  if (!elements.composerStatus) return;
  if (!state.currentConversation) {
    elements.composerStatus.textContent = "Creating new conversation";
  } else if (state.currentConversation.archived) {
    elements.composerStatus.textContent = "Sending will restore this chat";
  } else if (state.pendingAttachments.length) {
    elements.composerStatus.textContent = `${state.pendingAttachments.length} attachment(s) ready`;
  } else {
    elements.composerStatus.textContent = "";
  }
}

function renderPersonaInsights(persona) {
  if (!persona) {
    elements.insightsBar.classList.add("hidden");
    elements.insightsBar.innerHTML = "";
    return;
  }

  elements.insightsBar.classList.remove("hidden");
  elements.insightsBar.innerHTML = "";

  const topics = document.createElement("div");
  topics.className = "insight-chip";
  const topicList = (persona.top_topics || []).join(", ") || "Learning";
  topics.innerHTML = `<strong>Top topics</strong><span>${topicList}</span>`;

  const tone = document.createElement("div");
  tone.className = "insight-chip";
  tone.innerHTML = `<strong>Tone</strong><span>${persona.tone || "curious"}</span>`;

  const count = document.createElement("div");
  count.className = "insight-chip";
  count.innerHTML = `<strong>Messages</strong><span>${persona.message_count || 0}</span>`;

  elements.insightsBar.appendChild(topics);
  elements.insightsBar.appendChild(tone);
  elements.insightsBar.appendChild(count);
}

async function refreshSession() {
  try {
    const session = await fetchJSON("/auth/session", { method: "GET" });
    if (session.authenticated) {
      state.session = session.user;
      state.persona = session.dashboard?.persona || null;
      elements.authButton.textContent = `Hi, ${session.user.username}`;
      renderPersonaInsights(state.persona);
    } else {
      state.session = null;
      state.persona = null;
      elements.authButton.textContent = "Sign in";
      renderPersonaInsights(null);
    }
  } catch (error) {
    console.error("Failed to refresh session", error);
  }
}

async function fetchConversations() {
  if (!state.session) {
    state.conversations = [];
    renderConversations();
    renderMessages(null);
    return;
  }
  try {
    const data = await fetchJSON(
      `/conversations?archived=${state.showArchived ? "true" : "false"}`
    );
    state.conversations = data.items || [];
    if (!state.currentConversation && state.conversations.length) {
      state.currentConversation = state.conversations[0];
    }
    if (state.currentConversation) {
      const fresh = state.conversations.find((c) => c.id === state.currentConversation.id);
      state.currentConversation = fresh || state.currentConversation;
    }
    elements.conversationSectionTitle.textContent = state.showArchived ? "Archive" : "Today";
    renderConversations();
    renderMessages(state.currentConversation);
  } catch (error) {
    console.error("Failed to load conversations", error);
    showToast(`Unable to load conversations: ${error.message}`);
  }
}

async function loadConversation(id) {
  try {
    const conversation = await fetchJSON(`/conversations/${id}`);
    state.currentConversation = conversation;
    const index = state.conversations.findIndex((c) => c.id === conversation.id);
    if (index !== -1) {
      state.conversations[index] = conversation;
    } else {
      state.conversations.unshift(conversation);
    }
    renderConversations();
    renderMessages(conversation);
  } catch (error) {
    showToast(error.message);
  }
}

async function uploadFiles(files) {
  const uploads = Array.from(files).map(async (file) => {
    const formData = new FormData();
    if (state.currentConversation) {
      formData.append("conversation_id", state.currentConversation.id);
    }
    formData.append("file", file);
    const response = await fetch("/upload", {
      method: "POST",
      body: formData,
      credentials: "include",
    });
    if (!response.ok) {
      throw new Error("Upload failed");
    }
    return response.json();
  });

  const results = await Promise.all(uploads);
  state.pendingAttachments.push(...results);
  renderAttachments();
}

async function sendMessage() {
  const message = elements.messageInput.value.trim();
  if (!message && state.pendingAttachments.length === 0) {
    return;
  }
  elements.sendButton.disabled = true;

  try {
    const payload = {
      conversation_id: state.currentConversation ? state.currentConversation.id : null,
      message,
      attachment_ids: state.pendingAttachments.map((attachment) => attachment.id),
    };

    const data = await fetchJSON("/chat", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    state.currentConversation = data.conversation;
    const index = state.conversations.findIndex((c) => c.id === state.currentConversation.id);
    if (index !== -1) {
      state.conversations[index] = state.currentConversation;
    } else {
      state.conversations.unshift(state.currentConversation);
    }
    elements.messageInput.value = "";
    state.pendingAttachments = [];
    renderAttachments();
    renderConversations();
    renderMessages(state.currentConversation);
    elements.messageInput.focus();
  } catch (error) {
    showToast(error.message || "Unable to send message");
  } finally {
    elements.sendButton.disabled = false;
  }
}

function resetComposer() {
  state.currentConversation = null;
  elements.messageInput.value = "";
  state.pendingAttachments = [];
  renderAttachments();
  renderMessages(null);
  renderConversations();
  elements.messageInput.focus();
}

function toggleSettings(open) {
  if (!elements.controlCenter) return;
  elements.controlCenter.classList.toggle("hidden", !open);
}

function toggleAuthDialog(open) {
  if (!elements.authDialog) return;
  elements.authDialog.classList.toggle("hidden", !open);
  if (open) {
    elements.authUsername.focus();
  } else {
    if (elements.authForm) {
      elements.authForm.reset();
    }
    updateAuthMode("login");
  }
}

function updateAuthMode(mode) {
  state.authMode = mode;
  const isRegister = mode === "register";
  const isReset = mode === "reset";

  const usernameLabel = elements.authUsername?.parentElement?.querySelector("span");
  const emailWrapper = elements.authEmail?.parentElement;
  const emailLabel = emailWrapper?.querySelector("span");
  const passwordLabel = elements.authPassword?.parentElement?.querySelector("span");

  elements.authTitle.textContent = isRegister
    ? "Register"
    : isReset
    ? "Reset password"
    : "Sign in";

  elements.authToggleMode.textContent = isRegister
    ? "Switch to sign in"
    : isReset
    ? "Back to sign in"
    : "Switch to register";

  if (emailWrapper) {
    emailWrapper.classList.toggle("hidden", !(isRegister || isReset));
  }

  if (elements.authConfirmWrapper) {
    elements.authConfirmWrapper.classList.toggle(
      "hidden",
      !(isRegister || isReset)
    );
  }

  if (elements.authForgotPassword) {
    elements.authForgotPassword.classList.toggle("hidden", mode !== "login");
  }

  if (elements.authHelpText) {
    elements.authHelpText.classList.toggle("hidden", !isReset);
  }

  if (usernameLabel) {
    usernameLabel.textContent = isReset ? "Username (optional)" : "Username";
  }

  if (emailLabel) {
    emailLabel.textContent = isReset ? "Email (optional)" : "Email";
  }

  if (passwordLabel) {
    passwordLabel.textContent = isReset ? "New password" : "Password";
  }

  elements.authUsername.required = !isReset;
  elements.authPassword.required = true;
  elements.authEmail.required = false;
  if (elements.authConfirmPassword) {
    elements.authConfirmPassword.required = isRegister || isReset;
    if (isRegister || isReset) {
      elements.authConfirmPassword.value = "";
    }
  }

  elements.authPassword.autocomplete = isReset || isRegister ? "new-password" : "current-password";

  if (!isRegister && !isReset && elements.authConfirmPassword) {
    elements.authConfirmPassword.value = "";
  }

  if (isReset && elements.authHelpText) {
    elements.authHelpText.textContent =
      "Enter your username or email along with a new password to reset your access.";
  }

  if (elements.authSubmit) {
    elements.authSubmit.textContent = isReset
      ? "Update password"
      : isRegister
      ? "Create account"
      : "Continue";
  }
}

async function handleAuthSubmit(event) {
  event.preventDefault();
  const username = elements.authUsername.value.trim();
  const email = elements.authEmail.value.trim();
  const password = elements.authPassword.value;
  const confirmPassword = elements.authConfirmPassword
    ? elements.authConfirmPassword.value
    : "";

  if (state.authMode === "reset") {
    if (!username && !email) {
      showToast("Provide your username or email to reset the password");
      return;
    }
    if (!password) {
      showToast("New password is required");
      return;
    }
    if (!confirmPassword) {
      showToast("Confirm your new password");
      return;
    }
    if (password !== confirmPassword) {
      showToast("Passwords do not match");
      return;
    }

    try {
      const payload = { new_password: password };
      if (username) payload.username = username;
      if (email) payload.email = email;
      if (confirmPassword) payload.confirm_password = confirmPassword;

      await fetchJSON("/auth/reset-password", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      showToast("Password updated. You can now sign in.");
      const preservedIdentifier = username || email;
      if (elements.authForm) {
        elements.authForm.reset();
      }
      updateAuthMode("login");
      if (preservedIdentifier) {
        elements.authUsername.value = preservedIdentifier;
      }
      elements.authPassword.value = "";
      elements.authPassword.focus();
    } catch (error) {
      showToast(error.message);
    }
    return;
  }

  if (!username || !password) {
    showToast("Username and password are required");
    return;
  }

  if (state.authMode === "register") {
    if (!confirmPassword || password !== confirmPassword) {
      showToast("Passwords do not match");
      return;
    }
  }

  try {
    const endpoint = state.authMode === "register" ? "/auth/register" : "/auth/login";
    const payload = { username, password };
    if (state.authMode === "register" && email) {
      payload.email = email;
    }
    if (state.authMode === "register" && confirmPassword) {
      payload.confirm_password = confirmPassword;
    }

    const mode = state.authMode;

    await fetchJSON(endpoint, {
      method: "POST",
      body: JSON.stringify(payload),
    });

    toggleAuthDialog(false);
    await refreshSession();
    await fetchConversations();
    showToast(mode === "register" ? "Account created" : "Welcome back!");
  } catch (error) {
    showToast(error.message);
  }
}

async function signOut() {
  try {
    await fetchJSON("/auth/logout", { method: "POST" });
  } catch (error) {
    console.error(error);
  } finally {
    state.session = null;
    state.conversations = [];
    state.currentConversation = null;
    renderConversations();
    renderMessages(null);
    elements.authButton.textContent = "Sign in";
    showToast("Signed out");
  }
}

async function renameConversation() {
  if (!state.currentConversation) return;
  const newTitle = prompt("Rename conversation", state.currentConversation.title || "");
  if (!newTitle) return;
  try {
    const updated = await fetchJSON(
      `/conversations/${state.currentConversation.id}/update`,
      {
        method: "PATCH",
        body: JSON.stringify({ title: newTitle }),
      }
    );
    state.currentConversation = updated;
    const index = state.conversations.findIndex((c) => c.id === updated.id);
    if (index !== -1) {
      state.conversations[index] = updated;
    }
    renderConversations();
    renderMessages(updated);
    showToast("Conversation renamed");
  } catch (error) {
    showToast(error.message);
  }
}

async function toggleArchiveCurrent(forceValue) {
  if (!state.currentConversation) return;
  const archived =
    typeof forceValue === "boolean" ? forceValue : !state.currentConversation.archived;
  try {
    const updated = await fetchJSON(
      `/conversations/${state.currentConversation.id}/update`,
      {
        method: "PATCH",
        body: JSON.stringify({ archived }),
      }
    );
    state.currentConversation = archived ? null : updated;
    await fetchConversations();
    renderMessages(state.currentConversation);
    showToast(archived ? "Conversation archived" : "Conversation restored");
  } catch (error) {
    showToast(error.message);
  }
}

async function deleteConversation() {
  if (!state.currentConversation) return;
  const confirmation = confirm("Delete this conversation permanently?");
  if (!confirmation) return;
  try {
    await fetch(`/conversations/${state.currentConversation.id}/delete`, {
      method: "DELETE",
      credentials: "include",
    });
    state.currentConversation = null;
    await fetchConversations();
    renderMessages(null);
    showToast("Conversation deleted");
  } catch (error) {
    showToast("Unable to delete conversation");
  }
}

function openPopover(anchor) {
  if (!elements.toolPopover) return;
  const rect = anchor.getBoundingClientRect();
  elements.toolPopover.style.top = `${rect.bottom + 8}px`;
  elements.toolPopover.style.left = `${rect.left}px`;
  elements.toolPopover.classList.remove("hidden");
  state.popoverOpen = true;
}

function closePopover() {
  if (!elements.toolPopover) return;
  elements.toolPopover.classList.add("hidden");
  state.popoverOpen = false;
}

function openDrawer(panel) {
  panel.classList.remove("hidden");
}

function closeDrawer(panel) {
  panel.classList.add("hidden");
}

async function performSearch(query) {
  try {
    const results = await fetchJSON("/tools/search", {
      method: "POST",
      body: JSON.stringify({ query }),
    });
    elements.searchResults.innerHTML = "";
    results.results.forEach((item) => {
      const card = document.createElement("div");
      card.className = "result-card";
      card.innerHTML = `<strong>${item.title}</strong><span>${item.excerpt}</span><span class="source">${item.source}</span>`;
      elements.searchResults.appendChild(card);
    });
    showToast(`Web Pulse analysed ${results.results.length} sources`);
  } catch (error) {
    showToast(error.message);
  }
}

function renderImageJobs(jobs) {
  elements.imageJobs.innerHTML = "";
  jobs.forEach((job, index) => {
    const card = document.createElement("div");
    card.className = "job-card";
    const title = document.createElement("strong");
    title.textContent = job.prompt || `Image job ${index + 1}`;
    card.appendChild(title);

    const status = document.createElement("span");
    status.className = "source";
    status.textContent = `Job ${index + 1} · ${job.status}`;
    card.appendChild(status);

    if (Array.isArray(job.palette) && job.palette.length) {
      const palette = document.createElement("div");
      palette.className = "job-palette";
      job.palette.forEach((color) => {
        const swatch = document.createElement("span");
        swatch.className = "palette-swatch";
        swatch.style.background = color;
        swatch.title = color;
        palette.appendChild(swatch);
      });
      card.appendChild(palette);
    }

    if (job.image_url) {
      const preview = document.createElement("img");
      preview.src = job.image_url;
      preview.alt = job.prompt || "Generated artwork";
      preview.loading = "lazy";
      card.appendChild(preview);

      const actions = document.createElement("div");
      actions.className = "job-actions";

      const downloadLink = document.createElement("a");
      downloadLink.href = job.image_url;
      downloadLink.download = job.filename ? job.filename.split("/").pop() : "imageforge.svg";
      downloadLink.textContent = "Download";
      actions.appendChild(downloadLink);

      if (job.prompt && navigator.clipboard) {
        const copyButton = document.createElement("button");
        copyButton.type = "button";
        copyButton.textContent = "Copy prompt";
        copyButton.addEventListener("click", async () => {
          try {
            await navigator.clipboard.writeText(job.prompt);
            showToast("Prompt copied to clipboard");
          } catch (error) {
            showToast("Couldn't copy prompt");
          }
        });
        actions.appendChild(copyButton);
      }

      card.appendChild(actions);
    } else {
      const progress = document.createElement("progress");
      progress.max = 100;
      progress.value = 100;
      card.appendChild(progress);
    }

    if (job.created_at) {
      const stamp = document.createElement("span");
      stamp.className = "source";
      stamp.textContent = `Generated ${formatISOTime(job.created_at)}`;
      card.appendChild(stamp);
    }

    elements.imageJobs.appendChild(card);
  });
}

async function submitImageJob(prompt, count) {
  try {
    const response = await fetchJSON("/tools/images", {
      method: "POST",
      body: JSON.stringify({ prompt, count }),
    });
    renderImageJobs(response.jobs);
    showToast(`Queued ${response.jobs.length} image job(s)`);
  } catch (error) {
    showToast(error.message);
  }
}

async function requestAdminUpgrade() {
  try {
    const response = await fetchJSON("/auth/become-admin", { method: "POST" });
    showToast(response.detail || "Admin request submitted");
  } catch (error) {
    showToast(error.message);
  }
}

async function refreshAdminStats() {
  if (!state.session || !state.session.is_staff) {
    elements.adminStats.innerHTML = "<p>Admin metrics are available after approval.</p>";
    return;
  }

  try {
    const overview = await fetchJSON("/admin/overview", { method: "GET" });
    elements.adminStats.innerHTML = "";
    const metrics = overview.metrics || {};
    Object.entries(metrics).forEach(([key, value]) => {
      const card = document.createElement("div");
      card.className = "stat-card";
      card.innerHTML = `<strong>${key.replace(/_/g, " ")}</strong><div>${value}</div>`;
      elements.adminStats.appendChild(card);
    });
  } catch (error) {
    elements.adminStats.innerHTML = `<p>${error.message}</p>`;
  }
}

function setupEventListeners() {
  elements.sendButton.addEventListener("click", sendMessage);
  elements.messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  });
  elements.messageInput.addEventListener("input", () => {
    elements.messageInput.style.height = "auto";
    elements.messageInput.style.height = `${Math.min(elements.messageInput.scrollHeight, 240)}px`;
  });

  elements.newChatButton.addEventListener("click", () => {
    resetComposer();
    showToast("New conversation ready");
  });

  elements.fileInput.addEventListener("change", async (event) => {
    const files = event.target.files;
    if (!files?.length) return;
    elements.sendButton.disabled = true;
    try {
      await uploadFiles(files);
    } catch (error) {
      showToast("Upload failed");
    } finally {
      elements.sendButton.disabled = false;
      elements.fileInput.value = "";
    }
  });

  elements.archiveToggle.addEventListener("click", async () => {
    state.showArchived = !state.showArchived;
    await fetchConversations();
  });

  elements.refreshConversations.addEventListener("click", fetchConversations);

  elements.settingsButton.addEventListener("click", () => toggleSettings(true));
  elements.closeSettings.addEventListener("click", () => toggleSettings(false));

  elements.authButton.addEventListener("click", () => {
    if (state.session) {
      const signOutConfirmed = confirm("Sign out?");
      if (signOutConfirmed) {
        signOut();
      }
    } else {
      if (elements.authForm) {
        elements.authForm.reset();
      }
      updateAuthMode("login");
      toggleAuthDialog(true);
    }
  });

  elements.closeAuth.addEventListener("click", () => toggleAuthDialog(false));
  elements.authForm.addEventListener("submit", handleAuthSubmit);
  elements.authToggleMode.addEventListener("click", () => {
    if (state.authMode === "login") {
      updateAuthMode("register");
    } else {
      updateAuthMode("login");
    }
  });
  if (elements.authForgotPassword) {
    elements.authForgotPassword.addEventListener("click", () => {
      const currentIdentifier = elements.authUsername.value.trim();
      updateAuthMode("reset");
      if (currentIdentifier.includes("@")) {
        elements.authEmail.value = currentIdentifier;
        elements.authUsername.value = "";
      }
      elements.authUsername.focus();
    });
  }

  elements.themeToggle.addEventListener("click", () => {
    const isDark = document.body.classList.contains("theme-dark");
    document.body.classList.toggle("theme-dark", !isDark);
    document.body.classList.toggle("theme-light", isDark);
    showToast(isDark ? "Light mode" : "Dark mode");
  });

  elements.tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const tab = button.dataset.tab;
      elements.tabButtons.forEach((b) => b.classList.toggle("active", b === button));
      elements.tabPanels.forEach((panel) => panel.classList.toggle("active", panel.dataset.tab === tab));
      if (tab === "admin") {
        refreshAdminStats();
      }
    });
  });

  elements.renameChat.addEventListener("click", renameConversation);
  elements.conversationMenu.addEventListener("click", (event) => {
    const action = prompt("Choose action: archive, restore, delete", "archive");
    if (!action) return;
    if (action === "archive") toggleArchiveCurrent(true);
    if (action === "restore") toggleArchiveCurrent(false);
    if (action === "delete") deleteConversation();
    event.stopPropagation();
  });

  elements.toolboxButton.addEventListener("click", (event) => {
    if (state.popoverOpen) {
      closePopover();
    } else {
      openPopover(event.currentTarget);
    }
  });

  document.addEventListener("click", (event) => {
    if (state.popoverOpen && !elements.toolPopover.contains(event.target) && event.target !== elements.toolboxButton) {
      closePopover();
    }
  });

  elements.toolPopover.addEventListener("click", (event) => {
    const target = event.target.closest(".popover-item");
    if (!target) return;
    const action = target.dataset.action;
    if (action === "web-search") {
      openDrawer(elements.searchPanel);
      elements.searchQuery.focus();
    }
    if (action === "image-forge") {
      openDrawer(elements.imagePanel);
      elements.imagePrompt.focus();
    }
    if (action === "persona-insights") {
      renderPersonaInsights(state.persona);
      showToast("Persona insights refreshed");
    }
    if (action === "upload-doc") {
      elements.fileInput.click();
    }
    closePopover();
  });

  elements.openSearch.addEventListener("click", () => {
    openDrawer(elements.searchPanel);
    elements.searchQuery.focus();
  });

  elements.closeSearch.addEventListener("click", () => closeDrawer(elements.searchPanel));

  elements.searchForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const query = elements.searchQuery.value.trim();
    if (!query) return;
    performSearch(query);
  });

  elements.openImages.addEventListener("click", () => {
    openDrawer(elements.imagePanel);
    elements.imagePrompt.focus();
  });

  elements.closeImages.addEventListener("click", () => closeDrawer(elements.imagePanel));

  elements.imageCount.addEventListener("input", () => {
    elements.imageCountOutput.textContent = elements.imageCount.value;
  });

  elements.imageForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const prompt = elements.imagePrompt.value.trim();
    if (!prompt) return;
    submitImageJob(prompt, Number(elements.imageCount.value));
  });

  if (elements.becomeAdmin) {
    elements.becomeAdmin.addEventListener("click", requestAdminUpgrade);
  }

  if (elements.refreshAdmin) {
    elements.refreshAdmin.addEventListener("click", refreshAdminStats);
  }
}

async function init() {
  updateAuthMode("login");
  await refreshSession();
  await fetchConversations();
  setupEventListeners();
}

init();
