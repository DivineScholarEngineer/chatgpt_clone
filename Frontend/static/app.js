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
  accountMenu: document.getElementById("account-menu"),
  authDialog: document.getElementById("auth-dialog"),
  authTitle: document.getElementById("auth-title"),
  closeAuth: document.getElementById("close-auth"),
  authForm: document.getElementById("auth-form"),
  authUsername: document.getElementById("auth-username"),
  authEmail: document.getElementById("auth-email"),
  authPassword: document.getElementById("auth-password"),
  authSubmit: document.getElementById("auth-submit"),
  authToggleMode: document.getElementById("auth-toggle-mode"),
  authHelpText: document.getElementById("auth-help-text"),
  authResetToken: document.getElementById("auth-reset-token"),
  authNewPassword: document.getElementById("auth-new-password"),
  authConfirmPassword: document.getElementById("auth-confirm-password"),
  authResetTokenRow: document.getElementById("auth-reset-token-row"),
  authNewPasswordRow: document.getElementById("auth-new-password-row"),
  authConfirmPasswordRow: document.getElementById("auth-confirm-password-row"),
  authForgot: document.getElementById("auth-forgot"),
  authBackToLogin: document.getElementById("auth-back-to-login"),
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
  searchSummary: document.getElementById("search-summary"),
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
  accountDialog: document.getElementById("account-dialog"),
  closeAccount: document.getElementById("close-account"),
  accountForm: document.getElementById("account-form"),
  accountUsername: document.getElementById("account-username"),
  accountEmail: document.getElementById("account-email"),
  accountCurrentPassword: document.getElementById("account-current-password"),
  accountNewPassword: document.getElementById("account-new-password"),
  accountConfirmPassword: document.getElementById("account-confirm-password"),
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
  accountMenuOpen: false,
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
  if (response.status === 204 || response.status === 205) {
    return {};
  }
  const text = await response.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch (error) {
    return {};
  }
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

  row.dataset.messageId = message.id;
  row.dataset.conversationId = message.conversation_id;

  const body = document.createElement("div");
  body.className = "message-body";
  body.appendChild(content);

  if (state.session && message.role === "user") {
    const actions = document.createElement("div");
    actions.className = "message-actions";

    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.className = "icon-button subtle";
    editButton.title = "Edit message";
    editButton.textContent = "✏️";
    editButton.addEventListener("click", (event) => {
      event.stopPropagation();
      openEditMessageDialog(message);
    });

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "icon-button subtle";
    deleteButton.title = "Delete message";
    deleteButton.textContent = "🗑️";
    deleteButton.addEventListener("click", (event) => {
      event.stopPropagation();
      confirmDeleteMessage(message);
    });

    actions.appendChild(editButton);
    actions.appendChild(deleteButton);
    body.appendChild(actions);
  }

  row.appendChild(role);
  row.appendChild(body);

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

function updateMessageInState(updated) {
  if (!state.currentConversation || state.currentConversation.id !== updated.conversation_id) {
    return;
  }
  const index = state.currentConversation.messages.findIndex((msg) => msg.id === updated.id);
  if (index !== -1) {
    state.currentConversation.messages[index] = updated;
    renderMessages(state.currentConversation);
  }
}

function removeMessageFromState(messageId) {
  if (!state.currentConversation) return;
  const before = state.currentConversation.messages.length;
  state.currentConversation.messages = state.currentConversation.messages.filter(
    (msg) => msg.id !== messageId
  );
  if (state.currentConversation.messages.length !== before) {
    renderMessages(state.currentConversation);
  }
}

async function openEditMessageDialog(message) {
  const current = message.content || "";
  const updated = prompt("Edit your message", current);
  if (!updated || updated === current) {
    return;
  }
  try {
    const response = await fetchJSON(
      `/conversations/${message.conversation_id}/messages/${message.id}`,
      {
        method: "PATCH",
        body: JSON.stringify({ content: updated }),
      }
    );
    updateMessageInState(response);
    showToast("Message updated");
  } catch (error) {
    showToast(error.message);
  }
}

