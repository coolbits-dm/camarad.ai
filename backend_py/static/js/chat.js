document.addEventListener('DOMContentLoaded', function() {
    const input = document.getElementById('message-input');
    const sendBtn = document.getElementById('send-btn');
    const history = document.getElementById('chat-history');

    function sendMessage() {
        const message = input.value.trim();
        if (!message) return;

        // Add user message
        addMessage('user', message);
        input.value = '';

        // Send to server
        fetch(window.location.pathname, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert(data.error);
                if (data.limit_reached) {
                    // Optional: disable input
                }
            } else if (data.redirect) {
                window.location.href = data.redirect;
            } else {
                addMessage('agent', data.response_html || data.response);
            }
        })
        .catch(error => console.error('Error:', error));
    }

    function addMessage(role, content) {
        const div = document.createElement('div');
        div.className = `d-flex mb-2 ${role === 'user' ? 'justify-content-end' : 'justify-content-start'}`;
        div.innerHTML = `
            <div class="alert ${role === 'user' ? 'alert-primary' : 'alert-secondary'} mb-0" style="max-width: 70%;">
                <strong>${role === 'user' ? 'You' : window.agentName}:</strong> ${content}
            </div>
        `;
        history.appendChild(div);
        history.scrollTop = history.scrollHeight;
    }

    sendBtn.addEventListener('click', sendMessage);
    input.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') sendMessage();
    });
});