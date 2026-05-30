let bridge = null;

new QWebChannel(qt.webChannelTransport, function(channel) {
    bridge = channel.objects.bridge;
});

function addMessage(role, text) {
    const container = document.getElementById('chat-container');
    const div = document.createElement('div');
    div.className = 'message ' + role;
    div.textContent = text;
    container.appendChild(div);
    window.scrollTo(0, document.body.scrollHeight);
}

function updateLastAssistant(text) {
    const container = document.getElementById('chat-container');
    const messages = container.querySelectorAll('.message.assistant');
    if (messages.length > 0) {
        messages[messages.length - 1].textContent = text;
    } else {
        addMessage('assistant', text);
    }
    window.scrollTo(0, document.body.scrollHeight);
}

function startAssistantMessage() {
    addMessage('assistant', '');
}
