
(() => {
    "use strict";

    if (!("serviceWorker" in navigator)) {
        return;
    }

    let refreshing = false;
    let shouldReloadAfterUpdate = false;
    let waitingWorker = null;
    let updateNotice = null;

    function createUpdateNotice() {
        if (updateNotice) {
            return;
        }

        updateNotice = document.createElement("div");
        updateNotice.id = "pwa-update-notice";
        updateNotice.setAttribute("role", "status");
        updateNotice.setAttribute("aria-live", "polite");

        Object.assign(updateNotice.style, {
            position: "fixed",
            right: "16px",
            bottom: "16px",
            zIndex: "99999",
            width: "min(360px, calc(100% - 32px))",
            padding: "16px",
            borderRadius: "12px",
            background: "#ffffff",
            color: "#1f2937",
            boxShadow: "0 8px 30px rgba(0, 0, 0, 0.20)",
            border: "1px solid #dbe2ea",
            fontFamily: "Arial, sans-serif"
        });

        const title = document.createElement("strong");
        title.textContent = "Actualización disponible";

        const message = document.createElement("p");
        message.textContent =
            "Hay una nueva versión del sistema. Puedes actualizar cuando estés listo.";
        Object.assign(message.style, {
            margin: "8px 0 14px",
            fontSize: "14px",
            lineHeight: "1.5"
        });

        const updateButton = document.createElement("button");
        updateButton.type = "button";
        updateButton.textContent = "Actualizar ahora";

        Object.assign(updateButton.style, {
            border: "0",
            borderRadius: "8px",
            padding: "10px 14px",
            background: "#1B396A",
            color: "#ffffff",
            cursor: "pointer",
            fontWeight: "600"
        });

        updateButton.addEventListener("click", () => {
    if (!waitingWorker) return;

    shouldReloadAfterUpdate = true;
    updateButton.disabled = true;
    updateButton.textContent = "Actualizando...";
    waitingWorker.postMessage({ type: "SKIP_WAITING" });
});

        updateNotice.append(title, message, updateButton);
        document.body.appendChild(updateNotice);
    }

    function hideUpdateNotice() {
        if (updateNotice) {
            updateNotice.remove();
            updateNotice = null;
        }
    }

navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (!shouldReloadAfterUpdate || refreshing) return;

    refreshing = true;
    window.location.reload();
});

    window.addEventListener("load", async () => {
        try {
            const registration = await navigator.serviceWorker.register(
                "/sw.js",
                { scope: "/" }
            );

            function checkWaitingWorker() {
                if (registration.waiting && navigator.serviceWorker.controller) {
                    waitingWorker = registration.waiting;
                    createUpdateNotice();
                }
            }

            checkWaitingWorker();

            registration.addEventListener("updatefound", () => {
                const installingWorker = registration.installing;

                if (!installingWorker) {
                    return;
                }

                installingWorker.addEventListener("statechange", () => {
                    if (
                        installingWorker.state === "installed" &&
                        navigator.serviceWorker.controller
                    ) {
                        checkWaitingWorker();
                    }
                });
            });

            // Solicitar al navegador que compruebe si hay una versión nueva.
            await registration.update();

            checkWaitingWorker();

            // Comprobar periódicamente mientras la página permanezca abierta.
            window.setInterval(async () => {
                try {
                    await registration.update();
                    checkWaitingWorker();
                } catch (error) {
                    console.debug(
                        "PWA: no fue posible comprobar actualizaciones.",
                        error
                    );
                }
            }, 60 * 60 * 1000);
        } catch (error) {
            console.error(
                "PWA: no se pudo registrar o comprobar el Service Worker.",
                error
            );
        }
    });
})();
