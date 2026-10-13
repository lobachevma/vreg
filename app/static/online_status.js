(function () {
    function applyOnlineStatus(el, online) {
        el.dataset.state = online ? "online" : "offline";
        var dot = el.querySelector(".online-dot");
        if (dot) {
            dot.classList.remove(
                "online-dot--unknown",
                "online-dot--online",
                "online-dot--offline"
            );
            dot.classList.add(online ? "online-dot--online" : "online-dot--offline");
        }
        var label = el.querySelector(".online-label");
        if (label) {
            label.textContent = online ? "Да" : "Нет";
        }
        el.setAttribute("aria-label", online ? "В сети" : "Не в сети");
    }

    window.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll(".online-status[data-online-url]").forEach(function (el) {
            fetch(el.dataset.onlineUrl, {
                headers: { Accept: "application/json" },
                credentials: "same-origin",
            })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("status check failed");
                    }
                    return response.json();
                })
                .then(function (data) {
                    applyOnlineStatus(el, !!data.online);
                })
                .catch(function () {
                    applyOnlineStatus(el, false);
                });
        });
    });
})();
