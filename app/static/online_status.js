/**
 * Проверка «В сети» только на карточке регистратора.
 *
 * Браузер не умеет ICMP ping — запросы идут с компьютера пользователя
 * (fetch HEAD/no-cors к HTTP на IP регистратора), не с сервера Docker.
 * За один цикл — не более MAX_ATTEMPTS попыток; повтор цикла каждые 60 с.
 */
(function () {
    var CHECK_INTERVAL_MS = 60000;
    var MAX_ATTEMPTS = 3;
    var ATTEMPT_TIMEOUT_MS = 2500;

    function buildProbeUrls(ip) {
        var host = ip.trim();
        return [
            "http://" + host + "/",
            "http://" + host + ":8000/",
            "http://" + host + "/",
        ];
    }

    function probeOnce(url) {
        var controller = new AbortController();
        var timer = window.setTimeout(function () {
            controller.abort();
        }, ATTEMPT_TIMEOUT_MS);

        return fetch(url, {
            method: "HEAD",
            mode: "no-cors",
            cache: "no-store",
            signal: controller.signal,
        })
            .then(function () {
                return true;
            })
            .catch(function () {
                return false;
            })
            .finally(function () {
                window.clearTimeout(timer);
            });
    }

    function runReachabilityCheck(ip) {
        var urls = buildProbeUrls(ip).slice(0, MAX_ATTEMPTS);
        var chain = Promise.resolve(false);

        urls.forEach(function (url) {
            chain = chain.then(function (alreadyOnline) {
                if (alreadyOnline) {
                    return true;
                }
                return probeOnce(url);
            });
        });

        return chain;
    }

    function setLoading(el) {
        el.dataset.state = "loading";
        var dot = el.querySelector(".online-dot");
        if (dot) {
            dot.classList.remove(
                "online-dot--online",
                "online-dot--offline"
            );
            dot.classList.add("online-dot--unknown");
        }
        var label = el.querySelector(".online-label");
        if (label) {
            label.textContent = "Проверка…";
        }
        el.setAttribute("aria-label", "Проверка связи");
    }

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
            label.textContent = online ? "В сети" : "Не в сети";
        }
        el.setAttribute("aria-label", online ? "В сети" : "Не в сети");
    }

    window.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll(".online-status[data-recorder-ip]").forEach(function (el) {
            var ip = (el.dataset.recorderIp || "").trim();
            if (!ip) {
                applyOnlineStatus(el, false);
                return;
            }

            var intervalId = null;
            var checkInFlight = false;

            function runCycle() {
                if (checkInFlight) {
                    return;
                }
                checkInFlight = true;
                setLoading(el);
                runReachabilityCheck(ip)
                    .then(function (online) {
                        applyOnlineStatus(el, online);
                    })
                    .catch(function () {
                        applyOnlineStatus(el, false);
                    })
                    .finally(function () {
                        checkInFlight = false;
                    });
            }

            runCycle();
            intervalId = window.setInterval(runCycle, CHECK_INTERVAL_MS);

            function clearTimer() {
                if (intervalId !== null) {
                    window.clearInterval(intervalId);
                    intervalId = null;
                }
            }

            window.addEventListener("beforeunload", clearTimer);
            window.addEventListener("pagehide", clearTimer);
        });
    });
})();
