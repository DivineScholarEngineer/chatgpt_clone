const conversationListEl = document.getElementById("conversation-list");
const messagesEl = document.getElementById("messages");
const messageInput = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");
const newChatButton = document.getElementById("new-chat");
const fileInput = document.getElementById("file-input");
const attachmentBar = document.getElementById("attachment-bar");

let conversations = [];
let currentConversation = null;
let pendingAttachments = [];

function formatRole(role) {
  return role === "assistant" ? "🤖" : "🧑";
}

function renderConversations() {
  conversationListEl.innerHTML = "";
  conversations.forEach((conversation) => {
    const item = document.createElement("div");
    item.className = "conversation-item" + (currentConversation && currentConversation.id === conversation.id ? " active" : "");
    item.textContent = conversation.title || "New chat";
    item.addEventListener("click", () => loadConversation(conversation.id));
    conversationListEl.appendChild(item);
  });
}

function renderMessages(conversation) {
  messagesEl.innerHTML = "";
  if (!conversation) return;
  conversation.messages.forEach((message) => {
    const row = document.createElement("div");
    row.className = `message-row ${message.role}`;

    const role = document.createElement("div");
    role.className = "message-role";
    role.textContent = formatRole(message.role);

    const content = document.createElement("div");
    content.className = "message-content";
    content.textContent = message.content;

    if (message.attachments && message.attachments.length) {
      const attachmentContainer = document.createElement("div");
      attachmentContainer.className = "attachment-preview";
      message.attachments.forEach((attachment) => {
        const link = document.createElement("a");
        link.href = `/${attachment.filename}`;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = attachment.original_name;
        attachmentContainer.appendChild(link);
      });
      content.appendChild(attachmentContainer);
    }

    row.appendChild(role);
    row.appendChild(content);
    messagesEl.appendChild(row);
  });
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderAttachments() {
  attachmentBar.innerHTML = "";
  pendingAttachments.forEach((attachment, index) => {
    const pill = document.createElement("div");
    pill.className = "attachment-pill";
    pill.textContent = attachment.original_name;

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.textContent = "✕";
    removeBtn.addEventListener("click", async () => {
      const [removed] = pendingAttachments.splice(index, 1);
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
    attachmentBar.appendChild(pill);
  });
}

async function fetchConversations() {
  const response = await fetch("/conversations");
  conversations = await response.json();
  if (!currentConversation && conversations.length) {
    currentConversation = conversations[0];
  }
  if (currentConversation) {
    const fresh = conversations.find((c) => c.id === currentConversation.id);
    currentConversation = fresh || currentConversation;
  }
  renderConversations();
  renderMessages(currentConversation);
}

async function loadConversation(id) {
  const response = await fetch(`/conversations/${id}`);
  currentConversation = await response.json();
  const index = conversations.findIndex((c) => c.id === currentConversation.id);
  if (index !== -1) {
    conversations[index] = currentConversation;
  } else {
    conversations.unshift(currentConversation);
  }
  renderConversations();
  renderMessages(currentConversation);
}

async function uploadFiles(files) {
  const uploads = Array.from(files).map(async (file) => {
    const formData = new FormData();
    if (currentConversation) {
      formData.append("conversation_id", currentConversation.id);
    }
    formData.append("file", file);
    const response = await fetch("/upload", {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      throw new Error("Upload failed");
    }
    return response.json();
  });
  const results = await Promise.all(uploads);
  pendingAttachments.push(...results);
  renderAttachments();
}

async function sendMessage() {
  const message = messageInput.value.trim();
  if (!message && pendingAttachments.length === 0) {
    return;
  }
  sendButton.disabled = true;
  const payload = {
    conversation_id: currentConversation ? currentConversation.id : null,
    message,
    attachment_ids: pendingAttachments.map((attachment) => attachment.id),
  };

  const response = await fetch("/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    sendButton.disabled = false;
    return;
  }

  const data = await response.json();
  currentConversation = data.conversation;
  const index = conversations.findIndex((c) => c.id === currentConversation.id);
  if (index !== -1) {
    conversations[index] = currentConversation;
  } else {
    conversations.unshift(currentConversation);
  }
  renderConversations();
  renderMessages(currentConversation);
  messageInput.value = "";
  pendingAttachments = [];
  renderAttachments();
  sendButton.disabled = false;
  messageInput.focus();
}

messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
});

messageInput.addEventListener("input", () => {
  messageInput.style.height = "auto";
  messageInput.style.height = `${Math.min(messageInput.scrollHeight, 200)}px`;
});

sendButton.addEventListener("click", sendMessage);

newChatButton.addEventListener("click", () => {
  currentConversation = null;
  messageInput.value = "";
  pendingAttachments = [];
  renderAttachments();
  renderConversations();
  renderMessages(null);
  messageInput.focus();
});

fileInput.addEventListener("change", async (event) => {
  if (!event.target.files?.length) return;
  sendButton.disabled = true;
  try {
    await uploadFiles(event.target.files);
  } catch (error) {
    console.error(error);
  } finally {
    sendButton.disabled = false;
    fileInput.value = "";
  }
});

fetchConversations();