async function confirmDeleteMessage(message) {
  const ok = confirm("Delete this message?");
  if (!ok) return;
  try {
    await fetchJSON(`/conversations/${message.conversation_id}/messages/${message.id}`, {
      method: "DELETE",
    });
    removeMessageFromState(message.id);
    showToast("Message deleted");
  } catch (error) {
    showToast(error.message);
  }
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
      toggleAccountMenu(false);
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

function clearAuthForm() {
  if (elements.authUsername) elements.authUsername.value = "";
  if (elements.authEmail) elements.authEmail.value = "";
  if (elements.authPassword) elements.authPassword.value = "";
  if (elements.authResetToken) elements.authResetToken.value = "";
  if (elements.authNewPassword) elements.authNewPassword.value = "";
  if (elements.authConfirmPassword) elements.authConfirmPassword.value = "";
  if (elements.authHelpText) elements.authHelpText.textContent = "";
}

function toggleAuthDialog(open) {
  if (!elements.authDialog) return;
  elements.authDialog.classList.toggle("hidden", !open);
  if (open) {
    clearAuthForm();
    updateAuthMode("login");
    elements.authUsername?.focus();
  } else {
    clearAuthForm();
    updateAuthMode("login");
  }
}

function toggleAccountMenu(open, anchor) {
  if (!elements.accountMenu || !elements.authButton) return;
  if (open) {
    const rect = (anchor || elements.authButton).getBoundingClientRect();
    elements.accountMenu.style.top = `${rect.bottom + 8}px`;
    elements.accountMenu.style.left = `${rect.left}px`;
    elements.accountMenu.classList.remove("hidden");
  } else {
    elements.accountMenu.classList.add("hidden");
  }
  state.accountMenuOpen = open;
}

function toggleAccountDialog(open) {
  if (!elements.accountDialog) return;
  elements.accountDialog.classList.toggle("hidden", !open);
  if (open) {
    elements.accountUsername?.focus();
  }
}

async function loadAccountProfile() {
  if (!state.session) return;
  try {
    const response = await fetchJSON("/account/profile", { method: "GET" });
    const user = response.user || {};
    if (elements.accountUsername) {
      elements.accountUsername.value = user.username || "";
    }
    if (elements.accountEmail) {
      elements.accountEmail.value = user.email || "";
    }
  } catch (error) {
    showToast(error.message || "Unable to load profile");
  }
}

async function handleAccountSubmit(event) {
  event.preventDefault();
  const payload = {
    username: elements.accountUsername?.value.trim(),
    email: elements.accountEmail?.value.trim(),
  };

  const currentPassword = elements.accountCurrentPassword?.value || "";
  const newPassword = elements.accountNewPassword?.value || "";
  const confirmPassword = elements.accountConfirmPassword?.value || "";

  if (newPassword || confirmPassword || currentPassword) {
    payload.current_password = currentPassword;
    payload.new_password = newPassword;
    payload.confirm_password = confirmPassword;
  }

  try {
    const response = await fetchJSON("/account/profile", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    toggleAccountDialog(false);
    toggleAccountMenu(false);
    await refreshSession();
    showToast(response.detail || "Profile updated");
  } catch (error) {
    showToast(error.message);
    return;
  } finally {
    if (elements.accountCurrentPassword) elements.accountCurrentPassword.value = "";
    if (elements.accountNewPassword) elements.accountNewPassword.value = "";
    if (elements.accountConfirmPassword) elements.accountConfirmPassword.value = "";
  }
}

function updateAuthMode(mode) {
  state.authMode = mode;
  const isLogin = mode === "login";
  const isRegister = mode === "register";
  const isForgot = mode === "forgot";
  const isReset = mode === "reset";

  if (elements.authTitle) {
    if (isRegister) {
      elements.authTitle.textContent = "Register";
    } else if (isForgot) {
      elements.authTitle.textContent = "Forgot password";
    } else if (isReset) {
      elements.authTitle.textContent = "Reset password";
    } else {
      elements.authTitle.textContent = "Sign in";
    }
  }

  const usernameRow = elements.authUsername?.closest("label");
  const emailRow = elements.authEmail?.closest("label");
  const passwordRow = elements.authPassword?.closest("label");

  usernameRow?.classList.toggle("hidden", isReset);
  emailRow?.classList.toggle("hidden", !(isRegister || isForgot));
  passwordRow?.classList.toggle("hidden", !(isLogin || isRegister));
  elements.authResetTokenRow?.classList.toggle("hidden", !isReset);
  elements.authNewPasswordRow?.classList.toggle("hidden", !isReset);
  elements.authConfirmPasswordRow?.classList.toggle("hidden", !isReset);

  if (elements.authToggleMode) {
    elements.authToggleMode.classList.toggle("hidden", isForgot || isReset);
    elements.authToggleMode.textContent = isRegister
      ? "Switch to sign in"
      : "Switch to register";
  }

  elements.authForgot?.classList.toggle("hidden", !isLogin);
  elements.authBackToLogin?.classList.toggle("hidden", isLogin);

  if (elements.authSubmit) {
    if (isForgot) {
      elements.authSubmit.textContent = "Send reset code";
    } else if (isReset) {
      elements.authSubmit.textContent = "Update password";
    } else if (isRegister) {
      elements.authSubmit.textContent = "Create account";
    } else {
      elements.authSubmit.textContent = "Continue";
    }
  }

  elements.authUsername.required = isRegister || isLogin;
  elements.authPassword.required = isRegister || isLogin;
  elements.authEmail.required = isRegister;
  if (elements.authNewPassword) elements.authNewPassword.required = isReset;
  if (elements.authConfirmPassword) elements.authConfirmPassword.required = isReset;

  if (elements.authHelpText) {
    let message = "";
    if (isLogin) {
      message = "Sign in with your username or email and password.";
    } else if (isRegister) {
      message = "Create a new account to unlock GPT-OSS features.";
    } else if (isForgot) {
      message = "Enter your email (or username) and we'll email you a reset code.";
    } else if (isReset) {
      message = "Paste the reset code from your email and choose a new password.";
    }
    elements.authHelpText.textContent = message;
  }
}

async function handleAuthSubmit(event) {
  event.preventDefault();
  const mode = state.authMode;

  if (mode === "forgot") {
    const identifier = (elements.authEmail?.value.trim() || elements.authUsername?.value.trim() || "").trim();
    if (!identifier) {
      showToast("Enter your email or username");
      return;
    }

    try {
      await fetchJSON("/auth/password/forgot", {
        method: "POST",
        body: JSON.stringify({ identifier }),
      });
      showToast("Reset code sent if the account exists");
      updateAuthMode("reset");
    } catch (error) {
      showToast(error.message);
    }
    return;
  }

  if (mode === "reset") {
    const token = elements.authResetToken?.value.trim();
    const newPassword = elements.authNewPassword?.value || "";
    const confirmPassword = elements.authConfirmPassword?.value || "";
    const loginIdentifier =
      elements.authEmail?.value.trim() || elements.authUsername?.value.trim() || "";

    if (!token) {
      showToast("Reset code is required");
      return;
    }
    if (newPassword.length < 8) {
      showToast("New password must be at least 8 characters");
      return;
    }
    if (newPassword !== confirmPassword) {
      showToast("Passwords do not match");
      return;
    }

    try {
      await fetchJSON("/auth/password/reset", {
        method: "POST",
        body: JSON.stringify({
          token,
          new_password: newPassword,
          confirm_password: confirmPassword,
        }),
      });
      showToast("Password updated. You can sign in now.");
      clearAuthForm();
      updateAuthMode("login");
      if (loginIdentifier && elements.authUsername) {
        elements.authUsername.value = loginIdentifier;
      }
      elements.authPassword?.focus();
    } catch (error) {
      showToast(error.message);
    }
    return;
  }

  const username = elements.authUsername?.value.trim();
  const email = elements.authEmail?.value.trim();
  const password = elements.authPassword?.value || "";

  if (!username || !password) {
    showToast("Username and password are required");
    return;
  }

  try {
    const endpoint = mode === "register" ? "/auth/register" : "/auth/login";
    const payload = { username, password };
    if (mode === "register" && email) {
      payload.email = email;
    }

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
    toggleAccountMenu(false);
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
    if (elements.searchSummary) {
      if (results.summary) {
        elements.searchSummary.textContent = results.summary;
        elements.searchSummary.classList.remove("hidden");
      } else {
        elements.searchSummary.textContent = "";
        elements.searchSummary.classList.add("hidden");
      }
    }
    if (!results.results.length) {
      elements.searchResults.innerHTML = `<p class="empty-state">No results yet – try refining your query.</p>`;
    }
    results.results.forEach((item) => {
      const card = document.createElement("div");
      card.className = "result-card";
      const title = document.createElement("a");
      title.href = item.url;
      title.target = "_blank";
      title.rel = "noopener";
      title.textContent = item.title;
      title.className = "result-title";

      const excerpt = document.createElement("p");
      excerpt.textContent = item.excerpt;

      const meta = document.createElement("span");
      meta.className = "source";
      meta.textContent = item.source || results.provider;

      card.appendChild(title);
      card.appendChild(excerpt);
      card.appendChild(meta);
      elements.searchResults.appendChild(card);
    });
    showToast(`Web Pulse found ${results.results.length} result(s)`);
  } catch (error) {
    if (elements.searchSummary) {
      elements.searchSummary.textContent = "";
      elements.searchSummary.classList.add("hidden");
    }
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

    if (job.caption) {
      const caption = document.createElement("p");
      caption.className = "job-caption";
      caption.textContent = job.caption;
      card.appendChild(caption);
    }

    const status = document.createElement("span");
    status.className = "source";
    const provider = job.provider ? ` · ${job.provider}` : "";
    status.textContent = `Job ${index + 1} · ${job.status}${provider}`;
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
            const promptToCopy = job.director_prompt || job.prompt;
            await navigator.clipboard.writeText(promptToCopy);
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

  elements.authButton.addEventListener("click", (event) => {
    if (state.session) {
      event.stopPropagation();
      toggleAccountMenu(!state.accountMenuOpen, event.currentTarget);
    } else {
      toggleAuthDialog(true);
    }
  });

  document.addEventListener("click", (event) => {
    if (
      state.accountMenuOpen &&
      elements.accountMenu &&
      !elements.accountMenu.contains(event.target) &&
      event.target !== elements.authButton
    ) {
      toggleAccountMenu(false);
    }
  });

  elements.closeAuth.addEventListener("click", () => toggleAuthDialog(false));
  elements.authForm.addEventListener("submit", handleAuthSubmit);
  elements.authToggleMode.addEventListener("click", () => {
    updateAuthMode(state.authMode === "login" ? "register" : "login");
  });

  if (elements.authForgot) {
    elements.authForgot.addEventListener("click", () => updateAuthMode("forgot"));
  }

  if (elements.authBackToLogin) {
    elements.authBackToLogin.addEventListener("click", () => updateAuthMode("login"));
  }

  if (elements.accountForm) {
    elements.accountForm.addEventListener("submit", handleAccountSubmit);
  }

  if (elements.closeAccount) {
    elements.closeAccount.addEventListener("click", () => toggleAccountDialog(false));
  }

  if (elements.accountMenu) {
    elements.accountMenu.addEventListener("click", async (event) => {
      const button = event.target.closest(".popover-item");
      if (!button) return;
      const action = button.dataset.action;
      if (action === "profile") {
        await loadAccountProfile();
        toggleAccountDialog(true);
        toggleAccountMenu(false);
      }
      if (action === "settings") {
        toggleSettings(true);
        toggleAccountMenu(false);
      }
      if (action === "sign-out") {
        toggleAccountMenu(false);
        signOut();
      }
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
